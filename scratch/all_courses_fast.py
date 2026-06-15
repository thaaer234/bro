import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.db.models import Sum
from quick.models import QuickCourse, QuickEnrollment, QuickStudentReceipt
from accounts.models import Account

def main():
    print("Starting fast course summary...")
    courses = QuickCourse.objects.all().order_by('id')
    with open('scratch/all_courses_fast.txt', 'w', encoding='utf-8') as f:
        f.write("ID | Name | Price | Type | Active | Enrollments (Active) | Receipts Paid Sum | Deferred Balance\n")
        f.write("=" * 100 + "\n")
        for c in courses:
            active_enroll_count = QuickEnrollment.objects.filter(course=c, is_completed=False).count()
            receipts_sum = QuickStudentReceipt.objects.filter(course=c).aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
            deferred_account = Account.get_or_create_quick_course_deferred_account(c)
            deferred_balance = deferred_account.get_net_balance()
            f.write(f"{c.id} | {c.name} | {c.price} | {c.course_type} | {c.is_active} | {active_enroll_count} | {receipts_sum} | {deferred_balance}\n")
    print("Done writing file.")
    os._exit(0)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        os._exit(1)
