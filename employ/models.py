from django.db import models
from django.core.validators import MinLengthValidator
from datetime import date
from decimal import Decimal
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


# =============================
# Employee & Permissions
# =============================

class Employee(models.Model):
    """الموظف: مرتبط بمستخدم النظام، ويُمنح صلاحيات ميزات مباشرةً عبر EmployeePermission."""

    # حقل الربط مع مستخدم Django
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='employee_profile')

    # حقول اختيارية للإدارة
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name='رقم الهاتف')
    hire_date = models.DateField(blank=True, null=True, verbose_name='تاريخ التعيين')

    # الراتب الشهري الثابت (تستخدمه الفيوز الخاصة بملف الموظف ودفع الراتب)
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='راتب شهري')

    # مسمى وظيفي (اختياري، لا يوزّع صلاحيات تلقائيًا)
    POSITION_CHOICES = [
        ('admin', 'مسؤول'),
        ('accountant', 'محاسب'),
        ('hr', 'موارد بشرية'),
        ('staff', 'موظف'),
    ]
    position = models.CharField(max_length=50, choices=POSITION_CHOICES, default='staff', verbose_name='الوظيفة')

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
