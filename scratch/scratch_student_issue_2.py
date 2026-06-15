import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from classroom.models import Classroom, Classroomenrollment
from students.models import Student
from accounts.models import Studentenrollment

print("=== SEARCHING FOR NAME VARIATIONS ===")

print("\nSearching for students with 'منجد' in their name:")
students = Student.objects.filter(full_name__icontains="منجد")
for s in students:
    print(f"ID={s.id} | student_id={s.student_id} | name={s.full_name} | is_active={s.is_active}")
    course_enrolls = Studentenrollment.objects.filter(student=s)
    for ce in course_enrolls:
        print(f"   * Course: {ce.course} (ID={ce.course.id if ce.course else None})")
    class_enrolls = Classroomenrollment.objects.filter(student=s)
    for cle in class_enrolls:
        print(f"   * Classroom: {cle.classroom.name} (ID={cle.classroom.id}) | Course: {cle.classroom.course}")

print("\nSearching for students with 'عبد الكريم' or 'عبدالكريم' or 'كريم' in their name:")
students = Student.objects.filter(full_name__icontains="كريم")
for s in students:
    if "منجد" in s.full_name or "عبد" in s.full_name:
        print(f"ID={s.id} | student_id={s.student_id} | name={s.full_name} | is_active={s.is_active}")
        course_enrolls = Studentenrollment.objects.filter(student=s)
        for ce in course_enrolls:
            print(f"   * Course: {ce.course} (ID={ce.course.id if ce.course else None})")
        class_enrolls = Classroomenrollment.objects.filter(student=s)
        for cle in class_enrolls:
            print(f"   * Classroom: {cle.classroom.name} (ID={cle.classroom.id}) | Course: {cle.classroom.course}")

print("\nSearching for students with 'عجاج' in their name:")
students = Student.objects.filter(full_name__icontains="عجاج")
for s in students:
    print(f"ID={s.id} | student_id={s.student_id} | name={s.full_name} | is_active={s.is_active}")
    course_enrolls = Studentenrollment.objects.filter(student=s)
    for ce in course_enrolls:
        print(f"   * Course: {ce.course} (ID={ce.course.id if ce.course else None})")
    class_enrolls = Classroomenrollment.objects.filter(student=s)
    for cle in class_enrolls:
        print(f"   * Classroom: {cle.classroom.name} (ID={cle.classroom.id}) | Course: {cle.classroom.course}")
