import json
from typing import Any, Optional, Protocol


class _Headers(Protocol):
    def get(self, name: str, /) -> Any: ...


class PostilonError(Exception):
    """An error answered by the Postilon API: ``{"error": {"code", "message"}}`` with an HTTP status.

    See https://postilon.com/docs/errors for the codes. Network failures are not wrapped: they
    raise the ``urllib.error.URLError`` (or ``OSError``) that ``urllib`` raised.
    """

    status: int
    """HTTP status, such as 403."""
    code: str
    """Error code, such as ``domain_not_verified``; ``http_error`` when the body was not a Postilon error."""
    message: str
    rate_limit_reset: Optional[int]
    """For ``429 rate_limit_exceeded``: when the rate limit window resets, in Unix seconds
    (the ``X-RateLimit-Reset`` header). Retry after this time."""

    def __init__(self, status: int, code: str, message: str, rate_limit_reset: Optional[int] = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.rate_limit_reset = rate_limit_reset

    def __repr__(self) -> str:
        return f"PostilonError(status={self.status}, code={self.code!r}, message={self.message!r})"


def error_from_response(status: int, headers: _Headers, body: bytes) -> PostilonError:
    """Builds the error for a non-2xx response from its status, headers and body."""
    code, message = "http_error", f"HTTP {status}"
    try:
        err = json.loads(body.decode("utf-8")).get("error")
        if isinstance(err, dict) and isinstance(err.get("code"), str):
            code = err["code"]
            if isinstance(err.get("message"), str) and err["message"]:
                message = err["message"]
    except (ValueError, AttributeError):
        pass  # Not JSON (a proxy's error page, say): keep the generic code and message.
    reset = None
    if status == 429 and code == "rate_limit_exceeded":
        try:
            n = int(headers.get("X-RateLimit-Reset") or "")
            reset = n if n > 0 else None
        except ValueError:
            pass
    return PostilonError(status, code, message, reset)
