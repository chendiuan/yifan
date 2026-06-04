import base64
import hashlib
import hmac
import json

from django.test import Client, TestCase, override_settings

from .models import CareRecord


def line_signature(body, channel_secret):
    digest = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


class TrackerApiTests(TestCase):
    def test_create_and_delete_diaper_record_with_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/")
        token = client.cookies["csrftoken"].value

        response = client.post(
            "/api/records/",
            data=json.dumps({
                "type": "diaper",
                "time": "2026-05-28T16:50",
                "pee": True,
                "poop": True,
                "poopAmount": "中等",
                "poopColor": "黃色",
            }),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 201)
        record_id = response.json()["record"]["id"]
        self.assertEqual(CareRecord.objects.count(), 1)

        delete_response = client.delete(
            f"/api/records/{record_id}/",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(CareRecord.objects.count(), 0)


class LineWebhookTests(TestCase):
    @override_settings(LINE_CHANNEL_SECRET="test-channel-secret")
    def test_accepts_valid_line_signature(self):
        body = json.dumps({"events": [{}]}).encode("utf-8")
        secret = "test-channel-secret"

        response = self.client.post(
            "/line/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_LINE_SIGNATURE=line_signature(body, secret),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "events": 1})

    @override_settings(LINE_CHANNEL_SECRET="")
    def test_rejects_when_line_channel_secret_is_not_configured(self):
        body = json.dumps({"events": []}).encode("utf-8")

        response = self.client.post(
            "/line/webhook/",
            data=body,
            content_type="application/json",
            HTTP_X_LINE_SIGNATURE=line_signature(body, "test-channel-secret"),
        )

        self.assertEqual(response.status_code, 503)

    @override_settings(LINE_CHANNEL_SECRET="test-channel-secret")
    def test_rejects_missing_line_signature(self):
        response = self.client.post(
            "/line/webhook/",
            data=json.dumps({"events": []}).encode("utf-8"),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    @override_settings(LINE_CHANNEL_SECRET="test-channel-secret")
    def test_rejects_invalid_line_signature(self):
        response = self.client.post(
            "/line/webhook/",
            data=json.dumps({"events": []}).encode("utf-8"),
            content_type="application/json",
            HTTP_X_LINE_SIGNATURE="invalid",
        )

        self.assertEqual(response.status_code, 403)

# Create your tests here.
