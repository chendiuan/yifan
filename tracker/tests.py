import json

from django.test import Client, TestCase

from .models import CareRecord


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

# Create your tests here.
