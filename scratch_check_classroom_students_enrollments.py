import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom
from accounts.models import Studentenrollment

classrooms = Classroom.objects.filter(is_visible=True)
for c in classrooms:
    print(f"\nClassroom: {c.name} (ID: {c.id})")
    course = c.course
    if not course:
        print("  No course linked.")
        continue
    
    students = list(c.students)
    print(f"  Total students: {len(students)}")
    
    no_enrollment_count = 0
    for s in students:
        has_enrollment = Studentenrollment.objects.filter(student=s, course=course).exists()
        if not has_enrollment:
            no_enrollment_count += 1
            print(f"    - Student {s.full_name} (ID: {s.id}) has NO enrollment in course {course.name}")
            
    print(f"  Students with NO enrollment: {no_enrollment_count}")
