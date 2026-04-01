from django import forms
from django.core.exceptions import ValidationError

from classroom.models import Classroom
from students.models import Student

from .models import (
    AcademicYear,
    QuickCourse,
    QuickCourseTimeOption,
    QuickCourseSession,
    QuickCourseSessionAttendance,
    QuickStudent,
    QuickEnrollment,
)


ARABIC_DIGITS_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def _normalize_quick_name(name):
    return " ".join((name or "").split()).casefold()


def _normalize_quick_phone(phone):
    return str(phone or "").translate(ARABIC_DIGITS_TRANSLATION)


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ["name", "year", "start_date", "end_date", "is_active"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class QuickCourseForm(forms.ModelForm):
    class Meta:
        model = QuickCourse
        fields = [
            "name",
            "name_ar",
            "course_type",
            "academic_year",
            "price",
            "duration_weeks",
            "hours_per_week",
            "description",
            "cost_center",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class QuickStudentForm(forms.ModelForm):
    gender = forms.ChoiceField(
        choices=[("", "---")] + list(Student.Gender.choices),
        required=False,
        label="الجنس",
    )
    course_track = forms.ChoiceField(
        choices=[
            ("", "مكثفات (افتراضي)"),
            ("EXAM", "امتحانية"),
        ],
        required=False,
        label="نوع الدورة",
    )

    class Meta:
        model = QuickStudent
        fields = ["full_name", "phone", "student_type", "course_track", "academic_year", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        student = getattr(self.instance, "student", None)
        if student:
            self.fields["gender"].initial = student.gender
        self.fields["course_track"].initial = (
            "EXAM" if getattr(self.instance, "course_track", None) == "EXAM" else ""
        )

    def clean_phone(self):
        phone = _normalize_quick_phone(self.cleaned_data.get("phone", "").strip())
        if not phone:
            raise ValidationError("يرجى إدخال رقم هاتف صالح.")
        if not phone.isdigit():
            raise ValidationError("يجب أن يحتوي رقم الهاتف على أرقام فقط.")
        if len(phone) != 10:
            raise ValidationError("رقم الهاتف يجب أن يتكون من 10 أرقام.")
        return phone

    def clean(self):
        cleaned = super().clean()
        full_name = cleaned.get("full_name")
        phone = cleaned.get("phone")
        cleaned["course_track"] = cleaned.get("course_track") or "INTENSIVE"
        current_quick_student_id = getattr(self.instance, "pk", None)

        if full_name:
            normalized_name = _normalize_quick_name(full_name)
            existing_name_match = next(
                (
                    student
                    for student in QuickStudent.objects.exclude(pk=current_quick_student_id).only(
                        "id", "full_name", "phone"
                    )
                    if _normalize_quick_name(student.full_name) == normalized_name
                ),
                None,
            )
            if existing_name_match:
                self.add_error(
                    "full_name",
                    f"الطالب السريع موجود مسبقاً باسم: {existing_name_match.full_name}",
                )

        if phone:
            normalized_phone = _normalize_quick_phone(phone)
            existing_phone_match = next(
                (
                    student
                    for student in QuickStudent.objects.exclude(pk=current_quick_student_id).only(
                        "id", "full_name", "phone"
                    )
                    if _normalize_quick_phone(student.phone) == normalized_phone
                ),
                None,
            )
            if existing_phone_match:
                self.add_error(
                    "phone",
                    f"رقم الهاتف موجود مسبقاً باسم: {existing_phone_match.full_name}",
                )

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=commit)
        gender = self.cleaned_data.get("gender", "")
        student = getattr(instance, "student", None)
        if student is not None and student.gender != (gender or ""):
            student.gender = gender or ""
            if commit:
                student.save(update_fields=["gender"])
        return instance


class QuickEnrollmentForm(forms.ModelForm):
    class Meta:
        model = QuickEnrollment
        fields = [
            "student",
            "course",
            "enrollment_date",
            "net_amount",
            "discount_percent",
            "discount_amount",
            "payment_method",
        ]
        widgets = {
            "enrollment_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = QuickStudent.objects.filter(is_active=True)
        self.fields["course"].queryset = QuickCourse.objects.filter(is_active=True)

        if "course" in self.data:
            try:
                course_id = int(self.data.get("course"))
                course = QuickCourse.objects.get(id=course_id)
                self.fields["net_amount"].initial = course.price
            except (ValueError, TypeError, QuickCourse.DoesNotExist):
                pass
        elif self.instance and self.instance.course:
            self.fields["net_amount"].initial = self.instance.course.price


class QuickCourseSessionForm(forms.ModelForm):
    class Meta:
        model = QuickCourseSession
        fields = [
            "title",
            "code",
            "min_capacity",
            "capacity",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "meeting_days",
            "room_name",
            "notes",
            "is_active",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class QuickCourseTimeOptionForm(forms.ModelForm):
    class Meta:
        model = QuickCourseTimeOption
        fields = [
            "title",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "meeting_days",
            "min_capacity",
            "max_capacity",
            "preferred_room",
            "priority",
            "is_active",
            "notes",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class QuickClassroomForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ["name", "min_capacity", "max_capacity", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.class_type = "course"
        self.instance.branches = None

    def clean(self):
        cleaned_data = super().clean()
        self.instance.class_type = "course"
        self.instance.branches = None
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.class_type = "course"
        instance.branches = None
        if commit:
            instance.save()
        return instance


class QuickSessionAssignStudentsForm(forms.Form):
    enrollment_ids = forms.ModelMultipleChoiceField(
        queryset=QuickEnrollment.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="الطلاب غير الموزعين",
    )

    def __init__(self, *args, session=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session
        if session is None:
            return
        self.fields["enrollment_ids"].queryset = (
            QuickEnrollment.objects.filter(
                course=session.course,
                is_completed=False,
                student__is_active=True,
                session_assignment__isnull=True,
            )
            .select_related("student")
            .order_by("student__full_name")
        )


class QuickSessionTransferForm(forms.Form):
    source_session = forms.ModelChoiceField(queryset=QuickCourseSession.objects.none(), label="من الكلاس")
    target_session = forms.ModelChoiceField(queryset=QuickCourseSession.objects.none(), label="إلى الكلاس")
    enrollment_ids = forms.ModelMultipleChoiceField(
        queryset=QuickEnrollment.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="الطلاب",
    )

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        sessions = QuickCourseSession.objects.none()
        if course is not None:
            sessions = course.sessions.filter(is_active=True).order_by("start_date", "start_time", "title")
        self.fields["source_session"].queryset = sessions
        self.fields["target_session"].queryset = sessions
        self.fields["enrollment_ids"].queryset = (
            QuickEnrollment.objects.filter(
                course=course,
                is_completed=False,
                student__is_active=True,
                session_assignment__isnull=False,
            )
            .select_related("student", "session_assignment__session")
            .order_by("student__full_name")
            if course is not None
            else QuickEnrollment.objects.none()
        )

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get("source_session")
        target = cleaned.get("target_session")
        enrollments = cleaned.get("enrollment_ids")
        if source and target and source == target:
            self.add_error("target_session", "يجب اختيار كلاس مختلف للنقل.")
        if source and enrollments:
            invalid = [
                enrollment.student.full_name
                for enrollment in enrollments
                if getattr(getattr(enrollment, "session_assignment", None), "session_id", None) != source.id
            ]
            if invalid:
                raise ValidationError("بعض الطلاب المحددين ليسوا ضمن الكلاس المصدر.")
        return cleaned


class QuickSessionAttendanceBulkForm(forms.Form):
    attendance_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), label="تاريخ الحضور")

    def __init__(self, *args, session=None, assignments=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session
        self.assignments = list(assignments or [])

        for assignment in self.assignments:
            field_prefix = f"student_{assignment.enrollment_id}"
            self.fields[f"{field_prefix}_status"] = forms.ChoiceField(
                choices=QuickCourseSessionAttendance.STATUS_CHOICES,
                initial="present",
                label=assignment.enrollment.student.full_name,
            )
            self.fields[f"{field_prefix}_notes"] = forms.CharField(
                required=False,
                label=f"ملاحظات {assignment.enrollment.student.full_name}",
            )
