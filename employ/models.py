from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


# =============================
# Employee & Permissions
# =============================

class EmployeeShiftSnapshot:
    def __init__(self, employee):
        self.employee = employee
        self.name = 'دوام مخصص'
        self.start_time = employee.work_start_time
        self.end_time = employee.work_end_time
        self.grace_period_minutes = employee.work_grace_period_minutes or 0
        self.break_seconds = (employee.work_break_minutes or 0) * 60
        self.required_work_seconds = employee.get_required_daily_seconds()
        self.is_night_shift = self.end_time <= self.start_time if self.start_time and self.end_time else False

    def get_bounds_for_date(self, target_date):
        start_dt = timezone.make_aware(datetime.combine(target_date, self.start_time))
        end_dt = timezone.make_aware(datetime.combine(target_date, self.end_time))
        if self.is_night_shift or end_dt <= start_dt:
            end_dt += timedelta(days=1)
        return start_dt, end_dt


class Employee(models.Model):
    """الموظف: مرتبط بمستخدم النظام، ويُمنح صلاحيات ميزات مباشرةً عبر EmployeePermission."""

    PAYROLL_METHOD_CHOICES = [
        ('monthly', 'شهري'),
        ('hourly', 'ساعي'),
        ('mixed', 'مختلط'),
    ]

    # حقل الربط مع مستخدم Django
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')

    # حقول اختيارية للإدارة
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='رقم الهاتف')
    hire_date = models.DateField(blank=True, null=True, verbose_name='تاريخ التعيين')
    employee_code = models.CharField(max_length=30, unique=True, blank=True, null=True, verbose_name='الرقم الوظيفي')
    biometric_user_id = models.CharField(max_length=30, unique=True, blank=True, null=True, verbose_name='معرف البصمة')
    national_id = models.CharField(max_length=30, blank=True, null=True, verbose_name='الرقم الوطني')
    address = models.TextField(blank=True, null=True, verbose_name='العنوان')

    # الراتب الإجمالي حسب العقد
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='الراتب الإجمالي حسب العقد')
    payroll_method = models.CharField(max_length=20, choices=PAYROLL_METHOD_CHOICES, default='monthly', verbose_name='طريقة حساب الراتب')
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='أجر الساعة')
    overtime_hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='أجر ساعة الإضافي')
    required_monthly_hours = models.PositiveIntegerField(default=0, verbose_name='الساعات المطلوبة شهريًا')
    auto_calculate_hourly_rate = models.BooleanField(default=True, verbose_name='حساب سعر الساعة تلقائيًا')
    overtime_multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.00'), verbose_name='معامل الإضافي')
    holiday_overtime_multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('2.00'), verbose_name='معامل إضافي العطلة')
    deduction_multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.00'), verbose_name='معامل الخصم')
    work_start_time = models.TimeField(blank=True, null=True, verbose_name='بداية الدوام')
    work_end_time = models.TimeField(blank=True, null=True, verbose_name='نهاية الدوام')
    required_daily_hours = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name='ساعات الدوام اليومية')
    work_grace_period_minutes = models.PositiveIntegerField(default=0, verbose_name='سماح التأخير بالدقائق')
    work_break_minutes = models.PositiveIntegerField(default=0, verbose_name='الاستراحة بالدقائق')
    weekend_days = models.CharField(max_length=20, blank=True, default='4,5', verbose_name='أيام العطلة الأسبوعية')
    annual_leave_days = models.PositiveIntegerField(default=14, verbose_name='الإجازات النظامية السنوية')
    sick_leave_days = models.PositiveIntegerField(default=7, verbose_name='الإجازات المرضية السنوية')

    # مسمى وظيفي (اختياري، لا يوزّع صلاحيات تلقائيًا)
    POSITION_CHOICES = [
        ('admin', 'مسؤول'),
        ('accountant', 'محاسب'),
        ('hr', 'موارد بشرية'),
        ('staff', 'موظف'),
    ]
    WEEKDAY_LABELS = {
        0: 'الاثنين',
        1: 'الثلاثاء',
        2: 'الأربعاء',
        3: 'الخميس',
        4: 'الجمعة',
        5: 'السبت',
        6: 'الأحد',
    }
    position = models.CharField(max_length=50, choices=POSITION_CHOICES, default='staff', verbose_name='الوظيفة')
    contract_type = models.CharField(
        max_length=20,
        choices=[
            ('permanent', 'دائم'),
            ('temporary', 'مؤقت'),
            ('probation', 'تجربة'),
            ('freelance', 'تعاقد حر'),
        ],
        default='permanent',
        verbose_name='نوع العقد'
    )
    contract_start = models.DateField(blank=True, null=True, verbose_name='بداية العقد')
    contract_end = models.DateField(blank=True, null=True, verbose_name='نهاية العقد')
    employment_status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'على رأس العمل'),
            ('suspended', 'موقوف'),
            ('vacation', 'في إجازة'),
            ('terminated', 'منتهي الخدمة'),
        ],
        default='active',
        verbose_name='حالة الموظف'
    )
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name='القسم'
    )
    job_title = models.ForeignKey(
        'JobTitle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name='المسمى الوظيفي'
    )
    default_shift = models.ForeignKey(
        'Shift',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name='الشفت الافتراضي'
    )
    attendance_policy = models.ForeignKey(
        'AttendancePolicy',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name='سياسة الدوام'
    )
    salary_rule = models.ForeignKey(
        'EmployeeSalaryRule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name='قاعدة الراتب'
    )
    emergency_contact_name = models.CharField(max_length=150, blank=True, null=True, verbose_name='اسم جهة الطوارئ')
    emergency_contact_phone = models.CharField(max_length=30, blank=True, null=True, verbose_name='هاتف جهة الطوارئ')
    profile_photo = models.ImageField(upload_to='employees/profiles/', blank=True, null=True, verbose_name='الصورة الشخصية')

    def __str__(self):
        return self.full_name or (self.user.get_username() if self.user_id else 'Employee')

    # اسم العرض للموظف (يحل مشكلة AttributeError: full_name)
    @property
    def full_name(self):
        if self.user_id:
            return self.user.get_full_name() or self.user.get_username()
        return ''

    # فحص صلاحية معينة
    def has_permission(self, code: str) -> bool:
        return self.permissions.filter(permission=code, is_granted=True).exists()

    # جميع الصلاحيات (ممنوحة/غير ممنوحة) بشكل جاهز للعرض
    def get_all_permissions(self):
        granted = set(self.permissions.filter(is_granted=True).values_list('permission', flat=True))
        return [
            {'code': code, 'label': label, 'is_granted': code in granted}
            for code, label in EmployeePermission.PERMISSION_CHOICES
        ]

    # حالة راتب شهر معيّن (مطلوبة في الفيوز)
    def get_salary_status(self, year=None, month=None):
        if year is None:
            year = timezone.now().year
        if month is None:
            month = timezone.now().month
        try:
            from accounts.models import ExpenseEntry
            qs = ExpenseEntry.objects.filter(employee=self, date__year=year, date__month=month)
            if qs.exists():
                return True

            # دعم البحث القديم بالاسم
            name_hint = (self.full_name or '').strip()
            if name_hint:
                legacy_qs = ExpenseEntry.objects.filter(
                    description__icontains=name_hint,
                    category__in=['SALARY', 'TEACHER_SALARY'],
                    date__year=year,
                    date__month=month
                )
                if legacy_qs.exists():
                    return True
            return False
        except Exception:
            return False

    # حساب مصروف رواتب الموظف (يُستخدم عند إنشاء قيود)
    def get_salary_account(self):
        from accounts.models import get_or_create_employee_salary_account
        return get_or_create_employee_salary_account(self)

    def get_cash_account(self):
        from accounts.models import Account

        code = f"121-{self.pk:04d}"
        return Account.objects.filter(code=code).first()

    @property
    def has_cash_account(self):
        return self.get_cash_account() is not None

    @property
    def effective_shift(self):
        if self.work_start_time and self.work_end_time:
            return EmployeeShiftSnapshot(self)
        return self.default_shift

    @property
    def effective_attendance_policy(self):
        return self.attendance_policy

    @property
    def effective_salary_rule(self):
        return self.salary_rule

    @property
    def payroll_method_display(self):
        return dict(self.PAYROLL_METHOD_CHOICES).get(self.payroll_method, self.payroll_method)

    def get_weekend_day_numbers(self):
        raw_value = str(self.weekend_days or '').strip()
        if not raw_value and self.attendance_policy_id:
            raw_value = str(self.attendance_policy.weekend_days or '').strip()
        if not raw_value:
            return set()
        values = set()
        for part in raw_value.split(','):
            part = part.strip()
            if part.isdigit():
                values.add(int(part))
        return {value for value in values if 0 <= value <= 6}

    def get_weekend_day_labels(self):
        return [self.WEEKDAY_LABELS[value] for value in sorted(self.get_weekend_day_numbers()) if value in self.WEEKDAY_LABELS]

    @property
    def weekend_days_display(self):
        labels = self.get_weekend_day_labels()
        return '، '.join(labels) if labels else '-'

    def get_required_daily_seconds(self):
        if self.required_daily_hours:
            return int(Decimal(self.required_daily_hours) * Decimal('3600'))
        if not self.work_start_time or not self.work_end_time:
            return self.default_shift.required_work_seconds if self.default_shift_id else 28800

        start_dt = datetime.combine(date.today(), self.work_start_time)
        end_dt = datetime.combine(date.today(), self.work_end_time)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        seconds = int((end_dt - start_dt).total_seconds()) - ((self.work_break_minutes or 0) * 60)
        return max(seconds, 0)


