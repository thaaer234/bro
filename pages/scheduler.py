import logging
import os
import sys
import threading
import time
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from .email_reports import send_daily_operations_report
from .models import DailyEmailReportSchedule

logger = logging.getLogger(__name__)

_scheduler_lock = threading.Lock()
_scheduler_started = False


def should_start_background_scheduler():
    blocked_commands = {
        'makemigrations',
        'migrate',
        'collectstatic',
        'shell',
        'dbshell',
        'createsuperuser',
        'changepassword',
        'test',
    }
    if len(sys.argv) > 1 and sys.argv[1] in blocked_commands:
        return False
    if 'runserver' in sys.argv:
        return os.environ.get('RUN_MAIN') == 'true'
    return True


def process_due_daily_operations_report(now=None):
    lock_key = 'daily-operations-report-schedule-lock'
    if not cache.add(lock_key, '1', timeout=180):
        return {'ran': False, 'reason': 'locked'}

    try:
        schedule = DailyEmailReportSchedule.get_solo()
        if not schedule.is_enabled:
            return {'ran': False, 'reason': 'disabled'}

        current_time = now or timezone.now()
        if not schedule.next_run:
            schedule.next_run = schedule.compute_next_run(current_time)
            schedule.save(update_fields=['next_run'])
            return {'ran': False, 'reason': 'initialized'}

        if schedule.next_run > current_time:
            return {'ran': False, 'reason': 'not_due', 'next_run': schedule.next_run}

        report_day = timezone.localtime(current_time).date()
        result = send_daily_operations_report(
            day=report_day,
            recipients=schedule.get_recipient_list() or None,
            report_type='scheduled',
        )
        if not result.get('sent'):
            schedule.next_run = current_time + timedelta(minutes=10)
            schedule.save(update_fields=['next_run'])
            logger.error(
                'Daily operations report schedule failed. error=%s recipients=%s',
                result.get('error', ''),
                result.get('recipients', []),
            )
            return {'ran': False, 'reason': 'send_failed', 'error': result.get('error', '')}

        schedule.last_run = current_time
        schedule.next_run = schedule.compute_next_run(current_time + timedelta(seconds=1))
        schedule.save(update_fields=['last_run', 'next_run'])
        logger.info(
            'Daily operations report sent automatically to %s',
            ', '.join(result.get('recipients', [])),
        )
        return {'ran': True, 'reason': 'sent', 'next_run': schedule.next_run}
    except Exception:
        logger.exception('Unexpected error while processing daily operations report schedule.')
        return {'ran': False, 'reason': 'exception'}
    finally:
        cache.delete(lock_key)


class DailyOperationsReportScheduler(threading.Thread):
    def __init__(self, interval_seconds=30):
        super().__init__(name='daily-operations-report-scheduler', daemon=True)
        self.interval_seconds = interval_seconds

    def run(self):
        logger.info('Daily operations report scheduler thread started.')
        while True:
            process_due_daily_operations_report()
            time.sleep(self.interval_seconds)


def start_background_scheduler():
    global _scheduler_started

    if not should_start_background_scheduler():
        return

    with _scheduler_lock:
        if _scheduler_started:
            return
        DailyOperationsReportScheduler().start()
        _scheduler_started = True
