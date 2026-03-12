from django.core.management.base import BaseCommand
from django.utils import timezone

from errors.security import send_daily_report


class Command(BaseCommand):
    help = 'Send the daily security report email.'

    def add_arguments(self, parser):
        parser.add_argument('--date', dest='date', help='ISO date, example 2026-03-12')

    def handle(self, *args, **options):
        day = timezone.datetime.fromisoformat(options['date']).date() if options.get('date') else None
        count = send_daily_report(day=day)
        self.stdout.write(self.style.SUCCESS(f'Security report sent. Incident count: {count}'))
