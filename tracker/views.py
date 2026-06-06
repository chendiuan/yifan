import base64
import hashlib
import hmac
import json
import re
from decimal import Decimal, InvalidOperation
from datetime import date

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .ai_parser import (
    CareRecordParseError,
    OpenAIConfigurationError,
    OpenAIRequestError,
    parse_care_record_message,
)
from .line_client import LineConfigurationError, LineReplyError, reply_to_line
from .models import Baby, CareRecord


def get_baby():
    baby, _ = Baby.objects.get_or_create(
        id=1,
        defaults={"name": "依杋", "birth_date": "2026-05-18"},
    )
    return baby


@ensure_csrf_cookie
def index(request):
    return render(request, "tracker/index.html")


def serialize_baby(baby):
    birth_date = baby.birth_date
    if isinstance(birth_date, str):
        birth_date = date.fromisoformat(birth_date)
    return {
        "name": baby.name,
        "birthDate": birth_date.isoformat(),
    }


def serialize_record(record):
    return {
        "id": record.id,
        "type": record.record_type,
        "time": timezone.localtime(record.time).strftime("%Y-%m-%dT%H:%M"),
        "note": record.note,
        "feedKind": record.feed_kind,
        "feedAmount": record.feed_amount,
        "sleepMinutes": record.sleep_minutes or 0,
        "pee": record.pee,
        "poop": record.poop,
        "poopAmount": record.poop_amount,
        "poopColor": record.poop_color,
        "temperature": str(record.temperature) if record.temperature is not None else "",
        "symptom": record.symptom,
        "weight": str(record.weight) if record.weight is not None else "",
        "height": str(record.height) if record.height is not None else "",
    }


