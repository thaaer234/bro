from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Send a real SMTP test email using the current Django email settings.'

    def add_arguments(self, parser):
        parser.add_argument('--to', dest='to_email', help='Recipient email address')

    def handle(self, *args, **options):
        recipient = options.get('to_email') or (settings.SECURITY_ALERT_EMAILS[0] if settings.SECURITY_ALERT_EMAILS else None)
        if not recipient:
            raise CommandError('No recipient email was provided and SECURITY_ALERT_EMAILS is empty.')

        self.stdout.write('Opening SMTP connection...')
        connection = get_connection(fail_silently=False)
        connection.open()

        subject = f"{settings.EMAIL_SUBJECT_PREFIX}SMTP test message"
        body = (
            'This is a real SMTP test from the Django security system.\n\n'
            f'Backend: {settings.EMAIL_BACKEND}\n'
            f'Host: {settings.EMAIL_HOST}\n'
            f'Port: {settings.EMAIL_PORT}\n'
            f'TLS: {settings.EMAIL_USE_TLS}\n'
            f'SSL: {settings.EMAIL_USE_SSL}\n'
            f'From: {settings.DEFAULT_FROM_EMAIL}\n'
            f'To: {recipient}\n'
        )
        html = f"""
        <html><body style='font-family:Segoe UI,Tahoma,sans-serif'>
        <h2>SMTP test message</h2>
        <p>This is a real SMTP test from the Django security system.</p>
        <ul>
          <li><strong>Backend:</strong> {settings.EMAIL_BACKEND}</li>
          <li><strong>Host:</strong> {settings.EMAIL_HOST}</li>
          <li><strong>Port:</strong> {settings.EMAIL_PORT}</li>
          <li><strong>TLS:</strong> {settings.EMAIL_USE_TLS}</li>
          <li><strong>SSL:</strong> {settings.EMAIL_USE_SSL}</li>
          <li><strong>From:</strong> {settings.DEFAULT_FROM_EMAIL}</li>
          <li><strong>To:</strong> {recipient}</li>
        </ul>
        </body></html>
        """

        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
            connection=connection,
        )
        email.attach_alternative(html, 'text/html')
        email.send(fail_silently=False)
        connection.close()

        self.stdout.write(self.style.SUCCESS(f'Test email sent successfully to {recipient}'))