class Department(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name='اسم القسم')
    code = models.CharField(max_length=30, unique=True, blank=True, null=True, verbose_name='رمز القسم')
    description = models.TextField(blank=True, verbose_name='الوصف')
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'قسم'
        verbose_name_plural = 'الأقسام'
        ordering = ['name']

    def __str__(self):
        return self.name


class JobTitle(models.Model):
    name = models.CharField(max_length=150, verbose_name='المسمى الوظيفي')
    code = models.CharField(max_length=30, blank=True, null=True, verbose_name='الرمز')
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_titles',
        verbose_name='القسم'
    )
    description = models.TextField(blank=True, verbose_name='الوصف')
    is_active = models.BooleanField(default=True, verbose_name='نشط')

    class Meta:
        verbose_name = 'مسمى وظيفي'
        verbose_name_plural = 'المسميات الوظيفية'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['department', 'name'], name='unique_job_title_per_department'),
        ]

    def __str__(self):
        return self.name


class Shift(models.Model):
    name = models.CharField(max_length=120, unique=True, verbose_name='اسم الشفت')
    code = models.CharField(max_length=30, unique=True, blank=True, null=True, verbose_name='رمز الشفت')
    start_time = models.TimeField(verbose_name='وقت الدخول')
    end_time = models.TimeField(verbose_name='وقت الخروج')
    grace_period_minutes = models.PositiveIntegerField(default=0, verbose_name='وقت السماح بالدقائق')
    required_work_seconds = models.PositiveIntegerField(default=28800, verbose_name='ساعات العمل المطلوبة بالثواني')
    is_night_shift = models.BooleanField(default=False, verbose_name='دوام ليلي')
    break_seconds = models.PositiveIntegerField(default=0, verbose_name='مدة الاستراحة بالثواني')
    break_start = models.TimeField(blank=True, null=True, verbose_name='بداية الاستراحة')
    break_end = models.TimeField(blank=True, null=True, verbose_name='نهاية الاستراحة')
    is_active = models.BooleanField(default=True, verbose_name='نشط')

    class Meta:
        verbose_name = 'شفت'
        verbose_name_plural = 'الشفتات'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_bounds_for_date(self, target_date):
        start_dt = timezone.make_aware(datetime.combine(target_date, self.start_time))
        end_dt = timezone.make_aware(datetime.combine(target_date, self.end_time))
        if self.is_night_shift or end_dt <= start_dt:
            end_dt += timedelta(days=1)
        return start_dt, end_dt


