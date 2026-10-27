"""Request and response shapes of the Postilon API (https://postilon.com/docs/api).

Every shape is a plain ``dict`` at runtime; these ``TypedDict`` definitions are for type
checkers and editors. Field names are the API's own, in snake_case, so a field named ``from``
uses the functional ``TypedDict`` syntax. Times are RFC 3339 strings in UTC.
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

# Lists


class ListPage(TypedDict):
    """One page of a list. Ask for the next with ``offset + count`` while ``has_more`` is true."""

    object: Literal["list"]
    data: List[Dict[str, Any]]
    count: int
    total: int
    has_more: bool


class Deleted(TypedDict):
    deleted: bool


# Emails

EmailStatus = Literal[
    "scheduled", "queued", "sent", "delivered", "opened", "clicked", "bounced", "complained", "suppressed", "failed", "canceled"
]


class Tag(TypedDict):
    name: str
    value: str


class InlineAttachment(TypedDict):
    """A file sent inline, its ``content`` encoded in Base64."""

    filename: str
    content_type: str
    content: str


class _FileAttachmentBase(TypedDict):
    file_id: str


class FileAttachment(_FileAttachmentBase, total=False):
    """A file uploaded earlier with ``files.upload``."""

    filename: str
    content_type: str


Attachment = Union[InlineAttachment, FileAttachment]

_SendEmailRequired = TypedDict("_SendEmailRequired", {"from": str, "to": Union[str, List[str]]})


class SendEmailParams(_SendEmailRequired, total=False):
    """``from`` is ``hello@acme.com`` or ``Acme <hello@acme.com>``; with a live key its domain must
    be verified. ``subject`` is required unless ``template_id`` is set."""

    cc: Union[str, List[str]]
    bcc: Union[str, List[str]]
    subject: str
    html: str
    text: str
    reply_to: str
    template_id: str
    variables: Dict[str, str]
    attachments: List[Attachment]
    headers: Dict[str, str]
    tags: List[Tag]
    scheduled_at: str


SendEmailResponse = TypedDict(
    "SendEmailResponse",
    {
        "id": str,
        "status": Literal["queued", "scheduled"],
        "from": str,
        "to": List[str],
        "environment": Literal["live", "test"],
        "credits_used": int,
        "scheduled_at": Optional[str],
        "created_at": str,
    },
)


class BatchRecipient(TypedDict, total=False):
    to: str
    variables: Dict[str, str]


_SendBatchRequired = TypedDict("_SendBatchRequired", {"from": str, "batch": List[BatchRecipient]})


class SendBatchParams(_SendBatchRequired, total=False):
    """``batch`` holds 1 to 100 emails, each with its own recipient and variables."""

    subject: str
    html: str
    text: str
    template_id: str


class SendBatchResponse(TypedDict):
    object: Literal["batch_result"]
    count: int
    data: List[Dict[str, str]]


class EmailEvent(TypedDict, total=False):
    id: str
    email_id: str
    event_type: str
    recipient: str
    metadata: Dict[str, str]
    occurred_at: str


Email = TypedDict(
    "Email",
    {
        "id": str,
        "workspace_id": str,
        "from": str,
        "to": List[str],
        "cc": List[str],
        "bcc": List[str],
        "reply_to": str,
        "subject": str,
        "html": str,
        "text": str,
        "attachments": List[Attachment],
        "variables": Dict[str, str],
        "headers": Dict[str, str],
        "template_id": str,
        "tags": List[Tag],
        "status": EmailStatus,
        "environment": Literal["live", "test"],
        "transport": Literal["rest_api", "rest_api_batch", "smtp_relay"],
        "source": Literal["api", "smtp"],
        "credits_used": int,
        "dkim_signed": bool,
        "events": List[EmailEvent],
        "scheduled_at": str,
        "sent_at": str,
        "delivered_at": str,
        "created_at": str,
        "content_purged_at": str,
    },
    total=False,
)

# Domains


class DnsRecord(TypedDict, total=False):
    type: str
    name: str
    value: str
    priority: int
    purpose: str
    status: Literal["pending", "verified"]
    required: bool
    """False for a recommended record (DMARC), which is not needed to verify the domain."""


class Domain(TypedDict, total=False):
    id: str
    workspace_id: str
    domain_name: str
    status: Literal["pending", "verified", "failed"]
    dkim_selector: str
    dkim_public_key: str
    dmarc_record: str
    return_path_domain: str
    dns_records: List[DnsRecord]
    open_tracking_enabled: bool
    click_tracking_enabled: bool
    inbound_domain: str
    """The domain (or its subdomain) that receives email; empty while inbound is off."""
    inbound_record: DnsRecord
    """The MX record the inbound domain needs; on a single domain while inbound is on."""
    verified_at: str
    created_at: str


class CreateDomainParams(TypedDict):
    domain_name: str


class UpdateDomainParams(TypedDict, total=False):
    open_tracking_enabled: bool
    click_tracking_enabled: bool
    inbound_domain: str
    """Receive email on this domain or a subdomain of it; ``""`` turns inbound off."""


class DomainVerification(TypedDict):
    domain: Domain
    dns_verification: Dict[str, Any]


# Templates


class Template(TypedDict, total=False):
    id: str
    workspace_id: str
    name: str
    subject_template: str
    html_template: str
    text_template: str
    variables: List[str]
    updated_at: str
    created_at: str


class _CreateTemplateRequired(TypedDict):
    name: str


class CreateTemplateParams(_CreateTemplateRequired, total=False):
    subject_template: str
    html_template: str
    text_template: str
    variables: List[str]


class UpdateTemplateParams(TypedDict, total=False):
    """Fields left out (or empty) keep their current value."""

    name: str
    subject_template: str
    html_template: str
    text_template: str
    variables: List[str]


# Files


class _UploadFileRequired(TypedDict):
    filename: str
    content: str
    """The file encoded in Base64, such as ``base64.b64encode(data).decode()``."""


class UploadFileParams(_UploadFileRequired, total=False):
    content_type: str


class FileObject(TypedDict, total=False):
    id: str
    workspace_id: str
    filename: str
    content_type: str
    size_bytes: int
    expires_at: str
    created_at: str


# Suppressions


class Suppression(TypedDict, total=False):
    id: str
    workspace_id: str
    email_address: str
    reason: Literal["hard_bounce", "complaint", "unsubscribe", "manual"]
    source_email_id: str
    created_at: str


class CreateSuppressionParams(TypedDict):
    email_address: str


# Inbound

AuthResult = str
"""An SPF, DKIM or DMARC result: ``pass``, ``fail``, ``softfail``, ``neutral``, ``none``,
``temperror`` or ``permerror``."""


class InboundAttachment(TypedDict, total=False):
    filename: str
    content_type: str
    size: int
    """Bytes."""
    content_id: str
    """Set for an inline image the HTML shows as ``cid:<content_id>``."""


InboundEmail = TypedDict(
    "InboundEmail",
    {
        "id": str,
        "workspace_id": str,
        "domain_id": str,
        "envelope_from": str,
        "recipient": str,
        "remote_ip": str,
        "from": str,
        "to": List[str],
        "cc": List[str],
        "reply_to": str,
        "subject": str,
        "message_id": str,
        "in_reply_to": str,
        "references": str,
        "text": str,
        "html": str,
        "headers": Dict[str, List[str]],
        "attachments": List[InboundAttachment],
        "size_bytes": int,
        "spf": AuthResult,
        "dkim": AuthResult,
        "dmarc": AuthResult,
        "spam": bool,
        "credits_used": int,
        "content_purged_at": str,
        "created_at": str,
    },
    total=False,
)
"""One inbound email per recipient; ``headers`` only from ``inbound.get``, and the content is
deleted 30 days after it arrived (``content_purged_at``)."""

# Webhooks

WebhookEventType = Literal[
    "email.sent", "email.delivered", "email.bounced", "email.complained", "email.opened", "email.clicked", "email.failed", "email.received"
]


class Webhook(TypedDict, total=False):
    id: str
    workspace_id: str
    url: str
    description: str
    signing_secret: str
    """``whsec_…``: the key for ``verify_signature``."""
    subscribed_events: List[WebhookEventType]
    is_active: bool
    created_at: str


class _CreateWebhookRequired(TypedDict):
    url: str
    """HTTPS and reachable from the internet."""


class CreateWebhookParams(_CreateWebhookRequired, total=False):
    description: str
    subscribed_events: List[WebhookEventType]
    """Leave out to receive every event."""


class UpdateWebhookParams(TypedDict, total=False):
    url: str
    description: str
    subscribed_events: List[WebhookEventType]
    is_active: bool


class WebhookDelivery(TypedDict, total=False):
    id: str
    webhook_id: str
    workspace_id: str
    url: str
    event_type: str
    payload: str
    """The JSON body that was sent, as a string."""
    signature: str
    response_status: int
    attempt_count: int
    status: Literal["pending", "delivered", "failed"]
    next_attempt_at: str
    last_error: str
    created_at: str


class WebhookEvent(TypedDict):
    """The JSON body Postilon posts to a webhook endpoint. ``data`` depends on ``type``: an email
    event carries ``email_id``, ``recipient`` and ``status``; ``email.received`` carries the
    received email (``inbound_id``, ``text``, ``html``, ``attachments``, ``auth``, ``spam`` …)."""

    id: str
    type: str
    created_at: str
    workspace_id: str
    data: Dict[str, Any]
