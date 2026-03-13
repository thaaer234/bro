# models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, time, timedelta

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'إنشاء'),
        ('update', 'تعديل'),
        ('delete', 'حذف'),
        ('login', 'دخول'),
        ('logout', 'خروج'),
        ('view', 'عرض'),
        ('other', 'أخرى'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    content_type = models.CharField(max_length=100)  # نوع المودل
    object_id = models.PositiveIntegerField(null=True, blank=True)  # معرف العنصر
    object_repr = models.CharField(max_length=200)  # وصف العنصر
    timestamp = models.DateTimeField(default=timezone.now)
    details = models.TextField(blank=True)  # تفاصيل إضافية
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    path = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'سجل النشاط'
        verbose_name_plural = 'سجلات النشاطات'

    def __str__(self):
        return f"{self.user} - {self.get_action_display()} - {self.content_type}"


class UserClickEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    path = models.CharField(max_length=255, blank=True)
    page_title = models.CharField(max_length=255, blank=True)
    element_tag = models.CharField(max_length=40, blank=True)
    element_id = models.CharField(max_length=120, blank=True)
    element_class = models.CharField(max_length=255, blank=True)
    element_text = models.CharField(max_length=255, blank=True)
    is_trusted = models.BooleanField(default=True)
    session_key = models.CharField(max_length=120, blank=True)
    client_x = models.IntegerField(null=True, blank=True)
    client_y = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'سجل النقرات'
        verbose_name_plural = 'سجلات النقرات'

    def __str__(self):
        user_label = self.user.get_full_name() if self.user else 'system'
        return f"{user_label} - {self.path} - {self.timestamp:%Y-%m-%d %H:%M}"


class SystemReport(models.Model):
    REPORT_TYPE_CHOICES = [
        ('manual', 'Manual'),
        ('scheduled', 'Scheduled'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default='manual')
    summary = models.JSONField(default=dict)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'System Report'
        verbose_name_plural = 'System Reports'

    def __str__(self):
        return f"{self.get_report_type_display()} report {self.period_start} - {self.period_end}"


class SystemReportRequest(models.Model):
    REQUESTER_TYPE_CHOICES = [
        ('admin', 'Admin'),
        ('student', 'Student'),
        ('system', 'System'),
    ]

    report = models.ForeignKey(SystemReport, on_delete=models.CASCADE, related_name='requests')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    requester_type = models.CharField(max_length=20, choices=REQUESTER_TYPE_CHOICES, default='system')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'System Report Request'
        verbose_name_plural = 'System Report Requests'

    def __str__(self):
        return f"{self.get_requester_type_display()} request {self.created_at:%Y-%m-%d %H:%M}"


class SystemReportCounts(models.Model):
    report = models.OneToOneField(SystemReport, on_delete=models.CASCADE, related_name='counts_snapshot')
    students_total = models.PositiveIntegerField(default=0)
    students_active = models.PositiveIntegerField(default=0)
    quick_students_total = models.PositiveIntegerField(default=0)
    teachers_total = models.PositiveIntegerField(default=0)
    employees_total = models.PositiveIntegerField(default=0)
    users_total = models.PositiveIntegerField(default=0)
    users_active = models.PositiveIntegerField(default=0)
    users_staff = models.PositiveIntegerField(default=0)
    users_superusers = models.PositiveIntegerField(default=0)
    users_logged_in = models.PositiveIntegerField(default=0)
    classrooms_total = models.PositiveIntegerField(default=0)
    subjects_total = models.PositiveIntegerField(default=0)
    courses_total = models.PositiveIntegerField(default=0)


class SystemReportActivitySummary(models.Model):
    report = models.OneToOneField(SystemReport, on_delete=models.CASCADE, related_name='activity_summary')
    total = models.PositiveIntegerField(default=0)


class SystemReportActivityAction(models.Model):
    report = models.ForeignKey(SystemReport, on_delete=models.CASCADE, related_name='activity_actions')
    action = models.CharField(max_length=30)
    count = models.PositiveIntegerField(default=0)


class SystemReportAttendanceStats(models.Model):
    report = models.OneToOneField(SystemReport, on_delete=models.CASCADE, related_name='attendance_stats')
    students_records = models.PositiveIntegerField(default=0)
    teachers_records = models.PositiveIntegerField(default=0)


class SystemReportTransactionSummary(models.Model):
    report = models.OneToOneField(SystemReport, on_delete=models.CASCADE, related_name='transaction_summary')
    count = models.PositiveIntegerField(default=0)
    debit_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)


class SystemReportCourseStats(models.Model):
    report = models.ForeignKey(SystemReport, on_delete=models.CASCADE, related_name='course_stats')
    course = models.ForeignKey('accounts.Course', on_delete=models.SET_NULL, null=True, blank=True)
    quick_course = models.ForeignKey('quick.QuickCourse', on_delete=models.SET_NULL, null=True, blank=True)
    course_type = models.CharField(max_length=20, blank=True)
    is_quick = models.BooleanField(default=False)
    enrollments_count = models.PositiveIntegerField(default=0)
    receipts_count = models.PositiveIntegerField(default=0)
    receipts_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    received_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    account_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)


class SystemReportClassroomStats(models.Model):
    report = models.ForeignKey(SystemReport, on_delete=models.CASCADE, related_name='classroom_stats')
    classroom = models.ForeignKey('classroom.Classroom', on_delete=models.SET_NULL, null=True, blank=True)
    students_total = models.PositiveIntegerField(default=0)
    students_in_period = models.PositiveIntegerField(default=0)


