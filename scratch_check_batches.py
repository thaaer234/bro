import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from academic_years.models import AcademicYearTransferBatch, AcademicYearTransferLog

print("Batches:")
for batch in AcademicYearTransferBatch.objects.all():
    print(f"Batch ID: {batch.id} | Source: {batch.source_academic_year} | Target: {batch.target_academic_year} | Status: {batch.status} | Created at: {batch.created_at}")
    print(f"Summary: {batch.summary_json}")
    print(f"Failure reason: {batch.failure_reason}")
    print("-" * 50)

print("\nLogs:")
for log in AcademicYearTransferLog.objects.all().order_by('-id')[:20]:
    print(f"Log: {log.level} | {log.message} | {log.created_at}")