class AttendancePolicy(models.Model):
    ROUNDING_CHOICES = [
        ('none', 'بدون تقريب'),
        ('minute', 'تقريب للدقيقة'),
        ('5_minutes', 'تقريب لـ 5 دقائق'),
        ('15_minutes', 'تقريب لـ 15 دقيقة'),
    ]
    HOLIDAY_CHOICES = [
        ('ignore', 'تجاهل'),
        ('treat_as_overtime', 'إضافي'),
        ('treat_as_regular', 'دوام عادي'),
    ]

    name = models.CharField(max_length=150, unique=True, verbose_name='اسم السياسة')
    late_deduction_rate = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'), verbose_name='خصم التأخير لكل ساعة')
    early_leave_deduction_rate = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'), verbose_name='خصم الخروج المبكر لكل ساعة')
    absence_deduction_rate = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('1.0000'), verbose_name='معامل خصم الغياب')
    overtime_enabled = models.BooleanField(default=True, verbose_name='حساب الإضافي')
    overtime_multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.00'), verbose_name='نسبة الإضافي')
    rounding_method = models.CharField(max_length=20, choices=ROUNDING_CHOICES, default='minute', verbose_name='طريقة التقريب')
    holiday_handling = models.CharField(max_length=20, choices=HOLIDAY_CHOICES, default='ignore', verbose_name='التعامل مع العطل')
    weekend_days = models.CharField(max_length=20, default='4,5', verbose_name='أيام العطل الأسبوعية')
    is_active = models.BooleanField(default=True, verbose_name='نشط')

    class Meta:
        verbose_name = 'سياسة دوام'
        verbose_name_plural = 'سياسات الدوام'
        ordering = ['name']

    def __str__(self):
        return self.name


class HRHoliday(models.Model):
    name = models.CharField(max_length=150, verbose_name='اسم العطلة')
    start_date = models.DateField(verbose_name='من تاريخ')
    end_date = models.DateField(verbose_name='إلى تاريخ')
    overtime_multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('2.00'), verbose_name='معامل إضافي العطلة')
    is_paid = models.BooleanField(default=True, verbose_name='عطلة مدفوعة')
    is_active = models.BooleanField(default=True, verbose_name='نشطة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')

    class Meta:
        verbose_name = 'عطلة رسمية'
        verbose_name_plural = 'العطل الرسمية'
        ordering = ['-start_date', 'name']

    def __str__(self):
        return f'{self.name} ({self.start_date} - {self.end_date})'

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError('تاريخ نهاية العطلة يجب أن يكون بعد تاريخ البداية.')


class EmployeeSalaryRule(models.Model):
    SALARY_TYPE_CHOICES = [
        ('monthly', 'شهري'),
        ('daily', 'يومي'),
        ('hourly', 'بالساعة'),
    ]
    ROUNDING_CHOICES = AttendancePolicy.ROUNDING_CHOICES

    name = models.CharField(max_length=150, unique=True, verbose_name='اسم القاعدة')
    salary_type = models.CharField(max_length=20, choices=SALARY_TYPE_CHOICES, default='monthly', verbose_name='نوع الراتب')
    overtime_enabled = models.BooleanField(default=True, verbose_name='احتساب الإضافي')
    overtime_multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.00'), verbose_name='نسبة الإضافي')
    late_deduction_enabled = models.BooleanField(default=True, verbose_name='خصم التأخير')
    absence_deduction_enabled = models.BooleanField(default=True, verbose_name='خصم الغياب')
    tax_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), verbose_name='الضريبة %')
    insurance_percent = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'), verbose_name='التأمين %')
    max_overtime_seconds = models.PositiveIntegerField(default=0, verbose_name='الحد الأعلى للإضافي بالثواني')
    max_deduction_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='الحد الأعلى للخصومات')
    rounding_method = models.CharField(max_length=20, choices=ROUNDING_CHOICES, default='minute', verbose_name='التقريب')
    is_active = models.BooleanField(default=True, verbose_name='نشط')

    class Meta:
        verbose_name = 'قاعدة راتب موظف'
        verbose_name_plural = 'قواعد رواتب الموظفين'
        ordering = ['name']

    def __str__(self):
        return self.name


class BiometricDevice(models.Model):
    name = models.CharField(max_length=150, verbose_name='اسم الجهاز')
    ip = models.GenericIPAddressField(verbose_name='عنوان IP')
    port = models.PositiveIntegerField(default=4370, verbose_name='المنفذ')
    serial = models.CharField(max_length=100, unique=True, verbose_name='الرقم التسلسلي')
    location = models.CharField(max_length=150, blank=True, verbose_name='الموقع')
    active = models.BooleanField(default=True, verbose_name='نشط')
    last_synced_at = models.DateTimeField(blank=True, null=True, verbose_name='آخر مزامنة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'جهاز بصمة'
        verbose_name_plural = 'أجهزة البصمة'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.serial})'


