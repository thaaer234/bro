import logging
from typing import Any, Mapping, Optional

import requests
from django.conf import settings

from .models import MobileUser
from mobile.models import MobileDeviceToken

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'
EXPO_ACCESS_TOKEN = getattr(settings, 'EXPO_PUSH_ACCESS_TOKEN', None)


def send_expo_push(device_token: str, title: str, body: str, data: Optional[Mapping[str, Any]] = None) -> bool:
    """Fire an Expo push notification for a single token."""
    if not device_token:
        return False

    payload: dict[str, Any] = {
        'to': device_token,
        'sound': 'default',
        'title': title,
        'body': body,
    }
    if data:
        payload['data'] = data

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if EXPO_ACCESS_TOKEN:
        headers['Authorization'] = f'Bearer {EXPO_ACCESS_TOKEN}'

    try:
        resp = requests.post(EXPO_PUSH_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning('Expo push failed for %s: %s', device_token, exc)
        return False

    logger.debug('Expo push queued for %s (%s)', device_token, title)
    return True


def _get_parent_device_tokens(student) -> set[str]:
    """Return unique Expo tokens for all mobile users linked to a student."""
    tokens = (
        MobileUser.objects.filter(student=student)
        .exclude(device_token__isnull=True)
        .exclude(device_token__exact='')
        .values_list('device_token', flat=True)
    )
    device_tokens = (
        MobileDeviceToken.objects.filter(user_type="parent", user_id=getattr(student, "id", None))
        .exclude(token__isnull=True)
        .exclude(token__exact="")
        .values_list("token", flat=True)
    )

    return {token for token in tokens if token}.union(
        {token for token in device_tokens if token}
    )


def notify_student_parents(student, title: str, body: str, data: Optional[Mapping[str, Any]] = None) -> int:
    """Send a push notification to every parent token registered for a student."""
    if not student:
        logger.debug('Skipping notification because student is missing')
        return 0

    tokens = _get_parent_device_tokens(student)
    if not tokens:
        logger.debug('No device tokens registered for student id %s', getattr(student, 'id', None))
        return 0

    sent = 0
    for token in tokens:
        if send_expo_push(token, title, body, data=data):
            sent += 1
    return sent
