# -*- coding: utf-8 -*-
import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
import django
django.setup()

from academic_years.models import AcademicYearTransferBatch

def main():
    print("🔍 Checking AcademicYearTransferBatch status...")
    batches = AcademicYearTransferBatch.objects.all().order_by('-id')
    for b in batches:
        print(f"Batch ID: {b.id}")
        print(f"  Source: {b.source_academic_year}")
        print(f"  Target: {b.target_academic_year}")
        print(f"  Status: {b.status}")
        print(f"  Failure Reason: {b.failure_reason}")
        print(f"  Created By: {b.created_by}")
        print(f"  Logs count: {b.logs.count()}")
        print("  Recent Logs:")
        for log in b.logs.all().order_by('-created_at', '-id')[:10]:
            print(f"    [{log.created_at}] [{log.log_level}] {log.message}")
        print("-" * 50)

if __name__ == "__main__":
    main()
