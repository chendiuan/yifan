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


@require_http_methods(["GET"])
def api_export(request):
    baby = get_baby()
    records = [serialize_record(record) for record in CareRecord.objects.filter(baby=baby)]
    exported_at = timezone.localtime().strftime("%Y-%m-%dT%H:%M:%S%z")

    return JsonResponse(
        {
            "exportedAt": exported_at,
            "version": 1,
            "profile": serialize_baby(baby),
            "recordCount": len(records),
            "records": records,
        },
        json_dumps_params={"ensure_ascii": False, "indent": 2},
    )


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
    except (LineConfigurationError, LineReplyError, OSError):
        return False


def empty_parse_result(action="create_record", record_type=CareRecord.NOTE):
    return {
        "action": action,
        "record_type": record_type,
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
        "clarification": "",
    }


def parse_local_care_record_message(message):
    text = str(message).strip()
    normalized = text.lower().replace(",", "")
    action = "correct_record" if any(
        keyword in normalized for keyword in ("更正", "改成", "應該是")
    ) else "create_record"

    weight_match = re.search(
        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(kg|公斤|g|公克|克)\b",
        normalized,
    )
    if "體重" in normalized or weight_match:
        result = empty_parse_result(action, CareRecord.GROWTH)
        if weight_match:
            amount, unit = weight_match.groups()
            result["weight"] = f"{amount}{unit}"
        return result

    height_match = re.search(
        r"(?:身高|身長)\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(cm|公分)?",
        normalized,
    )
    if height_match:
        result = empty_parse_result(action, CareRecord.GROWTH)
        result["height"] = height_match.group(1)
        return result

    temperature_match = re.search(
        r"(?:體溫|燒|發燒)\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(?:°c|度|c)?",
        normalized,
    )
    if temperature_match:
        result = empty_parse_result(action, CareRecord.HEALTH)
        result["temperature"] = temperature_match.group(1)
        return result

    amount_match = re.search(
        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(ml|cc|c\.c\.|毫升)\b",
        normalized,
    )
    if amount_match and any(keyword in normalized for keyword in ("奶", "喝", "母乳", "配方")):
        result = empty_parse_result(action, CareRecord.FEEDING)
        amount, unit = amount_match.groups()
        result["feed_amount"] = f"{amount}{unit}"
        if "配方" in normalized:
            result["feed_kind"] = "配方奶"
        elif "瓶" in normalized:
            result["feed_kind"] = "瓶餵母乳"
        else:
            result["feed_kind"] = "母乳"
        return result

    if any(keyword in normalized for keyword in ("尿", "小便", "便便", "大便", "屎")):
        result = empty_parse_result(action, CareRecord.DIAPER)
        result["pee"] = any(keyword in normalized for keyword in ("尿", "小便"))
        result["poop"] = any(keyword in normalized for keyword in ("便便", "大便", "屎"))
        for amount in ("少量", "中等", "大量", "爆量"):
            if amount in text:
                result["poop_amount"] = amount
                break
        for color in ("黃色", "芥末黃", "綠色", "棕色", "黑色", "紅色", "白色"):
            if color in text:
                result["poop_color"] = color
                break
        return result

    if "睡" in normalized:
        hours_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:小時|hr|hour|h)", normalized)
        minutes_match = re.search(r"(\d+)\s*(?:分鐘|分|min|m)\b", normalized)
        minutes = 0
        if hours_match:
            minutes += int(Decimal(hours_match.group(1)) * 60)
        if minutes_match:
            minutes += int(minutes_match.group(1))
        if "半小時" in normalized:
            minutes += 30

        if minutes:
            result = empty_parse_result(action, CareRecord.SLEEP)
            result["sleep_minutes"] = minutes
            return result

    return None


def enrich_parse_result_from_message(result, message):
    enriched = dict(result)
    normalized_message = str(message).strip().lower().replace(",", "")

    if any(keyword in normalized_message for keyword in ("更正", "改成", "應該是")):
        enriched["action"] = "correct_record"

    weight_match = re.search(
        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+))\s*(kg|公斤|g|公克|克)\b",
        normalized_message,
    )
    if weight_match:
        amount, unit = weight_match.groups()
        enriched["record_type"] = CareRecord.GROWTH
        enriched["weight"] = f"{amount}{unit}"

    return enriched


def handle_line_text_event(event, parser=parse_care_record_message, replier=reply_to_line):
    message = event.get("message", {})
    if event.get("type") != "message" or message.get("type") != "text":
        return "ignored"

    reply_token = event.get("replyToken", "")
    text = message.get("text", "")

    result = parse_local_care_record_message(text)
    try:
        if result is None:
            result = parser(text)
    except OpenAIConfigurationError:
        result = parse_local_care_record_message(text)
        if result is not None:
            record = create_record_from_parse_result(result)
            safe_reply_to_line(reply_token, format_created_reply(record), replier)
            return "created"
        safe_reply_to_line(reply_token, "AI 尚未設定完成，請先設定 OPENAI_API_KEY。", replier)
        return "configuration_error"
    except OpenAIRequestError:
        result = parse_local_care_record_message(text)
        if result is not None:
            record = create_record_from_parse_result(result)
            safe_reply_to_line(reply_token, format_created_reply(record), replier)
            return "created"
        safe_reply_to_line(reply_token, "AI 目前無法使用，請檢查 OpenAI 額度或付款設定。", replier)
        return "ai_error"
    except CareRecordParseError:
        result = parse_local_care_record_message(text)
        if result is not None:
            record = create_record_from_parse_result(result)
            safe_reply_to_line(reply_token, format_created_reply(record), replier)
            return "created"
        safe_reply_to_line(reply_token, "我剛剛沒有成功解析，請再簡短說一次，例如：剛剛喝奶 90ml。", replier)
        return "parse_error"

    result = enrich_parse_result_from_message(result, text)

    if (
        result["action"] in {"create_record", "correct_record"}
        and result["record_type"] == CareRecord.GROWTH
        and not result.get("weight")
        and not result.get("height")
    ):
        safe_reply_to_line(reply_token, "請提供體重或身高，例如：寶寶今天體重3060g。", replier)
        return "clarify"

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
