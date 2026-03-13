import logging
from .scheduler import process_due_daily_operations_report

logger = logging.getLogger(__name__)


class DailyOperationsReportSchedulerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._run_due_schedule()
        return self.get_response(request)

    def _run_due_schedule(self):
        state = process_due_daily_operations_report()
        if state.get('reason') == 'send_failed':
            logger.error('Daily operations report middleware fallback failed: %s', state.get('error', ''))
