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
from decimal import Decimal
from django.db import transaction as db_transaction

student = Student.objects.get(id=1531)
enrollment = Studentenrollment.objects.get(student=student)
course = enrollment.course

print(f"fixing student: {student.full_name}")

with db_transaction.atomic():
    # 1. auto link original JE
    ar_account = Account.get_student_ar_account_for_course(student, course)
    
    # Get all enrollment entries on this account
    enrollment_jes = JournalEntry.objects.filter(
        entry_type='enrollment',
        transactions__account=ar_account,
        transactions__is_debit=True
    ).distinct().order_by('id')
    
    print(f"Found enrollment JEs count: {enrollment_jes.count()}")
    for je in enrollment_jes:
        print(f"  - JE ID: {je.id}, total_amount: {je.total_amount}")
        
    if enrollment_jes.exists():
        # Main is the first/oldest one
        main_je = enrollment_jes[0]
        enrollment.enrollment_journal_entry = main_je
        enrollment.save(update_fields=['enrollment_journal_entry'])
        print(f"Linked enrollment to main JE ID: {main_je.id}")
        
        # Delete duplicates (the ones created by previous attempts)
        for duplicate_je in enrollment_jes[1:]:
            print(f"Deleting duplicate JE ID: {duplicate_je.id}")
            duplicate_je._skip_linked_cleanup = True
            duplicate_je.transactions.all().delete()
            duplicate_je.delete()

    # 2. Re-audit mismatch logic:
    # computed net should be 10,000,000
    computed_net = max(Decimal('0'), enrollment.total_amount - (enrollment.total_amount * enrollment.discount_percent / Decimal('100')) - enrollment.discount_amount)
    print(f"Computed net should be: {computed_net}")
    
    # Delete old adjustments
    adjustments = JournalEntry.objects.filter(
        entry_type='ADJUSTMENT',
        description__contains=student.full_name
    ).filter(description__contains=course.name)
    if enrollment.enrollment_journal_entry:
        adjustments = adjustments.exclude(id=enrollment.enrollment_journal_entry.id)
        
    print(f"Deleting adjustments count: {adjustments.count()}")
    for adj in adjustments:
        print(f"  - Deleting adjustment ID: {adj.id}")
        adj._skip_linked_cleanup = True
        adj.transactions.all().delete()
        adj.delete()
        
    # Update main JE to computed_net (since there is no adjustment entry, the net debit is exactly the main JE amount)
    je = enrollment.enrollment_journal_entry
    if je:
        je.total_amount = computed_net
        je.save(update_fields=['total_amount'])
        
        debit_trans = je.transactions.filter(is_debit=True).first()
        credit_trans = je.transactions.filter(is_debit=False).first()
        if debit_trans:
            debit_trans.amount = computed_net
            debit_trans.save(update_fields=['amount'])
        if credit_trans:
            credit_trans.amount = computed_net
            credit_trans.save(update_fields=['amount'])
        print("Updated main JE to correct net amount.")
        
    # Recalculate balances bottom-up to parent
    curr = ar_account
    while curr:
        old_val = curr.balance
        curr.balance = curr.get_net_balance()
        curr.save(update_fields=['balance'])
        print(f"Recalculated Account {curr.code} ({curr.name_ar or curr.name}): {old_val} -> {curr.balance}")
        curr = curr.parent
        
print("Successfully fixed Areej Al-Houri's ledger accounts!")
