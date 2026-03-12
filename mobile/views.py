import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Count, Q, Sum, Avg
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import FormView, TemplateView, View

from accounts.models import StudentReceipt, Studentenrollment, TeacherAdvance
from attendance.models import Attendance, TeacherAttendance
from announcements.services import (
    count_unread_parent_announcements,
    get_parent_announcements,
    get_teacher_announcements,
)
from classroom.models import Classroom
from courses.models import Subject
from employ.models import ManualTeacherSalary, Teacher
from exams.models import Exam, ExamGrade
from students.models import Student, StudentWarning

from .forms import MobileLoginForm
from .models import (
    ListeningTest,
    ListeningTestAssignment,
    MobileDeviceToken,
    MobileNotification,
)


def normalize_digits(value):
    return ''.join(ch for ch in str(value or '').strip() if ch.isdigit())


def _resolve_mobile_user_from_request(request):
    user_type = request.session.get("mobile_user_type")
    user_id = request.session.get("mobile_user_id")
    if user_type and user_id:
        return user_type, user_id

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        return None, None

    try:
        from api.models import MobileUser
    except Exception:
        MobileUser = None
    if not MobileUser:
        return None, None

    try:
        mobile_user = MobileUser.verify_jwt_token(token)
    except Exception:
        return None, None

    if mobile_user.user_type == "teacher" and mobile_user.teacher_id:
        return "teacher", mobile_user.teacher_id
    if mobile_user.user_type == "parent" and mobile_user.student_id:
        return "parent", mobile_user.student_id
    return None, None


@csrf_exempt
@require_http_methods(["POST"])
def register_push_token(request):

    data = {}
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            data = {}
    if not data:
        data = request.POST

    token = data.get("expo_push_token") or data.get("token") or data.get("fcm_token")
    platform = (data.get("platform") or "").strip().lower()
    device_id = (data.get("device_id") or data.get("deviceId") or "").strip()
    app_version = data.get("app_version") or data.get("appVersion") or ""
    device_name = (data.get("device_name") or data.get("deviceName") or "").strip()

    if not token or not platform:
        return JsonResponse(
            {"detail": "Token and platform are required"},
            status=400,
        )

    user_type, user_id = _resolve_mobile_user_from_request(request)
    if not user_type or not user_id:
        fallback_user_id = data.get("userId") or data.get("user_id")
        fallback_user_type = (
            data.get("userType") or data.get("user_type") or "parent"
        ).lower()
        if fallback_user_id not in (None, ""):
            try:
                user_id = int(fallback_user_id)
            except (TypeError, ValueError):
                return JsonResponse({"detail": "userId must be a number"}, status=400)
            valid_user_types = {choice[0] for choice in MobileDeviceToken.USER_TYPES}
            user_type = fallback_user_type if fallback_user_type in valid_user_types else "parent"

    if not device_id and not (user_type and user_id):
        return JsonResponse(
            {"detail": "device_id is required for anonymous registration"},
            status=400,
        )

    existing = None
    if device_id:
        existing = MobileDeviceToken.objects.filter(device_id=device_id).first()

    login_role = request.session.get("mobile_login_role") or data.get("login_role") or data.get("role")

    if existing:
        if existing.token != token:
            MobileDeviceToken.objects.filter(token=token).exclude(id=existing.id).delete()
            existing.token = token
        if user_type and user_id:
            existing.user_type = user_type
            existing.user_id = user_id
        if login_role:
            existing.login_role = str(login_role)[:20]
        existing.platform = platform[:20]
        if device_id:
            existing.device_id = device_id[:255]
        if device_name:
            existing.device_name = device_name[:100]
        existing.app_version = app_version[:50]
        existing.last_seen_at = timezone.now()
        existing.save()
        return JsonResponse(
            {"status": "success", "message": "Token registered successfully"},
            status=200,
        )

    if not user_type or not user_id:
        token_existing = MobileDeviceToken.objects.filter(token=token).first()
        if token_existing:
            token_existing.platform = platform[:20]
            if device_id:
                token_existing.device_id = device_id[:255]
            if device_name:
                token_existing.device_name = device_name[:100]
            token_existing.app_version = app_version[:50]
            if login_role:
                token_existing.login_role = str(login_role)[:20]
            token_existing.last_seen_at = timezone.now()
            token_existing.save()
            return JsonResponse(
                {"status": "success", "message": "Token registered successfully"},
                status=200,
            )

    obj, created = MobileDeviceToken.objects.update_or_create(
        token=token,
        defaults={
            "user_type": user_type,
            "user_id": user_id,
            "login_role": str(login_role)[:20] if login_role else None,
            "platform": platform[:20],
            "device_id": device_id[:255],
            "device_name": device_name[:100],
            "app_version": app_version[:50],
            "last_seen_at": timezone.now(),
        },
    )
    status_code = 201 if created else 200
    return JsonResponse(
        {"status": "success", "message": "Token registered successfully"},
        status=status_code,
    )


