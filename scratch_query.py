# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
import django
django.setup()

from django.db import connections
connections['default'].cursor().execute("PRAGMA busy_timeout = 30000;")

from quick.models import QuickCourse, QuickEnrollment
from accounts.models import JournalEntry, Transaction
from django.db.models import Sum
from decimal import Decimal

quick_courses = QuickCourse.objects.all()

total_missing = 0
total_mismatch = 0
mismatched_courses = {}

for qc in quick_courses:
    enrollments = QuickEnrollment.objects.filter(course=qc)
    course_errors = 0
    
    for e in enrollments:
        computed_net = e.calculated_net_amount
        enrollment_entry = e.enrollment_journal_entry
        discount_entry = JournalEntry.objects.filter(
            entry_type='ADJUSTMENT',
            description__icontains=f'[QUICK_DISCOUNT #{e.id}]'
        ).first()
        
        gross_ledger = enrollment_entry.total_amount if enrollment_entry else Decimal('0')
        discount_ledger = discount_entry.total_amount if discount_entry else Decimal('0')
        actual_net_debit = gross_ledger - discount_ledger
        
        if computed_net > 0 and not enrollment_entry:
            total_missing += 1
            course_errors += 1
        elif abs(actual_net_debit - computed_net) > Decimal('0.01'):
            total_mismatch += 1
            course_errors += 1
            
    if course_errors > 0:
        mismatched_courses[qc.name] = course_errors

print(f"=== GLOBAL AUDIT SUMMARY FOR ALL QUICK COURSES ===")
print(f"Total Quick Courses with errors: {len(mismatched_courses)} out of {quick_courses.count()}")
print(f"Total Missing Enrollment Entries: {total_missing}")
print(f"Total Balance Mismatches: {total_mismatch}")
print("\nCourses and their error counts:")
for cname, err_count in mismatched_courses.items():
    print(f" - {cname}: {err_count} errors")
