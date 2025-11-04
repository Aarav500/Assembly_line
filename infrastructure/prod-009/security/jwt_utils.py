import uuid
import jwt
from typing import Tuple, Dict
from config import Config
from utils.time import now_ts

config = Config()

ALG = "HS256"


def generate_jti() -> str:
    return str(uuid.uuid4())


def _base_claims(sub: str, session_id: str, typ: str, expires_in: int) -> Dict:
    iat = now_ts()
    exp = iat + expires_in
    return {
        "sub": sub,
        "sid": session_id,
        "jti": generate_jti(),
        "type": typ,
        "iat": iat,
        "exp": exp,
    }


def create_access_token(user_id: str, session_id: str) -> Tuple[str, Dict]:
    claims = _base_claims(user_id, session_id, "access", config.ACCESS_TOKEN_EXPIRES_SECONDS)
    token = jwt.encode(claims, config.JWT_SECRET, algorithm=ALG)
    return token, claims


def create_refresh_token(user_id: str, session_id: str) -> Tuple[str, Dict]:
    claims = _base_claims(user_id, session_id, "refresh", config.REFRESH_TOKEN_EXPIRES_SECONDS)
    token = jwt.encode(claims, config.JWT_SECRET, algorithm=ALG)
    return token, claims


def decode_token(token: str) -> Dict:
    return jwt.decode(token, config.JWT_SECRET, algorithms=[ALG])

