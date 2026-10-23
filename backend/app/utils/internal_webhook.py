"""HMAC authentication for internal AI-generation callbacks.

Replicate jobs are polled by the backend; callbacks to /replicate/{work_id}
are emitted by VidGen's internal provider adapters. External untrusted
callbacks must not be sent directly to this endpoint.
"""
import hashlib
import hmac
import json
import os
from urllib.parse import parse_qs, urlsplit


SIGNATURE_HEADER = "X-VidGen-Signature"


def _secret() -> str:
    return os.getenv("VIDGEN_WEBHOOK_SECRET") or os.getenv("JWT_SECRET", "")


def sign_generation_callback(work_id: int, body: bytes, node_id: str = "") -> str:
    secret = _secret()
    if not secret:
        raise RuntimeError("VIDGEN_WEBHOOK_SECRET or JWT_SECRET must be configured")
    signed_bytes = f"{work_id}:{node_id or ''}:".encode("utf-8") + body
    return hmac.new(secret.encode("utf-8"), signed_bytes, hashlib.sha256).hexdigest()


def verify_generation_callback(
    work_id: int, body: bytes, signature: str | None, node_id: str = ""
) -> bool:
    if not signature or not _secret():
        return False
    expected = sign_generation_callback(work_id, body, node_id)
    return hmac.compare_digest(signature, expected)


async def post_signed_generation_callback(client, url: str, work_id: int, payload: dict, **kwargs):
    """Sign the exact serialized body, work ID and workflow node ID."""
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    node_id = parse_qs(urlsplit(url).query).get("node_id", [""])[0]
    headers = {
        "Content-Type": "application/json",
        SIGNATURE_HEADER: sign_generation_callback(work_id, body, node_id),
    }
    return await client.post(url, content=body, headers=headers, **kwargs)