class MobileLoginView(FormView):
    template_name = "mobile/login.html"
    form_class = MobileLoginForm
    success_url = reverse_lazy("mobile:dashboard")

    def form_valid(self, form):
        username = form.cleaned_data["username"].strip()
        password = form.cleaned_data["password"].strip()
        normalized_pass = normalize_digits(password)

        teacher = self._find_teacher(username)
        if teacher:
            if not teacher.phone_number:
                form.add_error("password", "رقم الهاتف غير مسجل للمدرس.")
                return self.form_invalid(form)
            if normalize_digits(teacher.phone_number) != normalized_pass:
                form.add_error("password", "كلمة المرور غير مطابقة لرقم الهاتف.")
                return self.form_invalid(form)

            self._set_mobile_session("teacher", teacher.id, teacher.full_name, "teacher")
            return super().form_valid(form)

        student = self._find_student(username)
        if not student:
            form.add_error("username", "لا يوجد مستخدم بهذا الاسم.")
            return self.form_invalid(form)

        login_role = self._check_student_password(student, normalized_pass)
        if not login_role:
            form.add_error("password", "كلمة المرور غير صحيحة.")
            return self.form_invalid(form)

        self._set_mobile_session("parent", student.id, student.full_name, login_role)
        return super().form_valid(form)

    def _set_mobile_session(self, user_type, user_id, label, login_role=None):
        self.request.session["mobile_user_type"] = user_type
        self.request.session["mobile_user_id"] = user_id
        self.request.session["mobile_user_label"] = label
        if login_role:
            self.request.session["mobile_login_role"] = login_role
        self.request.session["mobile_login_time"] = timezone.now().isoformat()

    def _find_teacher(self, identifier):
        identifier = identifier.strip()
        if not identifier:
            return None
        teacher = (
            Teacher.objects.filter(full_name__iexact=identifier).first()
            or Teacher.objects.filter(full_name__icontains=identifier).first()
            or Teacher.objects.filter(phone_number__icontains=identifier).first()
        )
        return teacher

    def _find_student(self, identifier):
        identifier = identifier.strip()
        if not identifier:
            return None
        student = (
            Student.objects.filter(student_number__iexact=identifier).first()
            or Student.objects.filter(full_name__iexact=identifier).first()
            or Student.objects.filter(full_name__icontains=identifier).first()
            or Student.objects.filter(phone__icontains=identifier).first()
        )
        return student

    def _check_student_password(self, student, normalized_pass):
        if not normalized_pass:
            return None
        phones = [
            getattr(student, "student_number", None),
            student.phone,
            getattr(student, "father_phone", None),
            getattr(student, "mother_phone", None),
            getattr(student, "home_phone", None),
        ]
        role_map = {
            normalize_digits(getattr(student, "student_number", None)): "student",
            normalize_digits(student.phone): "student",
            normalize_digits(getattr(student, "father_phone", None)): "father",
            normalize_digits(getattr(student, "mother_phone", None)): "mother",
            normalize_digits(getattr(student, "home_phone", None)): "parent",
        }
        for phone in phones:
            if normalize_digits(phone) and normalize_digits(phone) == normalized_pass:
                return role_map.get(normalize_digits(phone), "parent")
        return None


@method_decorator(csrf_exempt, name="dispatch")
class MobileDeviceTokenView(View):
    def post(self, request, *args, **kwargs):
        user_type = request.session.get("mobile_user_type")
        user_id = request.session.get("mobile_user_id")
        if not user_type or not user_id:
            auth_header = request.headers.get("Authorization", "")
            token = auth_header.replace("Bearer ", "").strip()
            if token:
                try:
                    from api.models import MobileUser
                except Exception:
                    MobileUser = None
                if MobileUser:
                    try:
                        mobile_user = MobileUser.verify_jwt_token(token)
                    except Exception:
                        mobile_user = None
                    if mobile_user:
                        if mobile_user.user_type == "teacher" and mobile_user.teacher_id:
                            user_type = "teacher"
                            user_id = mobile_user.teacher_id
                        elif mobile_user.user_type == "parent" and mobile_user.student_id:
                            user_type = "parent"
                            user_id = mobile_user.student_id
            if not user_type or not user_id:
                return JsonResponse({"detail": "غير مصرح"}, status=401)

        data = {}
        if request.content_type and "application/json" in request.content_type:
            try:
                data = json.loads(request.body.decode() or "{}")
            except json.JSONDecodeError:
                data = {}
        if not data:
            data = request.POST

        token = data.get("token") or data.get("fcm_token")
        if not token:
            return JsonResponse({"detail": "الرمز مفقود"}, status=400)

        platform = (data.get("platform") or "android").lower()
        device_id = data.get("device_id") or ""
        app_version = data.get("app_version") or ""
        device_name = (data.get("device_name") or data.get("deviceName") or "").strip()
        login_role = request.session.get("mobile_login_role") or data.get("login_role") or data.get("role")

        obj, created = MobileDeviceToken.objects.update_or_create(
            token=token,
            defaults={
                "user_type": user_type,
                "user_id": user_id,
                "login_role": str(login_role)[:20] if login_role else None,
                "platform": platform[:20],
                "device_id": device_id[:255],
                "device_name": device_name[:100],
                "app_version": app_version[:50],
                "last_seen_at": timezone.now(),
            },
        )
        status_code = 201 if created else 200
        return JsonResponse(
            {"status": "ok", "created": created, "platform": obj.platform},
            status=status_code,
        )


class MobileWelcomeView(TemplateView):
    template_name = "mobile/welcome.html"


