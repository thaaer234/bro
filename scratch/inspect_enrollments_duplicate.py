import os
import sys
import django

sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from accounts.models import Course, Studentenrollment

print("Total student enrollments:", Studentenrollment.objects.count())
print("Enrollments for Course 18 (Year 1):", Studentenrollment.objects.filter(course_id=18).count())
print("Enrollments for Course 30 (Year 2):", Studentenrollment.objects.filter(course_id=30).count())

# Let's inspect some enrollments
for e in Studentenrollment.objects.filter(course_id=18)[:3]:
    print(f"Course 18 Enrollment - ID: {e.id} | Student: {e.student.full_name} | Amount: {e.total_amount}")
for e in Studentenrollment.objects.filter(course_id=30)[:3]:
    print(f"Course 30 Enrollment - ID: {e.id} | Student: {e.student.full_name} | Amount: {e.total_amount}")
