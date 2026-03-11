# api/serializers.py
from rest_framework import serializers
from .models import MobileUser, EmergencyAlert, Announcement
from students.models import Student, StudentWarning
from employ.models import Teacher
from attendance.models import Attendance, TeacherAttendance
from exams.models import ExamGrade, StudentExam
from classroom.models import Classroom
from courses.models import Subject
from accounts.models import Studentenrollment, StudentReceipt
from django.contrib.auth.hashers import make_password

class StudentLoginSerializer(serializers.Serializer):
    student_name = serializers.CharField(max_length=200)
    password = serializers.CharField(max_length=20)
    
    def validate(self, data):
        def normalize(val: str) -> str:
            return ''.join(ch for ch in str(val).strip() if ch.isdigit())

        student_name = data.get('student_name')
        password = data.get('password')
        normalized_pass = normalize(password)

        student = (
            Student.objects.filter(student_number=student_name).first()
            or Student.objects.filter(phone=student_name).first()
            or Student.objects.filter(full_name__iexact=student_name).first()
            or Student.objects.filter(full_name__icontains=student_name).first()
        )

        if not student:
            raise serializers.ValidationError("???????????? ?????? ??????????")

        existing_mobile_user = MobileUser.objects.filter(student=student).first()
        if existing_mobile_user and existing_mobile_user.check_password(password):
            data['student'] = student
            data['mobile_user'] = existing_mobile_user
            return data

        phone_numbers = [
            student.phone,
            student.father_phone,
            student.mother_phone,
            student.home_phone,
        ]

        normalized_list = [
            normalize(p) for p in phone_numbers if p and normalize(p) and normalize(p) != '0'
        ]

        if not normalized_list:
            raise serializers.ValidationError("???? ???????? ?????? ???????? ???????????? ???? ????????????.")

        if normalized_pass not in normalized_list:
            raise serializers.ValidationError("???????? ???????????? ?????? ??????????")

        data['student'] = student
        return data

class TeacherLoginSerializer(serializers.Serializer):
    teacher_name = serializers.CharField(max_length=200)
    password = serializers.CharField(max_length=20)
    
    def validate(self, data):
        def normalize(val: str) -> str:
            return ''.join(ch for ch in str(val).strip() if ch.isdigit())

        teacher_name = data.get('teacher_name')
        password = data.get('password')
        normalized_pass = normalize(password)
        
        # البحث عن المدرس مع تفضيل المطابقة الدقيقة
        teacher = (
            Teacher.objects.filter(phone_number=teacher_name).first()
            or Teacher.objects.filter(full_name__iexact=teacher_name).first()
            or Teacher.objects.filter(full_name__icontains=teacher_name).first()
            or Teacher.objects.filter(phone_number__icontains=teacher_name).first()
        )

        if not teacher:
            raise serializers.ValidationError("المدرس غير موجود")

        # التحقق من كلمة المرور (رقم الهاتف مطلوب للتحقق)
        if teacher.phone_number and str(teacher.phone_number).strip():
            clean_phone = normalize(teacher.phone_number)
            if normalized_pass != clean_phone:
                raise serializers.ValidationError("كلمة المرور غير صحيحة")
        else:
            raise serializers.ValidationError("لا يوجد رقم هاتف للتحقق من الهوية.")

        data['teacher'] = teacher
        return data

class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            'id', 'full_name', 'student_number', 'email', 'phone', 
            'gender', 'branch', 'birth_date', 'nationality',
            'father_name', 'father_phone', 'father_job',
            'mother_name', 'mother_phone', 'mother_job',
            'address', 'home_phone', 'previous_school',
            'elementary_school', 'how_knew_us', 'notes',
            'registration_date', 'is_active', 'discount_percent',
            'discount_amount', 'discount_reason',
            'academic_level', 'registration_status'
        ]


class StudentWarningSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentWarning
        fields = [
            'id',
            'title',
            'details',
            'severity',
            'is_active',
            'created_at',
            'created_by_name',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

class AttendanceSerializer(serializers.ModelSerializer):
    classroom_name = serializers.CharField(source='classroom.name', read_only=True)
    
    class Meta:
        model = Attendance
        fields = ['id', 'date', 'status', 'classroom_name', 'notes']

class ExamGradeSerializer(serializers.ModelSerializer):
    exam_name = serializers.CharField(source='exam.name', read_only=True)
    subject_name = serializers.CharField(source='exam.subject.name', read_only=True)
    max_grade = serializers.DecimalField(source='exam.max_grade', read_only=True, max_digits=5, decimal_places=2)
    
    class Meta:
        model = ExamGrade
        fields = ['id', 'exam_name', 'subject_name', 'grade', 'max_grade', 'notes']

class ClassroomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = ['id', 'name', 'branches', 'class_type']

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'subject_type']

class TeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Teacher
        fields = [
            'id', 'full_name', 'phone_number', 'branch', 'branches',
            'hire_date', 'hourly_rate', 'monthly_salary', 'salary_type',
            'notes'
        ]


class StudentEnrollmentSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source='course.name', read_only=True)
    course_id = serializers.IntegerField(source='course.id', read_only=True)
    net_amount = serializers.SerializerMethodField()
    amount_paid = serializers.SerializerMethodField()
    balance_due = serializers.SerializerMethodField()

    class Meta:
        model = Studentenrollment
        fields = [
            'id', 'course_id', 'course_name', 'enrollment_date', 'total_amount',
            'discount_percent', 'discount_amount', 'net_amount', 'amount_paid',
            'balance_due', 'payment_method', 'is_completed', 'completion_date', 'notes'
        ]

    def get_net_amount(self, obj):
        return obj.net_amount

    def get_amount_paid(self, obj):
        return obj.amount_paid

    def get_balance_due(self, obj):
        return obj.balance_due


class StudentReceiptSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    course_name = serializers.SerializerMethodField()
    net_amount = serializers.SerializerMethodField()

    class Meta:
        model = StudentReceipt
        fields = [
            'id', 'receipt_number', 'date', 'student_name', 'course_name',
            'amount', 'paid_amount', 'discount_percent', 'discount_amount',
            'net_amount', 'payment_method', 'notes', 'created_at'
        ]

    def get_student_name(self, obj):
        # Prefer linked student profile/enrollment, then stored fallback
        try:
            return obj.get_student_name()
        except Exception:
            return obj.student_name

    def get_course_name(self, obj):
        # Ensure course is returned even when the name field is empty
        try:
            return obj.get_course_name()
        except Exception:
            return obj.course_name

    def get_net_amount(self, obj):
        return obj.net_amount

class EmergencyAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyAlert
        fields = '__all__'
        read_only_fields = ['user', 'status', 'responded_by', 'responded_at']

class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = '__all__'
  



  