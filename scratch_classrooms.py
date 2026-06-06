import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom
from quick.models import AcademicYear

print("=== ALL CLASSROOMS ===")
for c in Classroom.objects.all()[:20]:
    student_count = c.enrollments.count()
    print(f"ID: {c.id} | Name: {c.name} | Type: {c.class_type} | Is Active: {c.is_active} | Students: {student_count}")
