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

classroom_id = 25
print(f"=== Classroom {classroom_id} Info ===")
try:
    classroom = Classroom.objects.get(id=classroom_id)
    print(f"Classroom Name: {classroom.name}")
    print(f"Class Type: {classroom.class_type}")
    print(f"Branches: {classroom.branches}")
    print(f"Associated Course: {classroom.course}")
except Classroom.DoesNotExist:
    print("Classroom not found!")
    sys.exit(1)

print("\n=== Searching for students by name ===")
names_to_search = ["لانا عجاج", "عبد الكريم المنجد"]
for name in names_to_search:
    print(f"\nSearching for '{name}':")
    students = Student.objects.filter(full_name__icontains=name)
    if not students.exists():
        print("Not found.")
    for s in students:
        print(f"Student: ID={s.id} | student_id={s.student_id} | name={s.full_name} | is_active={s.is_active}")
        
        # Check general course enrollments
        course_enrolls = Studentenrollment.objects.filter(student=s)
        print("  - Course enrollments:")
        for ce in course_enrolls:
            print(f"    * Course: {ce.course} (ID={ce.course.id if ce.course else None})")
            
        # Check classroom enrollments
        class_enrolls = Classroomenrollment.objects.filter(student=s)
        print("  - Classroom enrollments:")
        for cle in class_enrolls:
            print(f"    * Classroom: {cle.classroom.name} (ID={cle.classroom.id}) | Course: {cle.classroom.course}")

# Now let's print how available_students query is computed in views.py
print("\n=== View Logic breakdown for Classroom 25 ===")
base_students = Student.objects.filter(is_active=True)
print(f"Total active students: {base_students.count()}")

if classroom.course:
    course_student_ids = Studentenrollment.objects.filter(
        course=classroom.course
    ).values_list('student__id', flat=True)
    print(f"Total students enrolled in course '{classroom.course}': {len(course_student_ids)}")
    
    assigned_student_ids = Classroomenrollment.objects.filter(
        classroom__course=classroom.course
    ).values_list('student__id', flat=True)
    print(f"Total students already assigned to classrooms for this course: {len(assigned_student_ids)}")
    
    available_students = Student.objects.filter(
        id__in=course_student_ids
    ).exclude(
        id__in=assigned_student_ids
    ).distinct()
    print(f"Available students according to logic: {available_students.count()}")
    
    # Are our specific students in course_student_ids or assigned_student_ids?
    for name in names_to_search:
        students = Student.objects.filter(full_name__icontains=name)
        for s in students:
            in_course = s.id in course_student_ids
            is_assigned = s.id in assigned_student_ids
            print(f"Student {s.full_name}: in_course={in_course}, is_assigned={is_assigned}")
else:
    if classroom.class_type == 'study':
        enrolled_in_study = Classroomenrollment.objects.filter(
            classroom__class_type='study',
            classroom__course__isnull=True
        ).values_list('student__id', flat=True)
        available_students = base_students.exclude(
            id__in=enrolled_in_study
        ).distinct()
        print(f"Available students (study): {available_students.count()}")
        
        for name in names_to_search:
            students = Student.objects.filter(full_name__icontains=name)
            for s in students:
                is_active = s.is_active
                in_study_enroll = s.id in enrolled_in_study
                print(f"Student {s.full_name}: is_active={is_active}, in_study_enroll={in_study_enroll}")
    else:
        current_enrollments = Classroomenrollment.objects.filter(classroom=classroom)
        enrolled_in_course = current_enrollments.values_list('student__id', flat=True)
        available_students = base_students.exclude(id__in=enrolled_in_course).distinct()
        print(f"Available students (course type without course link): {available_students.count()}")
        
        for name in names_to_search:
            students = Student.objects.filter(full_name__icontains=name)
            for s in students:
                is_active = s.is_active
                in_current = s.id in enrolled_in_course
                print(f"Student {s.full_name}: is_active={is_active}, in_current={in_current}")
