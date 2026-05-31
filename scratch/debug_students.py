import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from classroom.models import Classroom, Classroomenrollment
from accounts.models import Studentenrollment, Course
from students.models import Student

def debug():
    classroom_id = 25
    try:
        classroom = Classroom.objects.get(id=classroom_id)
        print(f"Classroom ID: {classroom.id}")
        print(f"Classroom Name: {classroom.name}")
        print(f"Classroom Type: {classroom.class_type}")
        print(f"Classroom Course: {classroom.course}")
        
        if classroom.course:
            course = classroom.course
            print(f"Linked Course: {course.name} (ID: {course.id})")
            
            # Check enrollments for this course in accounts
            enrollments = Studentenrollment.objects.filter(course=course)
            print(f"Enrollments count for this course: {enrollments.count()}")
            for e in enrollments[:10]:
                print(f"  - Student: {e.student.full_name if hasattr(e.student, 'full_name') else e.student} (ID: {e.student.id})")
                
            # Check classroom enrollments for this course
            class_enrollments = Classroomenrollment.objects.filter(classroom__course=course)
            print(f"Classroom enrollments count for this course: {class_enrollments.count()}")
            for ce in class_enrollments[:10]:
                print(f"  - Student: {ce.student} (ID: {ce.student.id if ce.student else None}) in Classroom: {ce.classroom.name}")
                
            # Let's run our logic
            course_student_ids = list(enrollments.values_list('student__id', flat=True))
            assigned_student_ids = list(class_enrollments.values_list('student__id', flat=True))
            print(f"Course Student IDs: {course_student_ids}")
            print(f"Assigned Student IDs: {assigned_student_ids}")
            
            # Check properties of these specific student IDs in the DB
            for sid in course_student_ids:
                try:
                    s = Student.objects.get(id=sid)
                    print(f"  ID: {sid}, Name: {s.full_name}, is_active: {s.is_active}")
                except Student.DoesNotExist:
                    print(f"  ID: {sid} DOES NOT EXIST in Student model!")
            
            base_students = Student.objects.all()
            print(f"Total Student count in Student model: {base_students.count()}")
            print(f"Total active Student count: {base_students.filter(is_active=True).count()}")
            
            available_students = base_students.filter(
                id__in=course_student_ids
            ).exclude(
                id__in=assigned_student_ids
            )
            print(f"Available students count (without is_active filter): {available_students.count()}")
            
            available_active_students = base_students.filter(is_active=True).filter(
                id__in=course_student_ids
            ).exclude(
                id__in=assigned_student_ids
            )
            print(f"Available active students count: {available_active_students.count()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug()
