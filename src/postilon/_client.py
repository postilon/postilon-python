import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Union, cast

from ._errors import error_from_response
from ._signature import verify_webhook_signature
from .types import (
    CreateDomainParams,
    CreateSuppressionParams,
    CreateTemplateParams,
    CreateWebhookParams,
    Deleted,
    Domain,
    DomainVerification,
    Email,
    FileObject,
    InboundEmail,
    ListPage,
    SendBatchParams,
    SendBatchResponse,
    SendEmailParams,
    SendEmailResponse,
    Suppression,
    Template,
    UpdateDomainParams,
    UpdateTemplateParams,
    UpdateWebhookParams,
    UploadFileParams,
    Webhook,
    WebhookDelivery,
)

DEFAULT_BASE_URL = "https://api.postilon.com"
USER_AGENT = "postilon-python/1.0.0"

Query = Dict[str, Union[str, int, None]]


def _id(value: str) -> str:
    return urllib.parse.quote(value, safe="")


class _Transport:
    def __init__(self, api_key: str, base_url: str, timeout: float) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Query] = None,
        body: Any = None,
        idempotency_key: Optional[str] = None,
        raw: bool = False,
    ) -> Any:
        url = self._base_url + path
        params = {k: str(v) for k, v in (query or {}).items() if v is not None}
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as res:
                content = res.read()
        except urllib.error.HTTPError as err:
            raise error_from_response(err.code, err.headers, err.read()) from None
        if raw:
            return content
        return json.loads(content.decode("utf-8")) if content else None


class Postilon:
    """Client for the Postilon API. Every method returns the parsed JSON response as a ``dict``,
    and raises ``PostilonError`` when the API answers with an error.

    >>> postilon = Postilon(os.environ["POSTILON_API_KEY"])
    >>> postilon.emails.send({"from": "hello@acme.com", "to": "jane@example.com", "subject": "Hi", "text": "Hello"})
    """

    def __init__(self, api_key: str, *, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0) -> None:
        """``api_key`` is a ``ps_live_…`` or ``ps_test_…`` key. ``timeout`` is in seconds."""
        if not api_key:
            raise ValueError("Postilon: an API key is required (ps_live_… or ps_test_…).")
        transport = _Transport(api_key, base_url, timeout)
        self.emails = Emails(transport)
        self.domains = Domains(transport)
        self.templates = Templates(transport)
        self.files = Files(transport)
        self.suppressions = Suppressions(transport)
        self.webhooks = Webhooks(transport)
        self.inbound = Inbound(transport)


class _Resource:
    def __init__(self, transport: _Transport) -> None:
        self._t = transport


class Emails(_Resource):
    def send(self, params: SendEmailParams, *, idempotency_key: Optional[str] = None) -> SendEmailResponse:
        """``POST /v1/emails``. ``idempotency_key`` is sent as the ``Idempotency-Key`` header: a retry
        with the same key and body returns the original response instead of sending again."""
        return cast(SendEmailResponse, self._t.request("POST", "/v1/emails", body=params, idempotency_key=idempotency_key))

    def send_batch(self, params: SendBatchParams) -> SendBatchResponse:
        """``POST /v1/emails/batch``: up to 100 emails, all or nothing."""
        return cast(SendBatchResponse, self._t.request("POST", "/v1/emails/batch", body=params))

    def get(self, email_id: str) -> Email:
        """``GET /v1/emails/{id}``, with its events."""
        return cast(Email, self._t.request("GET", f"/v1/emails/{_id(email_id)}"))

    def list(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        status: Optional[str] = None,
        q: Optional[str] = None,
        source: Optional[str] = None,
        days: Optional[int] = None,
    ) -> ListPage:
        """``GET /v1/emails``, newest first. ``q`` searches the subject, ID, sender and recipients;
        ``source`` is ``api`` or ``smtp``; ``days`` keeps emails from the last N days."""
        query: Query = {"limit": limit, "offset": offset, "status": status, "q": q, "source": source, "days": days}
        return cast(ListPage, self._t.request("GET", "/v1/emails", query=query))

    def cancel(self, email_id: str) -> Email:
        """A queued or scheduled email; fails with ``409 cannot_cancel`` once delivery started."""
        return cast(Email, self._t.request("POST", f"/v1/emails/{_id(email_id)}/cancel"))


class Domains(_Resource):
    def create(self, params: CreateDomainParams) -> Domain:
        return cast(Domain, self._t.request("POST", "/v1/domains", body=params))

    def list(self, *, limit: Optional[int] = None, offset: Optional[int] = None) -> ListPage:
        return cast(ListPage, self._t.request("GET", "/v1/domains", query={"limit": limit, "offset": offset}))

    def get(self, domain_id: str) -> Domain:
        return cast(Domain, self._t.request("GET", f"/v1/domains/{_id(domain_id)}"))

    def verify(self, domain_id: str) -> DomainVerification:
        """Checks the domain's DNS records now."""
        return cast(DomainVerification, self._t.request("POST", f"/v1/domains/{_id(domain_id)}/verify"))

    def update(self, domain_id: str, params: UpdateDomainParams) -> Domain:
        """Turns open or click tracking on or off, or inbound email (``inbound_domain``, ``""`` for off)."""
        return cast(Domain, self._t.request("PATCH", f"/v1/domains/{_id(domain_id)}", body=params))

    def delete(self, domain_id: str) -> Deleted:
        return cast(Deleted, self._t.request("DELETE", f"/v1/domains/{_id(domain_id)}"))


