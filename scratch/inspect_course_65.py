import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from decimal import Decimal
from django.db.models import Sum
from quick.models import QuickCourse, QuickEnrollment, QuickStudentReceipt
from accounts.models import Account, Transaction, JournalEntry

def main():
    course = QuickCourse.objects.get(pk=65)
    print(f"Course: {course.name} (ID: {course.id})")
    print(f"Price: {course.price}")
    
    # Active enrollments
    active_enrollments = QuickEnrollment.objects.filter(course=course, is_completed=False)
    print(f"\nActive Enrollments: {active_enrollments.count()}")
    for i, e in enumerate(active_enrollments, 1):
        paid = QuickStudentReceipt.objects.filter(quick_enrollment=e).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        print(f"  {i}. Student ID: {e.student.id} | Student Name: {e.student.full_name} | Net: {e.net_amount} | Paid (Receipts): {paid} | Gross: {e.gross_amount} | Discount: {e.discount_value}")

    # Completed/withdrawn enrollments
    completed_enrollments = QuickEnrollment.objects.filter(course=course, is_completed=True)
    print(f"\nCompleted/Withdrawn Enrollments: {completed_enrollments.count()}")
    for i, e in enumerate(completed_enrollments, 1):
        paid = QuickStudentReceipt.objects.filter(quick_enrollment=e).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        print(f"  {i}. Student ID: {e.student.id} | Student Name: {e.student.full_name} | Net: {e.net_amount} | Paid (Receipts): {paid} | Completion Date: {e.completion_date}")

    # All Receipts for the course
    print("\n--- Receipts for this Course ---")
    receipts = QuickStudentReceipt.objects.filter(course=course)
    print(f"Total Receipts count: {receipts.count()}")
    total_receipts_paid = receipts.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
    print(f"Total receipts paid sum: {total_receipts_paid}")
    for r in receipts:
        enrollment_status = r.quick_enrollment.is_completed if r.quick_enrollment else 'No Enrollment'
        print(f"  Receipt ID {r.id}: {r.student_name} | Amount: {r.amount} | Paid: {r.paid_amount} | Enroll Completed?: {enrollment_status}")

    # Deferred Account
    deferred_account = Account.get_or_create_quick_course_deferred_account(course)
    print(f"\nDeferred Account: {deferred_account.code}")
    print(f"Deferred Account Balance: {deferred_account.get_net_balance()}")
    
    # Transactions in Deferred Account
    print("\n--- Deferred Account Transactions ---")
    txs = Transaction.objects.filter(account=deferred_account).order_by('journal_entry__date', 'id')
    for tx in txs:
        je = tx.journal_entry
        print(f"  TX ID {tx.id}: Date: {je.date} | Ref: {je.reference} | Desc: {je.description} / {tx.description} | Debit: {tx.amount if tx.is_debit else 0} | Credit: {0 if tx.is_debit else tx.amount}")

if __name__ == '__main__':
    main()
