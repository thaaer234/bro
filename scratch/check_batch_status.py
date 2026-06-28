# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
import django
django.setup()

from academic_years.models import AcademicYearTransferBatch

try:
    batch = AcademicYearTransferBatch.objects.get(id=1)
    print(f"Batch ID: {batch.id}")
    print(f"Status: {batch.status}")
    print(f"Failure Reason: {batch.failure_reason}")
    print("\nLogs:")
    for log in batch.logs.order_by('created_at'):
        print(f" - [{log.created_at}] {log.message} (Level={log.level})")
except Exception as e:
    print(f"Error: {e}")