class SystemReportUserStats(models.Model):
    report = models.ForeignKey(SystemReport, on_delete=models.CASCADE, related_name='user_stats')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    full_name = models.CharField(max_length=200, blank=True)
    username = models.CharField(max_length=150, blank=True)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    permissions = models.JSONField(default=list, blank=True)
    receipts_students_count = models.PositiveIntegerField(default=0)
    receipts_students_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    receipts_quick_count = models.PositiveIntegerField(default=0)
    receipts_quick_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expenses_count = models.PositiveIntegerField(default=0)
    expenses_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    enrollments_students_count = models.PositiveIntegerField(default=0)
    enrollments_quick_count = models.PositiveIntegerField(default=0)
    attendance_students_count = models.PositiveIntegerField(default=0)
    attendance_teachers_count = models.PositiveIntegerField(default=0)
    created_students_count = models.PositiveIntegerField(default=0)
    created_quick_students_count = models.PositiveIntegerField(default=0)
    active_seconds = models.PositiveIntegerField(default=0)
    active_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    teacher_sessions_count = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    teacher_half_sessions_count = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    activity_total = models.PositiveIntegerField(default=0)
    logins = models.PositiveIntegerField(default=0)


class SystemReportUserCourseReceipt(models.Model):
    report = models.ForeignKey(SystemReport, on_delete=models.CASCADE, related_name='user_course_receipts')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    course = models.ForeignKey('accounts.Course', on_delete=models.SET_NULL, null=True, blank=True)
    quick_course = models.ForeignKey('quick.QuickCourse', on_delete=models.SET_NULL, null=True, blank=True)
    is_quick = models.BooleanField(default=False)
    count = models.PositiveIntegerField(default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)


class SystemReportUserCourseEnrollment(models.Model):
    report = models.ForeignKey(SystemReport, on_delete=models.CASCADE, related_name='user_course_enrollments')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    course = models.ForeignKey('accounts.Course', on_delete=models.SET_NULL, null=True, blank=True)
    quick_course = models.ForeignKey('quick.QuickCourse', on_delete=models.SET_NULL, null=True, blank=True)
    is_quick = models.BooleanField(default=False)
    count = models.PositiveIntegerField(default=0)


class SystemReportDiscountSummary(models.Model):
    report = models.OneToOneField(SystemReport, on_delete=models.CASCADE, related_name='discount_summary')
    student_receipts_count = models.PositiveIntegerField(default=0)
    student_receipts_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    student_receipts_discount_percent_count = models.PositiveIntegerField(default=0)
    quick_receipts_count = models.PositiveIntegerField(default=0)
    quick_receipts_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quick_receipts_discount_percent_count = models.PositiveIntegerField(default=0)
    enrollments_count = models.PositiveIntegerField(default=0)
    enrollments_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    enrollments_discount_percent_count = models.PositiveIntegerField(default=0)
    quick_enrollments_count = models.PositiveIntegerField(default=0)
    quick_enrollments_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quick_enrollments_discount_percent_count = models.PositiveIntegerField(default=0)


class SystemReportDiscountPercent(models.Model):
    report = models.ForeignKey(SystemReport, on_delete=models.CASCADE, related_name='discount_percents')
    source = models.CharField(max_length=40)
    percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    count = models.PositiveIntegerField(default=0)


class SystemReportDiscountRuleUsage(models.Model):
    report = models.ForeignKey(SystemReport, on_delete=models.CASCADE, related_name='discount_rule_usages')
    source = models.CharField(max_length=40)
    rule_name = models.CharField(max_length=200)
    percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    count = models.PositiveIntegerField(default=0)


class SystemReportTopAddress(models.Model):
    report = models.ForeignKey(SystemReport, on_delete=models.CASCADE, related_name='top_addresses')
    address = models.CharField(max_length=255)
    count = models.PositiveIntegerField(default=0)


class ReportSchedule(models.Model):
    is_enabled = models.BooleanField(default=False)
    weekday = models.IntegerField(default=0)  # Monday
    time_of_day = models.TimeField(default=time(9, 0))
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Report Schedule'
        verbose_name_plural = 'Report Schedules'

    def __str__(self):
        status = 'enabled' if self.is_enabled else 'disabled'
        return f"Weekly schedule ({status})"

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def compute_next_run(self, from_dt=None):
        base = timezone.localtime(from_dt or timezone.now())
        days_ahead = (self.weekday - base.weekday()) % 7
        candidate_date = base.date() + timedelta(days=days_ahead)
        candidate_dt = datetime.combine(candidate_date, self.time_of_day)
        candidate_dt = timezone.make_aware(candidate_dt, timezone.get_current_timezone())

        if candidate_dt <= base:
            candidate_dt += timedelta(days=7)

        return candidate_dt


class DailyEmailReportSchedule(models.Model):
    is_enabled = models.BooleanField(default=False)
    time_of_day = models.TimeField(default=time(19, 0))
    recipient_emails = models.TextField(blank=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Daily Email Report Schedule'
        verbose_name_plural = 'Daily Email Report Schedules'

    def __str__(self):
        status = 'enabled' if self.is_enabled else 'disabled'
        return f"Daily email schedule ({status})"

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def get_recipient_list(self):
        return [item.strip() for item in (self.recipient_emails or '').split(',') if item.strip()]

    def compute_next_run(self, from_dt=None):
        base = timezone.localtime(from_dt or timezone.now())
        candidate_dt = datetime.combine(base.date(), self.time_of_day)
        candidate_dt = timezone.make_aware(candidate_dt, timezone.get_current_timezone())
        if candidate_dt <= base:
            candidate_dt += timedelta(days=1)
        return candidate_dt
