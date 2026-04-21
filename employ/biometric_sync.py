import logging
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from .models import BiometricDevice
from .services import BiometricImportService

logger = logging.getLogger(__name__)

try:
    from zk import ZK
    PYZK_AVAILABLE = True
except Exception:
    ZK = None
    PYZK_AVAILABLE = False


class BiometricAutoSyncService:
    DRIVER_NAME = 'pyzk'
    DEFAULT_TIMEOUT_SECONDS = 5
    OVERLAP_MINUTES = 2
    FAILURE_BACKOFF_SECONDS = 300

    @classmethod
    def is_available(cls):
        return PYZK_AVAILABLE

    @classmethod
    def _resolve_punch_type(cls, record):
        punch_code = getattr(record, 'punch', None)
        if punch_code == 0:
            return 'check_in'
        if punch_code == 1:
            return 'check_out'
        if punch_code == 2:
            return 'break_out'
        if punch_code == 3:
            return 'break_in'
        return 'unknown'

    @classmethod
    def _record_to_payload(cls, record):
        timestamp = getattr(record, 'timestamp', None)
        if not timestamp:
            return None
        if timezone.is_naive(timestamp):
            timestamp = timezone.make_aware(timestamp)

        device_user_id = str(getattr(record, 'user_id', '') or '').strip()
        if not device_user_id:
            return None

        return {
            'device_user_id': device_user_id,
            'punch_time': timestamp,
            'punch_type': cls._resolve_punch_type(record),
            'raw_data': {
                'uid': getattr(record, 'uid', 0),
                'status': getattr(record, 'status', None),
                'punch': getattr(record, 'punch', None),
            },
        }

    @classmethod
    def _fetch_device_logs(cls, device):
        if not cls.is_available():
            raise RuntimeError('مكتبة pyzk غير مثبتة، لذلك لا يمكن الاتصال التلقائي بجهاز البصمة.')

        zk = ZK(
            device.ip,
            port=device.port,
            timeout=cls.DEFAULT_TIMEOUT_SECONDS,
            ommit_ping=True,
        )
        conn = None
        try:
            conn = zk.connect()
            conn.disable_device()
            records = conn.get_attendance() or []
            return records
        finally:
            if conn:
                try:
                    conn.enable_device()
                except Exception:
                    logger.debug('Failed to re-enable biometric device %s', device.pk, exc_info=True)
                try:
                    conn.disconnect()
                except Exception:
                    logger.debug('Failed to disconnect biometric device %s', device.pk, exc_info=True)

    @classmethod
    def sync_device(cls, device):
        if isinstance(device, int):
            device = BiometricDevice.objects.get(pk=device)

        raw_records = cls._fetch_device_logs(device)
        since = None
        if device.last_synced_at:
            since = device.last_synced_at - timedelta(minutes=cls.OVERLAP_MINUTES)

        payload = []
        for record in raw_records:
            item = cls._record_to_payload(record)
            if not item:
                continue
            if since and item['punch_time'] < since:
                continue
            payload.append(item)

        result = BiometricImportService.import_logs(device, payload)
        result['device'] = device
        result['fetched'] = len(payload)
        return result

    @classmethod
    def sync_active_devices(cls):
        if not cls.is_available():
            return {'available': False, 'results': []}

        results = []
        for device in BiometricDevice.objects.filter(active=True).order_by('id'):
            failure_key = f'employ-biometric-device-failure:{device.pk}'
            if cache.get(failure_key):
                results.append({
                    'device': device,
                    'created': 0,
                    'duplicates': 0,
                    'unresolved': 0,
                    'fetched': 0,
                    'skipped': True,
                    'error': 'skipped_after_recent_failure',
                })
                continue
            try:
                result = cls.sync_device(device)
                cache.delete(failure_key)
                results.append(result)
            except Exception as exc:
                logger.exception('Automatic biometric sync failed for device %s', device.pk)
                cache.set(failure_key, '1', timeout=cls.FAILURE_BACKOFF_SECONDS)
                results.append({
                    'device': device,
                    'created': 0,
                    'duplicates': 0,
                    'unresolved': 0,
                    'fetched': 0,
                    'error': str(exc),
                })
        return {'available': True, 'results': results}
