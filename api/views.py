from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import AuthenticationFailed
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.db.models import Q, Sum
from datetime import datetime, timedelta
from types import SimpleNamespace
import csv
from decimal import Decimal
import jwt
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import logging

logger = logging.getLogger(__name__)

from .models import MobileUser, EmergencyAlert, Announcement
from .serializers import *
from students.models import Student, StudentWarning
from employ.models import Teacher
from attendance.models import Attendance, TeacherAttendance
from exams.models import ExamGrade, StudentExam
from classroom.models import Classroom, Classroomenrollment
from courses.models import Subject
from employ.models import Employee, Vacation
from accounts.models import Studentenrollment, StudentReceipt
from pages.reporting import build_system_report_summary

# Helper to safely resolve a Student instance even if a string/name was stored
def resolve_student_instance(student_like):
    """
    Safely turn a legacy value into an actual Student instance.
    Some old records stored the student's name as a plain string,
    which breaks FK lookups and throws "Must be Student instance".
    """
    if isinstance(student_like, Student):
        return student_like
    if student_like is None:
        return None

    # Try primary key if it looks numeric
    try:
        return Student.objects.get(pk=student_like)
    except Exception:
        pass

    # Try by name (case-insensitive)
    try:
        name_val = str(student_like).strip()
        return (
            Student.objects.filter(full_name__iexact=name_val).first()
            or Student.objects.filter(full_name__icontains=name_val).first()
        )
    except Exception:
        return None

def hydrate_student(mobile_user):
    """
    Ensure mobile_user.student is a real Student instance to avoid
    "Cannot query ... Must be Student instance" from legacy corrupted values.
    """
    student_obj = None
    sid = getattr(mobile_user, "student_id", None)
    if sid:
        student_obj = Student.objects.filter(pk=sid).first()
    if not student_obj and mobile_user.student:
        student_obj = resolve_student_instance(mobile_user.student)
    if student_obj and mobile_user.student_id != student_obj.id:
        mobile_user.student = student_obj
        mobile_user.save(update_fields=["student"])
    elif mobile_user.student and not student_obj:
        mobile_user.student = None
        mobile_user.save(update_fields=["student"])
        return None
    return student_obj

# ============ اختبار الاتصال ============
@api_view(['GET'])
@permission_classes([AllowAny])
def test_connection(request):
    """اختبار اتصال API"""
    logger.info("Test connection endpoint called")
    return Response({
        'success': True,
        'status': 'online',
        'message': 'Mobile API is working!',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0'
    })

# ============ ????? ?????? ??????? ============
@csrf_exempt
@api_view(['POST'])

