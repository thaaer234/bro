from django import forms
from django.forms import DateInput
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.apps import apps

from decimal import Decimal
from .models import (
    AttendancePolicy,
    BiometricDevice,
    Department,
    Employee,
    EmployeeAttendance,
    EmployeeSalaryRule,
    JobTitle,
    PayrollPeriod,
    Shift,
    Vacation,
    Teacher,
)


class TeacherForm(forms.ModelForm):
    branches = forms.MultipleChoiceField(
        choices=Teacher.BranchChoices.choices,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=True,
        label='الفروع التي يدرسها'
    )

    class Meta:
        model = Teacher
        fields = [
            'full_name',
            'phone_number',
            'hire_date',
            'salary_type',
            'hourly_rate',
            'hourly_rate_scientific',
            'hourly_rate_literary',
            'hourly_rate_ninth',
            'hourly_rate_preparatory',
            'monthly_salary',
            'notes',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'أدخل الاسم الكامل'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'أدخل رقم الهاتف'}),
            'hire_date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'salary_type': forms.Select(attrs={'class': 'form-control'}),
            'hourly_rate': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control', 'placeholder': '0.00'}),
            'hourly_rate_scientific': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control', 'placeholder': '0.00'}),
            'hourly_rate_literary': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control', 'placeholder': '0.00'}),
            'hourly_rate_ninth': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control', 'placeholder': '0.00'}),
            'hourly_rate_preparatory': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control', 'placeholder': '0.00'}),
            'monthly_salary': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control', 'placeholder': '0.00'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'ملاحظات إضافية'}),
        }
        labels = {
            'full_name': 'الاسم الكامل',
            'phone_number': 'رقم الهاتف',
            'hire_date': 'تاريخ التعيين',
            'salary_type': 'نوع الراتب',
            'hourly_rate': 'أجر الساعة (ل.س)',
            'monthly_salary': 'الراتب الشهري الثابت (ل.س)',
            'notes': 'ملاحظات',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # القيمة الابتدائية للفروع عند التعديل
        if self.instance and self.instance.pk and self.instance.branches:
            self.fields['branches'].initial = self.instance.get_branches_list()

        # الحقول اختيارية افتراضيًا ونقيّدها بالتحقق في clean()
        self.fields['hourly_rate'].required = False
        self.fields['hourly_rate_scientific'].required = False
        self.fields['hourly_rate_literary'].required = False
        self.fields['hourly_rate_ninth'].required = False
        self.fields['hourly_rate_preparatory'].required = False
        self.fields['monthly_salary'].required = False
        self.fields['notes'].required = False
        self.fields['salary_type'].required = False

    def clean(self):
        cleaned_data = super().clean()
        branches = cleaned_data.get('branches') or []
        salary_type = cleaned_data.get('salary_type') or getattr(self.instance, 'salary_type', None) or 'hourly'
        hourly_rate = cleaned_data.get('hourly_rate')
        monthly_salary = cleaned_data.get('monthly_salary')
        branch_rates = [
            cleaned_data.get('hourly_rate_scientific'),
            cleaned_data.get('hourly_rate_literary'),
            cleaned_data.get('hourly_rate_ninth'),
            cleaned_data.get('hourly_rate_preparatory'),
        ]
        has_branch_rate = any(rate and rate > 0 for rate in branch_rates)

        cleaned_data['salary_type'] = salary_type
        if hourly_rate in (None, ''):
            hourly_rate = getattr(self.instance, 'hourly_rate', None)
            cleaned_data['hourly_rate'] = hourly_rate
        if monthly_salary in (None, ''):
            monthly_salary = getattr(self.instance, 'monthly_salary', None)
            cleaned_data['monthly_salary'] = monthly_salary

        if not branches:
            raise forms.ValidationError('يجب اختيار فرع واحد على الأقل.')

        if salary_type == 'hourly' and not hourly_rate and not has_branch_rate:
            self.add_error('hourly_rate', 'يجب إدخال أجر الساعة للراتب بالساعة.')

        if salary_type == 'monthly' and not monthly_salary:
            self.add_error('monthly_salary', 'يجب إدخال الراتب الشهري للراتب الثابت.')

        if salary_type == 'mixed':
            if not hourly_rate and not has_branch_rate:
                self.add_error('hourly_rate', 'يجب إدخال أجر الساعة للراتب المختلط.')
            if not monthly_salary:
                self.add_error('monthly_salary', 'يجب إدخال الراتب الشهري للراتب المختلط.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # تحويل قائمة الفروع إلى نص مفصول بفواصل
        branches = self.cleaned_data.get('branches') or []
        if isinstance(branches, list):
            instance.branches = ','.join(branches)

        # قيم افتراضية للرواتب
        if not instance.hourly_rate:
            instance.hourly_rate = Decimal('0.00')
        if not instance.monthly_salary:
            instance.monthly_salary = Decimal('0.00')

        if commit:
            instance.save()

        return instance


class EmployeeRegistrationForm(UserCreationForm):
    WEEKEND_DAY_CHOICES = [(str(number), label) for number, label in Employee.WEEKDAY_LABELS.items()]

    position = forms.ChoiceField(
        choices=lambda: Employee._meta.get_field('position').choices,
        label='الوظيفة'
    )
    phone_number = forms.CharField(label='رقم الهاتف', required=True)
    salary = forms.DecimalField(
        label='الراتب',
        required=True,
        min_value=0,
        max_digits=10,
        decimal_places=2
    )
    employee_code = forms.CharField(label='الرقم الوظيفي', required=False)
    biometric_user_id = forms.CharField(label='معرف البصمة', required=False)
    national_id = forms.CharField(label='الرقم الوطني', required=False)
    address = forms.CharField(label='العنوان', required=False, widget=forms.Textarea(attrs={'rows': 2}))
    contract_type = forms.ChoiceField(choices=Employee._meta.get_field('contract_type').choices, label='نوع العقد')
    contract_start = forms.DateField(label='بداية العقد', required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    contract_end = forms.DateField(label='نهاية العقد', required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    employment_status = forms.ChoiceField(choices=Employee._meta.get_field('employment_status').choices, label='الحالة الوظيفية')
    payroll_method = forms.ChoiceField(choices=Employee.PAYROLL_METHOD_CHOICES, required=False, label='طريقة حساب الراتب')
    hourly_rate = forms.DecimalField(label='أجر الساعة', required=False, min_value=0, max_digits=10, decimal_places=2)
    overtime_hourly_rate = forms.DecimalField(label='أجر ساعة الإضافي', required=False, min_value=0, max_digits=10, decimal_places=2)
    required_monthly_hours = forms.IntegerField(label='الساعات المطلوبة شهريًا', required=False, min_value=0)
    weekend_days = forms.MultipleChoiceField(
        choices=WEEKEND_DAY_CHOICES,
        required=False,
        label='أيام العطلة الأسبوعية',
        widget=forms.CheckboxSelectMultiple,
    )
    department = forms.ModelChoiceField(queryset=Department.objects.filter(is_active=True).order_by('name'), required=False, label='القسم')
    job_title = forms.ModelChoiceField(queryset=JobTitle.objects.filter(is_active=True).select_related('department').order_by('name'), required=False, label='المسمى الوظيفي')
    default_shift = forms.ModelChoiceField(queryset=Shift.objects.filter(is_active=True), required=False, label='الشفت الافتراضي')
    attendance_policy = forms.ModelChoiceField(queryset=AttendancePolicy.objects.filter(is_active=True), required=False, label='سياسة الدوام')
    salary_rule = forms.ModelChoiceField(queryset=EmployeeSalaryRule.objects.filter(is_active=True), required=False, label='قاعدة الراتب')
    emergency_contact_name = forms.CharField(label='اسم جهة الطوارئ', required=False)
    emergency_contact_phone = forms.CharField(label='هاتف جهة الطوارئ', required=False)
    profile_photo = forms.ImageField(label='الصورة الشخصية', required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        labels = {
            'username': 'اسم المستخدم',
            'first_name': 'الاسم الأول',
            'last_name': 'الاسم الأخير',
            'email': 'البريد الإلكتروني',
            'password1': 'كلمة السر',
            'password2': 'تأكيد كلمة السر',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css_class = field.widget.attrs.get('class', '')
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs['class'] = (css_class + ' form-check-input').strip()
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs['class'] = (css_class + ' form-select').strip()
            elif isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs['class'] = (css_class + ' form-control').strip()
            else:
                field.widget.attrs['class'] = (css_class + ' form-control').strip()
        self.fields['weekend_days'].help_text = 'اختر الأيام بدل كتابة الأرقام. الجمعة = 4.'
        self.fields['job_title'].help_text = 'تظهر المسميات المناسبة حسب القسم المختار.'

    def clean_weekend_days(self):
        values = self.cleaned_data.get('weekend_days') or []
        return ','.join(str(value) for value in values)

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()

        employee = Employee.objects.create(
            user=user,
            position=self.cleaned_data['position'],
            phone_number=self.cleaned_data['phone_number'],
            salary=self.cleaned_data['salary'],
            payroll_method=self.cleaned_data.get('payroll_method') or 'monthly',
            hourly_rate=self.cleaned_data.get('hourly_rate') or Decimal('0.00'),
            overtime_hourly_rate=self.cleaned_data.get('overtime_hourly_rate') or Decimal('0.00'),
            required_monthly_hours=self.cleaned_data.get('required_monthly_hours') or 0,
            weekend_days=self.cleaned_data.get('weekend_days') or '4,5',
            annual_leave_days=self.cleaned_data.get('annual_leave_days') or 14,
            sick_leave_days=self.cleaned_data.get('sick_leave_days') or 7,
            employee_code=self.cleaned_data.get('employee_code') or None,
            biometric_user_id=self.cleaned_data.get('biometric_user_id') or None,
            national_id=self.cleaned_data.get('national_id') or None,
            address=self.cleaned_data.get('address') or None,
            contract_type=self.cleaned_data['contract_type'],
            contract_start=self.cleaned_data.get('contract_start'),
            contract_end=self.cleaned_data.get('contract_end'),
            employment_status=self.cleaned_data['employment_status'],
            department=self.cleaned_data.get('department'),
            job_title=self.cleaned_data.get('job_title'),
            default_shift=self.cleaned_data.get('default_shift'),
            attendance_policy=self.cleaned_data.get('attendance_policy'),
            salary_rule=self.cleaned_data.get('salary_rule'),
            emergency_contact_name=self.cleaned_data.get('emergency_contact_name') or None,
            emergency_contact_phone=self.cleaned_data.get('emergency_contact_phone') or None,
            profile_photo=self.cleaned_data.get('profile_photo'),
        )

        from .services import BiometricImportService
        BiometricImportService.relink_employee_logs(employee)
        return user


class VacationForm(forms.ModelForm):
    class Meta:
        model = Vacation
        fields = ['vacation_type', 'reason', 'start_date', 'end_date', 'is_replacement_secured']
        widgets = {
            'start_date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        labels = {
            'vacation_type': 'نوع الإجازة',
            'reason': 'سبب الإجازة',
            'start_date': 'تاريخ بدء الإجازة',
            'end_date': 'تاريخ انتهاء الإجازة',
            'is_replacement_secured': 'تم تأمين البديل',
        }


class AdminVacationForm(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.select_related('user').all(),
        label='اختيار الموظف',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Vacation
        fields = [
            'employee',
            'vacation_type',
            'reason',
            'start_date',
            'end_date',
            'is_replacement_secured',
            'manager_opinion',
            'general_manager_opinion',
            'status',
        ]
        widgets = {
            'start_date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'manager_opinion': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'general_manager_opinion': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'vacation_type': 'نوع الإجازة',
            'reason': 'سبب الإجازة',
            'start_date': 'تاريخ بدء الإجازة',
            'end_date': 'تاريخ انتهاء الإجازة',
            'is_replacement_secured': 'تم تأمين البديل',
            'manager_opinion': 'رأي المدير',
            'general_manager_opinion': 'رأي المدير العام',
            'status': 'حالة الإجازة',
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # إضافة منطق لتصفية الرواتب بناءً على الموظف المحدد
        employee = self.instance.employee if self.instance.pk else None

        # محاولة الحصول على نموذج ExpenseEntry ديناميكيًا لتجنب أخطاء الاستيراد الدائري أو غيابه
        try:
            ExpenseEntry = apps.get_model('employ', 'ExpenseEntry')
        except LookupError:
            ExpenseEntry = None

        if employee:
            # الحصول على المدفوعات المتعلقة بالموظف المحدد
            if getattr(employee, 'user', None) and ExpenseEntry is not None:
                salary_qs = ExpenseEntry.objects.filter(created_by=employee.user).select_related(
                    'account', 'journal_entry', 'created_by'
                ).order_by('-date')
            else:
                # استخدم QuerySet خالي من نموذج موجود كبديل آمن
                salary_qs = ExpenseEntry.objects.none()
        else:
            salary_qs = ExpenseEntry.objects.none()

        # يمكنك الآن استخدام salary_qs كما هو مطلوب، على سبيل المثال، لتحديد خيارات حقل الراتب
        # مثال:
        # self.fields['salary'].queryset = salary_qs
        # self.fields['salary'].queryset = salary_qs


class EmployeeProfileForm(forms.ModelForm):
    WEEKEND_DAY_CHOICES = EmployeeRegistrationForm.WEEKEND_DAY_CHOICES

    username = forms.CharField(label='اسم المستخدم')
    first_name = forms.CharField(label='الاسم الأول', required=False)
    last_name = forms.CharField(label='الاسم الأخير', required=False)
    email = forms.EmailField(label='البريد الإلكتروني', required=False)
    weekend_days = forms.MultipleChoiceField(
        choices=WEEKEND_DAY_CHOICES,
        required=False,
        label='أيام العطلة الأسبوعية',
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Employee
        fields = [
            'position',
            'phone_number',
            'salary',
            'payroll_method',
            'hourly_rate',
            'overtime_hourly_rate',
            'required_monthly_hours',
            'weekend_days',
            'annual_leave_days',
            'sick_leave_days',
            'employee_code',
            'biometric_user_id',
            'national_id',
            'address',
            'contract_type',
            'contract_start',
            'contract_end',
            'employment_status',
            'department',
            'job_title',
            'default_shift',
            'attendance_policy',
            'salary_rule',
            'emergency_contact_name',
            'emergency_contact_phone',
            'profile_photo',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'contract_start': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'contract_end': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = getattr(self.instance, 'user', None)
        if user:
            self.fields['username'].initial = user.username
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
        self.fields['weekend_days'].initial = [str(value) for value in sorted(self.instance.get_weekend_day_numbers())]
        self.fields['weekend_days'].help_text = 'اختر الأيام بدل كتابة الأرقام. الجمعة = 4.'
        self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('name')
        self.fields['job_title'].queryset = JobTitle.objects.filter(is_active=True).select_related('department').order_by('name')
        self.fields['job_title'].help_text = 'تظهر المسميات المناسبة حسب القسم المختار.'

        for name, field in self.fields.items():
            css_class = field.widget.attrs.get('class', '')
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = (css_class + ' form-check-input').strip()
            elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs['class'] = (css_class + ' form-check-input').strip()
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs['class'] = (css_class + ' form-select').strip()
            elif isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs['class'] = (css_class + ' form-control').strip()
            else:
                field.widget.attrs['class'] = (css_class + ' form-control').strip()

    def clean_weekend_days(self):
        values = self.cleaned_data.get('weekend_days') or []
        return ','.join(str(value) for value in values)

    def save(self, commit=True):
        employee = super().save(commit=False)
        user = employee.user
        user.username = self.cleaned_data['username']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.email = self.cleaned_data.get('email', '')
        if commit:
            user.save()
            employee.save()
            self.save_m2m()
            from .services import BiometricImportService
            BiometricImportService.relink_employee_logs(employee)
        return employee


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description', 'is_active']


class JobTitleForm(forms.ModelForm):
    class Meta:
        model = JobTitle
        fields = ['name', 'code', 'department', 'description', 'is_active']


class ShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = [
            'name', 'code', 'start_time', 'end_time', 'grace_period_minutes',
            'required_work_seconds', 'is_night_shift', 'break_seconds',
            'break_start', 'break_end', 'is_active'
        ]
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'break_start': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'break_end': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }


class AttendancePolicyForm(forms.ModelForm):
    class Meta:
        model = AttendancePolicy
        fields = [
            'name', 'late_deduction_rate', 'early_leave_deduction_rate',
            'absence_deduction_rate', 'overtime_enabled', 'overtime_multiplier',
            'rounding_method', 'holiday_handling', 'weekend_days', 'is_active'
        ]


class EmployeeSalaryRuleForm(forms.ModelForm):
    class Meta:
        model = EmployeeSalaryRule
        fields = [
            'name', 'salary_type', 'overtime_enabled', 'overtime_multiplier',
            'late_deduction_enabled', 'absence_deduction_enabled', 'tax_percent',
            'insurance_percent', 'max_overtime_seconds', 'max_deduction_amount',
            'rounding_method', 'is_active'
        ]


class BiometricDeviceForm(forms.ModelForm):
    class Meta:
        model = BiometricDevice
        fields = ['name', 'ip', 'port', 'serial', 'location', 'active']


class BiometricImportForm(forms.Form):
    device = forms.ModelChoiceField(queryset=BiometricDevice.objects.filter(active=True), label='جهاز البصمة')
    raw_logs = forms.CharField(
        label='سجلات البصمة',
        help_text='أدخل JSON Array يحتوي على device_user_id و punch_time و punch_type.',
        widget=forms.Textarea(attrs={'rows': 8, 'class': 'form-control'})
    )


class PayrollPeriodForm(forms.ModelForm):
    class Meta:
        model = PayrollPeriod
        fields = ['name', 'start_date', 'end_date', 'status']
        widgets = {
            'start_date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }


class EmployeeAttendanceUpdateForm(forms.ModelForm):
    class Meta:
        model = EmployeeAttendance
        fields = [
            'check_in',
            'check_out',
            'status',
            'review_status',
            'review_notes',
            'notes',
            'manual_adjustment_reason',
        ]
        widgets = {
            'check_in': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'check_out': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'review_status': forms.Select(attrs={'class': 'form-control'}),
            'review_notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'manual_adjustment_reason': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')
        if check_in and check_out and check_out < check_in:
            self.add_error('check_out', 'وقت الخروج يجب أن يكون بعد وقت الدخول.')
        review_status = cleaned_data.get('review_status')
        review_notes = (cleaned_data.get('review_notes') or '').strip()
        if review_status in {'justified', 'unjustified'} and not review_notes:
            self.add_error('review_notes', 'يرجى كتابة سبب القرار الإداري.')
        return cleaned_data


class AttendanceFilterForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.select_related('user'), required=False, label='الموظف')
    start_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), label='من')
    end_date = forms.DateField(required=False, widget=DateInput(attrs={'type': 'date', 'class': 'form-control'}), label='إلى')
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'كل الحالات')] + list(EmployeeAttendance.STATUS_CHOICES),
        label='الحالة'
    )
