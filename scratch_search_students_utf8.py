import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from students.models import Student

print("=== SEARCHING FOR STUDENTS ===")
for s in Student.objects.filter(id__in=[501, 794, 1794]):
    print(f"Student: ID={s.id} | student_id={s.student_id} | name={s.full_name}")

print("\n=== ALL STUDENTS CONTAINING 'غوراني' ===")
for s in Student.objects.filter(full_name__icontains="غوراني"):
    print(f"Student: ID={s.id} | student_id={s.student_id} | name={s.full_name}")
