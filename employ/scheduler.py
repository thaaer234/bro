import logging
import os
import sys
import threading
import time

from django.core.cache import cache

from .biometric_sync import BiometricAutoSyncService

logger = logging.getLogger(__name__)

_scheduler_lock = threading.Lock()
_scheduler_started = False


def should_start_biometric_scheduler():
    blocked_commands = {
        'check',
        'makemigrations',
        'migrate',
        'collectstatic',
        'shell',
        'dbshell',
        'createsuperuser',
        'changepassword',
        'test',
        'sync_biometric_devices',
    }
    if len(sys.argv) > 1 and sys.argv[1] in blocked_commands:
        return False
    if 'runserver' in sys.argv:
        return os.environ.get('RUN_MAIN') == 'true'
    return True


def process_due_biometric_sync():
    if not BiometricAutoSyncService.is_available():
        return {'ran': False, 'reason': 'driver_missing'}

    lock_key = 'employ-biometric-auto-sync-lock'
    if not cache.add(lock_key, '1', timeout=20):
        return {'ran': False, 'reason': 'locked'}

    try:
        result = BiometricAutoSyncService.sync_active_devices()
        if not result['results']:
            return {'ran': False, 'reason': 'no_active_devices'}
        return {'ran': True, 'reason': 'synced', 'results': result['results']}
    except Exception:
        logger.exception('Unexpected error while processing biometric auto sync.')
        return {'ran': False, 'reason': 'exception'}
    finally:
        cache.delete(lock_key)


class BiometricAutoSyncScheduler(threading.Thread):
    def __init__(self, interval_seconds=15):
        super().__init__(name='employ-biometric-auto-sync', daemon=True)
        self.interval_seconds = interval_seconds

    def run(self):
        logger.info('Biometric auto-sync scheduler thread started.')
        while True:
            process_due_biometric_sync()
            time.sleep(self.interval_seconds)


def start_biometric_scheduler():
    global _scheduler_started

    if not should_start_biometric_scheduler():
        return

    with _scheduler_lock:
        if _scheduler_started:
            return
        BiometricAutoSyncScheduler().start()
        _scheduler_started = True
