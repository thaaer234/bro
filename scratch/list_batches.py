# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
import django
django.setup()

from academic_years.models import AcademicYearTransferBatch

batches = AcademicYearTransferBatch.objects.all()
print(f"Total batches: {batches.count()}")
for b in batches:
    print(f"ID: {b.id} | Source: {b.source_academic_year} | Target: {b.target_academic_year} | Status: {b.status}")
