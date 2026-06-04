import json

from django.conf import settings
from django.utils import timezone

from .models import CareRecord


class OpenAIConfigurationError(Exception):
    pass


class OpenAIRequestError(Exception):
    pass


class CareRecordParseError(Exception):
    pass


CARE_RECORD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {
            "type": "string",
            "enum": ["create_record", "clarify", "ignore"],
        },
        "record_type": {
            "type": "string",
            "enum": [
                CareRecord.FEEDING,
                CareRecord.SLEEP,
                CareRecord.DIAPER,
                CareRecord.HEALTH,
                CareRecord.GROWTH,
                CareRecord.NOTE,
            ],
        },
        "time": {"type": "string"},
        "note": {"type": "string"},
        "feed_kind": {"type": "string"},
        "feed_amount": {"type": "string"},
        "sleep_minutes": {"type": ["integer", "null"]},
        "pee": {"type": "boolean"},
        "poop": {"type": "boolean"},
        "poop_amount": {"type": "string"},
        "poop_color": {"type": "string"},
        "temperature": {"type": "string"},
        "symptom": {"type": "string"},
        "weight": {"type": "string"},
        "height": {"type": "string"},
        "clarification": {"type": "string"},
    },
    "required": [
        "action",
        "record_type",
        "time",
        "note",
        "feed_kind",
        "feed_amount",
        "sleep_minutes",
        "pee",
        "poop",
        "poop_amount",
        "poop_color",
        "temperature",
        "symptom",
        "weight",
        "height",
        "clarification",
    ],
}


PARSER_INSTRUCTIONS = """
你是寶寶照護紀錄解析器。把照顧者用中文輸入的簡短訊息，轉成寶寶紀錄 JSON。

規則：
- 只從使用者文字推論，不要編造數值。
- action 用 create_record、clarify 或 ignore。
- 可以建立紀錄時，action=create_record。
- 資訊不足但看起來想記錄寶寶照護時，action=clarify，clarification 放一個簡短追問。
- 與寶寶照護無關時，action=ignore。
- record_type 只能是 feeding、sleep、diaper、health、growth、note。
- time 用 YYYY-MM-DDTHH:MM；若使用者說「剛剛」或沒有明確時間，用目前台北時間。
- 沒有的文字欄位給空字串；沒有的數字欄位給 null；沒有提到尿/便就給 false。
- feed_amount 保留單位，例如 90ml。
- temperature、weight、height 只放數字字串，不要放單位。
""".strip()


def parse_care_record_message(message, client=None):
    if client is None:
        if not settings.OPENAI_API_KEY:
            raise OpenAIConfigurationError("OPENAI_API_KEY is not configured")

        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

    now = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
    try:
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            instructions=PARSER_INSTRUCTIONS,
            input=f"目前台北時間：{now}\n使用者訊息：{message}",
            text={
                "format": {
                    "type": "json_schema",
                    "name": "care_record_parse",
                    "schema": CARE_RECORD_SCHEMA,
                    "strict": True,
                },
            },
        )
    except Exception as exc:
        raise OpenAIRequestError("OpenAI request failed") from exc

    return normalize_parse_result(response.output_text)


def normalize_parse_result(output_text):
    try:
        data = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise CareRecordParseError("OpenAI returned invalid JSON") from exc

    required_keys = set(CARE_RECORD_SCHEMA["required"])
    if not isinstance(data, dict) or not required_keys.issubset(data):
        raise CareRecordParseError("OpenAI response did not match the parser schema")

    if data["action"] not in {"create_record", "clarify", "ignore"}:
        raise CareRecordParseError("OpenAI returned an unsupported action")

    valid_record_types = {
        CareRecord.FEEDING,
        CareRecord.SLEEP,
        CareRecord.DIAPER,
        CareRecord.HEALTH,
        CareRecord.GROWTH,
        CareRecord.NOTE,
    }
    if data["record_type"] not in valid_record_types:
        raise CareRecordParseError("OpenAI returned an unsupported record type")

    return data
