# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
import django
django.setup()

from accounts.models import Course, Studentenrollment, StudentReceipt, JournalEntry

course_ids = [18, 19, 20, 21, 22, 23]
courses = Course.objects.filter(id__in=course_ids)
print(f"Courses count: {courses.count()}")

enrollments = Studentenrollment.objects.filter(course__in=courses)
print(f"Enrollments count: {enrollments.count()}")

receipts = StudentReceipt.objects.filter(enrollment__in=enrollments)
print(f"Receipts count: {receipts.count()}")

je_count = JournalEntry.objects.filter(enrollments__in=enrollments).distinct().count()
print(f"Journal Entries count: {je_count}")
