import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from quick.models import AcademicYear
from accounts.models import Course, Studentenrollment
from classroom.models import Classroom, Classroomenrollment

source_year = AcademicYear.objects.get(id=1) # 2025-2026
target_year = AcademicYear.objects.get(id=2) # 2026-2027

classrooms = Classroom.objects.filter(is_visible=True)
print(f"Target Year: {target_year.name} (ID: {target_year.id})")
print(f"Source Year: {source_year.name} (ID: {source_year.id})")
print(f"Visible Classrooms: {classrooms.count()}")

total_students_to_transfer = 0
for classroom in classrooms:
    print(f"\nClassroom: {classroom.name} (ID: {classroom.id})")
    source_course = classroom.course
    if not source_course:
        print("  No course linked.")
        continue
    print(f"  Course: {source_course.name} (ID: {source_course.id}) | Course Year: {source_course.academic_year}")
    
    old_students = list(classroom.students)
    print(f"  Students enrolled: {len(old_students)}")
    total_students_to_transfer += len(old_students)
    
    for i, s in enumerate(old_students[:5]):
        print(f"    - Student {i+1}: {s.full_name} | Phone: {s.phone}")
    if len(old_students) > 5:
        print(f"    - ... and {len(old_students) - 5} more")

print(f"\nTotal classroom student enrollments to process: {total_students_to_transfer}")
