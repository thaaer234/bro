# -*- coding: utf-8 -*-
import os
import sys

# Setup path and environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"

import django
django.setup()

from academic_years.models import AcademicYearTransferBatch

def main():
    try:
        batch = AcademicYearTransferBatch.objects.get(id=1)
        print(f"Batch ID: {batch.id}")
        print(f"Source Year: {batch.source_academic_year}")
        print(f"Target Year: {batch.target_academic_year}")
        print(f"Batch Status: {batch.status}")
        print(f"Failure Reason: {batch.failure_reason}")
        
        # Count target enrollments
        from accounts.models import Studentenrollment
        target_enrollments = Studentenrollment.objects.filter(academic_year=batch.target_academic_year)
        print(f"Target enrollments count in DB: {target_enrollments.count()}")
        
        print("\nLast 50 Execution Logs:")
        logs = batch.logs.order_by('-created_at', '-id')[:50]
        for log in reversed(list(logs)):
            print(f"[{log.created_at}] {log.message} | Payload: {log.payload}")
            
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
