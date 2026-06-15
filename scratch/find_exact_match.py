import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from decimal import Decimal
from django.db.models import Sum
from quick.models import QuickCourse, QuickEnrollment, QuickStudentReceipt
from accounts.models import Account
from quick.views import _build_quick_outstanding_course_summary

def main():
    courses = QuickCourse.objects.all()
    course_data, totals = _build_quick_outstanding_course_summary(courses, include_zero_outstanding=True)
    
    print("--- Searching for the exact course row ---")
    for row in course_data:
        c = row['course']
        # Let's print the row if it's close or matches the numbers
        # 26, 26, 0, 3900000, 5550000
        if row['total_students'] == 26 or row['total_paid'] == Decimal('3900000') or row['deferred_revenue'] == Decimal('5550000'):
            print(f"MATCH: ID: {c.id} | Name: {c.name} | Price: {c.price} | Active: {c.is_active} | Type: {c.course_type}")
            print(f"  Students: Total={row['total_students']}, Paid={row['paid_students']}, Outstanding={row['outstanding_students']}")
            print(f"  Amounts: Paid={row['total_paid']}, Deferred={row['deferred_revenue']}, Withdrawals={row['teacher_withdrawals']}, Net={row['net_remaining_after_withdrawals']}")
            print("-" * 50)

if __name__ == '__main__':
    main()
