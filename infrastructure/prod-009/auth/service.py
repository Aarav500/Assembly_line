import json
import uuid
from typing import Dict, Optional, Tuple, List

from storage.redis_client import get_redis
from config import Config
from utils.passwords import hash_password, verify_password
from utils.time import now_ts, ttl_from_deadline
from security.jwt_utils import create_access_token, create_refresh_token

config = Config()
rdb = get_redis()

# Keys
# user:{username} -> {id, username, password_hash, created_at}
# user:id:{id} -> {id, username, created_at}
# user:id:counter -> int
# user:sessions:{user_id} -> set(session_id)
# session:{session_id} -> hash(user_id, created_at, last_seen, ip, ua, revoked, absolute_exp)
# session:refresh:{session_id} -> set(refresh_jti)
# refresh:{jti} -> hash(user_id, session_id, exp, created_at, used, revoked, rotated_to, parent_jti)
# access:block:{jti} -> 1 with TTL until exp

class AuthError(Exception):
    def __init__(self, message: str, code: str = "auth_error", status: int = 401):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _user_key(username: str) -> str:
    return f"user:{username}"


def _user_id_key(user_id: str) -> str:
    return f"user:id:{user_id}"


def _user_sessions_key(user_id: str) -> str:
    return f"user:sessions:{user_id}"


def _session_key(session_id: str) -> str:
    return f"session:{session_id}"


def _session_refresh_set(session_id: str) -> str:
    return f"session:refresh:{session_id}"


def _refresh_key(jti: str) -> str:
    return f"refresh:{jti}"


def _access_block_key(jti: str) -> str:
    return f"access:block:{jti}"


def register_user(username: str, password: str) -> Dict:
    if not username or not password:
        raise AuthError("Username and password are required", status=400, code="invalid_request")

    key = _user_key(username)
    if rdb.exists(key):
        raise AuthError("Username already exists", status=409, code="conflict")

    user_id = str(rdb.incr("user:id:counter"))
    created_at = now_ts()
    pwd_hash = hash_password(password)

    pipe = rdb.pipeline(True)
    pipe.hset(key, mapping={"id": user_id, "username": username, "password_hash": pwd_hash, "created_at": created_at})
    pipe.hset(_user_id_key(user_id), mapping={"id": user_id, "username": username, "created_at": created_at})
    pipe.execute()

    return {"id": user_id, "username": username, "created_at": created_at}


def _get_user_by_username(username: str) -> Optional[Dict]:
    data = rdb.hgetall(_user_key(username))
    return data if data else None


def get_user_by_id(user_id: str) -> Optional[Dict]:
    data = rdb.hgetall(_user_id_key(user_id))
    return data if data else None


def authenticate(username: str, password: str) -> Dict:
    user = _get_user_by_username(username)
    if not user:
        raise AuthError("Invalid credentials", status=401, code="invalid_credentials")
    if not verify_password(password, user.get("password_hash", "")):
        raise AuthError("Invalid credentials", status=401, code="invalid_credentials")
    return user


def _compute_session_ttls(created_at: int, last_seen: int) -> Tuple[int, int, int, int]:
    absolute_exp = created_at + config.SESSION_ABSOLUTE_SECONDS
    idle_exp = last_seen + config.SESSION_IDLE_SECONDS
    now = now_ts()
    ttl_abs = max(0, absolute_exp - now)
    ttl_idle = max(0, idle_exp - now)
    ttl = min(ttl_abs, ttl_idle)
    return absolute_exp, idle_exp, ttl_abs, ttl


def create_session(user_id: str, ip: str, ua: str) -> Dict:
    session_id = str(uuid.uuid4())
    created_at = now_ts()
    last_seen = created_at
    absolute_exp, idle_exp, ttl_abs, ttl = _compute_session_ttls(created_at, last_seen)

    pipe = rdb.pipeline(True)
    pipe.hset(_session_key(session_id), mapping={
        "user_id": user_id,
        "created_at": created_at,
        "last_seen": last_seen,
        "ip": ip or "",
        "ua": ua or "",
        "revoked": 0,
        "absolute_exp": absolute_exp,
    })
    pipe.sadd(_user_sessions_key(user_id), session_id)
    # TTL handles idle expiration by updating on activity to min(abs, idle)
    pipe.expire(_session_key(session_id), ttl)
    pipe.execute()

    return {
        "session_id": session_id,
        "created_at": created_at,
        "absolute_exp": absolute_exp,
        "ttl": ttl,
    }


