from django import forms
from django.forms import DateInput
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.apps import apps

from decimal import Decimal
from .models import Teacher, Employee, Vacation


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
    # لا نعتمد على ثابت POSITION_CHOICES؛ نقرأ من تعريف الحقل
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

    def save(self, commit=True):
        # أنشئ المستخدم أولًا
        user = super().save(commit=False)
        if commit:
            user.save()

        # ثم أنشئ الموظف المرتبط به
        Employee.objects.create(
            user=user,
            position=self.cleaned_data['position'],
            phone_number=self.cleaned_data['phone_number'],
            salary=self.cleaned_data['salary'],
        )

        # ملاحظة: لا نوزّع صلاحيات حسب الوظيفة إطلاقًا (كما طلبت)
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
