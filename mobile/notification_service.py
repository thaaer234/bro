import logging
from typing import Any, Iterable, Mapping, Optional

import requests

from .models import MobileDeviceToken

logger = logging.getLogger(__name__)


class ExpoNotificationService:
    def __init__(self) -> None:
        self.expo_api_url = "https://exp.host/--/api/v2/push/send"

    def send_notification(
        self,
        tokens: Iterable[str],
        title: str,
        body: str,
        data: Optional[Mapping[str, Any]] = None,
    ):
        tokens = [token for token in tokens if token]
        if not tokens:
            return None

        messages = [
            {
                "to": token,
                "title": title,
                "body": body,
                "data": data or {},
                "sound": "default",
                "priority": "high",
                "channelId": "alyaman-notifications",
            }
            for token in tokens
        ]

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }

        try:
            response = requests.post(
                self.expo_api_url,
                headers=headers,
                json=messages,
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            logger.info("Expo push response: %s", payload)
            return payload
        except Exception as exc:
            logger.warning("Expo notification error: %s", exc)
            return None

    def send_to_user(self, user_id: int, title: str, body: str, data=None, user_type="parent"):
        tokens = MobileDeviceToken.objects.filter(
            user_type=user_type, user_id=user_id
        ).values_list("token", flat=True)
        return self.send_notification(list(tokens), title, body, data=data)

    def send_to_all(self, title: str, body: str, data=None, user_type: Optional[str] = None):
        qs = MobileDeviceToken.objects.all()
        if user_type:
            qs = qs.filter(user_type=user_type)
        tokens = qs.values_list("token", flat=True)
        return self.send_notification(list(tokens), title, body, data=data)

    def send_breaking_news(self, title: str, body: str, url: Optional[str] = None):
        data = {"type": "breaking_news", "priority": "high", "url": url}
        return self.send_to_all(title, body, data=data)


def send_push_notification(tokens, title, body, data=None):
    """Convenience wrapper to send a push notification via Expo."""
    return ExpoNotificationService().send_notification(tokens, title, body, data=data)


def notify_all_users(title, body, data=None, user_type: Optional[str] = None):
    """Send a notification to all active devices, optionally filtered by user_type."""
    return ExpoNotificationService().send_to_all(title, body, data=data, user_type=user_type)


def notify_user(user_id, title, body, data=None, user_type="parent"):
    """Send a notification to a specific user by id and type."""
    return ExpoNotificationService().send_to_user(
        user_id=user_id,
        title=title,
        body=body,
        data=data,
        user_type=user_type,
    )
