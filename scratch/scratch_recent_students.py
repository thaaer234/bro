import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from students.models import Student

print("=== 20 MOST RECENTLY CREATED STUDENTS ===")
for s in Student.objects.all().order_by('-id')[:20]:
    print(f"ID={s.id} | student_id={s.student_id} | Name={s.full_name} | is_active={s.is_active} | Created={s.created_at}")