# ============ تسجيل دخول الطالب (ولي الأمر) ============
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def student_parent_login(request):
    """تسجيل دخول الطالب أو ولي الأمر باستخدام اسم الطالب ورقم الهاتف"""
    logger.info(f"Student/parent login attempt with data: {request.data}")
    
    serializer = StudentLoginSerializer(data=request.data)

    if serializer.is_valid():
        student = serializer.validated_data['student']
        password = request.data.get("password")

        if not password:
            logger.warning("No password provided")
            return Response({
                'success': False,
                'message': 'كلمة المرور مطلوبة'
            }, status=status.HTTP_400_BAD_REQUEST)

        def _normalize_digits(value):
            return "".join(ch for ch in str(value or "").strip() if ch.isdigit())

        normalized_pass = _normalize_digits(password)
        login_role = None
        if normalized_pass and _normalize_digits(getattr(student, "student_number", None)) == normalized_pass:
            login_role = "student"
        elif normalized_pass and _normalize_digits(student.phone) == normalized_pass:
            login_role = "student"
        elif normalized_pass and _normalize_digits(student.father_phone) == normalized_pass:
            login_role = "father"
        elif normalized_pass and _normalize_digits(student.mother_phone) == normalized_pass:
            login_role = "mother"

        if not login_role:
            logger.warning("Password does not match any student/parent phone")
            return Response({
                'success': False,
                'message': 'كلمة المرور غير صحيحة'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # إنشاء أو جلب مستخدم MobileUser
        mobile_user, created = MobileUser.objects.get_or_create(
            student=student,
            defaults={
                'username': f"parent_{student.id}_{student.phone}",
                'phone_number': student.phone or student.student_number or "",
                'user_type': 'student' if login_role == 'student' else 'parent',
                'is_active': True,
                'is_verified': True
            }
        )

        # إذا لم يكن جديد → تحقق من كلمة المرور
        mobile_user.user_type = 'student' if login_role == 'student' else 'parent'
        mobile_user.phone_number = password
        mobile_user.set_password(password)
        mobile_user.save()

        # تأكد من ربط الحساب بالطالب الصحيح حتى لو كان سجلاً قديماً فيه قيمة نصية
        if mobile_user.student_id != student.id:
            mobile_user.student = student
            mobile_user.save(update_fields=['student'])
        hydrate_student(mobile_user)

        # تسجيل الدخول وتوليد توكن
        logger.info(f"Generating JWT token for user {mobile_user.id}")
        token = mobile_user.login()
        
        logger.info(f"Login successful for user {mobile_user.id}, token generated")

        return Response({
            'success': True,
            'message': 'تم تسجيل الدخول بنجاح',
            'token': token,
            'user': {
                'id': mobile_user.id,
                'username': mobile_user.username,
                'user_type': mobile_user.user_type,
                'login_role': login_role,
            },
            'student': {
                'id': student.id,
                'full_name': student.full_name,
                'student_number': student.student_number,
                'phone': student.phone,
                'father_name': student.father_name,
                'father_phone': student.father_phone,
            }
        })

    logger.warning(f"Login serializer errors: {serializer.errors}")
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=400)

# ============ تسجيل دخول المدرس ============
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def teacher_login(request):
    """تسجيل دخول المدرس باستخدام اسم المدرس ورقم الهاتف"""
    logger.info(f"Teacher login attempt with data: {request.data}")
    
    serializer = TeacherLoginSerializer(data=request.data)

    if serializer.is_valid():
        teacher = serializer.validated_data['teacher']
        password = request.data.get('password')

        if not password:
            logger.warning("No password provided for teacher login")
            return Response({
                'success': False,
                'message': 'كلمة المرور مطلوبة'
            }, status=status.HTTP_400_BAD_REQUEST)

        # إنشاء أو جلب مستخدم MobileUser
        mobile_user, created = MobileUser.objects.get_or_create(
            teacher=teacher,
            defaults={
                'username': f"teacher_{teacher.id}_{teacher.phone_number}",
                'phone_number': teacher.phone_number,
                'user_type': 'teacher',
                'is_active': True,
                'is_verified': True
            }
        )

        # إذا كان جديد، قم بتعيين كلمة المرور
        if created:
            mobile_user.set_password(password)
            mobile_user.save()
            logger.info(f"Created new teacher mobile user: {mobile_user.username}")
        else:
            if not mobile_user.check_password(password):
                logger.warning(f"Password check failed for teacher mobile user {mobile_user.id}")
                return Response({
                    'success': False,
                    'message': 'كلمة المرور غير صحيحة'
                }, status=status.HTTP_401_UNAUTHORIZED)
        
        # تسجيل الدخول
        logger.info(f"Generating JWT token for teacher {mobile_user.id}")
        token = mobile_user.login()
        logger.info(f"Teacher login successful for user {mobile_user.id}")
        
        return Response({
            'success': True,
            'message': 'تم تسجيل الدخول بنجاح',
            'token': token,
            'user': {
                'id': mobile_user.id,
                'username': mobile_user.username,
                'user_type': mobile_user.user_type,
            },
            'teacher': {
                'id': teacher.id,
                'full_name': teacher.full_name,
                'phone_number': teacher.phone_number,
                'branch': teacher.branch,
            }
        })
    
    logger.warning(f"Teacher login serializer errors: {serializer.errors}")
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

# ============ مصادقة JWT ============
def jwt_auth_required(view_func):
    """ديكوراتور للتحقق من JWT token"""
    def wrapper(request, *args, **kwargs):
        logger.info(f"JWT auth required for path: {request.path}")
        
        auth_header = request.headers.get('Authorization', '') or request.META.get('HTTP_AUTHORIZATION', '')
        alt_header = (
            request.headers.get('X-Authorization') or request.META.get('HTTP_X_AUTHORIZATION')
            or request.headers.get('X-Auth-Token') or request.META.get('HTTP_X_AUTH_TOKEN')
        )
        token = None

        def extract_from_header(header_value):
            if not header_value:
                return None
            parts = header_value.split()
            if len(parts) == 2 and parts[0].lower() in ('bearer', 'token'):
                return parts[1]
            if len(parts) == 1:
                return parts[0]
            return None

        # دعم أكثر من شكل للتوكن (Bearer/Token + كويكري بارام في حالات الويب)
        token = extract_from_header(auth_header) or extract_from_header(alt_header)
        if not token:
            token = (
                request.GET.get('token')
                or request.POST.get('token')
                or request.data.get('token')
            )
        
        logger.info(f"Token extraction - Header: {auth_header[:50] if auth_header else 'None'}, "
                   f"Alt header: {alt_header[:50] if alt_header else 'None'}, "
                   f"Query param: {request.GET.get('token', 'None')}")
        
        if not token:
            logger.warning("No token found in request")
            return Response({
                'success': False,
                'message': 'مطلوب توكن للمصادقة'
            }, status=401)
        
        logger.info(f"Token found: {token[:30]}...")
        
        try:
            mobile_user = MobileUser.verify_jwt_token(token)
            logger.info(f"Token verification successful for user: {mobile_user.username}")
        except AuthenticationFailed as exc:
            logger.error(f"Authentication failed: {exc}")
            return Response({
                'success': False,
                'message': str(exc)
            }, status=401)
        except Exception as e:
            logger.error(f"Unexpected error during token verification: {e}", exc_info=True)
            return Response({
                'success': False,
                'message': f'خطأ في المصادقة: {str(e)}'
            }, status=401)
        
        try:
            mobile_user.refresh_from_db()
        except Exception:
            pass
        
        # اجعل student المحفوظ ككائن فعلي (يتجنب خطأ Cannot query ... Must be Student instance)
        resolved_student = hydrate_student(mobile_user)
        # إذا كانت قيمة الطالب مخزنة كنص قديم، امسح الربط لتفادي الاستعلام الخاطئ
        if mobile_user.student and not isinstance(resolved_student, Student):
            mobile_user.student = None
            mobile_user.save(update_fields=['student'])
            logger.warning(f"Cleared invalid student reference for user {mobile_user.id}")
            return Response({
                'success': False,
                'message': 'الطالب المرتبط بالحساب غير موجود، يرجى تسجيل الدخول مجدداً'
            }, status=401)

        request.mobile_user = mobile_user
        logger.info(f"Request authenticated for user: {mobile_user.username} (type: {mobile_user.user_type})")
        return view_func(request, *args, **kwargs)
    
    return wrapper

# ============ الحصول على ملف الطالب الكامل ============
@api_view(['GET'])
@jwt_auth_required
def get_student_full_profile(request):
    """الحصول على ملف الطالب الكامل مع جميع المعلومات"""
    mobile_user = request.mobile_user
    logger.info(f"Getting student full profile for user: {mobile_user.username}")
    
    # التحقق من أن المستخدم مرتبط بطالب
    student = resolve_student_instance(mobile_user.student)
    if not student:
        logger.warning(f"User {mobile_user.username} is not associated with a student")
        return Response({
            'success': False,
            'message': 'ليس لديك صلاحية الوصول لملف الطالب'
        }, status=403)
    
    logger.info(f"Fetching profile for student: {student.full_name}")
    
    try:
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
                'enrolled_at': enrollment.enrolled_at,
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
        
        logger.info(f"Successfully fetched profile for student {student.full_name}")
        
        return Response({
            'success': True,
            'student': student_serializer.data,
            'attendance': attendance_serializer.data,
            'exam_grades': exam_serializer.data,
            'classrooms': classrooms_data,
            'teachers': teachers_data,
            'warnings': warnings_data,
        })
        
    except Exception as e:
        logger.error(f"Error fetching student profile: {e}", exc_info=True)
        return Response({
            'success': False,
            'message': f'حدث خطأ في جلب بيانات الملف الشخصي: {str(e)}'
        }, status=500)


# ============ الحصول على ملف المدرس الكامل ============
@api_view(['GET'])
@jwt_auth_required
def get_teacher_full_profile(request):
    mobile_user = request.mobile_user
    logger.info(f"Getting teacher full profile for user: {mobile_user.username}")
    
    if not mobile_user.teacher:
        logger.warning(f"User {mobile_user.username} is not a teacher")
        return Response({
            'success': False,
            'message': 'ليس لديك صلاحية الوصول لملف المدرس'
        }, status=403)
    
    teacher = mobile_user.teacher
    logger.info(f"Fetching profile for teacher: {teacher.full_name}")
    
    try:
        teacher_serializer = TeacherSerializer(teacher)
        
        attendance = TeacherAttendance.objects.filter(teacher=teacher).order_by('-date')
        attendance_data = [{
            'id': a.id,
            'date': a.date,
            'status': a.status,
            'status_display': a.get_status_display(),
            'branch': a.branch,
            'branch_display': a.get_branch_display(),
            'session_count': a.session_count,
            'half_session_count': a.half_session_count,
            'total_sessions': a.total_sessions,
            'notes': a.notes
        } for a in attendance]
        
        subjects = Subject.objects.filter(teachers=teacher)
        subjects_data = SubjectSerializer(subjects, many=True).data
        
        classrooms = Classroom.objects.filter(classroomsubject__subject__in=subjects).distinct()
        classrooms_data = ClassroomSerializer(classrooms, many=True).data
        
        from employ.models import ManualTeacherSalary
        salaries = ManualTeacherSalary.objects.filter(teacher=teacher).order_by('-year', '-month')
        salaries_data = [{
            'year': s.year,
            'month': s.get_month_display(),
            'gross_salary': s.gross_salary,
            'advance_deduction': s.advance_deduction,
            'net_salary': s.net_salary,
            'is_paid': s.is_paid,
            'paid_date': s.paid_date,
            'notes': s.notes
        } for s in salaries]
        
        logger.info(f"Successfully fetched profile for teacher {teacher.full_name}")
        
        return Response({
            'success': True,
            'teacher': teacher_serializer.data,
            'attendance': attendance_data,
            'subjects': subjects_data,
            'classrooms': classrooms_data,
            'salaries': salaries_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching teacher profile: {e}", exc_info=True)
        return Response({
            'success': False,
            'message': f'حدث خطأ في جلب بيانات المدرس: {str(e)}'
        }, status=500)


# ============ إحصائيات وأداء المدرس ============
@api_view(['GET'])
@jwt_auth_required
def get_teacher_performance(request):
    mobile_user = request.mobile_user
    logger.info(f"Getting teacher performance for user: {mobile_user.username}")

    if not mobile_user.teacher:
        logger.warning(f"User {mobile_user.username} is not a teacher")
        return Response({
            'success': False,
            'message': 'غير مصرح - الحساب ليس مدرساً'
        }, status=403)

    teacher = mobile_user.teacher
    logger.info(f"Fetching performance data for teacher: {teacher.full_name}")
    
    try:
        teacher_data = TeacherSerializer(teacher).data

        subjects = Subject.objects.filter(teachers=teacher)
        classrooms = Classroom.objects.filter(
            classroomsubject__subject__in=subjects
        ).distinct()
        students = Student.objects.filter(
            classroom_enrollments__classroom__in=classrooms
        ).distinct()

        attendance_qs = TeacherAttendance.objects.filter(teacher=teacher)
        attendance_totals = attendance_qs.aggregate(
            total_sessions=Sum('session_count'),
            total_half_sessions=Sum('half_session_count')
        )
        total_sessions = Decimal(attendance_totals.get('total_sessions') or 0)
        half_sessions = Decimal(attendance_totals.get('total_half_sessions') or 0)
        total_sessions = total_sessions + (half_sessions * Decimal('0.5'))

        recent_attendance = [{
            'id': a.id,
            'date': a.date,
            'status': a.status,
            'branch': a.branch,
            'branch_display': a.get_branch_display(),
            'session_count': a.session_count,
            'half_session_count': a.half_session_count,
            'total_sessions': a.total_sessions,
            'notes': a.notes
        } for a in attendance_qs.order_by('-date')[:15]]

        classrooms_data = []
        for classroom in classrooms:
            class_students = students.filter(
                classroom_enrollments__classroom=classroom
            )
            classrooms_data.append({
                'id': classroom.id,
                'name': classroom.name,
                'branch': classroom.branches,
                'class_type': classroom.class_type,
                'student_count': class_students.count()
            })

        logger.info(f"Successfully fetched performance data for teacher {teacher.full_name}")
        
        return Response({
            'success': True,
            'teacher': teacher_data,
            'stats': {
                'subjects_count': subjects.count(),
                'classrooms_count': classrooms.count(),
                'students_count': students.count(),
                'days_present': attendance_qs.filter(status='present').count(),
                'days_no_duty': attendance_qs.filter(status='no_duty').count(),
                'total_sessions': total_sessions
            },
            'classrooms': classrooms_data,
            'subjects': SubjectSerializer(subjects, many=True).data,
            'recent_attendance': recent_attendance
        })
        
    except Exception as e:
        logger.error(f"Error fetching teacher performance: {e}", exc_info=True)
        return Response({
            'success': False,
            'message': f'حدث خطأ في جلب بيانات الأداء: {str(e)}'
        }, status=500)

# ============ جلب الطلاب للمدرس ============
@api_view(['GET'])
@jwt_auth_required
def get_teacher_students(request):
    mobile_user = request.mobile_user
    logger.info(f"Getting teacher students for user: {mobile_user.username}")
    
    if not mobile_user.teacher:
        logger.warning(f"User {mobile_user.username} is not a teacher")
        return Response({
            'success': False,
            'message': 'صلاحية المدرس مطلوبة'
        }, status=403)
    
    teacher = mobile_user.teacher
    logger.info(f"Fetching students for teacher: {teacher.full_name}")
    
    try:
        teacher_subjects = Subject.objects.filter(teachers=teacher)
        
        classrooms = Classroom.objects.filter(
            classroomsubject__subject__in=teacher_subjects
        ).distinct()
        
        students = Student.objects.filter(
            classroom_enrollments__classroom__in=classrooms
        ).distinct()
        
        result = []
        for classroom in classrooms:
            classroom_students = students.filter(
                classroom_enrollments__classroom=classroom
            )
            
            result.append({
                'classroom': {
                    'id': classroom.id,
                    'name': classroom.name,
                    'branch': classroom.branches,
                    'type': classroom.class_type
                },
                'students': StudentProfileSerializer(classroom_students, many=True).data,
                'student_count': classroom_students.count()
            })
        
        logger.info(f"Successfully fetched {students.count()} students for teacher {teacher.full_name}")
        
        return Response({
            'success': True,
            'data': result,
            'total_students': students.count(),
            'total_classrooms': classrooms.count()
        })
        
    except Exception as e:
        logger.error(f"Error fetching teacher students: {e}", exc_info=True)
        return Response({
            'success': False,
            'message': f'حدث خطأ في جلب بيانات الطلاب: {str(e)}'
        }, status=500)

# ============ تسجيل حضور الطلاب ============
@csrf_exempt
@api_view(['POST'])
@jwt_auth_required
def record_student_attendance(request):
    mobile_user = request.mobile_user
    logger.info(f"Recording student attendance by user: {mobile_user.username}")
    
    if not mobile_user.teacher:
        logger.warning(f"User {mobile_user.username} is not a teacher")
        return Response({
            'success': False,
            'message': 'صلاحية المدرس مطلوبة'
        }, status=403)
    
    try:
        data = request.data
        logger.info(f"Attendance data: {data}")
        
        raw_date = data.get('date')
        if raw_date:
            try:
                date = datetime.strptime(str(raw_date), '%Y-%m-%d').date()
            except ValueError:
                logger.warning(f"Invalid date format: {raw_date}")
                return Response({
                    'success': False,
                    'message': 'صيغة التاريخ غير صحيحة، استخدم YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            date = timezone.now().date()
            
        classroom_id = data.get('classroom_id')
        attendance_list = data.get('attendance', [])
        
        classroom = get_object_or_404(Classroom, id=classroom_id)
        logger.info(f"Recording attendance for classroom: {classroom.name} on {date}")
        
        teacher_subjects = Subject.objects.filter(teachers=mobile_user.teacher)
        if not classroom.classroomsubject_set.filter(subject__in=teacher_subjects).exists():
            logger.warning(f"Teacher {mobile_user.teacher.full_name} not authorized for classroom {classroom.name}")
            return Response({
                'success': False,
                'message': 'ليس لديك صلاحية تسجيل الحضور في هذه الشعبة'
            }, status=403)
        
        results = []
        for att_data in attendance_list:
            student_id = att_data.get('student_id')
            status_val = att_data.get('status', 'absent')
            notes = att_data.get('notes', '')
            
            student = get_object_or_404(Student, id=student_id)
            
            if not Classroomenrollment.objects.filter(student=student, classroom=classroom).exists():
                logger.warning(f"Student {student.full_name} not enrolled in classroom {classroom.name}")
                results.append({
                    'student_id': student_id,
                    'success': False,
                    'message': 'الطالب غير مسجل في هذه الشعبة'
                })
                continue
            
            attendance, created = Attendance.objects.update_or_create(
                student=student,
                date=date,
                defaults={
                    'classroom': classroom,
                    'status': status_val,
                    'notes': notes
                }
            )
            
            results.append({
                'student_id': student_id,
                'student_name': student.full_name,
                'success': True,
                'created': created,
                'attendance_id': attendance.id,
                'status': status_val
            })
        
        logger.info(f"Successfully recorded attendance for {len([r for r in results if r['success']])} students")
        
        return Response({
            'success': True,
            'message': 'تم تسجيل الحضور بنجاح',
            'date': date,
            'classroom': classroom.name,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error recording attendance: {e}", exc_info=True)
        return Response({
            'success': False,
            'message': f'حدث خطأ: {str(e)}'
        }, status=500)

# ============ إرسال تنبيه طارئ ============
@csrf_exempt
@api_view(['POST'])
@jwt_auth_required
def send_emergency_alert(request):
    mobile_user = request.mobile_user
    logger.info(f"Sending emergency alert by user: {mobile_user.username}")
    
    try:
        alert_type = request.data.get('alert_type', 'emergency')
        message = request.data.get('message')
        location = request.data.get('location', '')
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not message:
            logger.warning("No message provided for emergency alert")
            return Response({
                'success': False,
                'message': 'الرسالة مطلوبة'
            }, status=400)
        
        logger.info(f"Creating emergency alert: type={alert_type}, location={location}")
        
        alert = EmergencyAlert.objects.create(
            user=mobile_user,
            alert_type=alert_type,
            message=message,
            location=location,
            latitude=latitude,
            longitude=longitude,
            status='pending'
        )
        
        logger.info(f"Emergency alert created with ID: {alert.id}")
        
        return Response({
            'success': True,
            'message': 'تم إرسال التنبيه بنجاح',
            'alert': {
                'id': alert.id,
                'alert_type': alert.alert_type,
                'alert_type_display': alert.get_alert_type_display(),
                'message': alert.message,
                'location': alert.location,
                'status': alert.status,
                'created_at': alert.created_at
            }
        })
        
    except Exception as e:
        logger.error(f"Error sending emergency alert: {e}", exc_info=True)
        return Response({
            'success': False,
            'message': f'حدث خطأ: {str(e)}'
        }, status=500)

# ============ جلب الإعلانات ============
@api_view(['GET'])
@jwt_auth_required
def get_announcements(request):
    mobile_user = request.mobile_user
    logger.info(f"Getting announcements for user: {mobile_user.username} (type: {mobile_user.user_type})")

    student = resolve_student_instance(mobile_user.student)
    target_audience = []
    
    if mobile_user.user_type == 'parent':
        target_audience = ['all', 'parents']
        if student:
            classroom_enrollments = Classroomenrollment.objects.filter(
                student=student
            )
            if classroom_enrollments.exists():
                target_audience.append('specific_class')
    elif mobile_user.user_type == 'teacher':
        target_audience = ['all', 'teachers']
    elif mobile_user.user_type == 'student':
        target_audience = ['all', 'students']

    audience_filter = Q(target_audience__in=target_audience) if target_audience else Q(target_audience='__none__')

    if student:
        student_classrooms = Classroom.objects.filter(
            enrollments__student=student
        )
        audience_filter |= Q(
            target_audience='specific_class',
            classroom__in=student_classrooms
        )

    announcements = Announcement.objects.filter(
        audience_filter,
        is_active=True,
        is_published=True
    ).exclude(expiration_date__lt=timezone.now()).order_by('-publish_date')
    
    serializer = AnnouncementSerializer(announcements, many=True)
    
    logger.info(f"Found {announcements.count()} announcements for user {mobile_user.username}")
    
    return Response({
        'success': True,
        'announcements': serializer.data,
        'count': announcements.count()
    })

# ============ تحديث بيانات المستخدم ============
@csrf_exempt
@api_view(['POST'])
@jwt_auth_required
def update_user_profile(request):
    mobile_user = request.mobile_user
    logger.info(f"Updating profile for user: {mobile_user.username}")

    try:
        new_password = request.data.get('new_password')
        current_password = request.data.get('current_password')
        
        if new_password:
            if not current_password or not mobile_user.check_password(current_password):
                logger.warning(f"Password update failed - current password incorrect for user {mobile_user.id}")
                return Response({
                    'success': False,
                    'message': 'كلمة المرور الحالية غير صحيحة'
                }, status=status.HTTP_401_UNAUTHORIZED)

            if len(str(new_password)) < 4:
                logger.warning(f"Password too short for user {mobile_user.id}")
                return Response({
                    'success': False,
                    'message': 'كلمة المرور الجديدة قصيرة جداً'
                }, status=status.HTTP_400_BAD_REQUEST)

            mobile_user.set_password(new_password)
            logger.info(f"Password updated for user {mobile_user.id}")

        device_token = request.data.get('device_token')
        if device_token:
            mobile_user.device_token = device_token
            logger.info(f"Device token updated for user {mobile_user.id}")
        
        mobile_user.save()
        logger.info(f"Profile updated successfully for user {mobile_user.id}")
        
        return Response({
            'success': True,
            'message': 'تم تحديث البيانات بنجاح'
        })
        
    except Exception as e:
        logger.error(f"Error updating user profile: {e}", exc_info=True)
        return Response({
            'success': False,
            'message': f'حدث خطأ: {str(e)}'
        }, status=500)

# ============ اختبار المصادقة ============
@api_view(['GET'])
@jwt_auth_required
def test_auth(request):
    mobile_user = request.mobile_user
    logger.info(f"Test auth for user: {mobile_user.username}")
    
    student_resolved = resolve_student_instance(mobile_user.student)
    
    user_data = {
        'id': mobile_user.id,
        'username': mobile_user.username,
        'user_type': mobile_user.user_type,
        'phone_number': mobile_user.phone_number,
        'last_login': mobile_user.last_login,
        'is_verified': mobile_user.is_verified,
    }
    
    if mobile_user.user_type == 'parent' and student_resolved:
        user_data['student'] = {
            'id': student_resolved.id,
            'full_name': student_resolved.full_name,
            'student_number': student_resolved.student_number
        }
    elif mobile_user.user_type == 'teacher' and mobile_user.teacher:
        user_data['teacher'] = {
            'id': mobile_user.teacher.id,
            'full_name': mobile_user.teacher.full_name,
            'phone_number': mobile_user.teacher.phone_number
        }
    
    logger.info(f"Auth test successful for user {mobile_user.username}")
    
    return Response({
        'success': True,
        'message': 'المصادقة ناجحة',
        'user': user_data
    })

# ============ دالة لتصحيح التوكن ============
@api_view(['GET'])
@permission_classes([AllowAny])
def debug_token(request):
    """دالة لتصحيح مشاكل التوكن"""
    logger.info("Debug token endpoint called")
    
    auth_header = request.headers.get('Authorization', '')
    token_param = request.GET.get('token')
    
    debug_info = {
        'auth_header': auth_header,
        'token_param': token_param,
        'headers': dict(request.headers),
        'method': request.method,
        'path': request.path,
        'query_params': dict(request.GET),
    }
    
    # محاولة تحليل التوكن
    if auth_header:
        try:
            # استخراج التوكن من header
            token = auth_header.split(' ')[1] if ' ' in auth_header else auth_header
            debug_info['token_from_header'] = token
            debug_info['header_type'] = auth_header.split(' ')[0] if ' ' in auth_header else 'plain'
            debug_info['token_length'] = len(token)
            
            # محاولة التحقق من التوكن
            try:
                mobile_user = MobileUser.verify_jwt_token(token)
                debug_info['token_verification'] = 'SUCCESS'
                debug_info['verified_user'] = {
                    'id': mobile_user.id,
                    'username': mobile_user.username,
                    'user_type': mobile_user.user_type
                }
            except Exception as e:
                debug_info['token_verification'] = 'FAILED'
                debug_info['verification_error'] = str(e)
                
        except Exception as e:
            debug_info['header_error'] = str(e)
    
    logger.info(f"Debug token response: {debug_info}")
    
    return Response({
        'success': True,
        'debug': debug_info,
        'message': 'Token debugging information'
    })

# ============ دالة للتحقق من التوكن ============
@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_token(request):
    """التحقق من صحة التوكن"""
    logger.info("Verify token endpoint called")
    
    try:
        token = request.data.get('token')
        if not token:
            logger.warning("No token provided for verification")
            return Response({
                'success': False,
                'message': 'يجب إرسال التوكن'
            }, status=400)
        
        logger.info(f"Verifying token: {token[:30]}...")
        
        try:
            mobile_user = MobileUser.verify_jwt_token(token)
            logger.info(f"Token verification successful for user: {mobile_user.username}")
            
            return Response({
                'success': True,
                'message': 'التوكن صالح',
                'user': {
                    'id': mobile_user.id,
                    'username': mobile_user.username,
                    'user_type': mobile_user.user_type,
                    'is_active': mobile_user.is_active,
                    'is_verified': mobile_user.is_verified
                }
            })
            
        except AuthenticationFailed as e:
            logger.warning(f"Token verification failed: {e}")
            return Response({
                'success': False,
                'message': str(e)
            }, status=401)
            
    except Exception as e:
        logger.error(f"Error in verify_token: {e}", exc_info=True)
        return Response({
            'success': False,
            'message': f'خطأ في التحقق: {str(e)}'
        }, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def system_report(request):
    user = request.user
    if not user.is_authenticated or not user.is_superuser:
        return JsonResponse({'detail': 'Permission denied.'}, status=403)

    start_raw = request.GET.get('start_date')
    end_raw = request.GET.get('end_date')
    course_id = request.GET.get('course_id')
    user_id = request.GET.get('user_id')
    report_scope = request.GET.get('type') or None
    sections = request.GET.get('sections')
    response_format = (request.GET.get('format') or 'json').lower()

    try:
        start_date = datetime.strptime(start_raw, '%Y-%m-%d').date() if start_raw else None
    except ValueError:
        start_date = None
    try:
        end_date = datetime.strptime(end_raw, '%Y-%m-%d').date() if end_raw else None
    except ValueError:
        end_date = None

    today = timezone.localdate()
    if not end_date:
        end_date = today
    if not start_date:
        start_date = end_date - timedelta(days=6)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    try:
        course_id = int(course_id) if course_id else None
    except ValueError:
        course_id = None
    try:
        user_id = int(user_id) if user_id else None
    except ValueError:
        user_id = None

    summary = build_system_report_summary(
        period_start=start_date,
        period_end=end_date,
        course_id=course_id,
        user_id=user_id,
        report_scope=report_scope,
        sections=sections,
    )

    if response_format == 'json':
        return JsonResponse(summary, json_dumps_params={'ensure_ascii': False})

    if response_format == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="system_report.csv"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['metric', 'value'])
        for key, value in summary.get('counts', {}).items():
            writer.writerow([f'counts.{key}', value])
        for key, value in summary.get('transactions', {}).items():
            writer.writerow([f'transactions.{key}', value])
        for key, value in summary.get('attendance', {}).items():
            writer.writerow([f'attendance.{key}', value])
        writer.writerow(['activity.total', summary.get('activity', {}).get('total', 0)])
        return response

    if response_format in ('xlsx', 'excel'):
        try:
            import pandas as pd
        except Exception:
            return JsonResponse({'detail': 'pandas is not installed for Excel export.'}, status=501)

        data = []
        for key, value in summary.get('counts', {}).items():
            data.append({'metric': f'counts.{key}', 'value': value})
        for key, value in summary.get('transactions', {}).items():
            data.append({'metric': f'transactions.{key}', 'value': value})
        for key, value in summary.get('attendance', {}).items():
            data.append({'metric': f'attendance.{key}', 'value': value})
        data.append({'metric': 'activity.total', 'value': summary.get('activity', {}).get('total', 0)})
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="system_report.xlsx"'
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Summary')
        return response

    if response_format == 'pdf':
        try:
            from weasyprint import HTML
        except Exception:
            return JsonResponse({'detail': 'WeasyPrint is not installed for PDF export.'}, status=501)

        report_view = SimpleNamespace(
            period_start=start_date,
            period_end=end_date,
            summary=summary,
            created_at=timezone.now(),
        )
        html = render_to_string('pages/system_report_print.html', {'report': report_view})
        pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="system_report.pdf"'
        return response

    return JsonResponse({'detail': 'Unsupported format.'}, status=400)
