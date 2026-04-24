from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date

from employ.email_notifications import send_daily_biometric_summary


class Command(BaseCommand):
    help = 'Send the biometric attendance daily email summary.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            help='Summary date in YYYY-MM-DD format. Defaults to today.',
        )

    def handle(self, *args, **options):
        target_date = timezone.localdate()
        if options.get('date'):
            parsed = parse_date(options['date'])
            if not parsed:
                self.stderr.write(self.style.ERROR('Invalid --date value. Use YYYY-MM-DD.'))
                return
            target_date = parsed

        sent = send_daily_biometric_summary(target_date)
        if sent:
            self.stdout.write(self.style.SUCCESS(f'Sent biometric summary for {target_date}.'))
        else:
            self.stderr.write(self.style.ERROR(f'Biometric summary for {target_date} was not sent.'))