def _touch_session(session_id: str):
    skey = _session_key(session_id)
    sess = rdb.hgetall(skey)
    if not sess:
        return False
    if str(sess.get("revoked", "0")) == "1":
        return False
    created_at = int(sess.get("created_at", now_ts()))
    last_seen = now_ts()
    absolute_exp, idle_exp, ttl_abs, ttl = _compute_session_ttls(created_at, last_seen)
    pipe = rdb.pipeline(True)
    pipe.hset(skey, mapping={"last_seen": last_seen})
    pipe.expire(skey, ttl)
    pipe.execute()
    return True


def _session_valid(session_id: str) -> Tuple[bool, Optional[Dict]]:
    sess = rdb.hgetall(_session_key(session_id))
    if not sess:
        return False, None
    if str(sess.get("revoked", "0")) == "1":
        return False, sess
    now = now_ts()
    absolute_exp = int(sess.get("absolute_exp", now))
    last_seen = int(sess.get("last_seen", now))
    if now > absolute_exp:
        return False, sess
    if now > last_seen + config.SESSION_IDLE_SECONDS:
        return False, sess
    return True, sess


def issue_tokens(user_id: str, session_id: str) -> Dict:
    access_token, access_claims = create_access_token(user_id, session_id)
    refresh_token, refresh_claims = create_refresh_token(user_id, session_id)

    # Persist refresh record for rotation
    rkey = _refresh_key(refresh_claims["jti"])
    pipe = rdb.pipeline(True)
    pipe.hset(rkey, mapping={
        "user_id": user_id,
        "session_id": session_id,
        "exp": refresh_claims["exp"],
        "created_at": refresh_claims["iat"],
        "used": 0,
        "revoked": 0,
        "rotated_to": "",
        "parent_jti": "",
    })
    # track under session for mass revocation
    pipe.sadd(_session_refresh_set(session_id), refresh_claims["jti"])
    # TTL slightly beyond token exp to allow inspection
    pipe.expire(rkey, max(1, refresh_claims["exp"] - now_ts()))
    pipe.execute()

    return {
        "access_token": access_token,
        "access_token_expires": access_claims["exp"],
        "refresh_token": refresh_token,
        "refresh_token_expires": refresh_claims["exp"],
        "session_id": session_id,
    }


def login(username: str, password: str, ip: str, ua: str) -> Dict:
    user = authenticate(username, password)
    sess = create_session(user_id=user["id"], ip=ip, ua=ua)
    tokens = issue_tokens(user_id=user["id"], session_id=sess["session_id"])
    return {"user": {"id": user["id"], "username": user["username"]}, "session": sess, "tokens": tokens}


def _revoke_refresh_jti(jti: str):
    rkey = _refresh_key(jti)
    if rdb.exists(rkey):
        rdb.hset(rkey, mapping={"revoked": 1})


def revoke_session(session_id: str):
    skey = _session_key(session_id)
    sess = rdb.hgetall(skey)
    if not sess:
        return
    pipe = rdb.pipeline(True)
    pipe.hset(skey, mapping={"revoked": 1})
    pipe.expire(skey, 60 * 5)
    # revoke all refresh tokens in this session
    jtis = rdb.smembers(_session_refresh_set(session_id)) or []
    for jti in jtis:
        pipe.hset(_refresh_key(jti), mapping={"revoked": 1})
    pipe.delete(_session_refresh_set(session_id))
    pipe.execute()


def revoke_all_sessions(user_id: str):
    skeyset = _user_sessions_key(user_id)
    sessions = rdb.smembers(skeyset) or []
    for sid in sessions:
        revoke_session(sid)


def list_sessions(user_id: str) -> List[Dict]:
    sessions = []
    for sid in rdb.smembers(_user_sessions_key(user_id)) or []:
        sess = rdb.hgetall(_session_key(sid))
        if sess:
            sessions.append({
                "session_id": sid,
                "created_at": int(sess.get("created_at", 0)),
                "last_seen": int(sess.get("last_seen", 0)),
                "ip": sess.get("ip", ""),
                "ua": sess.get("ua", ""),
                "revoked": int(sess.get("revoked", 0)),
                "absolute_exp": int(sess.get("absolute_exp", 0)),
            })
    # sort by last_seen desc
    sessions.sort(key=lambda s: s.get("last_seen", 0), reverse=True)
    return sessions


