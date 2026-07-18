import base64
import hashlib
import hmac
import importlib
import json
from decimal import Decimal, InvalidOperation

from django.apps import apps as django_apps
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .ai_parser import (
    CareRecordParseError,
    OpenAIConfigurationError,
    OpenAIRequestError,
    parse_care_record_message,
)
from .models import Baby, CareRecord
from .views import handle_line_text_event, parse_weight


def line_signature(body, channel_secret):
    digest = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


class FakeOpenAIResponse:
    def __init__(self, output_text):
        self.output_text = output_text


class FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeOpenAIResponse(self.output_text)


class FakeOpenAIClient:
    def __init__(self, output_text):
        self.responses = FakeResponses(output_text)


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

    def test_export_returns_profile_and_all_records(self):
        baby = Baby.objects.create(
            id=1,
            name="Test Baby",
            birth_date="2026-05-18",
        )
        CareRecord.objects.create(
            baby=baby,
            record_type=CareRecord.FEEDING,
            time=timezone.now(),
            feed_kind="母乳",
            feed_amount="90ml",
        )
        CareRecord.objects.create(
            baby=baby,
            record_type=CareRecord.GROWTH,
            time=timezone.now(),
            weight="3.060",
        )

        response = self.client.get("/api/export/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["profile"]["name"], "Test Baby")
        self.assertEqual(data["recordCount"], 2)
        self.assertEqual(len(data["records"]), 2)
        self.assertIn("exportedAt", data)


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


class CareRecordParserTests(TestCase):
    @override_settings(OPENAI_MODEL="gpt-5-mini")
    def test_parse_care_record_message_uses_structured_responses_api(self):
        output = json.dumps({
            "action": "create_record",
            "record_type": "feeding",
            "time": "2026-06-04T09:15",
            "note": "",
            "feed_kind": "奶瓶",
            "feed_amount": "90ml",
            "sleep_minutes": None,
            "pee": False,
            "poop": False,
            "poop_amount": "",
            "poop_color": "",
            "temperature": "",
            "symptom": "",
            "weight": "",
            "height": "",
            "clarification": "",
        })
        client = FakeOpenAIClient(output)

        result = parse_care_record_message("剛剛喝奶 90ml", client=client)

        self.assertEqual(result["action"], "create_record")
        self.assertEqual(result["record_type"], "feeding")
        self.assertEqual(result["feed_amount"], "90ml")
        self.assertEqual(client.responses.last_kwargs["model"], "gpt-5-mini")
        self.assertEqual(
            client.responses.last_kwargs["text"]["format"]["type"],
            "json_schema",
        )
        self.assertTrue(client.responses.last_kwargs["text"]["format"]["strict"])

    def test_parse_care_record_message_rejects_invalid_json(self):
        client = FakeOpenAIClient("not json")

        with self.assertRaises(CareRecordParseError):
            parse_care_record_message("剛剛喝奶 90ml", client=client)


class LineTextEventHandlerTests(TestCase):
    def test_creates_record_and_replies_when_parser_returns_create_record(self):
        replies = []

        def parser(message):
            return {
                "action": "create_record",
                "record_type": "feeding",
                "time": "2026-06-04T09:15",
                "note": "",
                "feed_kind": "奶瓶",
                "feed_amount": "90ml",
                "sleep_minutes": None,
                "pee": False,
                "poop": False,
                "poop_amount": "",
                "poop_color": "",
                "temperature": "",
                "symptom": "",
                "weight": "",
                "height": "",
                "clarification": "",
            }

        def replier(reply_token, text):
            replies.append((reply_token, text))
            return True

        event = {
            "type": "message",
            "replyToken": "reply-token",
            "message": {"type": "text", "text": "寶寶今天狀態普通"},
        }

        status = handle_line_text_event(event, parser=parser, replier=replier)

        self.assertEqual(status, "created")
        self.assertEqual(CareRecord.objects.count(), 1)
        record = CareRecord.objects.get()
        self.assertEqual(record.record_type, "feeding")
        self.assertEqual(record.feed_amount, "90ml")
        self.assertEqual(replies[0][0], "reply-token")
        self.assertIn("已記錄", replies[0][1])
        self.assertIn("90ml", replies[0][1])

    def test_replies_with_clarification_without_creating_record(self):
        replies = []

        def parser(message):
            return {
                "action": "clarify",
                "record_type": "note",
                "time": "",
                "note": "",
                "feed_kind": "",
                "feed_amount": "",
                "sleep_minutes": None,
                "pee": False,
                "poop": False,
                "poop_amount": "",
                "poop_color": "",
                "temperature": "",
                "symptom": "",
                "weight": "",
                "height": "",
                "clarification": "請問睡覺是從幾點到幾點？",
            }

        def replier(reply_token, text):
            replies.append((reply_token, text))
            return True

        event = {
            "type": "message",
            "replyToken": "reply-token",
            "message": {"type": "text", "text": "寶寶睡了"},
        }

        status = handle_line_text_event(event, parser=parser, replier=replier)

        self.assertEqual(status, "clarify")
        self.assertEqual(CareRecord.objects.count(), 0)
        self.assertEqual(replies, [("reply-token", "請問睡覺是從幾點到幾點？")])

    def test_replies_when_openai_is_not_configured(self):
        replies = []

        def parser(message):
            raise OpenAIConfigurationError("missing key")

        def replier(reply_token, text):
            replies.append((reply_token, text))
            return True

        event = {
            "type": "message",
            "replyToken": "reply-token",
            "message": {"type": "text", "text": "寶寶今天狀態普通"},
        }

        status = handle_line_text_event(event, parser=parser, replier=replier)

        self.assertEqual(status, "configuration_error")
        self.assertEqual(CareRecord.objects.count(), 0)
        self.assertIn("OPENAI_API_KEY", replies[0][1])

    def test_replies_when_openai_request_fails(self):
        replies = []

        def parser(message):
            raise OpenAIRequestError("quota exceeded")

        def replier(reply_token, text):
            replies.append((reply_token, text))
            return True

        event = {
            "type": "message",
            "replyToken": "reply-token",
            "message": {"type": "text", "text": "寶寶今天狀態普通"},
        }

        status = handle_line_text_event(event, parser=parser, replier=replier)

        self.assertEqual(status, "ai_error")
        self.assertEqual(CareRecord.objects.count(), 0)
        self.assertIn("OpenAI", replies[0][1])

    def test_local_parser_records_feeding_when_openai_request_fails(self):
        replies = []

        def parser(message):
            raise OpenAIRequestError("temporary failure")

        status = handle_line_text_event(
            {
                "type": "message",
                "replyToken": "reply-token",
                "message": {"type": "text", "text": "剛剛喝奶 90ml"},
            },
            parser=parser,
            replier=lambda reply_token, text: replies.append(text) or True,
        )

        self.assertEqual(status, "created")
        record = CareRecord.objects.get()
        self.assertEqual(record.record_type, CareRecord.FEEDING)
        self.assertEqual(record.feed_amount, "90ml")
        self.assertIn("已記錄", replies[0])

    def test_local_parser_records_diaper_without_openai(self):
        status = handle_line_text_event(
            {
                "type": "message",
                "replyToken": "reply-token",
                "message": {"type": "text", "text": "尿尿便便黃色中等"},
            },
            parser=lambda message: (_ for _ in ()).throw(OpenAIRequestError("fail")),
            replier=lambda reply_token, text: True,
        )

        self.assertEqual(status, "created")
        record = CareRecord.objects.get()
        self.assertTrue(record.pee)
        self.assertTrue(record.poop)
        self.assertEqual(record.poop_amount, "中等")
        self.assertEqual(record.poop_color, "黃色")

    def test_local_parser_records_sleep_duration_without_openai(self):
        status = handle_line_text_event(
            {
                "type": "message",
                "replyToken": "reply-token",
                "message": {"type": "text", "text": "睡了2小時30分"},
            },
            parser=lambda message: (_ for _ in ()).throw(OpenAIRequestError("fail")),
            replier=lambda reply_token, text: True,
        )

        self.assertEqual(status, "created")
        record = CareRecord.objects.get()
        self.assertEqual(record.record_type, CareRecord.SLEEP)
        self.assertEqual(record.sleep_minutes, 150)

    def test_correction_replaces_latest_record_of_same_type(self):
        baby = Baby.objects.create(
            id=1,
            name="Test Baby",
            birth_date="2026-05-18",
        )
        previous = CareRecord.objects.create(
            baby=baby,
            record_type=CareRecord.GROWTH,
            time=timezone.now(),
            weight="3.069",
        )
        replies = []

        def parser(message):
            return {
                "action": "correct_record",
                "record_type": "growth",
                "time": "2026-06-06T08:40",
                "note": "",
                "feed_kind": "",
                "feed_amount": "",
                "sleep_minutes": None,
                "pee": False,
                "poop": False,
                "poop_amount": "",
                "poop_color": "",
                "temperature": "",
                "symptom": "",
                "weight": "3060",
                "height": "",
                "clarification": "",
            }

        def replier(reply_token, text):
            replies.append((reply_token, text))
            return True

        event = {
            "type": "message",
            "replyToken": "reply-token",
            "message": {"type": "text", "text": "更正3060g"},
        }

        status = handle_line_text_event(event, parser=parser, replier=replier)

        self.assertEqual(status, "corrected")
        self.assertEqual(CareRecord.objects.count(), 1)
        self.assertFalse(CareRecord.objects.filter(id=previous.id).exists())
        corrected = CareRecord.objects.get()
        self.assertEqual(str(corrected.weight), "3.060")
        self.assertIn("已更正", replies[0][1])
        self.assertIn("3060g", replies[0][1])

    def test_weight_parser_converts_grams_to_kilograms(self):
        self.assertEqual(parse_weight("3069g"), Decimal("3.069"))
        self.assertEqual(parse_weight("3060"), Decimal("3.06"))
        self.assertEqual(parse_weight("3.2kg"), Decimal("3.2"))

    def test_message_weight_is_used_when_ai_result_omits_weight(self):
        baby = Baby.objects.create(
            id=1,
            name="Test Baby",
            birth_date="2026-05-18",
        )

        def parser(message):
            return {
                "action": "create_record",
                "record_type": "growth",
                "time": "2026-06-06T08:39",
                "note": "",
                "feed_kind": "",
                "feed_amount": "",
                "sleep_minutes": None,
                "pee": False,
                "poop": False,
                "poop_amount": "",
                "poop_color": "",
                "temperature": "",
                "symptom": "",
                "weight": "",
                "height": "",
                "clarification": "",
            }

        event = {
            "type": "message",
            "replyToken": "reply-token",
            "message": {"type": "text", "text": "寶寶今天體重3069g"},
        }

        status = handle_line_text_event(
            event,
            parser=parser,
            replier=lambda reply_token, text: True,
        )

        self.assertEqual(status, "created")
        self.assertEqual(str(CareRecord.objects.get(baby=baby).weight), "3.069")

    def test_empty_growth_result_requests_clarification(self):
        replies = []

        def parser(message):
            return {
                "action": "create_record",
                "record_type": "growth",
                "time": "2026-06-06T08:39",
                "note": "",
                "feed_kind": "",
                "feed_amount": "",
                "sleep_minutes": None,
                "pee": False,
                "poop": False,
                "poop_amount": "",
                "poop_color": "",
                "temperature": "",
                "symptom": "",
                "weight": "",
                "height": "",
                "clarification": "",
            }

        status = handle_line_text_event(
            {
                "type": "message",
                "replyToken": "reply-token",
                "message": {"type": "text", "text": "記錄寶寶成長"},
            },
            parser=parser,
            replier=lambda reply_token, text: replies.append(text) or True,
        )

        self.assertEqual(status, "clarify")
        self.assertEqual(CareRecord.objects.count(), 0)
        self.assertIn("體重或身高", replies[0])


class DecimalDataRepairTests(TransactionTestCase):
    def test_repairs_decimal_values_that_include_units(self):
        baby = Baby.objects.create(name="Test Baby", birth_date="2026-05-18")
        record = CareRecord.objects.create(
            baby=baby,
            record_type=CareRecord.GROWTH,
            time=timezone.now(),
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE tracker_carerecord SET weight = %s WHERE id = %s",
                ["4.2kg", record.id],
            )

        with self.assertRaises((InvalidOperation, TypeError)):
            CareRecord.objects.get(id=record.id)

        repair_migration = importlib.import_module(
            "tracker.migrations.0002_repair_invalid_decimal_values"
        )

        class SchemaEditorStub:
            quote_name = connection.ops.quote_name

            def __init__(self):
                self.connection = connection

        repair_migration.repair_invalid_decimal_values(
            apps=None,
            schema_editor=SchemaEditorStub(),
        )

        repaired = CareRecord.objects.get(id=record.id)
        self.assertEqual(str(repaired.weight), "4.200")

    def test_removes_growth_records_without_measurements(self):
        baby = Baby.objects.create(name="Test Baby", birth_date="2026-05-18")
        empty_record = CareRecord.objects.create(
            baby=baby,
            record_type=CareRecord.GROWTH,
            time=timezone.now(),
        )
        valid_record = CareRecord.objects.create(
            baby=baby,
            record_type=CareRecord.GROWTH,
            time=timezone.now(),
            weight="3.060",
        )
        cleanup_migration = importlib.import_module(
            "tracker.migrations.0004_remove_empty_growth_records"
        )
        cleanup_migration.remove_empty_growth_records(
            apps=django_apps,
            schema_editor=None,
        )

        self.assertFalse(CareRecord.objects.filter(id=empty_record.id).exists())
        self.assertTrue(CareRecord.objects.filter(id=valid_record.id).exists())

# Create your tests here.
