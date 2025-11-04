import json
from typing import Dict, Any, Tuple
from .crypto import b64url_encode, b64url_decode, Ed25519Signer


def pae(payload_type: str, payload: bytes) -> bytes:
    # DSSE Pre-Authentication Encoding (PAE):
    # PAE(type, body) = "DSSEv1" + SP + len(type) + SP + type + SP + len(body) + SP + body
    def enc_int(n: int) -> bytes:
        return str(n).encode("utf-8")
    return b" ".join([
        b"DSSEv1",
        enc_int(len(payload_type)),
        payload_type.encode("utf-8"),
        enc_int(len(payload)),
        payload,
    ])


def create_envelope(signer: Ed25519Signer, payload_type: str, payload_obj: Dict[str, Any]) -> Dict[str, Any]:
    payload_bytes = json.dumps(payload_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    to_sign = pae(payload_type, payload_bytes)
    sig = signer.sign(to_sign)
    envelope = {
        "payloadType": payload_type,
        "payload": b64url_encode(payload_bytes),
        "signatures": [
            {"keyid": signer.keyid, "sig": b64url_encode(sig)}
        ],
    }
    return envelope


def verify_envelope_with_signer(signer: Ed25519Signer, envelope: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    try:
        payload_type = envelope["payloadType"]
        payload_bytes = b64url_decode(envelope["payload"])
        to_verify = pae(payload_type, payload_bytes)
        sigs = envelope.get("signatures", [])
        ok = False
        for s in sigs:
            sig_b = b64url_decode(s["sig"]) if isinstance(s.get("sig"), str) else None
            if sig_b is None:
                continue
            if signer.verify(to_verify, sig_b):
                ok = True
                break
        payload_obj = json.loads(payload_bytes)
        return ok, payload_obj
    except Exception:
        return False, {}

