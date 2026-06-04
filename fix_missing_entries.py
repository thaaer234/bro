# -*- coding: utf-8 -*-
"""
Fix missing enrollment journal entries for regular students.
This script identifies enrollments with positive net amounts but no journal entry,
and creates the entries using the same naming convention and the original registrar.
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')

import django
django.setup()

from decimal import Decimal
from accounts.models import Studentenrollment, JournalEntry, Transaction, Account
from students.models import Student
from django.contrib.auth.models import User

# ============================================
# STEP 1: Identify enrollments needing fix
# ============================================
enrollments_no_entry = Studentenrollment.objects.filter(
    is_completed=False,
    enrollment_journal_entry__isnull=True
).select_related('student', 'course', 'academic_year')

print(f"=" * 70)
print(f"Total active enrollments without journal entry: {enrollments_no_entry.count()}")
print(f"=" * 70)

needs_fix = []

for e in enrollments_no_entry:
    # Calculate net amount
    after_percent = e.total_amount - (e.total_amount * e.discount_percent / Decimal('100'))
    net = max(Decimal('0'), after_percent - e.discount_amount)
    
    student_name = getattr(e.student, 'full_name', None) or getattr(e.student, 'name', '')
    course_name = getattr(e.course, 'name', '')
    ay_name = e.academic_year.name if e.academic_year else 'N/A'
    
    # Find who originally created/registered this student
    added_by = getattr(e.student, 'added_by', None)
    added_by_name = added_by.username if added_by else 'N/A'
    
    if net > 0:
        print(f"\n*** NEEDS FIX ***")
        print(f"  Enrollment ID: {e.id}")
        print(f"  Student: {student_name}")
        print(f"  Course: {course_name}")
        print(f"  Academic Year: {ay_name}")
        print(f"  Total Amount: {e.total_amount}")
        print(f"  Discount: {e.discount_percent}% / {e.discount_amount}")
        print(f"  Net Amount: {net}")
        print(f"  Enrollment Date: {e.enrollment_date}")
        print(f"  Registered By: {added_by_name} (user_id={added_by.id if added_by else 'N/A'})")
        needs_fix.append((e, net, added_by))
    else:
        print(f"  OK (net=0): ID={e.id} | {student_name} | {course_name}")

print(f"\n{'=' * 70}")
print(f"Enrollments needing journal entry creation: {len(needs_fix)}")
print(f"{'=' * 70}")

# ============================================
# STEP 2: Create missing journal entries
# ============================================
if needs_fix:
    confirm = input("\nDo you want to create journal entries for these enrollments? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        from django.db import transaction as db_transaction
        
        for enrollment, net_amount, original_user in needs_fix:
            try:
                with db_transaction.atomic():
                    # Use the original registrar (added_by) as the creator
                    # If not available, use the first superuser
                    creator = original_user
                    if not creator:
                        creator = User.objects.filter(is_superuser=True).first()
                    
                    if not creator:
                        print(f"  ERROR: No user found to create entry for enrollment {enrollment.id}")
                        continue
                    
                    student_name = getattr(enrollment.student, 'full_name', None) or getattr(enrollment.student, 'name', '')
                    
                    print(f"\n  Creating entry for: {student_name} - {enrollment.course.name}")
                    print(f"  Net amount: {net_amount}")
                    print(f"  Creator: {creator.username}")
                    
                    # Create the enrollment journal entry using the existing method
                    entry = enrollment.create_accrual_enrollment_entry(creator)
                    
                    if entry:
                        print(f"  SUCCESS: Journal Entry #{entry.id} created and posted")
                        print(f"  Entry description: {entry.description}")
                    else:
                        print(f"  WARNING: create_accrual_enrollment_entry returned None")
                        
            except Exception as ex:
                print(f"  ERROR for enrollment {enrollment.id}: {ex}")
                import traceback
                traceback.print_exc()
        
        print(f"\n{'=' * 70}")
        print(f"DONE! All missing entries have been processed.")
        print(f"{'=' * 70}")
    else:
        print("\nCancelled. No changes were made.")
else:
    print("\nNo enrollments need fixing. All is good!")
