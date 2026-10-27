"""Python client for the Postilon transactional email API (https://postilon.com/docs)."""

from ._client import Domains, Emails, Files, Inbound, Postilon, Suppressions, Templates, Webhooks
from ._errors import PostilonError
from ._signature import verify_webhook_signature

__version__ = "1.0.0"

__all__ = [
    "Postilon",
    "PostilonError",
    "verify_webhook_signature",
    "Emails",
    "Domains",
    "Templates",
    "Files",
    "Suppressions",
    "Webhooks",
    "Inbound",
    "__version__",
]
