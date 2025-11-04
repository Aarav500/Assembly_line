from typing import Dict, Optional
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from .utils import b64url_encode, b64url_decode

DSSE_VERSION = "DSSEv1"


def pae(t: str, payload: bytes) -> bytes:
    # Pre-Authentication Encoding (PAE):
    # "DSSEv1" SP len(t) SP t SP len(payload) SP payload
    parts = [
        DSSE_VERSION.encode("utf-8"),
        str(len(t)).encode("utf-8"),
        t.encode("utf-8"),
        str(len(payload)).encode("utf-8"),
        payload,
    ]
    return b" ".join(parts)


def sign_envelope(payload_type: str, payload_bytes: bytes, private_key: Ed25519PrivateKey, keyid: Optional[str] = None) -> Dict:
    pae_bytes = pae(payload_type, payload_bytes)
    sig = private_key.sign(pae_bytes)

    envelope = {
        "payloadType": payload_type,
        "payload": b64url_encode(payload_bytes),
        "signatures": [
            {
                **({"keyid": keyid} if keyid else {}),
                "sig": b64url_encode(sig),
            }
        ],
    }
    return envelope


def verify_envelope(envelope: Dict, public_keys: Dict[str, bytes]) -> bytes:
    # public_keys: mapping of keyid -> ed25519 raw pub bytes
    if not isinstance(envelope, dict):
        raise ValueError("envelope must be an object")
    ptype = envelope.get("payloadType")
    payload_b64 = envelope.get("payload")
    sigs = envelope.get("signatures")

    if not isinstance(ptype, str) or not isinstance(payload_b64, str) or not isinstance(sigs, list) or not sigs:
        raise ValueError("invalid envelope structure")

    payload = b64url_decode(payload_b64)
    pae_bytes = pae(ptype, payload)

    last_err = None
    for s in sigs:
        if not isinstance(s, dict) or "sig" not in s:
            continue
        sig = b64url_decode(s["sig"]) if isinstance(s["sig"], str) else None
        kid = s.get("keyid")

        # If keyid provided, prefer it; otherwise try all keys
        candidates = []
        if kid and kid in public_keys:
            candidates.append(public_keys[kid])
        else:
            candidates.extend(public_keys.values())

        for pub_raw in candidates:
            try:
                pub = Ed25519PublicKey.from_public_bytes(pub_raw)
                pub.verify(sig, pae_bytes)
                return payload
            except InvalidSignature as e:
                last_err = e
                continue
    raise ValueError("signature verification failed" if last_err else "no valid signatures found")