def read_json(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None


def is_valid_line_signature(body, signature, channel_secret):
    if not signature or not channel_secret:
        return False

    digest = hmac.new(
        channel_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    expected_signature = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected_signature, signature)


@require_http_methods(["GET"])
def api_bootstrap(request):
    baby = get_baby()
    records = CareRecord.objects.filter(baby=baby)
    return JsonResponse({
        "profile": serialize_baby(baby),
        "records": [serialize_record(record) for record in records],
    })


@require_http_methods(["POST"])
def api_profile(request):
    data = read_json(request)
    if data is None:
        return HttpResponseBadRequest("Invalid JSON")

    baby = get_baby()
    baby.name = str(data.get("name", "")).strip() or "依杋"
    if data.get("birthDate"):
        baby.birth_date = date.fromisoformat(data["birthDate"])
    baby.save()
    return JsonResponse({"profile": serialize_baby(baby)})


@require_http_methods(["POST", "DELETE"])
def api_records(request):
    baby = get_baby()
    if request.method == "DELETE":
        CareRecord.objects.filter(baby=baby).delete()
        return JsonResponse({"records": []})

    data = read_json(request)
    if data is None:
        return HttpResponseBadRequest("Invalid JSON")

    record = CareRecord.objects.create(
        baby=baby,
        record_type=data.get("type", CareRecord.NOTE),
        time=parse_datetime(data.get("time")),
        note=str(data.get("note", "")).strip(),
        feed_kind=str(data.get("feedKind", "")).strip(),
        feed_amount=str(data.get("feedAmount", "")).strip(),
        sleep_minutes=parse_int(data.get("sleepMinutes")),
        pee=bool(data.get("pee")),
        poop=bool(data.get("poop")),
        poop_amount=str(data.get("poopAmount", "")).strip(),
        poop_color=str(data.get("poopColor", "")).strip(),
        temperature=parse_decimal(data.get("temperature")),
        symptom=str(data.get("symptom", "")).strip(),
        weight=parse_decimal(data.get("weight")),
        height=parse_decimal(data.get("height")),
    )
    return JsonResponse({"record": serialize_record(record)}, status=201)


@require_http_methods(["DELETE"])
def api_record_detail(request, record_id):
    record = get_object_or_404(CareRecord, id=record_id, baby=get_baby())
    record.delete()
    return JsonResponse({"deleted": record_id})


def create_record_from_parse_result(result, baby=None):
    return CareRecord.objects.create(
        baby=baby or get_baby(),
        record_type=result["record_type"],
        time=parse_datetime(result.get("time")),
        note=str(result.get("note", "")).strip(),
        feed_kind=str(result.get("feed_kind", "")).strip(),
        feed_amount=str(result.get("feed_amount", "")).strip(),
        sleep_minutes=parse_int(result.get("sleep_minutes")),
        pee=bool(result.get("pee")),
        poop=bool(result.get("poop")),
        poop_amount=str(result.get("poop_amount", "")).strip(),
        poop_color=str(result.get("poop_color", "")).strip(),
        temperature=parse_decimal(result.get("temperature")),
        symptom=str(result.get("symptom", "")).strip(),
        weight=parse_weight(result.get("weight")),
        height=parse_decimal(result.get("height")),
    )


def replace_latest_record_from_parse_result(result):
    baby = get_baby()

    with transaction.atomic():
        previous = (
            CareRecord.objects.select_for_update()
            .filter(baby=baby, record_type=result["record_type"])
            .order_by("-time", "-created_at")
            .first()
        )
        if previous is None:
            return None

        previous.delete()
        return create_record_from_parse_result(result, baby=baby)


def format_weight(weight):
    kilograms = Decimal(weight).quantize(Decimal("0.001"))
    grams = int(kilograms * 1000)
    return f"{kilograms:.3f}kg（{grams}g）"


def format_created_reply(record):
    parts = [
        f"已記錄：{record.get_record_type_display()}",
        timezone.localtime(record.time).strftime("%H:%M"),
    ]

    if record.feed_amount:
        parts.append(record.feed_amount)
    if record.sleep_minutes:
        parts.append(f"{record.sleep_minutes} 分鐘")
    if record.pee:
        parts.append("有尿")
    if record.poop:
        parts.append("有便")
    if record.temperature is not None:
        parts.append(f"{record.temperature}°C")
    if record.weight is not None:
        parts.append(format_weight(record.weight))
    if record.height is not None:
        parts.append(f"{record.height}cm")

    return " ".join(parts)


def safe_reply_to_line(reply_token, text, replier=reply_to_line):
    if not reply_token:
        return False

    try:
        return replier(reply_token, text)
    except (LineConfigurationError, LineReplyError):
        return False


def handle_line_text_event(event, parser=parse_care_record_message, replier=reply_to_line):
    message = event.get("message", {})
    if event.get("type") != "message" or message.get("type") != "text":
        return "ignored"

    reply_token = event.get("replyToken", "")
    text = message.get("text", "")

    try:
        result = parser(text)
    except OpenAIConfigurationError:
        safe_reply_to_line(reply_token, "AI 尚未設定完成，請先設定 OPENAI_API_KEY。", replier)
        return "configuration_error"
    except OpenAIRequestError:
        safe_reply_to_line(reply_token, "AI 目前無法使用，請檢查 OpenAI 額度或付款設定。", replier)
        return "ai_error"
    except CareRecordParseError:
        safe_reply_to_line(reply_token, "我剛剛沒有成功解析，請再簡短說一次，例如：剛剛喝奶 90ml。", replier)
        return "parse_error"

    if result["action"] == "clarify":
        question = result.get("clarification") or "你想記錄哪一項寶寶照護呢？"
        safe_reply_to_line(reply_token, question, replier)
        return "clarify"

    if result["action"] == "ignore":
        safe_reply_to_line(reply_token, "我目前只會幫忙記錄寶寶照護喔。", replier)
        return "ignored"

    if result["action"] == "correct_record":
        record = replace_latest_record_from_parse_result(result)
        if record is None:
            safe_reply_to_line(reply_token, "找不到可更正的同類紀錄。", replier)
            return "correction_not_found"
        safe_reply_to_line(
            reply_token,
            format_created_reply(record).replace("已記錄：", "已更正：", 1),
            replier,
        )
        return "corrected"

    record = create_record_from_parse_result(result)
    safe_reply_to_line(reply_token, format_created_reply(record), replier)
    return "created"


@csrf_exempt
@require_http_methods(["POST"])
def line_webhook(request):
    if not settings.LINE_CHANNEL_SECRET:
        return JsonResponse(
            {"error": "LINE_CHANNEL_SECRET is not configured"},
            status=503,
        )

    if not is_valid_line_signature(
        request.body,
        request.headers.get("X-Line-Signature", ""),
        settings.LINE_CHANNEL_SECRET,
    ):
        return JsonResponse({"error": "Invalid LINE signature"}, status=403)

    data = read_json(request)
    if data is None:
        return HttpResponseBadRequest("Invalid JSON")

    for event in data.get("events", []):
        handle_line_text_event(event)

    return JsonResponse({
        "ok": True,
        "events": len(data.get("events", [])),
    })


def parse_datetime(value):
    if not value:
        return timezone.now()
    parsed = timezone.datetime.fromisoformat(value)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def parse_int(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def parse_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def parse_weight(value):
    if value in (None, ""):
        return None

    text = str(value).strip().lower().replace(",", "")
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", text)
    if not match:
        return None

    try:
        weight = Decimal(match.group(0))
    except InvalidOperation:
        return None

    if text.endswith("g") and not text.endswith("kg"):
        return weight / Decimal("1000")
    if weight > 100:
        return weight / Decimal("1000")
    return weight

# Create your views here.