class MobileSessionRequiredMixin:
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        user_id = request.session.get("mobile_user_id")
        user_type = request.session.get("mobile_user_type")
        if not user_id or not user_type or (
            self.allowed_roles and user_type not in self.allowed_roles
        ):
            return redirect("mobile:welcome")

        user = self._resolve_mobile_profile(user_type, user_id)
        if not user:
            request.session.pop("mobile_user_type", None)
            request.session.pop("mobile_user_id", None)
            request.session.pop("mobile_user_label", None)
            request.session.pop("mobile_login_time", None)
            return redirect("mobile:welcome")

        request.mobile_profile = user
        self._sync_device_token(request, user_type, user_id)
        return super().dispatch(request, *args, **kwargs)

    def _resolve_mobile_profile(self, user_type, user_id):
        if user_type == "teacher":
            return Teacher.objects.filter(id=user_id).first()
        if user_type == "parent":
            return Student.objects.filter(id=user_id).first()
        return None

    def _sync_device_token(self, request, user_type, user_id):
        token = request.COOKIES.get("expo_push_token")
        if not token:
            return
        platform = (request.COOKIES.get("expo_platform") or "android").lower()
        app_version = request.COOKIES.get("expo_app_version") or ""
        login_role = request.session.get("mobile_login_role")
        try:
            MobileDeviceToken.objects.update_or_create(
                token=token,
                defaults={
                    "user_type": user_type,
                    "user_id": user_id,
                    "login_role": str(login_role)[:20] if login_role else None,
                    "platform": platform[:20],
                    "device_id": "",
                    "app_version": app_version[:50],
                    "last_seen_at": timezone.now(),
                },
            )
        except Exception:
            return


class MobileDashboardRedirectView(View):
    def get(self, request, *args, **kwargs):
        user_type = request.session.get("mobile_user_type")
        if user_type == "teacher":
            return redirect("mobile:teacher_dashboard")
        if user_type == "parent":
            return redirect("mobile:parent_dashboard")
        return redirect("mobile:welcome")


