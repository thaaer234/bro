import os
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
import django
django.setup()

from students.models import Student
from classroom.models import Classroomenrollment
from attendance.models import Attendance
from accounts.models import StudentReceipt, Studentenrollment
from academic_years.models import AcademicYearSystemState

print("=== DIAGNOSING STUDENT ON PRODUCTION ===")

# Search for the student
students = Student.objects.filter(full_name__icontains="الحج")
if not students.exists():
    students = Student.objects.filter(full_name__icontains="اية")

print(f"Found {students.count()} matching students:")
for s in students:
    print(f"\nID: {s.id} | Name: {s.full_name} | Student Number: {s.student_number} | Phone: {s.phone}")
    print(f"  - Father Phone: {s.father_phone} | Mother Phone: {s.mother_phone}")
    
    # Check classroom enrollments
    enrolls = Classroomenrollment.objects.filter(student=s)
    print(f"  - Classroom Enrollments ({enrolls.count()}):")
    for e in enrolls:
        print(f"    * Classroom: {e.classroom.name} (ID: {e.classroom.id}) | Branch: {e.classroom.branches} | Active: {e.classroom.is_active}")
        
    # Check attendance
    att_count = Attendance.objects.filter(student=s).count()
    print(f"  - Attendance Records count: {att_count}")
    
    # Check course enrollments
    course_enrolls = Studentenrollment.objects.filter(student=s)
    print(f"  - Course Enrollments ({course_enrolls.count()}):")
    for ce in course_enrolls:
        print(f"    * Course: {ce.course.name} (ID: {ce.course.id}) | Net: {ce.net_amount} | Paid: {ce.amount_paid}")
        
    # Check receipts
    receipts_count = StudentReceipt.objects.filter(student_profile=s).count()
    print(f"  - Receipts count: {receipts_count}")

# Check current academic year state
state = AcademicYearSystemState.objects.first()
if state:
    print(f"\nActive Academic Year in System: {state.active_year} (ID: {state.active_year.id if state.active_year else 'None'})")
else:
    print("\nActive Academic Year in System: None (Empty AcademicYearSystemState)")
