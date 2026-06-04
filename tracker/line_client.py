import json
import urllib.error
import urllib.request

from django.conf import settings


LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"


class LineConfigurationError(Exception):
    pass


class LineReplyError(Exception):
    pass


def reply_to_line(reply_token, text):
    if not settings.LINE_CHANNEL_ACCESS_TOKEN:
        raise LineConfigurationError("LINE_CHANNEL_ACCESS_TOKEN is not configured")

    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:5000]}],
    }
    request = urllib.request.Request(
        LINE_REPLY_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except urllib.error.URLError as exc:
        raise LineReplyError("LINE reply request failed") from exc
