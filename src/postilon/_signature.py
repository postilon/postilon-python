import hashlib
import hmac
import re
import time
from typing import Optional, Union

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_DIGITS = re.compile(r"^\d+$")


def verify_webhook_signature(
    raw_body: Union[str, bytes],
    header: Optional[str],
    secret: str,
    *,
    tolerance_seconds: int = 300,
) -> bool:
    """Checks the ``X-Postilon-Signature`` header of a webhook request.

    The header is ``t=<unix>,v1=<hex>``, where ``v1`` is the HMAC-SHA256 of ``"<t>.<raw body>"``
    keyed with the endpoint's signing secret. Pass the body exactly as received, before any JSON
    parsing. Returns False, never raises, for a missing or malformed header, a wrong signature or
    a timestamp more than ``tolerance_seconds`` away from now.
    """
    if not isinstance(header, str) or not secret:
        return False
    timestamp = None
    signatures = []
    for part in header.split(","):
        key, eq, value = part.partition("=")
        if not eq:
            continue
        key, value = key.strip(), value.strip()
        if key == "t":
            timestamp = value
        elif key == "v1" and _HEX64.match(value):
            signatures.append(bytes.fromhex(value))
    if not timestamp or not _DIGITS.match(timestamp) or not signatures:
        return False
    if abs(time.time() - int(timestamp)) > tolerance_seconds:
        return False
    body = raw_body.encode("utf-8") if isinstance(raw_body, str) else bytes(raw_body)
    expected = hmac.new(secret.encode("utf-8"), timestamp.encode("ascii") + b"." + body, hashlib.sha256).digest()
    return any(hmac.compare_digest(sig, expected) for sig in signatures)
