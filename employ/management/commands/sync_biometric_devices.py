from django.core.management.base import BaseCommand

from employ.biometric_sync import BiometricAutoSyncService


class Command(BaseCommand):
    help = 'Synchronize active biometric devices and import new attendance logs.'

    def handle(self, *args, **options):
        if not BiometricAutoSyncService.is_available():
            self.stdout.write(self.style.ERROR('pyzk is not installed. Automatic biometric sync is unavailable.'))
            return

        summary = BiometricAutoSyncService.sync_active_devices()
        for result in summary['results']:
            device = result['device']
            if result.get('error'):
                self.stdout.write(
                    self.style.ERROR(
                        f"[{device.name}] error={result['error']}"
                    )
                )
                continue
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{device.name}] fetched={result['fetched']} created={result['created']} duplicates={result['duplicates']} unresolved={result['unresolved']}"
                )
            )