def validate_access_token(token: str) -> Dict:
    from security.jwt_utils import decode_token
    try:
        claims = decode_token(token)
    except Exception as e:
        raise AuthError("Invalid access token", code="invalid_token")

    if claims.get("type") != "access":
        raise AuthError("Invalid token type", code="invalid_token")

    jti = claims.get("jti")

    # Optional access token blocklist check
    if rdb.exists(_access_block_key(jti)):
        raise AuthError("Token revoked", code="revoked_token")

    session_id = claims.get("sid")
    valid, sess = _session_valid(session_id)
    if not valid:
        raise AuthError("Session invalid or expired", code="session_invalid")

    # touch session for idle timeout extension
    _touch_session(session_id)

    return claims


def refresh_tokens(refresh_token: str, ip: str, ua: str) -> Dict:
    from security.jwt_utils import decode_token

    try:
        claims = decode_token(refresh_token)
    except Exception:
        raise AuthError("Invalid refresh token", code="invalid_token")

    if claims.get("type") != "refresh":
        raise AuthError("Invalid token type", code="invalid_token")

    jti = claims.get("jti")
    session_id = claims.get("sid")
    user_id = claims.get("sub")

    rkey = _refresh_key(jti)
    data = rdb.hgetall(rkey)
    if not data:
        # If not found, treat as reuse attempt (can't determine chain) -> revoke session
        revoke_session(session_id)
        raise AuthError("Refresh token invalid/reused", code="refresh_reuse_detected")

    if int(data.get("revoked", 0)) == 1:
        revoke_session(session_id)
        raise AuthError("Refresh token revoked", code="refresh_reuse_detected")

    used = int(data.get("used", 0)) == 1
    rotated_to = data.get("rotated_to", "")
    if used:
        # Token already used. If it has rotated_to, this is a reuse -> revoke session
        revoke_session(session_id)
        raise AuthError("Refresh token reuse detected", code="refresh_reuse_detected")

    # Verify session validity
    valid, sess = _session_valid(session_id)
    if not valid:
        # Expired or invalid session; mark refresh revoked
        rdb.hset(rkey, mapping={"revoked": 1})
        raise AuthError("Session invalid or expired", code="session_invalid")

    # Optional user-agent binding
    if config.STRICT_UA_MATCH:
        sess_ua = (sess or {}).get("ua", "")
        if sess_ua and sess_ua != (ua or ""):
            revoke_session(session_id)
            raise AuthError("User-Agent mismatch", code="ua_mismatch")

    # Rotate refresh token: mark old used, create new refresh, issue new access
    new_refresh_token, new_refresh_claims = create_refresh_token(user_id, session_id)
    new_jti = new_refresh_claims["jti"]

    pipe = rdb.pipeline(True)
    # Mark old as used and link to new
    pipe.hset(rkey, mapping={"used": 1, "rotated_to": new_jti})

    # Persist new refresh record
    new_rkey = _refresh_key(new_jti)
    pipe.hset(new_rkey, mapping={
        "user_id": user_id,
        "session_id": session_id,
        "exp": new_refresh_claims["exp"],
        "created_at": new_refresh_claims["iat"],
        "used": 0,
        "revoked": 0,
        "rotated_to": "",
        "parent_jti": jti,
    })
    pipe.sadd(_session_refresh_set(session_id), new_jti)
    pipe.expire(new_rkey, max(1, new_refresh_claims["exp"] - now_ts()))

    # Issue new access token
    new_access_token, access_claims = create_access_token(user_id, session_id)

    pipe.execute()

    # Touch session for idle timeout extension
    _touch_session(session_id)

    return {
        "access_token": new_access_token,
        "access_token_expires": access_claims["exp"],
        "refresh_token": new_refresh_token,
        "refresh_token_expires": new_refresh_claims["exp"],
        "session_id": session_id,
    }


def logout(access_token_claims: Dict):
    # revoke session and optionally blocklist this access token jti
    jti = access_token_claims.get("jti")
    sid = access_token_claims.get("sid")

    # blocklist access token until expiry, to immediately deny reuse
    exp = int(access_token_claims.get("exp", now_ts()))
    ttl = max(1, exp - now_ts())
    rdb.setex(_access_block_key(jti), ttl, 1)

    revoke_session(sid)


def logout_all(user_id: str):
    revoke_all_sessions(user_id)

