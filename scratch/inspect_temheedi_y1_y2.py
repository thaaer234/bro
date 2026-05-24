import os
import sys
import django

sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from accounts.models import Course, Studentenrollment, StudentReceipt

c1 = Course.objects.get(id=24)
c2 = Course.objects.get(id=32)

e1_students = set(Studentenrollment.objects.filter(course=c1).values_list('student__full_name', flat=True))
e2_students = set(Studentenrollment.objects.filter(course=c2).values_list('student__full_name', flat=True))

print("Course: تمهيدي 2026-2027")
print(f"  Year 1 (ID: 24) student count: {len(e1_students)} | Students: {e1_students}")
print(f"  Year 2 (ID: 32) student count: {len(e2_students)} | Students: {e2_students}")

r1_count = StudentReceipt.objects.filter(enrollment__course=c1).count()
r2_count = StudentReceipt.objects.filter(enrollment__course=c2).count()
print(f"  Year 1 receipt count: {r1_count} | Year 2 receipt count: {r2_count}")