class Templates(_Resource):
    def create(self, params: CreateTemplateParams) -> Template:
        return cast(Template, self._t.request("POST", "/v1/templates", body=params))

    def list(self, *, limit: Optional[int] = None, offset: Optional[int] = None) -> ListPage:
        return cast(ListPage, self._t.request("GET", "/v1/templates", query={"limit": limit, "offset": offset}))

    def get(self, template_id: str) -> Template:
        return cast(Template, self._t.request("GET", f"/v1/templates/{_id(template_id)}"))

    def update(self, template_id: str, params: UpdateTemplateParams) -> Template:
        return cast(Template, self._t.request("PATCH", f"/v1/templates/{_id(template_id)}", body=params))

    def delete(self, template_id: str) -> Deleted:
        return cast(Deleted, self._t.request("DELETE", f"/v1/templates/{_id(template_id)}"))


class Files(_Resource):
    def upload(self, params: UploadFileParams) -> FileObject:
        """Uploads an attachment to reuse in many emails as ``{"file_id": …}``."""
        return cast(FileObject, self._t.request("POST", "/v1/files", body=params))

    def list(self, *, limit: Optional[int] = None, offset: Optional[int] = None) -> ListPage:
        return cast(ListPage, self._t.request("GET", "/v1/files", query={"limit": limit, "offset": offset}))

    def delete(self, file_id: str) -> Deleted:
        return cast(Deleted, self._t.request("DELETE", f"/v1/files/{_id(file_id)}"))


class Suppressions(_Resource):
    def list(self, *, limit: Optional[int] = None, offset: Optional[int] = None) -> ListPage:
        return cast(ListPage, self._t.request("GET", "/v1/suppressions", query={"limit": limit, "offset": offset}))

    def create(self, params: CreateSuppressionParams) -> Suppression:
        return cast(Suppression, self._t.request("POST", "/v1/suppressions", body=params))

    def delete(self, suppression_id: str) -> Deleted:
        """Removes a suppression (``sup_…``), so the address can be sent to again."""
        return cast(Deleted, self._t.request("DELETE", f"/v1/suppressions/{_id(suppression_id)}"))


class Webhooks(_Resource):
    def create(self, params: CreateWebhookParams) -> Webhook:
        """The response's ``signing_secret`` is the key for ``verify_signature``."""
        return cast(Webhook, self._t.request("POST", "/v1/webhooks", body=params))

    def list(self, *, limit: Optional[int] = None, offset: Optional[int] = None) -> ListPage:
        return cast(ListPage, self._t.request("GET", "/v1/webhooks", query={"limit": limit, "offset": offset}))

    def get(self, webhook_id: str) -> Webhook:
        return cast(Webhook, self._t.request("GET", f"/v1/webhooks/{_id(webhook_id)}"))

    def update(self, webhook_id: str, params: UpdateWebhookParams) -> Webhook:
        return cast(Webhook, self._t.request("PATCH", f"/v1/webhooks/{_id(webhook_id)}", body=params))

    def delete(self, webhook_id: str) -> Deleted:
        return cast(Deleted, self._t.request("DELETE", f"/v1/webhooks/{_id(webhook_id)}"))

    def test(self, webhook_id: str) -> WebhookDelivery:
        """Sends a ``webhook.test`` event to the endpoint."""
        return cast(WebhookDelivery, self._t.request("POST", f"/v1/webhooks/{_id(webhook_id)}/test"))

    def list_event_types(self) -> Dict[str, List[str]]:
        """``GET /v1/webhooks/events``: the event types an endpoint can subscribe to."""
        return cast(Dict[str, List[str]], self._t.request("GET", "/v1/webhooks/events"))

    def list_deliveries(
        self, *, webhook_id: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> ListPage:
        """Recent deliveries, optionally of one endpoint (``webhook_id``)."""
        query: Query = {"webhook_id": webhook_id, "limit": limit, "offset": offset}
        return cast(ListPage, self._t.request("GET", "/v1/webhooks/deliveries", query=query))

    def replay_delivery(self, delivery_id: str) -> WebhookDelivery:
        """Sends a delivery again, as a new delivery."""
        return cast(WebhookDelivery, self._t.request("POST", f"/v1/webhooks/deliveries/{_id(delivery_id)}/replay"))

    @staticmethod
    def verify_signature(
        raw_body: Union[str, bytes], header: Optional[str], secret: str, *, tolerance_seconds: int = 300
    ) -> bool:
        """Same as ``postilon.verify_webhook_signature``."""
        return verify_webhook_signature(raw_body, header, secret, tolerance_seconds=tolerance_seconds)


class Inbound(_Resource):
    """Email received on an inbound domain (https://postilon.com/docs/inbound)."""

    def list(self, *, q: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> ListPage:
        """``GET /v1/inbound``, newest first; ``q`` searches the subject, sender and recipient."""
        return cast(ListPage, self._t.request("GET", "/v1/inbound", query={"q": q, "limit": limit, "offset": offset}))

    def get(self, inbound_id: str) -> InboundEmail:
        """``GET /v1/inbound/{id}``, with its headers."""
        return cast(InboundEmail, self._t.request("GET", f"/v1/inbound/{_id(inbound_id)}"))

    def attachment(self, inbound_id: str, index: int) -> bytes:
        """Attachment ``index`` (from 0, as in ``attachments``), as bytes."""
        return cast(bytes, self._t.request("GET", f"/v1/inbound/{_id(inbound_id)}/attachments/{int(index)}", raw=True))

    def raw(self, inbound_id: str) -> bytes:
        """The message as received (RFC 5322), as bytes for ``email.message_from_bytes``."""
        return cast(bytes, self._t.request("GET", f"/v1/inbound/{_id(inbound_id)}/raw", raw=True))


__all__ = ["Postilon", "Emails", "Domains", "Templates", "Files", "Suppressions", "Webhooks", "Inbound"]
