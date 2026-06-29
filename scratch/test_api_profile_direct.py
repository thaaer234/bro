import os
import sys
import json
from decimal import Decimal

# Add project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
import django
django.setup()

from students.models import Student, StudentWarning
from attendance.models import Attendance
from exams.models import ExamGrade
from classroom.models import Classroomenrollment
from api.serializers import (
    StudentProfileSerializer,
    AttendanceSerializer,
    ExamGradeSerializer,
    SubjectSerializer,
    TeacherSerializer,
    StudentWarningSerializer
)
from courses.models import Subject

student = Student.objects.get(id=482)

# 1. معلومات الطالب
student_serializer = StudentProfileSerializer(student)

# 2. الحضور
attendance = Attendance.objects.filter(student=student).select_related('classroom').order_by('-date')
attendance_serializer = AttendanceSerializer(attendance, many=True)

# 3. العلامات
exam_grades = ExamGrade.objects.filter(student=student).select_related('exam', 'exam__subject').order_by('-exam__exam_date')
exam_serializer = ExamGradeSerializer(exam_grades, many=True)

# 4. الشعب والمواد
classroom_enrollments = Classroomenrollment.objects.filter(student=student).select_related('classroom')
classrooms_data = []
for enrollment in classroom_enrollments:
    classroom = enrollment.classroom
    from classroom.models import ClassroomSubject
    subjects = ClassroomSubject.objects.filter(classroom=classroom).select_related('subject')
    
    classrooms_data.append({
        'id': classroom.id,
        'name': classroom.name,
        'branch': classroom.branches,
        'class_type': classroom.class_type,
        'enrolled_at': str(enrollment.enrolled_at),
        'subjects': SubjectSerializer([cs.subject for cs in subjects], many=True).data
    })

# 5. المدرسين
teachers = set()
for enrollment in classroom_enrollments:
    classroom = enrollment.classroom
    for subject in Subject.objects.filter(classroomsubject__classroom=classroom):
        teachers.update(subject.teachers.all())

teachers_data = TeacherSerializer(teachers, many=True).data

# 6. التنبيهات
warnings_qs = StudentWarning.objects.filter(
    student=student,
    is_active=True
).order_by('-created_at')
warnings_data = StudentWarningSerializer(warnings_qs, many=True).data

# Print summary
print("Student Name:", student.full_name)
print("Classrooms:", classrooms_data)
print("Teachers count:", len(teachers_data))
print("Attendance count:", len(attendance_serializer.data))
print("Grades count:", len(exam_serializer.data))