class BiometricLog(models.Model):
    PUNCH_TYPE_CHOICES = [
        ('check_in', 'دخول'),
        ('check_out', 'خروج'),
        ('break_out', 'خروج استراحة'),
        ('break_in', 'عودة استراحة'),
        ('unknown', 'غير معروف'),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='biometric_logs',
        verbose_name='الموظف'
    )
    device = models.ForeignKey(
        BiometricDevice,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='الجهاز'
    )
    device_user_id = models.CharField(max_length=30, verbose_name='معرف المستخدم على الجهاز')
    punch_time = models.DateTimeField(verbose_name='وقت البصمة')
    punch_type = models.CharField(max_length=20, choices=PUNCH_TYPE_CHOICES, default='unknown', verbose_name='نوع الحركة')
    raw_data = models.JSONField(default=dict, blank=True, verbose_name='البيانات الخام')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'سجل بصمة'
        verbose_name_plural = 'سجلات البصمة'
        ordering = ['-punch_time']
        constraints = [
            models.UniqueConstraint(
                fields=['device', 'device_user_id', 'punch_time', 'punch_type'],
                name='unique_biometric_log_event'
            ),
        ]

    def __str__(self):
        return f'{self.device_user_id} @ {self.punch_time:%Y-%m-%d %H:%M:%S}'

    def clean(self):
        if not self.employee_id and self.device_user_id:
            self.employee = Employee.objects.filter(biometric_user_id=self.device_user_id).first()


class EmployeeAttendance(models.Model):
    REVIEW_STATUS_CHOICES = [
        ('not_required', 'لا تحتاج مراجعة'),
        ('pending', 'بانتظار المراجعة'),
        ('justified', 'مبرر'),
        ('unjustified', 'غير مبرر'),
    ]
    STATUS_CHOICES = [
        ('present', 'حاضر'),
        ('partial', 'دوام جزئي'),
        ('late', 'متأخر'),
        ('absent', 'غائب'),
        ('vacation', 'إجازة'),
        ('weekend', 'عطلة'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records', verbose_name='الموظف')
    date = models.DateField(verbose_name='التاريخ')
    check_in = models.DateTimeField(blank=True, null=True, verbose_name='دخول')
    check_out = models.DateTimeField(blank=True, null=True, verbose_name='خروج')
    worked_seconds = models.PositiveIntegerField(default=0, verbose_name='العمل الفعلي بالثواني')
    late_seconds = models.PositiveIntegerField(default=0, verbose_name='التأخير بالثواني')
    early_leave_seconds = models.PositiveIntegerField(default=0, verbose_name='الخروج المبكر بالثواني')
    overtime_seconds = models.PositiveIntegerField(default=0, verbose_name='الإضافي بالثواني')
    absence_seconds = models.PositiveIntegerField(default=0, verbose_name='الغياب بالثواني')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='absent', verbose_name='الحالة')
    source = models.CharField(max_length=20, default='biometric', verbose_name='المصدر')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    review_status = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default='not_required', verbose_name='قرار المراجعة')
    review_notes = models.TextField(blank=True, verbose_name='ملاحظات المراجعة')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_employee_attendance', verbose_name='راجع السجل')
    reviewed_at = models.DateTimeField(blank=True, null=True, verbose_name='تاريخ المراجعة')
    is_manually_adjusted = models.BooleanField(default=False, verbose_name='معدل يدويًا')
    manual_adjustment_reason = models.TextField(blank=True, verbose_name='سبب التعديل اليدوي')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'دوام موظف'
        verbose_name_plural = 'دوام الموظفين'
        ordering = ['-date', 'employee__user__first_name']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'date'], name='unique_employee_attendance_day'),
        ]

    def __str__(self):
        return f'{self.employee} - {self.date}'


class PayrollPeriod(models.Model):
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('processing', 'قيد المعالجة'),
        ('closed', 'مغلق'),
    ]

    name = models.CharField(max_length=150, verbose_name='اسم الفترة')
    start_date = models.DateField(verbose_name='من')
    end_date = models.DateField(verbose_name='إلى')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='الحالة')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'فترة رواتب'
        verbose_name_plural = 'فترات الرواتب'
        ordering = ['-start_date']
        constraints = [
            models.UniqueConstraint(fields=['start_date', 'end_date'], name='unique_payroll_period_dates'),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError('نهاية الفترة يجب أن تكون بعد البداية.')


class EmployeePayroll(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payrolls', verbose_name='الموظف')
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='employee_payrolls', verbose_name='الفترة')
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='إجمالي الراتب')
    deductions_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='إجمالي الخصومات')
    overtime_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='إجمالي الإضافي')
    advances_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='السلف')
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='الضريبة')
    insurance_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='التأمين')
    compensation_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='التعويضات')
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='صافي الراتب')
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'مسير موظف'
        verbose_name_plural = 'مسيرات الموظفين'
        ordering = ['-generated_at']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'period'], name='unique_employee_payroll_per_period'),
        ]

    def __str__(self):
        return f'{self.employee} - {self.period}'


class EmployeePayrollLine(models.Model):
    LINE_TYPE_CHOICES = [
        ('base_salary', 'راتب أساسي'),
        ('attendance', 'دوام'),
        ('overtime', 'إضافي'),
        ('late_deduction', 'خصم تأخير'),
        ('absence_deduction', 'خصم غياب'),
        ('advance_deduction', 'خصم سلفة'),
        ('tax', 'ضريبة'),
        ('insurance', 'تأمين'),
        ('compensation', 'تعويض'),
        ('adjustment', 'تسوية'),
    ]

    payroll = models.ForeignKey(EmployeePayroll, on_delete=models.CASCADE, related_name='lines', verbose_name='المسير')
    line_type = models.CharField(max_length=30, choices=LINE_TYPE_CHOICES, verbose_name='النوع')
    title = models.CharField(max_length=150, verbose_name='العنوان')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='القيمة')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    source_reference = models.CharField(max_length=100, blank=True, verbose_name='مرجع المصدر')

    class Meta:
        verbose_name = 'سطر مسير'
        verbose_name_plural = 'سطور المسير'
        ordering = ['id']

    def __str__(self):
        return f'{self.title} - {self.amount}'


