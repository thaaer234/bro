import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.db.models import Sum
from quick.models import QuickCourse, QuickEnrollment, QuickStudentReceipt
from accounts.models import Account, Transaction

def main():
    courses = QuickCourse.objects.filter(name__icontains='ملهم علي')
    with open('scratch/mulham_courses.txt', 'w', encoding='utf-8') as f:
        f.write(f"Found {courses.count()} courses matching 'ملهم علي'\n\n")
        for c in courses:
            f.write(f"ID: {c.id} | Name: {c.name} | Price: {c.price} | Type: {c.course_type}\n")
            active_count = QuickEnrollment.objects.filter(course=c, is_completed=False).count()
            total_receipts = QuickStudentReceipt.objects.filter(course=c).count()
            f.write(f"  Active enrollments: {active_count}\n")
            f.write(f"  Total receipts: {total_receipts}\n")
            
            # Deferred Account
            deferred_account = Account.get_or_create_quick_course_deferred_account(c)
            f.write(f"  Deferred Account Code: {deferred_account.code}\n")
            f.write(f"  Deferred Account Balance: {deferred_account.get_net_balance()}\n")
            
            # Receipts Sum
            receipts_sum = QuickStudentReceipt.objects.filter(course=c).aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
            f.write(f"  Receipts paid sum: {receipts_sum}\n")
            
            # Sum of active enrollments paid amount
            from quick.views import _get_quick_course_total_paid
            f.write(f"  _get_quick_course_total_paid: {_get_quick_course_total_paid(c)}\n\n")

if __name__ == '__main__':
    main()
