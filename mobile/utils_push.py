import json
import urllib.error
import urllib.request

EXPO_PUSH_ENDPOINT = "https://exp.host/--/api/v2/push/send"


def send_expo_message(token, title, body, data=None, timeout=10):
    """
    Send a single push notification via Expo Push service.

    Args:
        token: Expo push token (from MobileDeviceToken.token).
        title: Notification title.
        body: Notification body text.
        data: Optional dict payload to send in "data".
        timeout: HTTP timeout in seconds.
    Returns:
        (status_code, response_text)
    """
    payload = {
        "to": token,
        "title": title,
        "body": body,
        "data": data or {},
        "sound": "default",
        "priority": "high",
        "channelId": "alyaman-notifications",
    }

    body_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        EXPO_PUSH_ENDPOINT,
        data=body_bytes,
        headers={
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return None, str(exc)
