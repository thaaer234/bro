# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
import django
django.setup()

from django.db import connections
connections['default'].cursor().execute("PRAGMA busy_timeout = 30000;")

from accounts.models import Course, Studentenrollment, JournalEntry, Transaction, Account
from students.models import Student
from django.db.models import Sum
from decimal import Decimal

student = Student.objects.get(id=1531)
print(f"Student: {student.full_name}")

enrollments = Studentenrollment.objects.filter(student=student)
print(f"Enrollments count: {enrollments.count()}")

for e in enrollments:
    print(f"\nEnrollment ID: {e.id}")
    print(f"Course: {e.course.name} (Price: {e.course.price})")
    print(f"Enrollment total: {e.total_amount}, discount percent: {e.discount_percent}, discount amount: {e.discount_amount}")
    computed_net = max(Decimal('0'), e.total_amount - (e.total_amount * e.discount_percent / Decimal('100')) - e.discount_amount)
    print(f"Computed net: {computed_net}")
    print(f"Enrollment Journal Entry: {e.enrollment_journal_entry}")
    
    ar_account = Account.get_student_ar_account_for_course(student, e.course)
    print(f"AR Account: {ar_account}")
    if ar_account:
        print(f"  Account Debit: {ar_account.get_debit_balance()}")
        print(f"  Account Credit: {ar_account.get_credit_balance()}")
        
        txs = Transaction.objects.filter(account=ar_account)
        print("  Transactions:")
        for tx in txs:
            print(f"    - TX ID: {tx.id}, JE ID: {tx.journal_entry.id}, JE Type: {tx.journal_entry.entry_type}, Reference: {tx.journal_entry.reference}, Description: {tx.journal_entry.description}, Amount: {tx.amount}, Is Debit: {tx.is_debit}")

        # Let's see the adjustment entries in the view query:
        adjustments = JournalEntry.objects.filter(
            entry_type='ADJUSTMENT',
            description__contains=student.full_name
        ).filter(description__contains=e.course.name)
        print("  Matching ADJUSTMENTS to delete in code:")
        for adj in adjustments:
            print(f"    - ADJ ID: {adj.id}, Reference: {adj.reference}, Description: {adj.description}, Amount: {adj.total_amount}")
