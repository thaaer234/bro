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
    
    with open('scratch/all_courses_summary.txt', 'w', encoding='utf-8') as f:
        f.write("All Courses Summary:\n\n")
        for row in course_data:
            c = row['course']
            f.write(f"ID: {c.id} | Name: {c.name} | Price: {c.price} | Type: {c.course_type}\n")
            f.write(f"  Students: Total={row['total_students']}, Paid={row['paid_students']}, Outstanding={row['outstanding_students']}\n")
            f.write(f"  Amounts: Paid={row['total_paid']}, Deferred={row['deferred_revenue']}, Withdrawals={row['teacher_withdrawals']}, Net={row['net_remaining_after_withdrawals']}\n")
            f.write("-" * 50 + "\n")

if __name__ == '__main__':
    main()
