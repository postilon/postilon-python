import hashlib
import hmac
import json
import sys
import time
import unittest
from typing import Optional

from postilon import Postilon, verify_webhook_signature

SECRET = "whsec_test_fixture_secret"


def sign(body: str, secret: str = SECRET, t: Optional[int] = None) -> str:
    """Signs like the server's crypto.SignWebhookPayload: t=<unix>,v1=hex(HMAC-SHA256(secret, "<t>.<body>"))."""
    t = int(time.time()) if t is None else t
    mac = hmac.new(secret.encode(), f"{t}.{body}".encode(), hashlib.sha256).hexdigest()
    return f"t={t},v1={mac}"


BODY = json.dumps({"id": "evt_1", "type": "email.delivered", "data": {"email_id": "msg_1"}})

# Signed by the Postilon API server itself (SECRET, GO_PAYLOAD, timestamp 1761386403).
GO_PAYLOAD = '{"id":"evt_2bC5dE8fG1hJ4kL7mN0p","type":"email.delivered","data":{"subject":"Grüße – 🎉"}}'
GO_HEADER = "t=1761386403,v1=7aed1efef187a50bfc3f2cc7d81ec15fe66f294727a58336826aa6878d7b96f6"
ANY_AGE = sys.maxsize


class VerifyWebhookSignatureTest(unittest.TestCase):
    def test_accepts_a_signature_made_by_the_go_server_as_str_or_bytes(self) -> None:
        self.assertTrue(verify_webhook_signature(GO_PAYLOAD, GO_HEADER, SECRET, tolerance_seconds=ANY_AGE))
        self.assertTrue(verify_webhook_signature(GO_PAYLOAD.encode("utf-8"), GO_HEADER, SECRET, tolerance_seconds=ANY_AGE))

    def test_rejects_that_signature_by_default_because_its_timestamp_is_old(self) -> None:
        self.assertFalse(verify_webhook_signature(GO_PAYLOAD, GO_HEADER, SECRET))

    def test_accepts_a_fresh_valid_signature_also_through_the_client(self) -> None:
        header = sign(BODY)
        self.assertTrue(verify_webhook_signature(BODY, header, SECRET))
        self.assertTrue(Postilon("ps_test_x").webhooks.verify_signature(BODY.encode(), header, SECRET))

    def test_rejects_a_tampered_body(self) -> None:
        self.assertFalse(verify_webhook_signature(BODY.replace("msg_1", "msg_2"), sign(BODY), SECRET))
        self.assertFalse(verify_webhook_signature(BODY + " ", sign(BODY), SECRET))

    def test_rejects_the_wrong_secret(self) -> None:
        self.assertFalse(verify_webhook_signature(BODY, sign(BODY, "whsec_other"), SECRET))
        self.assertFalse(verify_webhook_signature(BODY, sign(BODY), ""))

    def test_rejects_timestamps_outside_the_tolerance_past_or_future(self) -> None:
        now = int(time.time())
        self.assertFalse(verify_webhook_signature(BODY, sign(BODY, SECRET, now - 301), SECRET))
        self.assertFalse(verify_webhook_signature(BODY, sign(BODY, SECRET, now + 301), SECRET))
        self.assertTrue(verify_webhook_signature(BODY, sign(BODY, SECRET, now - 290), SECRET))
        self.assertFalse(verify_webhook_signature(BODY, sign(BODY, SECRET, now - 290), SECRET, tolerance_seconds=60))
        self.assertTrue(verify_webhook_signature(BODY, sign(BODY, SECRET, now - 3000), SECRET, tolerance_seconds=3600))

    def test_returns_false_without_raising_for_missing_or_malformed_headers(self) -> None:
        good = sign(BODY)
        t = good[2 : good.index(",")]
        v1 = good[good.index("v1=") + 3 :]
        for header in [
            None,
            "",
            "garbage",
            f"t={t}",
            f"v1={v1}",
            f"t=,v1={v1}",
            f"t=abc,v1={v1}",
            f"t=-{t},v1={v1}",
            f"t={t},v1=abcd",  # too short
            f"t={t},v1={v1}00",  # too long
            f"t={t},v1={'z' * 64}",  # not hex
            f"t={t},v0={v1}",
        ]:
            with self.subTest(header=header):
                self.assertFalse(verify_webhook_signature(BODY, header, SECRET))

    def test_tolerates_spaces_and_accepts_any_matching_v1(self) -> None:
        t_part, v1_part = sign(BODY).split(",")
        self.assertTrue(verify_webhook_signature(BODY, f" {t_part} , {v1_part} ", SECRET))
        self.assertTrue(verify_webhook_signature(BODY, f"{t_part},v1={'0' * 64},{v1_part}", SECRET))


if __name__ == "__main__":
    unittest.main()
