import json
import urllib.error
import urllib.request

from django.conf import settings


LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


class LineConfigurationError(Exception):
    pass


class LineReplyError(Exception):
    pass


def _post_line_message(url, payload):
    if not settings.LINE_CHANNEL_ACCESS_TOKEN:
        raise LineConfigurationError("LINE_CHANNEL_ACCESS_TOKEN is not configured")

    request = urllib.request.Request(
        url,
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
        raise LineReplyError("LINE message request failed") from exc


def reply_to_line(reply_token, text):
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:5000]}],
    }
    return _post_line_message(LINE_REPLY_URL, payload)


def push_to_line(user_id, text):
    """Send a push message instead of a reply.

    LINE's replyToken is only valid for about 10 seconds, which can easily
    expire while the message is still being parsed (e.g. waiting on the
    OpenAI call). Pushing directly to the user's id has no such time limit,
    so it's used as the primary channel whenever we know the user id, with
    reply kept as a fallback for cases where we don't.
    """
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text[:5000]}],
    }
    return _post_line_message(LINE_PUSH_URL, payload)
