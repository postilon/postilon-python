import json
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlsplit

from postilon import Postilon, PostilonError

KEY = "ps_test_abc123"

# (status, headers, body) answered for a recorded request.
Response = Tuple[int, Dict[str, str], bytes]


def json_response(status: int, body: Any, headers: Optional[Dict[str, str]] = None) -> Response:
    return status, {"Content-Type": "application/json", **(headers or {})}, json.dumps(body).encode()


class FakeAPI:
    """A local HTTP server that records each request and answers with ``respond(call)``."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.respond: Callable[[Dict[str, Any]], Response] = lambda call: json_response(200, {"ok": True})
        api = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else None
                parts = urlsplit(self.path)
                call = {
                    "method": self.command,
                    "path": parts.path,
                    "raw_path": self.path,
                    "query": dict(parse_qsl(parts.query)),
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": json.loads(raw) if raw else None,
                }
                api.calls.append(call)
                status, headers, body = api.respond(call)
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = do_PATCH = do_DELETE = _handle

            def log_message(self, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


class ClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.api = FakeAPI()
        self.addCleanup(self.api.close)
        self.client = Postilon(KEY, base_url=self.api.url + "/")

    def test_send_with_auth_json_body_and_idempotency_key(self) -> None:
        accepted = {"id": "msg_1", "status": "queued", "from": "hello@acme.com", "to": ["jane@example.com"]}
        self.api.respond = lambda call: json_response(202, accepted)
        params = {
            "from": "Acme <hello@acme.com>",
            "to": ["jane@example.com"],
            "subject": "Receipt",
            "html": "<p>Grüße 🎉</p>",
            "attachments": [{"filename": "a.pdf", "content_type": "application/pdf", "content": "JVBERi0="}, {"file_id": "file_1"}],
            "variables": {"name": "Jane"},
        }
        res = self.client.emails.send(params, idempotency_key="receipt-order-123")  # type: ignore[arg-type]
        self.assertEqual(res, accepted)
        [call] = self.api.calls
        self.assertEqual((call["method"], call["path"]), ("POST", "/v1/emails"))
        self.assertEqual(call["headers"]["authorization"], f"Bearer {KEY}")
        self.assertEqual(call["headers"]["content-type"], "application/json")
        self.assertEqual(call["headers"]["idempotency-key"], "receipt-order-123")
        self.assertTrue(call["headers"]["user-agent"].startswith("postilon-python/"))
        self.assertEqual(call["body"], params)

    def test_no_idempotency_key_unless_given(self) -> None:
        self.client.emails.send({"from": "a@acme.com", "to": "b@example.com", "subject": "s", "text": "t"})
        self.assertNotIn("idempotency-key", self.api.calls[0]["headers"])

    def test_get_sends_no_body_and_builds_list_queries(self) -> None:
        self.client.emails.list(status="bounced", q="jane", source="api", days=7, limit=50, offset=100)
        [call] = self.api.calls
        self.assertEqual((call["method"], call["path"], call["body"]), ("GET", "/v1/emails", None))
        self.assertNotIn("content-type", call["headers"])
        self.assertEqual(call["query"], {"status": "bounced", "q": "jane", "source": "api", "days": "7", "limit": "50", "offset": "100"})

    def test_omits_unset_query_parameters(self) -> None:
        self.client.webhooks.list_deliveries(limit=10)
        self.assertEqual(self.api.calls[0]["raw_path"], "/v1/webhooks/deliveries?limit=10")

    def test_encodes_ids(self) -> None:
        self.client.emails.get("msg_a/b?c")
        self.assertEqual(self.api.calls[0]["raw_path"], "/v1/emails/msg_a%2Fb%3Fc")

    def test_refuses_a_missing_api_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "API key is required"):
            Postilon("")

    def test_routes(self) -> None:
        c = self.client
        routes: List[Tuple[Callable[[], Any], str, str, Any]] = [
            (lambda: c.emails.send_batch({"from": "a@acme.com", "batch": [{"to": "b@example.com"}]}), "POST", "/v1/emails/batch", {"from": "a@acme.com", "batch": [{"to": "b@example.com"}]}),
            (lambda: c.emails.cancel("msg_1"), "POST", "/v1/emails/msg_1/cancel", None),
            (lambda: c.domains.create({"domain_name": "acme.com"}), "POST", "/v1/domains", {"domain_name": "acme.com"}),
            (lambda: c.domains.list(), "GET", "/v1/domains", None),
            (lambda: c.domains.get("dom_1"), "GET", "/v1/domains/dom_1", None),
            (lambda: c.domains.verify("dom_1"), "POST", "/v1/domains/dom_1/verify", None),
            (lambda: c.domains.update("dom_1", {"inbound_domain": "reply.acme.com"}), "PATCH", "/v1/domains/dom_1", {"inbound_domain": "reply.acme.com"}),
            (lambda: c.domains.delete("dom_1"), "DELETE", "/v1/domains/dom_1", None),
            (lambda: c.templates.create({"name": "Welcome"}), "POST", "/v1/templates", {"name": "Welcome"}),
            (lambda: c.templates.list(limit=5), "GET", "/v1/templates?limit=5", None),
            (lambda: c.templates.get("tmpl_1"), "GET", "/v1/templates/tmpl_1", None),
            (lambda: c.templates.update("tmpl_1", {"html_template": "<p/>"}), "PATCH", "/v1/templates/tmpl_1", {"html_template": "<p/>"}),
            (lambda: c.templates.delete("tmpl_1"), "DELETE", "/v1/templates/tmpl_1", None),
            (lambda: c.files.upload({"filename": "a.pdf", "content": "JVBERi0="}), "POST", "/v1/files", {"filename": "a.pdf", "content": "JVBERi0="}),
            (lambda: c.files.list(), "GET", "/v1/files", None),
            (lambda: c.files.delete("file_1"), "DELETE", "/v1/files/file_1", None),
            (lambda: c.suppressions.list(offset=100), "GET", "/v1/suppressions?offset=100", None),
            (lambda: c.suppressions.create({"email_address": "jane@example.com"}), "POST", "/v1/suppressions", {"email_address": "jane@example.com"}),
            (lambda: c.suppressions.delete("sup_1"), "DELETE", "/v1/suppressions/sup_1", None),
            (lambda: c.webhooks.create({"url": "https://acme.com/hook", "subscribed_events": ["email.received"]}), "POST", "/v1/webhooks", {"url": "https://acme.com/hook", "subscribed_events": ["email.received"]}),
            (lambda: c.webhooks.list(), "GET", "/v1/webhooks", None),
            (lambda: c.webhooks.get("wh_1"), "GET", "/v1/webhooks/wh_1", None),
            (lambda: c.webhooks.update("wh_1", {"is_active": False}), "PATCH", "/v1/webhooks/wh_1", {"is_active": False}),
            (lambda: c.webhooks.delete("wh_1"), "DELETE", "/v1/webhooks/wh_1", None),
            (lambda: c.webhooks.test("wh_1"), "POST", "/v1/webhooks/wh_1/test", None),
            (lambda: c.webhooks.list_event_types(), "GET", "/v1/webhooks/events", None),
            (lambda: c.webhooks.list_deliveries(webhook_id="wh_1"), "GET", "/v1/webhooks/deliveries?webhook_id=wh_1", None),
            (lambda: c.webhooks.replay_delivery("whd_1"), "POST", "/v1/webhooks/deliveries/whd_1/replay", None),
            (lambda: c.inbound.list(q="order", limit=10), "GET", "/v1/inbound?q=order&limit=10", None),
            (lambda: c.inbound.get("inb_1"), "GET", "/v1/inbound/inb_1", None),
        ]
        for invoke, method, path, body in routes:
            with self.subTest(f"{method} {path}"):
                self.api.calls.clear()
                self.assertEqual(invoke(), {"ok": True})
                [call] = self.api.calls
                self.assertEqual((call["method"], call["raw_path"], call["body"]), (method, path, body))
                self.assertEqual(call["headers"]["authorization"], f"Bearer {KEY}")
                self.assertEqual(call["headers"].get("content-type"), None if body is None else "application/json")


class InboundTest(unittest.TestCase):
    def setUp(self) -> None:
        self.api = FakeAPI()
        self.addCleanup(self.api.close)
        self.client = Postilon(KEY, base_url=self.api.url)

    def test_attachment_and_raw_as_bytes(self) -> None:
        payload = bytes([0, 255, 1, 128])
        message = "Subject: hi\r\n\r\nGrüße".encode("utf-8")
        self.api.respond = lambda call: (200, {"Content-Type": "message/rfc822"}, message) if call["path"].endswith("/raw") else (200, {"Content-Type": "application/octet-stream"}, payload)
        self.assertEqual(self.client.inbound.attachment("inb_1", 0), payload)
        self.assertEqual(self.client.inbound.raw("inb_1"), message)
        self.assertEqual(self.api.calls[0]["raw_path"], "/v1/inbound/inb_1/attachments/0")

    def test_deleted_content_raises(self) -> None:
        self.api.respond = lambda call: json_response(410, {"error": {"code": "content_purged", "message": "Deleted after 30 days."}})
        with self.assertRaises(PostilonError) as ctx:
            self.client.inbound.attachment("inb_1", 0)
        self.assertEqual((ctx.exception.status, ctx.exception.code), (410, "content_purged"))


class ErrorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.api = FakeAPI()
        self.addCleanup(self.api.close)
        self.client = Postilon(KEY, base_url=self.api.url)

    def send(self) -> Any:
        return self.client.emails.send({"from": "a@acme.com", "to": "b@example.com", "subject": "s", "text": "t"})

    def test_status_code_and_message(self) -> None:
        msg = "Sender domain acme.com is not verified in this workspace."
        self.api.respond = lambda call: json_response(403, {"error": {"code": "domain_not_verified", "message": msg}})
        with self.assertRaises(PostilonError) as ctx:
            self.send()
        err = ctx.exception
        self.assertEqual((err.status, err.code, err.message, str(err), err.rate_limit_reset), (403, "domain_not_verified", msg, msg, None))

    def test_rate_limit_reset_on_429(self) -> None:
        self.api.respond = lambda call: json_response(429, {"error": {"code": "rate_limit_exceeded", "message": "Slow down."}}, {"X-RateLimit-Reset": "1761386404"})
        with self.assertRaises(PostilonError) as ctx:
            self.send()
        self.assertEqual((ctx.exception.code, ctx.exception.rate_limit_reset), ("rate_limit_exceeded", 1761386404))

    def test_no_reset_for_daily_limit(self) -> None:
        self.api.respond = lambda call: json_response(429, {"error": {"code": "daily_limit_reached", "message": "Daily limit."}}, {"X-RateLimit-Reset": "1761386404"})
        with self.assertRaises(PostilonError) as ctx:
            self.send()
        self.assertEqual((ctx.exception.code, ctx.exception.rate_limit_reset), ("daily_limit_reached", None))

    def test_non_json_error_is_http_error(self) -> None:
        self.api.respond = lambda call: (502, {"Content-Type": "text/html"}, b"<html>Bad gateway</html>")
        with self.assertRaises(PostilonError) as ctx:
            self.client.domains.list()
        self.assertEqual((ctx.exception.status, ctx.exception.code, ctx.exception.message), (502, "http_error", "HTTP 502"))

    def test_network_failures_pass_through(self) -> None:
        self.api.close()
        with self.assertRaises(urllib.error.URLError):
            self.client.emails.get("msg_1")


if __name__ == "__main__":
    unittest.main()