class TeacherDashboardView(MobileSessionRequiredMixin, TemplateView):
    template_name = "mobile/teacher_dashboard.html"
    allowed_roles = ["teacher"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.request.mobile_profile

        subjects = Subject.objects.filter(teachers=teacher).distinct()
        classroom_qs = self._get_teacher_classrooms(teacher, subjects)
        students_qs = self._get_teacher_students(classroom_qs)

        attendance_qs = TeacherAttendance.objects.filter(teacher=teacher).order_by("-date")
        attendance_summary = attendance_qs.aggregate(
            present=Count("id", filter=Q(status="present"))
        )
        now = timezone.now()
        current_year, current_month = now.year, now.month
        monthly_attendance_qs = attendance_qs.filter(
            date__year=current_year, date__month=current_month
        )
        monthly_present_days = monthly_attendance_qs.filter(status="present").count()
        monthly_absent_days = monthly_attendance_qs.exclude(status="present").count()
        monthly_total_sessions = sum(
            (att.total_sessions for att in monthly_attendance_qs if att.status == "present"),
            Decimal("0"),
        )

        classroom_details = []
        for classroom in classroom_qs:
            students = Student.objects.filter(
                classroom_enrollments__classroom=classroom
            ).order_by("full_name").distinct()
            classroom_subjects = Subject.objects.filter(
                classroomsubject__classroom=classroom, teachers=teacher
            ).distinct()
            class_tests = []
            for test in ListeningTest.objects.filter(teacher=teacher, classroom=classroom):
                assignments = list(test.assignments.all())
                class_tests.append(
                    {
                        "test": test,
                        "total_assignments": len(assignments),
                        "listened_count": len([a for a in assignments if a.is_listened]),
                    }
                )

            exam_grades_qs = (
                ExamGrade.objects.filter(
                    exam__classroom=classroom,
                    exam__subject__in=subjects,
                )
                .select_related("exam", "exam__subject", "student")
                .order_by("-exam__exam_date", "student__full_name")
            )
            exam_buckets = {}
            for grade in exam_grades_qs:
                bucket = exam_buckets.setdefault(
                    grade.exam_id, {"exam": grade.exam, "grades": []}
                )
                bucket["grades"].append(grade)
            class_grades = (
                ExamGrade.objects.filter(
                    exam__classroom=classroom,
                    exam__subject__in=subjects,
                )
                .select_related("exam", "exam__subject", "student")
                .order_by("-exam__exam_date")[:5]
            )
            classroom_details.append(
                {
                    "classroom": classroom,
                    "students": students,
                    "subjects": classroom_subjects,
                    "tests": class_tests,
                    "exam_results": list(exam_buckets.values()),
                    "recent_grades": class_grades,
                }
            )

        subjects_overview = []
        for subject in subjects:
            subject_classes = classroom_qs.filter(classroomsubject__subject=subject).distinct()
            class_blocks = []
            for classroom in subject_classes:
                class_students = Student.objects.filter(
                    classroom_enrollments__classroom=classroom
                ).order_by("full_name").distinct()
                exams_qs = Exam.objects.filter(
                    subject=subject, classroom=classroom
                ).order_by("-exam_date")[:3]
                exam_blocks = []
                for exam in exams_qs:
                    grades_qs = ExamGrade.objects.filter(exam=exam).select_related("student")
                    avg_grade = grades_qs.aggregate(avg=Avg("grade")).get("avg")
                    exam_blocks.append(
                        {
                            "exam": exam,
                            "avg_grade": avg_grade,
                            "grades": list(grades_qs.order_by("-grade")[:5]),
                        }
                    )
                class_blocks.append(
                    {
                        "classroom": classroom,
                        "students": class_students,
                        "exams": exam_blocks,
                    }
                )
            subjects_overview.append({"subject": subject, "classes": class_blocks})

        # Teacher profile-style info
        branch_rate_labels = [
            ("hourly_rate_scientific", "أجر العلمي"),
            ("hourly_rate_literary", "أجر الأدبي"),
            ("hourly_rate_ninth", "أجر التاسع"),
            ("hourly_rate_preparatory", "أجر الإعدادي"),
        ]
        branch_rates = []
        for field, label in branch_rate_labels:
            rate = getattr(teacher, field, None)
            if rate is not None:
                branch_rates.append({"label": label, "rate": rate})

        attendance_stats = {
            "total": attendance_qs.count(),
            "present": attendance_qs.filter(status="present").count(),
            "absent": attendance_qs.filter(status="absent").count(),
            "late": attendance_qs.filter(status="late").count(),
        }

        latest_attendance_date = attendance_qs.first().date if attendance_qs.exists() else None
        latest_attendance_entries = (
            attendance_qs.filter(date=latest_attendance_date) if latest_attendance_date else []
        )

        month_names = dict(ManualTeacherSalary.MONTH_CHOICES)
        branches = teacher.get_branches_list() or [teacher.branch] if getattr(teacher, "branch", None) else []
        branch_monthly_tables = []
        for branch in branches:
            hourly_rate = teacher.get_hourly_rate_for_branch(branch)
            monthly_qs = TeacherAttendance.objects.filter(
                teacher=teacher, branch=branch, status="present"
            )
            monthly_totals = {}
            for att in monthly_qs:
                key = (att.date.year, att.date.month)
                monthly_totals[key] = monthly_totals.get(key, Decimal("0.00")) + att.total_sessions

            rows = []
            for (year_num, month_num), total_sessions in sorted(monthly_totals.items()):
                if total_sessions <= 0:
                    continue
                total_salary = total_sessions * (hourly_rate or Decimal("0.00"))
                month_name = month_names.get(month_num, str(month_num))
                rows.append(
                    {
                        "month_label": f"{month_name} - {year_num}",
                        "total_sessions": total_sessions,
                        "total_salary": total_salary,
                    }
                )
            if rows:
                branch_title = dict(Teacher.BranchChoices.choices).get(branch, branch)
                branch_monthly_tables.append(
                    {
                        "branch": branch,
                        "branch_title": branch_title,
                        "hourly_rate": hourly_rate,
                        "rows": rows,
                    }
                )

        recent_grades = (
            ExamGrade.objects.filter(
                exam__subject__in=subjects, exam__classroom__in=classroom_qs
            )
            .select_related("exam", "exam__subject", "exam__classroom", "student")
            .order_by("-exam__exam_date", "student__full_name")[:8]
        )

        exams = Exam.objects.filter(subject__in=subjects).order_by("-exam_date")[:5]
        advances = TeacherAdvance.objects.filter(teacher=teacher).order_by("-date")[:6]
        all_advances = TeacherAdvance.objects.filter(teacher=teacher)
        total_advances_amount = (
            all_advances.aggregate(total=Sum("amount")).get("total") or Decimal("0")
        )
        outstanding_advances = sum(
            (advance.outstanding_amount for advance in all_advances), Decimal("0")
        )
        advance_account = teacher.get_teacher_advance_account()
        advance_account_balance = (
            advance_account.get_net_balance() if advance_account else Decimal("0")
        )
        salaries = ManualTeacherSalary.objects.filter(
            teacher=teacher
        ).order_by("-year", "-month")[:6]
        salary_summary = {
            "latest": salaries.first(),
            "unpaid_count": ManualTeacherSalary.objects.filter(
                teacher=teacher, is_paid=False
            ).count(),
            "outstanding_advances": outstanding_advances,
            "total_advances": total_advances_amount,
            "monthly_salary_estimate": teacher.calculate_monthly_salary(
                year=current_year, month=current_month
            ),
            "monthly_present_days": monthly_present_days,
            "monthly_absent_days": monthly_absent_days,
            "monthly_total_sessions": monthly_total_sessions,
            "advance_account_balance": advance_account_balance,
        }

        listening_tests = (
            ListeningTest.objects.filter(teacher=teacher)
            .prefetch_related("classroom", "assignments__student")
            .order_by("-created_at")[:5]
        )
        for test in listening_tests:
            assignments = list(test.assignments.all())
            test.total_assignments = len(assignments)
            test.listened_count = len([a for a in assignments if a.is_listened])

        warning_choices = StudentWarning.Severity.choices

        context.update(
            {
                "teacher": teacher,
                "subjects": subjects,
                "classrooms": classroom_details,
                "students_count": students_qs.count(),
                "attendance_records": attendance_qs[:7],
                "monthly_attendance": monthly_attendance_qs,
                "attendance_summary": attendance_summary,
                "recent_grades": recent_grades,
                "subjects_overview": subjects_overview,
                "branch_rates": branch_rates,
                "attendance_stats": attendance_stats,
                "latest_attendance_entries": latest_attendance_entries,
                "branch_monthly_tables": branch_monthly_tables,
                "exams": exams,
                "advances": advances,
                "salaries": salaries,
                "salary_summary": salary_summary,
                "advance_account": advance_account,
                "listening_tests": listening_tests,
                "warning_choices": warning_choices,
                "active_tab": "home",
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        teacher = request.mobile_profile
        classrooms = self._get_teacher_classrooms(teacher)
        students_qs = self._get_teacher_students(classrooms)
        if action == "record_listening":
            return self._handle_listening_form(request, teacher, classrooms, students_qs)
        if action == "create_test":
            return self._handle_create_test(request, teacher, classrooms)
        if action == "create_warning":
            return self._handle_warning_form(request, teacher, students_qs)
        return redirect("mobile:teacher_dashboard")

    def _handle_listening_form(self, request, teacher, classrooms, students_qs):
        classroom_id = request.POST.get("listening_classroom_id")
        student_id = request.POST.get("listening_student_id")
        title = (request.POST.get("listening_title") or "").strip()
        note = (request.POST.get("listening_note") or "").strip()
        raw_grade = (request.POST.get("listening_grade") or "").strip()
        raw_max_grade = (request.POST.get("listening_max_grade") or "10").strip()

        if not classroom_id or not student_id:
            messages.error(request, "يرجى اختيار الشعبة والطالب.")
            return redirect("mobile:teacher_dashboard")

        classroom = classrooms.filter(id=classroom_id).first()
        if not classroom:
            messages.error(request, "الشعبة غير مرتبطة بهذا المدرس.")
            return redirect("mobile:teacher_dashboard")

        student = students_qs.filter(
            id=student_id,
            classroom_enrollments__classroom=classroom,
        ).distinct().first()
        if not student:
            messages.error(request, "الطالب غير موجود ضمن الشعبة المحددة.")
            return redirect("mobile:teacher_dashboard")

        if not title:
            title = f"تسميع {timezone.now().date().isoformat()}"

        grade_value = None
        if raw_grade:
            try:
                grade_value = Decimal(raw_grade.replace(",", "."))
            except InvalidOperation:
                grade_value = None
        try:
            max_grade_value = Decimal(raw_max_grade.replace(",", "."))
            if max_grade_value <= 0:
                max_grade_value = Decimal("10.00")
        except InvalidOperation:
            max_grade_value = Decimal("10.00")

        test = ListeningTest.objects.create(
            teacher=teacher,
            title=title,
            description=note,
            classroom=classroom,
            max_grade=max_grade_value,
        )
        assignment = ListeningTestAssignment.objects.create(
            test=test,
            student=student,
            is_listened=True,
            grade=grade_value,
            note=note,
        )

        grade_label = (
            f" (grade: {assignment.grade} / {test.max_grade})" if assignment.grade is not None else ""
        )
        MobileNotification.objects.create(
            student=student,
            teacher=teacher,
            notification_type="test_assignment",
            title="تم تسجيل تسميع",
            message=f"{test.title} - {classroom.name}{grade_label}",
        )

        messages.success(request, "تم تسجيل التسميع وإضافته إلى ملف الطالب.")
        return redirect("mobile:teacher_dashboard")

    def _handle_create_test(self, request, teacher, classrooms):
        title = request.POST.get("test_title", "").strip()
        description = request.POST.get("test_description", "").strip()
        classroom_id = request.POST.get("test_classroom_id")
        raw_max_grade = (request.POST.get("test_max_grade") or "10").strip()

        if not title or not classroom_id:
            messages.error(request, "يرجى إدخال عنوان الشعبة")
            return redirect("mobile:teacher_dashboard")

        classroom = classrooms.filter(id=classroom_id).first()
        if not classroom:
            messages.error(request, "الشعبة غير معتمدة.")
            return redirect("mobile:teacher_dashboard")

        selected_ids = {
            int(pk) for pk in request.POST.getlist("test_students") if pk.isdigit()
        }
        try:
            max_grade_value = Decimal(raw_max_grade.replace(",", "."))
            if max_grade_value <= 0:
                max_grade_value = Decimal("10.00")
        except InvalidOperation:
            max_grade_value = Decimal("10.00")

        test = ListeningTest.objects.create(
            teacher=teacher,
            title=title,
            description=description,
            classroom=classroom,
            max_grade=max_grade_value,
        )

        assigned_students = Student.objects.filter(
            classroom_enrollments__classroom=classroom
        ).distinct()
        for student in assigned_students:
            is_listened = student.id in selected_ids
            raw_grade = request.POST.get(f"grade_{student.id}", "").strip()
            grade_value = None
            if is_listened and raw_grade:
                try:
                    grade_value = Decimal(raw_grade.replace(",", "."))
                except InvalidOperation:
                    grade_value = None
            note = ""
            if not is_listened:
                note = f"لم يتم التسميع في {test.title}"
            ListeningTestAssignment.objects.create(
                test=test,
                student=student,
                is_listened=is_listened,
                grade=grade_value,
                note=note,
            )

        messages.success(request, "تم إنشاء الاختبار وإضافة الطلاب.")
        return redirect("mobile:teacher_dashboard")

    def _handle_warning_form(self, request, teacher, students_qs):
        student_id = request.POST.get("warning_student_id") or request.POST.get("student_id")
        classroom_id = request.POST.get("warning_classroom_id") or request.POST.get("classroom_id")
        title = (
            request.POST.get("warning_title")
            or request.POST.get("title")
            or ""
        ).strip()
        details = (
            request.POST.get("warning_details")
            or request.POST.get("note")
            or request.POST.get("details")
            or ""
        ).strip()
        severity = (
            request.POST.get("warning_severity")
            or request.POST.get("severity")
            or StudentWarning.Severity.WARNING
        )
        if severity not in StudentWarning.Severity.values:
            severity = StudentWarning.Severity.WARNING

        if not student_id or not title:
            messages.error(request, "يرجى اختيار طالب وكتابة عنوان الإنذار.")
            return redirect("mobile:teacher_dashboard")

        student_filters = {"id": student_id}
        if classroom_id:
            student_filters["classroom_enrollments__classroom_id"] = classroom_id
        student = students_qs.filter(**student_filters).distinct().first()
        if not student:
            messages.error(request, "الطالب غير موجود في الشعبة.")
            return redirect("mobile:teacher_dashboard")

        warning = StudentWarning.objects.create(
            student=student,
            title=title,
            details=details,
            severity=severity,
            created_by=None,
        )
        MobileNotification.objects.create(
            student=warning.student,
            teacher=teacher,
            notification_type="warning",
            title="تم إضافة إنذار",
            message=f"{warning.title} - {warning.details or 'بدون تفاصيل'}",
        )
        messages.success(request, "تم تسجيل الإنذار بنجاح.")
        return redirect("mobile:teacher_dashboard")

    def _get_teacher_classrooms(self, teacher, subjects=None):
        if subjects is None:
            subjects = Subject.objects.filter(teachers=teacher).distinct()
        return Classroom.objects.filter(
            classroomsubject__subject__in=subjects
        ).distinct()

    def _get_teacher_students(self, classrooms):
        return Student.objects.filter(
            classroom_enrollments__classroom__in=classrooms
        ).distinct().order_by("full_name")


class ListeningTestAssignmentToggleView(MobileSessionRequiredMixin, View):
    allowed_roles = ["teacher"]

    def post(self, request, test_id, student_id, *args, **kwargs):
        teacher = request.mobile_profile
        test = get_object_or_404(ListeningTest, pk=test_id, teacher=teacher)
        assignment = get_object_or_404(
            ListeningTestAssignment, test=test, student_id=student_id
        )

        assignment.is_listened = not assignment.is_listened
        assignment.save()
        messages.success(request, "تم تحديث حالة التسميع.")
        return redirect("mobile:teacher_dashboard")


class TeacherStudentDetailView(MobileSessionRequiredMixin, TemplateView):
    template_name = "mobile/teacher_student_detail.html"
    allowed_roles = ["teacher"]

    def _get_teacher_classrooms(self, teacher):
        subjects = Subject.objects.filter(teachers=teacher).distinct()
        return Classroom.objects.filter(
            classroomsubject__subject__in=subjects
        ).distinct()

    def _get_teacher_students(self, classrooms):
        return Student.objects.filter(
            classroom_enrollments__classroom__in=classrooms
        ).distinct().order_by("full_name")

    def _resolve_context_objects(self):
        teacher = self.request.mobile_profile
        classrooms = self._get_teacher_classrooms(teacher)
        students_qs = self._get_teacher_students(classrooms)
        student = get_object_or_404(students_qs, pk=self.kwargs["student_id"])
        classroom_id = self.request.GET.get("classroom_id")
        student_classrooms = classrooms.filter(enrollments__student=student).distinct()
        selected_classroom = student_classrooms.filter(id=classroom_id).first()
        if not selected_classroom:
            selected_classroom = student_classrooms.first()
        return teacher, student, student_classrooms, selected_classroom

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher, student, student_classrooms, selected_classroom = (
            self._resolve_context_objects()
        )
        # Restrict exams to subjects assigned to this teacher inside the student's classroom(s).
        if selected_classroom:
            teacher_subjects = Subject.objects.filter(
                classroomsubject__classroom=selected_classroom,
                teachers=teacher,
            ).distinct()
            classroom_scope = [selected_classroom]
        else:
            teacher_subjects = Subject.objects.filter(
                classroomsubject__classroom__in=student_classrooms,
                teachers=teacher,
            ).distinct()
            classroom_scope = student_classrooms

        # Fallback for legacy data where teacher-subject mapping is missing.
        if not teacher_subjects.exists():
            teacher_subjects = Subject.objects.filter(
                classroomsubject__classroom__in=classroom_scope
            ).distinct()

        exams_qs = Exam.objects.filter(
            classroom__in=classroom_scope,
            subject__in=teacher_subjects,
        ).select_related("subject", "classroom")

        # Fallback 1: teacher subjects generally (without requiring ClassroomSubject mapping).
        if not exams_qs.exists():
            exams_qs = Exam.objects.filter(
                classroom__in=classroom_scope,
                subject__teachers=teacher,
            ).select_related("subject", "classroom")

        # Fallback 2: all classroom exams, to avoid empty state with legacy/incomplete mappings.
        if not exams_qs.exists():
            exams_qs = Exam.objects.filter(
                classroom__in=classroom_scope,
            ).select_related("subject", "classroom")

        exams_qs = exams_qs.order_by("-exam_date", "-created_at")
        student_exam_grades = {
            grade.exam_id: grade
            for grade in ExamGrade.objects.filter(
                student=student,
                exam__in=exams_qs,
            ).select_related("exam")
        }
        exam_rows = [
            {"exam": exam, "grade": student_exam_grades.get(exam.id)}
            for exam in exams_qs
        ]

        listening_assignments = (
            ListeningTestAssignment.objects.filter(
                student=student,
                test__teacher=teacher,
            )
            .select_related("test", "test__classroom")
            .order_by("-created_at")
        )
        if selected_classroom:
            listening_assignments = listening_assignments.filter(
                test__classroom=selected_classroom
            )

        active_warnings = StudentWarning.objects.filter(
            student=student,
            is_active=True,
        ).order_by("-created_at")

        context.update(
            {
                "teacher": teacher,
                "teacher_announcements": get_teacher_announcements(teacher, limit=6, mark_read=True),
                "student": student,
                "student_classrooms": student_classrooms,
                "selected_classroom": selected_classroom,
                "exam_rows": exam_rows,
                "listening_assignments": listening_assignments,
                "active_warnings": active_warnings,
                "warning_choices": StudentWarning.Severity.choices,
                "active_tab": "home",
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        teacher, student, student_classrooms, selected_classroom = (
            self._resolve_context_objects()
        )
        action = request.POST.get("action")
        base_url = reverse_lazy(
            "mobile:teacher_student_detail",
            kwargs={"student_id": student.id},
        )
        query = f"?classroom_id={selected_classroom.id}" if selected_classroom else ""

        if action == "record_listening":
            classroom_id = request.POST.get("listening_classroom_id") or (
                str(selected_classroom.id) if selected_classroom else ""
            )
            title = (request.POST.get("listening_title") or "").strip()
            note = (request.POST.get("listening_note") or "").strip()
            raw_grade = (request.POST.get("listening_grade") or "").strip()
            raw_max_grade = (request.POST.get("listening_max_grade") or "10").strip()

            classroom = student_classrooms.filter(id=classroom_id).first()
            if not classroom:
                messages.error(request, "الشعبة غير صحيحة لهذا الطالب.")
                return redirect(f"{base_url}{query}")

            if not title:
                title = f"تسميع {timezone.now().date().isoformat()}"

            grade_value = None
            if raw_grade:
                try:
                    grade_value = Decimal(raw_grade.replace(",", "."))
                except InvalidOperation:
                    grade_value = None
            try:
                max_grade_value = Decimal(raw_max_grade.replace(",", "."))
                if max_grade_value <= 0:
                    max_grade_value = Decimal("10.00")
            except InvalidOperation:
                max_grade_value = Decimal("10.00")

            test = ListeningTest.objects.create(
                teacher=teacher,
                title=title,
                description=note,
                classroom=classroom,
                max_grade=max_grade_value,
            )
            assignment = ListeningTestAssignment.objects.create(
                test=test,
                student=student,
                is_listened=True,
                grade=grade_value,
                note=note,
            )
            grade_label = (
                f" (grade: {assignment.grade} / {test.max_grade})"
                if assignment.grade is not None
                else ""
            )
            MobileNotification.objects.create(
                student=student,
                teacher=teacher,
                notification_type="test_assignment",
                title="تم تسجيل تسميع",
                message=f"{test.title} - {classroom.name}{grade_label}",
            )
            messages.success(request, "تم تسجيل التسميع بنجاح.")
            return redirect(f"{base_url}?classroom_id={classroom.id}")

        if action == "create_warning":
            title = (request.POST.get("warning_title") or "").strip()
            details = (request.POST.get("warning_details") or "").strip()
            severity = (
                request.POST.get("warning_severity")
                or StudentWarning.Severity.WARNING
            )
            if severity not in StudentWarning.Severity.values:
                severity = StudentWarning.Severity.WARNING

            if not title:
                messages.error(request, "يرجى إدخال عنوان الإنذار.")
                return redirect(f"{base_url}{query}")

            warning = StudentWarning.objects.create(
                student=student,
                title=title,
                details=details,
                severity=severity,
                created_by=None,
            )
            MobileNotification.objects.create(
                student=warning.student,
                teacher=teacher,
                notification_type="warning",
                title="تم إضافة إنذار",
                message=f"{warning.title} - {warning.details or 'بدون تفاصيل'}",
            )
            messages.success(request, "تم تسجيل الإنذار بنجاح.")
            return redirect(f"{base_url}{query}")

        return redirect(f"{base_url}{query}")


class ParentContextMixin(MobileSessionRequiredMixin):
    allowed_roles = ["parent"]

    def _get_login_role(self):
        return self.request.session.get("mobile_login_role") or ""

    def _build_parent_context(self):
        student = self.request.mobile_profile
        login_role = self._get_login_role()
        classroom_enrollments = student.classroom_enrollments.select_related("classroom")
        classroom_list = [enrollment.classroom for enrollment in classroom_enrollments]
        notifications_qs = MobileNotification.objects.filter(student=student).order_by(
            "-created_at"
        )

        general_info = [
            ("رقم الطالب", getattr(student, "student_number", "غير متوفر")),
            ("الفرع/المعهد", getattr(student, "branch", "غير محدد")),
            (
                "السنة الدراسية",
                student.academic_year.name if student.academic_year else "غير محدد",
            ),
            ("الجنس", student.gender or "غير محدد"),
            ("رقم الهاتف", student.phone or "غير متوفر"),
            ("اسم الأب", student.father_name or "غير متوفر"),
            ("اسم الأم", student.mother_name or "غير متوفر"),
            ("العنوان", student.address or "غير متوفر"),
        ]

        return {
            "student": student,
            "classrooms": classroom_list,
            "general_info": general_info,
            "notifications_count": notifications_qs.count() + count_unread_parent_announcements(student, login_role),
        }

    def _build_recent_parent_activity(self, student, limit=4):
        login_role = self._get_login_role()
        attendance_qs = (
            Attendance.objects.filter(student=student)
            .select_related("classroom")
            .order_by("-date")[:limit]
        )
        grades_qs = (
            ExamGrade.objects.filter(student=student)
            .select_related("exam", "exam__subject", "exam__classroom")
            .order_by("-exam__exam_date", "-entered_at")[:limit]
        )
        notifications_qs = MobileNotification.objects.filter(student=student).order_by(
            "-created_at"
        )[:limit]
        latest_announcements = get_parent_announcements(student, login_role, limit=limit, mark_read=False)

        attendance_stats = Attendance.objects.filter(student=student).aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status="present")),
            absent=Count("id", filter=Q(status="absent")),
            late=Count("id", filter=Q(status="late")),
        )
        unread_notifications = MobileNotification.objects.filter(
            student=student, is_read=False
        ).count() + count_unread_parent_announcements(student, login_role)

        grade_values = [
            grade
            for grade in grades_qs
            if grade.grade is not None and grade.exam and grade.exam.max_grade
        ]
        grade_summary = {
            "count": len(grade_values),
            "average_percent": None,
        }
        if grade_values:
            valid_grade_values = [
                grade for grade in grade_values if float(grade.exam.max_grade) > 0
            ]
            total_percent = sum(
                float(grade.grade) / float(grade.exam.max_grade) * 100
                for grade in valid_grade_values
            )
            if valid_grade_values:
                grade_summary["average_percent"] = round(
                    total_percent / len(valid_grade_values), 1
                )

        return {
            "latest_attendance": attendance_qs,
            "latest_grades": grades_qs,
            "latest_notifications": notifications_qs,
            "latest_announcements": latest_announcements,
            "attendance_stats": attendance_stats,
            "grade_summary": grade_summary,
            "unread_notifications": unread_notifications,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._build_parent_context())
        return context

    def _build_financial_summary(self, enrollments):
        summary = {"total_due": 0, "total_paid": 0, "total_balance": 0}
        for enrollment in enrollments:
            net_amount = getattr(enrollment, "net_amount", 0) or 0
            paid = getattr(enrollment, "amount_paid", 0) or 0
            balance = getattr(enrollment, "balance_due", 0) or 0
            summary["total_due"] += net_amount
            summary["total_paid"] += paid
            summary["total_balance"] += balance
        return summary


class ParentDashboardView(ParentContextMixin, TemplateView):
    template_name = "mobile/parent_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.mobile_profile

        activity_context = self._build_recent_parent_activity(student, limit=4)
        warnings = StudentWarning.objects.filter(student=student, is_active=True).order_by(
            "-created_at"
        )[:4]

        active_enrollments = student.enrollments.filter(is_completed=False).select_related(
            "course"
        )
        financial_summary = self._build_financial_summary(active_enrollments)

        context.update(
            {
                "warnings": warnings,
                "financial_summary": financial_summary,
                "active_tab": "home",
            }
        )
        context.update(activity_context)
        return context


class ParentProfileView(ParentContextMixin, TemplateView):
    template_name = "mobile/parent_profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.mobile_profile
        activity_context = self._build_recent_parent_activity(student, limit=6)
        warnings = StudentWarning.objects.filter(student=student, is_active=True).order_by(
            "-created_at"
        )[:6]

        context.update(
            {
                "warnings": warnings,
                "active_tab": "profile",
            }
        )
        context.update(activity_context)
        return context


class ParentFinanceView(ParentContextMixin, TemplateView):
    template_name = "mobile/parent_finance.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.mobile_profile

        active_enrollments = student.enrollments.filter(is_completed=False).select_related(
            "course"
        )
        financial_summary = self._build_financial_summary(active_enrollments)
        receipts = StudentReceipt.objects.filter(student_profile=student).order_by(
            "-date"
        )[:10]

        context.update(
            {
                "financial_summary": financial_summary,
                "enrollments": active_enrollments,
                "receipts": receipts,
                "active_tab": "finance",
            }
        )
        return context


class ParentAttendanceView(ParentContextMixin, TemplateView):
    template_name = "mobile/parent_attendance.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.mobile_profile
        attendance = (
            Attendance.objects.filter(student=student)
            .select_related("classroom")
            .order_by("-date")
        )
        month_names = {
            1: "يناير",
            2: "فبراير",
            3: "مارس",
            4: "أبريل",
            5: "مايو",
            6: "يونيو",
            7: "يوليو",
            8: "أغسطس",
            9: "سبتمبر",
            10: "أكتوبر",
            11: "نوفمبر",
            12: "ديسمبر",
        }
        attendance_months = []
        month_lookup = {}
        for record in attendance:
            key = (record.date.year, record.date.month)
            if key not in month_lookup:
                month_label = f"{month_names.get(record.date.month, record.date.month)} {record.date.year}"
                month_block = {
                    "key": key,
                    "label": month_label,
                    "records": [],
                    "total": 0,
                    "present": 0,
                    "absent": 0,
                }
                month_lookup[key] = month_block
                attendance_months.append(month_block)
            month_block = month_lookup[key]
            month_block["records"].append(record)
            month_block["total"] += 1
            if record.status == "present":
                month_block["present"] += 1
            else:
                month_block["absent"] += 1

        context.update(
            {
                "attendance": attendance,
                "attendance_months": attendance_months,
                "active_tab": "attendance",
            }
        )
        return context


class ParentGradesView(ParentContextMixin, TemplateView):
    template_name = "mobile/parent_grades.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.mobile_profile
        grades = (
            ExamGrade.objects.filter(student=student)
            .select_related("exam", "exam__subject")
            .order_by("-exam__exam_date")[:20]
        )

        context.update(
            {
                "grades": grades,
                "active_tab": "grades",
            }
        )
        return context


class ParentNotificationsView(ParentContextMixin, TemplateView):
    template_name = "mobile/parent_notifications.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.mobile_profile
        login_role = self._get_login_role()
        notifications = MobileNotification.objects.filter(student=student).order_by(
            "-created_at"
        )[:20]
        announcements = get_parent_announcements(student, login_role, limit=20, mark_read=True)

        context.update(
            {
                "announcements": announcements,
                "notifications": notifications,
                "active_tab": "notifications",
            }
        )
        return context


class MobileLogoutView(View):
    def get(self, request, *args, **kwargs):
        user_type = request.session.get("mobile_user_type")
        user_id = request.session.get("mobile_user_id")
        login_role = request.session.get("mobile_login_role")

        token = (request.GET.get("token") or "").strip()
        device_id = (request.GET.get("device_id") or request.GET.get("deviceId") or "").strip()

        qs = MobileDeviceToken.objects.all()
        if token:
            qs = qs.filter(token=token)
        elif device_id:
            qs = qs.filter(device_id=device_id)
        if user_type and user_id:
            qs = qs.filter(user_type=user_type, user_id=user_id)
        if login_role:
            qs = qs.filter(login_role=login_role)
        if token or device_id:
            qs.delete()

        request.session.pop("mobile_user_type", None)
        request.session.pop("mobile_user_id", None)
        request.session.pop("mobile_user_label", None)
        request.session.pop("mobile_login_role", None)
        request.session.pop("mobile_login_time", None)
        return redirect("mobile:welcome")
