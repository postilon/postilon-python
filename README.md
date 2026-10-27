# postilon

Python client for the [Postilon](https://postilon.com) transactional email API. Typed, no dependencies, Python 3.9 or later.

Full API documentation: [postilon.com/docs](https://postilon.com/docs).

## Install

```bash
pip install postilon
```

## Send an email

Create an API key in the dashboard under **API Keys**, and keep it in an environment variable.

```python
import os
from postilon import Postilon

postilon = Postilon(os.environ["POSTILON_API_KEY"])

email = postilon.emails.send({
    "from": "Acme <hello@acme.com>",
    "to": "jane@example.com",
    "subject": "Your sign-in code",
    "html": "<p>Your code is <strong>482913</strong>.</p>",
    "text": "Your code is 482913.",
})
# {"id": "msg_…", "status": "queued", …}
```

Requests are plain dicts with the API's own field names (`from` is a Python keyword, so there are no keyword arguments for them), and every method returns the parsed JSON response as a dict. `send` takes every field of [`POST /v1/emails`](https://postilon.com/docs/sending): `cc`, `bcc`, `reply_to`, `headers`, `tags`, `attachments` (Base64 `content`, or a `file_id` from `postilon.files.upload`), `template_id` with `variables`, and `scheduled_at`. `postilon.types` has `TypedDict` definitions for type checkers.

The client also covers `emails.send_batch`, `get`, `list` and `cancel`, and `domains`, `templates`, `files`, `suppressions`, `webhooks` and `inbound`. `Postilon(key, base_url=…, timeout=30.0)` changes the API address or the timeout in seconds.

## Test keys

`ps_test_…` keys are for development: emails are accepted, rendered and reported like real ones, but nothing is delivered and no credits are used, and any `from` address works. `ps_live_…` keys send real mail from a [verified domain](https://postilon.com/docs/domains). The SDK treats both the same.

## Idempotency

Pass an idempotency key, such as the order or event ID the email is for, so a retried request never sends twice. It is sent as the `Idempotency-Key` header:

```python
postilon.emails.send(
    {"from": "billing@acme.com", "to": "jane@example.com", "subject": "Receipt for order #123", "text": "Thanks."},
    idempotency_key="receipt-order-123",
)
```

A retry with the same key and body returns the original response. The same key with a different body fails with `409 idempotency_key_reused`, so use one key per email.

## Errors

When the API answers with an error, the call raises `PostilonError` with the HTTP `status`, the `code` and the `message` ([list of codes](https://postilon.com/docs/errors)). Network failures raise the `urllib.error.URLError` that `urllib` raised.

```python
from postilon import PostilonError

try:
    postilon.emails.send({"from": "hello@acme.com", "to": "jane@example.com", "subject": "Hi", "text": "Hi"})
except PostilonError as err:
    if err.code == "rate_limit_exceeded":
        ...  # err.rate_limit_reset: when the window resets, in Unix seconds (X-RateLimit-Reset)
    else:
        print(err.status, err.code, err.message)  # 403 domain_not_verified …
```

A workspace can make 100 requests per second; use `emails.send_batch` for many emails at once. `429 daily_limit_reached` means the daily sending limit is reached, and retrying within the second will not help. An error response that is not JSON (from a proxy, say) gets the code `http_error`.

## Pagination

Lists return `{"object": "list", "data", "count", "total", "has_more"}` and take `limit` (default 100, at most 1000) and `offset`, newest first:

```python
offset = 0
while True:
    page = postilon.emails.list(status="bounced", limit=100, offset=offset)
    for email in page["data"]:
        print(email["id"], email["to"])
    if not page["has_more"]:
        break
    offset += page["count"]
```

## Verify webhooks

Each webhook request carries `X-Postilon-Signature: t=<unix>,v1=<hex>`. Verify it against the **raw** body, before any JSON parsing, with the endpoint's signing secret (`whsec_…`, returned when the endpoint is created). Signatures older than 5 minutes are refused; change that with `tolerance_seconds=`.

```python
import json
import os
from flask import Flask, request
from postilon import verify_webhook_signature

app = Flask(__name__)

@app.post("/webhooks/postilon")
def postilon_webhook():
    body = request.get_data()  # the raw bytes
    if not verify_webhook_signature(body, request.headers.get("X-Postilon-Signature"), os.environ["POSTILON_WEBHOOK_SECRET"]):
        return "", 400
    event = json.loads(body)
    if event["type"] == "email.bounced":
        ...  # event["data"]["recipient"] bounced
    return "", 200
```

`postilon.webhooks.verify_signature(...)` is the same function. Answer with a `2xx` within 8 seconds and do slow work afterwards. Events can arrive more than once and out of order, so use the event `id` to ignore duplicates. See [Webhooks](https://postilon.com/docs/webhooks).

## Receive email

Turn on inbound for a verified domain (or a subdomain of it), and add the MX record it returns:

```python
domain = postilon.domains.update("dom_…", {"inbound_domain": "reply.acme.com"})
# domain["inbound_record"]: {"type": "MX", "name": "reply.acme.com", "value": "inbound.postilon.com", "priority": 10, …}
```

Each message then reaches your webhooks as `email.received`, with its text and HTML (up to 256 KB), attachment list, SPF, DKIM and DMARC results and a `spam` flag. Read received email with `postilon.inbound.list`, `get`, `attachment(id, index)` and `raw(id)`; the last two return `bytes` (`email.message_from_bytes` parses the raw message). See [Inbound email](https://postilon.com/docs/inbound).

## License

MIT, see [LICENSE](./LICENSE).
