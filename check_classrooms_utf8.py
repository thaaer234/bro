import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom

with open("classrooms_debug.txt", "w", encoding="utf-8") as f:
    f.write("=== ALL CLASSROOMS ===\n")
    for c in Classroom.objects.all():
        course_name = c.course.name if c.course else "No Course"
        student_count = c.enrollments.count()
        f.write(f"ID: {c.id} | Name: {c.name} | Branch: {c.branches} | Class Type: {c.class_type} | Is Active: {c.is_active} | Course: {course_name} | Students: {student_count}\n")
print("Done writing classrooms_debug.txt")