class EmployeePermission(models.Model):
    """صلاحيات الميزات تُمنح مباشرةً للموظّف (ليست أدوار ولا Groups)."""

    PERMISSION_CHOICES = [
        # == Student Management ==
        ('students_view', 'عرض قائمة الطلاب'),
        ('students_create', 'إضافة طالب جديد'),
        ('students_edit', 'تعديل بيانات الطلاب'),
        ('students_delete', 'حذف الطلاب'),
        ('students_profile', 'عرض ملف الطالب'),
        ('students_receipt', 'قطع إيصالات الطلاب'),
        ('students_statement', 'كشف حساب الطالب'),
        ('students_register_course', 'تسجيل الطالب في دورة'),
        ('students_withdraw', 'سحب الطالب من دورة'),
        ('students_export', 'تصدير بيانات الطلاب'),
        # == Teacher Management ==
        ('teachers_view', 'عرض قائمة المدرسين'),
        ('teachers_create', 'إضافة مدرس جديد'),
        ('teachers_edit', 'تعديل بيانات المدرسين'),
        ('teachers_delete', 'حذف المدرسين'),
        ('teachers_profile', 'عرض ملف المدرس'),
        ('teachers_salary', 'إدارة رواتب المدرسين'),
        ('teachers_salary_pay', 'دفع رواتب المدرسين'),
        ('teachers_salary_accrual', 'إنشاء قيود استحقاق الرواتب'),
        ('teachers_advance', 'إدارة سلف المدرسين'),
        ('teachers_advance_create', 'إنشاء سلفة للمدرس'),
        # == Attendance ==
        ('attendance_view', 'عرض سجل الحضور'),
        ('attendance_take', 'تسجيل حضور الطلاب'),
        ('attendance_edit', 'تعديل سجل الحضور'),
        ('attendance_export', 'تصدير سجل الحضور'),
        ('attendance_teacher_view', 'عرض حضور المدرسين'),
        ('attendance_teacher_take', 'تسجيل حضور المدرسين'),
        ('attendance_teacher_export', 'تصدير حضور المدرسين'),
        # == Classroom ==
        ('classroom_view', 'عرض قائمة الشعب'),
        ('classroom_create', 'إنشاء شعبة جديدة'),
        ('classroom_edit', 'تعديل الشعب'),
        ('classroom_delete', 'حذف الشعب'),
        ('classroom_assign', 'تعيين الطلاب للشعب'),
        ('classroom_students', 'عرض طلاب الشعبة'),
        ('classroom_subjects', 'إدارة مواد الشعبة'),
        ('classroom_export', 'تصدير بيانات الشعب'),
        # == Grades ==
        # ('grades_view', 'عرض العلامات'),
        # ('grades_edit', 'تعديل العلامات'),
        # ('grades_export', 'تصدير العلامات لإكسل'),
        # ('grades_print', 'طباعة كشوف العلامات'),
        # ('grades_custom_print', 'طباعة مخصصة للعلامات'),
        # == Courses/Subjects ==
        ('courses_view', 'عرض قائمة المواد'),
        ('courses_create', 'إضافة مادة جديدة'),
        ('courses_edit', 'تعديل المواد'),
        ('courses_delete', 'حذف المواد'),
        ('courses_assign_teachers', 'تعيين المدرسين للمواد'),
        # == Accounting ==
        ('accounting_dashboard', 'لوحة تحكم المحاسبة'),
        ('accounting_view', 'عرض النظام المحاسبي'),
        ('accounting_entries', 'إنشاء وتعديل قيود اليومية'),
        ('accounting_entries_post', 'ترحيل قيود اليومية'),
        ('accounting_accounts', 'إدارة دليل الحسابات'),
        ('accounting_accounts_create', 'إنشاء حسابات جديدة'),
        ('accounting_reports', 'عرض التقارير المالية'),
        ('accounting_trial_balance', 'ميزان المراجعة'),
        ('accounting_income_statement', 'قائمة الدخل'),
        ('accounting_balance_sheet', 'الميزانية العمومية'),
        ('accounting_ledger', 'دفاتر الأستاذ'),
        ('accounting_receipts', 'إيصالات الطلاب'),
        ('accounting_receipts_create', 'إنشاء إيصالات جديدة'),
        ('accounting_expenses', 'إدارة المصروفات'),
        ('accounting_expenses_create', 'تسجيل مصروفات جديدة'),
        ('accounting_budgets', 'إدارة الميزانيات'),
        ('accounting_periods', 'الفترات المحاسبية'),
        ('accounting_cost_centers', 'مراكز التكلفة'),
        ('accounting_outstanding', 'تقارير المتبقي على الطلاب'),
        ('accounting_export', 'تصدير التقارير المالية'),
        # == HR ==
        ('hr_dashboard', 'لوحة تحكم الموارد البشرية'),
        ('hr_view', 'عرض قائمة الموظفين'),
        ('hr_create', 'تسجيل موظف جديد'),
        ('hr_edit', 'تعديل بيانات الموظفين'),
        ('hr_delete', 'حذف الموظفين'),
        ('hr_profile', 'عرض ملف الموظف'),
        ('hr_permissions', 'إدارة صلاحيات الموظفين'),
        ('hr_salary', 'إدارة رواتب الموظفين'),
        ('hr_salary_pay', 'دفع رواتب الموظفين'),
        ('hr_advances', 'إدارة سلف الموظفين'),
        ('hr_advances_create', 'إنشاء سلفة للموظف'),
        ('hr_vacations', 'إدارة إجازات الموظفين'),
        ('hr_vacations_approve', 'الموافقة على الإجازات'),
        # == System ==
        ('admin_dashboard', 'الوصول للوحة التحكم الرئيسية'),
        ('admin_settings', 'إعدادات النظام العامة'),
        ('admin_users', 'إدارة المستخدمين والحسابات'),
        ('admin_backup', 'النسخ الاحتياطي واستعادة البيانات'),
        ('admin_logs', 'عرض سجلات النظام'),
        ('admin_database', 'إدارة قاعدة البيانات'),
        ('admin_maintenance', 'صيانة النظام'),
        # == Reports ==
        ('reports_dashboard', 'لوحة تحكم التقارير'),
        ('reports_students', 'تقارير الطلاب وإحصائياتهم'),
        ('reports_students_export', 'تصدير تقارير الطلاب'),
        ('reports_teachers', 'تقارير المدرسين وأدائهم'),
        ('reports_teachers_export', 'تصدير تقارير المدرسين'),
        ('reports_financial', 'التقارير المالية والمحاسبية'),
        ('reports_financial_export', 'تصدير التقارير المالية'),
        ('reports_attendance', 'تقارير الحضور والغياب'),
        ('reports_attendance_export', 'تصدير تقارير الحضور'),
        ('reports_grades', 'تقارير العلامات والدرجات'),
        ('reports_grades_export', 'تصدير تقارير العلامات'),
        ('reports_custom', 'تقارير مخصصة'),
        # == Accounting Courses ==
        ('course_accounting_view', 'عرض دورات النظام المحاسبي'),
        ('course_accounting_create', 'إنشاء دورة جديدة'),
        ('course_accounting_edit', 'تعديل الدورات'),
        ('course_accounting_pricing', 'إدارة أسعار الدورات'),
        # == Inventory & Assets ==
        ('inventory_view', 'عرض المخزون'),
        ('inventory_manage', 'إدارة المخزون'),
        ('assets_view', 'عرض الأصول'),
        ('assets_manage', 'إدارة الأصول'),
        # == Marketing ==
        ('marketing_campaigns', 'إدارة الحملات التسويقية'),
        ('marketing_leads', 'إدارة العملاء المحتملين'),
        ('marketing_analytics', 'تحليلات التسويق'),
        # == Quality ==
        ('quality_surveys', 'استطلاعات رضا الطلاب'),
        ('quality_feedback', 'إدارة التغذية الراجعة'),
        ('quality_evaluation', 'تقييم المدرسين'),
        # == Quick Students Management ==
        ('quick_students_view', 'عرض الطلاب السريعين'),
        ('quick_students_create', 'إضافة طالب سريع'),
        ('quick_students_edit', 'تعديل الطلاب السريعين'),
        ('quick_students_delete', 'حذف الطلاب السريعين'),
        ('quick_students_profile', 'عرض ملف الطالب السريع'),
        ('quick_students_receipt', 'قطع إيصالات الطلاب السريعين'),
        ('quick_students_statement', 'كشف حساب الطالب السريع'),
        ('quick_students_register', 'تسجيل الطالب السريع في دورة'),
        ('quick_students_withdraw', 'سحب الطالب السريع'),
        ('quick_students_refund', 'استرجاع الطالب السريع'),
        ('quick_students_export', 'تصدير بيانات الطلاب السريعين'),
        
        # == Exams Management ==
        ('exams_view', 'عرض الاختبارات'),
        ('exams_create', 'إنشاء اختبار جديد'),
        ('exams_edit', 'تعديل الاختبارات'),
        ('exams_delete', 'حذف الاختبارات'),
        ('exams_grades_view', 'عرض علامات الاختبار'),
        ('exams_grades_edit', 'تعديل علامات الاختبار'),
        ('exams_export', 'تصدير نتائج الاختبار'),
        ('exams_print', 'طباعة نتائج الاختبار'),
        ('exams_stats', 'إحصائيات الاختبار'),
                # == Additional Accounting ==
        ('accounting_quick_receipt', 'الإيصال الفوري'),
        ('accounting_student_withdraw', 'سحب الطالب'),
        ('accounting_withdrawn_students', 'عرض الطلاب المسحوبين'),
        ('accounting_outstanding_classroom', 'المتبقي حسب الشعبة'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='permissions')
    permission = models.CharField(max_length=50, choices=PERMISSION_CHOICES)
    is_granted = models.BooleanField(default=False, verbose_name='ممنوح')
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='مُنح بواسطة')
    granted_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ المنح')

    class Meta:
        unique_together = ('employee', 'permission')
        verbose_name = 'صلاحية موظف'
        verbose_name_plural = 'صلاحيات الموظفين'

    def __str__(self):
        return f"{self.employee.full_name} - {self.get_permission_display()}"


