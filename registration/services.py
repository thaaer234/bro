import urllib.parse

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone


APPROVAL_SIGNER_SALT = 'registration.password-reset.approval'


def build_signed_reset_action_token(reset_request_id, action):
    return signing.dumps({'request_id': reset_request_id, 'action': action}, salt=APPROVAL_SIGNER_SALT)


def load_signed_reset_action_token(token, max_age=None):
    max_age = max_age or settings.PASSWORD_RESET_APPROVAL_MAX_AGE_SECONDS
    return signing.loads(token, salt=APPROVAL_SIGNER_SALT, max_age=max_age)


def build_action_url(request, reset_request, action):
    token = build_signed_reset_action_token(reset_request.id, action)
    path = reverse('registration:password_reset_email_action', args=[token])
    base_url = getattr(settings, 'PASSWORD_RESET_BASE_URL', '').strip()
    if base_url:
        return f"{base_url.rstrip('/')}{path}"
    return request.build_absolute_uri(path)


def send_reset_request_approval_email(reset_request, request):
    approval_url = build_action_url(request, reset_request, 'approve')
    reject_url = build_action_url(request, reset_request, 'reject')
    context = {
        'reset_request': reset_request,
        'approval_url': approval_url,
        'reject_url': reject_url,
        'brand_name': settings.SECURITY_BRAND_NAME,
    }
    subject = f"{settings.EMAIL_SUBJECT_PREFIX}طلب موافقة لإعادة ضبط كلمة المرور"
    text_body = render_to_string('registration/emails/password_reset_approval.txt', context)
    html_body = render_to_string('registration/emails/password_reset_approval.html', context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=settings.PASSWORD_RESET_APPROVAL_EMAILS,
    )
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)

    reset_request.approval_email_sent_at = timezone.now()
    reset_request.last_notification_error = ''
    reset_request.save(update_fields=['approval_email_sent_at', 'last_notification_error'])


def normalize_phone_number(raw_phone):
    phone = (raw_phone or '').strip()
    if not phone:
        return ''

    cleaned = ''.join(ch for ch in phone if ch.isdigit() or ch == '+')
    if cleaned.startswith('+'):
        return cleaned
    if cleaned.startswith('00'):
        return f"+{cleaned[2:]}"
    if cleaned.startswith('0'):
        return f"+{settings.WHATSAPP_DEFAULT_COUNTRY_CODE}{cleaned[1:]}"
    return f"+{cleaned}"


def build_reset_code_message(reset_request):
    expiry_text = timezone.localtime(reset_request.expires_at).strftime('%Y-%m-%d %H:%M') if reset_request.expires_at else '-'
    return (
        f"مرحباً {reset_request.user.get_full_name() or reset_request.user.username}\n"
        f"رمز إعادة ضبط كلمة المرور هو: {reset_request.code}\n"
        f"صلاحية الرمز حتى: {expiry_text}"
    )


def build_whatsapp_send_url(reset_request):
    normalized_phone = normalize_phone_number(reset_request.get_whatsapp_phone())
    if not normalized_phone:
        raise ValueError('لا يوجد رقم واتساب محفوظ لهذا المستخدم.')

    message_text = build_reset_code_message(reset_request)
    phone_digits = normalized_phone.replace('+', '')
    encoded_text = urllib.parse.quote(message_text)
    return f"https://wa.me/{phone_digits}?text={encoded_text}"
