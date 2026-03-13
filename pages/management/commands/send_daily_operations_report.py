from django.core.management.base import BaseCommand
from django.utils import timezone

from pages.email_reports import send_daily_operations_report
from pages.scheduler import process_due_daily_operations_report


class Command(BaseCommand):
    help = 'Send the daily operations report manually or when the configured schedule is due.'

    def add_arguments(self, parser):
        parser.add_argument('--date', dest='date', help='ISO date, example 2026-03-13')
        parser.add_argument('--due-only', action='store_true', help='Send only when the daily schedule is due')

    def handle(self, *args, **options):
        day = timezone.datetime.fromisoformat(options['date']).date() if options.get('date') else timezone.localdate()

        if options['due_only']:
            state = process_due_daily_operations_report()
            if state['reason'] == 'disabled':
                self.stdout.write('Daily email report schedule is disabled.')
                return
            if state['reason'] == 'initialized':
                self.stdout.write('Daily email report schedule initialized. Waiting for next due time.')
                return
            if state['reason'] == 'not_due':
                self.stdout.write(f"Next scheduled run: {state.get('next_run')}")
                return
            if state['reason'] in {'send_failed', 'exception'}:
                self.stdout.write(self.style.ERROR(f"Daily operations report was not sent: {state.get('error', 'unknown error')}"))
                return
            if state['reason'] == 'locked':
                self.stdout.write('Daily email report scheduler is currently locked by another process.')
                return
            self.stdout.write(self.style.SUCCESS('Daily operations report sent successfully.'))
            return

        result = send_daily_operations_report(day=day, report_type='manual')
        if not result.get('sent'):
            message = result.get('error') or 'No recipients configured.'
            self.stdout.write(self.style.ERROR(f'Daily operations report was not sent: {message}'))
            return
        self.stdout.write(self.style.SUCCESS(f"Daily operations report sent to: {', '.join(result['recipients'])}"))