# =============================
# Teacher
# =============================

class Teacher(models.Model):
    class BranchChoices(models.TextChoices):
        LITERARY = 'أدبي', 'أدبي'
        SCIENTIFIC = 'علمي', 'علمي'
        NINTH_GRADE = 'تاسع', 'الصف التاسع'
        PREPARATORY = 'تمهيدي', 'التمهيدي'

    BRANCH_CHOICES = [
        ('SCIENCE', 'علمي / Science'),
        ('LITERARY', 'أدبي / Literary'), 
        ('NINTH', 'تاسع / Ninth Grade'),
        ('PREPARATORY', 'تمهيدي / Preparatory'),
    ]
    branch = models.CharField(
        max_length=20,
        choices=BRANCH_CHOICES,
        verbose_name='التخصص / Branch'
    )
        
    full_name = models.CharField(
        max_length=100,
        verbose_name='الاسم الكامل',
        validators=[MinLengthValidator(3)]
    )
    phone_number = models.CharField(
        max_length=20,
        verbose_name='رقم الهاتف',
        validators=[MinLengthValidator(8)]
    )
    branches = models.CharField(
        max_length=100,
        verbose_name='الفروع',
        help_text='الفروع التي يدرّسها المدرّس مفصولة بفاصلة'
    )
    hire_date = models.DateField(default=date.today, verbose_name='تاريخ التعيين')
    notes = models.TextField(blank=True, null=True, verbose_name='ملاحظات')

    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal('0.00'),
        verbose_name='أجر الساعة',
        help_text='الأجر عن كل حصة دراسية'
    )
    hourly_rate_scientific = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal('0.00'),
        verbose_name='Hourly Rate - Scientific'
    )
    hourly_rate_literary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal('0.00'),
        verbose_name='Hourly Rate - Literary'
    )
    hourly_rate_ninth = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal('0.00'),
        verbose_name='Hourly Rate - Ninth'
    )
    hourly_rate_preparatory = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal('0.00'),
        verbose_name='Hourly Rate - Preparatory'
    )
    monthly_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=Decimal('0.00'),
        verbose_name='راتب شهري ثابت',
        help_text='يستخدم مع نوع الراتب الشهري أو المختلط'
    )
    salary_type = models.CharField(
        max_length=20,
        choices=[
            ('hourly', 'ساعي'),
            ('monthly', 'شهري ثابت'),
            ('mixed', 'مختلط (شهري + ساعي)')
        ],
        default='hourly',
        verbose_name='نوع الراتب'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name

    def get_branches_list(self):
        raw_branches = []
        if self.branches:
            raw_branches = [branch.strip() for branch in self.branches.split(',') if branch.strip()]
        elif getattr(self, 'branch', None):
            raw_branches = [str(self.branch).strip()]

        if not raw_branches:
            return []

        branch_map = {
            'SCIENCE': self.BranchChoices.SCIENTIFIC,
            'LITERARY': self.BranchChoices.LITERARY,
            'NINTH': self.BranchChoices.NINTH_GRADE,
            'PREPARATORY': self.BranchChoices.PREPARATORY,
            '1': self.BranchChoices.SCIENTIFIC,
        }

        normalized = []
        for branch in raw_branches:
            if not branch:
                continue
            mapped = branch_map.get(branch) or branch_map.get(branch.upper())
            value = mapped or branch
            if value not in normalized:
                normalized.append(value)

        return normalized

    def get_hourly_rate_for_branch(self, branch):
        branch_map = {
            self.BranchChoices.SCIENTIFIC: 'hourly_rate_scientific',
            self.BranchChoices.LITERARY: 'hourly_rate_literary',
            self.BranchChoices.NINTH_GRADE: 'hourly_rate_ninth',
            self.BranchChoices.PREPARATORY: 'hourly_rate_preparatory',
        }
        field_name = branch_map.get(branch)
        if field_name:
            rate = getattr(self, field_name, None)
            if rate and rate > 0:
                return rate
        return self.hourly_rate or Decimal('0.00')

    def _sum_total_sessions(self, queryset):
        total = Decimal('0.00')
        for att in queryset:
            total += att.total_sessions
        return total

    class Meta:
        verbose_name = 'مدرّس'
        verbose_name_plural = 'مدرّسون'
        ordering = ['-created_at']

    def get_daily_sessions(self, date=None):
        if date is None:
            date = timezone.now().date()
        from attendance.models import TeacherAttendance
        attendances = TeacherAttendance.objects.filter(
            teacher=self,
            date=date,
            status='present'
        )
        return self._sum_total_sessions(attendances)

    def get_monthly_sessions(self, year=None, month=None):
        if year is None:
            year = timezone.now().year
        if month is None:
            month = timezone.now().month
        from attendance.models import TeacherAttendance
        attendances = TeacherAttendance.objects.filter(
            teacher=self,
            date__year=year,
            date__month=month,
            status='present'
        )
        return self._sum_total_sessions(attendances)

    def get_yearly_sessions(self, year=None):
        if year is None:
            year = timezone.now().year
        from attendance.models import TeacherAttendance
        attendances = TeacherAttendance.objects.filter(
            teacher=self,
            date__year=year,
            status='present'
        )
        return self._sum_total_sessions(attendances)

    def calculate_monthly_salary(self, year=None, month=None):
        if year is None:
            year = timezone.now().year
        if month is None:
            month = timezone.now().month
        if self.salary_type == 'hourly':
            return self.calculate_monthly_hourly_total(year, month)
        if self.salary_type == 'monthly':
            return self.monthly_salary or Decimal('0')
        if self.salary_type == 'mixed':
            monthly_base = self.monthly_salary or Decimal('0')
            hourly_total = self.calculate_monthly_hourly_total(year, month)
            return monthly_base + hourly_total
        return Decimal('0.00')

    def calculate_monthly_hourly_total(self, year=None, month=None):
        if year is None:
            year = timezone.now().year
        if month is None:
            month = timezone.now().month
        from attendance.models import TeacherAttendance
        total = Decimal('0.00')
        attendances = TeacherAttendance.objects.filter(
            teacher=self,
            date__year=year,
            date__month=month,
            status='present'
        )
        for att in attendances:
            total += att.total_sessions * self.get_hourly_rate_for_branch(att.branch)
        return total

    def get_salary_account(self):
        """الحصول على حساب راتب المدرس (لا يتم إنشاؤه تلقائياً)"""
        from accounts.models import Account
        try:
            return Account.objects.get(
                code=f"501-{self.pk:04d}",
                name_ar__contains=self.full_name
            )
        except Account.DoesNotExist:
            return None
        except Account.MultipleObjectsReturned:
            return Account.objects.filter(
                code=f"501-{self.pk:04d}",
                name_ar__contains=self.full_name
            ).first()

    @property
    def salary_account(self):
        return self.get_salary_account()

    def get_salary_status(self, year=None, month=None):
        """التحقق من حالة دفع الراتب"""
        if year is None:
            year = timezone.now().year
        if month is None:
            month = timezone.now().month
        
        # التحقق من الرواتب اليدوية
        manual_salary = ManualTeacherSalary.objects.filter(
            teacher=self,
            year=year,
            month=month,
            is_paid=True
        ).exists()
        
        return manual_salary

    def get_total_advances(self, year=None, month=None):
        """الحصول على إجمالي السلف غير المسددة"""
        try:
            from accounts.models import TeacherAdvance
            advances_qs = TeacherAdvance.objects.filter(teacher=self, is_repaid=False)
            if year is not None and month is not None:
                advances_qs = advances_qs.filter(date__year=year, date__month=month)
            return sum(advance.outstanding_amount for advance in advances_qs)
        except Exception:
            return Decimal('0.00')

    def calculate_net_salary(self, year=None, month=None):
        """حساب الراتب الصافي بعد خصم السلف"""
        # للتوافق مع الكود القديم، لكننا سنستخدم الرواتب اليدوية
        return Decimal('0.00')

    def get_teacher_dues_account(self):
        """الحصول على حساب مستحقات المدرس (لا يتم إنشاؤه تلقائياً)"""
        from accounts.models import Account
        try:
            return Account.objects.get(
                code=f"201-{self.pk:04d}",
                name_ar__contains=self.full_name
            )
        except Account.DoesNotExist:
            return None

    def get_teacher_advance_account(self):
        """الحصول على حساب سلف المدرس (يدوي فقط عند الطلب)"""
        from accounts.models import Account
        try:
            return Account.objects.get(
                code=f"121-{self.pk:04d}",
                name_ar__contains=self.full_name
            )
        except Account.DoesNotExist:
            return None

    @property
    def has_advance_account(self):
        """التحقق من وجود حساب سلفة"""
        account = self.get_teacher_advance_account()
        return account is not None

    def save(self, *args, **kwargs):
        """حفظ بسيط بدون أي تعيينات تلقائية"""
        super().save(*args, **kwargs)
# =============================
# Vacation
# =============================

class Vacation(models.Model):
    VACATION_TYPES = [
        ('يومية', 'يومية'),
        ('طارئة', 'طارئة'),
        ('مرضية', 'مرضية'),
    ]

    STATUS_CHOICES = [
        ('معلقة', 'معلقة'),
        ('موافق', 'موافق'),
        ('غير موافق', 'غير موافق'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='vacations')
    vacation_type = models.CharField(max_length=20, choices=VACATION_TYPES, verbose_name='نوع الإجازة')
    reason = models.TextField(verbose_name='سبب الإجازة')
    start_date = models.DateField(verbose_name='تاريخ بدء الإجازة')
    end_date = models.DateField(verbose_name='تاريخ انتهاء الإجازة')
    submission_date = models.DateField(auto_now_add=True, verbose_name='تاريخ تقديم الطلب')
    is_replacement_secured = models.BooleanField(default=False, verbose_name='تم تأمين البديل')
    manager_opinion = models.TextField(blank=True, null=True, verbose_name='رأي المدير')
    general_manager_opinion = models.TextField(blank=True, null=True, verbose_name='رأي المدير العام')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='معلقة')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"إجازة {self.employee.full_name} - {self.get_vacation_type_display()}"

    class Meta:
        verbose_name = 'إجازة'
        verbose_name_plural = 'الإجازات'
        ordering = ['-created_at']


# =============================
# Signals
# =============================

@receiver(post_save, sender=Employee)
def ensure_employee_salary_account(sender, instance, **kwargs):
    from accounts.models import get_or_create_employee_salary_account
    get_or_create_employee_salary_account(instance)
    from .services import BiometricImportService
    BiometricImportService.relink_employee_logs(instance)


@receiver(post_save, sender=Teacher)
def ensure_teacher_salary_account(sender, instance, **kwargs):
    from accounts.models import get_or_create_teacher_salary_account
    get_or_create_teacher_salary_account(instance)




# =============================
# Manual Teacher Salary
# =============================

class ManualTeacherSalary(models.Model):
    """رواتب يدوية للمدرسين يتم إضافتها بشكل شهري"""
    
    MONTH_CHOICES = [
        (1, 'كانون الثاني'),
        (2, 'شباط'),
        (3, 'آذار'),
        (4, 'نيسان'),
        (5, 'أيار'),
        (6, 'حزيران'),
        (7, 'تموز'),
        (8, 'آب'),
        (9, 'أيلول'),
        (10, 'تشرين الأول'),
        (11, 'تشرين الثاني'),
        (12, 'كانون الأول'),
    ]
    
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='manual_salaries')
    year = models.IntegerField(verbose_name='السنة')
    month = models.IntegerField(choices=MONTH_CHOICES, verbose_name='الشهر')
    gross_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='الراتب الإجمالي')
    advance_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='خصم السلف')
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='الصافي المستحق')
    notes = models.TextField(blank=True, verbose_name='ملاحظات')
    is_paid = models.BooleanField(default=False, verbose_name='تم الدفع')
    paid_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الدفع')
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='تم الإنشاء بواسطة')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'راتب يدوي للمدرس'
        verbose_name_plural = 'رواتب يدوية للمدرسين'
        unique_together = ('teacher', 'year', 'month')
        ordering = ['-year', '-month']
    
    def __str__(self):
        return f"{self.teacher.full_name} - {self.get_month_display()} {self.year}"
    
    def save(self, *args, **kwargs):
        # حساب الصافي تلقائياً
        self.net_salary = max(Decimal('0'), self.gross_salary - self.advance_deduction)
        super().save(*args, **kwargs)
    
    def mark_as_paid(self):
        """تسجيل الراتب كمُدفوع"""
        self.is_paid = True
        self.paid_date = timezone.now().date()
        self.save()
        
        # إذا كان هناك خصم سلف، تحديث حالة السلف
        if self.advance_deduction > 0:
            from accounts.models import TeacherAdvance
            # تحديث السلف القديمة لهذا الشهر
            advances = TeacherAdvance.objects.filter(
                teacher=self.teacher,
                date__year=self.year,
                date__month=self.month,
                is_repaid=False
            )
            for advance in advances:
                if self.advance_deduction >= advance.outstanding_amount:
                    advance.is_repaid = True
                    advance.repaid_amount = advance.outstanding_amount
                    self.advance_deduction -= advance.outstanding_amount
                else:
                    advance.repaid_amount += self.advance_deduction
                    self.advance_deduction = Decimal('0')
                advance.save()
