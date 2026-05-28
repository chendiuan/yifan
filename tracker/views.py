import json
from decimal import Decimal, InvalidOperation
from datetime import date

from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie

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

# Create your views here.
