from django import forms
from .models import TeacherAttendance  # إذا كنت تحتاج نموذج حضور المدرسين فقط
from employ.models import Teacher, Employee, Vacation  # لأن هذه النماذج موجودة في تطبيق employ
  # استيرادهما من التطبيق الصحيح
from django.forms import DateInput
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User


class TeacherForm(forms.ModelForm):
    branches = forms.MultipleChoiceField(
        choices=Teacher.BranchChoices.choices,
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        required=True,
        label='الفروع'
    )

    class Meta:
        model = Teacher
        fields = '__all__'
        widgets = {
            'hire_date': DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        labels = {
            'full_name': 'الاسم الكامل',
            'phone_number': 'رقم الهاتف',
            'hire_date': 'تاريخ التعيين',
            'notes': 'ملاحظات',
        }
        
        


class EmployeeRegistrationForm(UserCreationForm):  # تغيير الوراثة إلى UserCreationForm
    position = forms.ChoiceField(choices=Employee.POSITION_CHOICES, label='الوظيفة')
    phone_number = forms.CharField(label='رقم الهاتف')
    salary = forms.DecimalField(
            label='الراتب',
            required=True,  # تأكد من أن الحقل مطلوب
            min_value=0,    # يمكنك تحديد حد أدنى للراتب
            max_digits=10,
            decimal_places=2
        )
    class Meta:
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
        if self.instance and hasattr(self.instance, 'employee'):
            employee = self.instance.employee
            self.fields['position'].initial = employee.position
            self.fields['phone_number'].initial = employee.phone_number
            self.fields['salary'].initial = employee.salary

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data["password1"]
        user.set_password(password)
        
        if commit:
            user.save()
            employee = Employee.objects.create(  # استخدم create بدلاً من get_or_create
                user=user,
                position=self.cleaned_data['position'],
                phone_number=self.cleaned_data['phone_number'],
                salary=self.cleaned_data['salary']  # تأكد من تمرير القيمة هنا
            )
            
            # تحديث الصلاحيات حسب الوظيفة
            user.groups.clear()
            group_name = self.get_group_name()
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
        
        return user
    
    def get_group_name(self):
        position = self.cleaned_data.get('position', 'employee')
        return {
            'admin': 'Admins',
            'accountant': 'Accountants',
            'mentor': 'Mentor',
            'manager': 'Managers',
            'marketing': 'Marketing',
            'reception': 'Reception',
        }.get(position, 'Employees')
        
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
        queryset=Employee.objects.all(),
        label='اختيار الموظف',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Vacation
        fields = ['employee', 'vacation_type', 'reason', 'start_date', 'end_date', 'is_replacement_secured', 'manager_opinion', 'general_manager_opinion', 'status']
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


from django import forms
from .models import TeacherAttendance

class TeacherAttendanceForm(forms.ModelForm):
    class Meta:
        model = TeacherAttendance
        fields = ['teacher', 'branch', 'date', 'status', 'session_count', 'half_session_count', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        labels = {
            'teacher': 'المدرس',
            'date': 'التاريخ',
            'status': 'الحالة',
            'session_count': 'عدد الجلسات الكاملة',
            'half_session_count': 'أنصاف الجلسات',
            'notes': 'ملاحظات',
        }
from django import forms

class JSONUploadForm(forms.Form):
    json_file = forms.FileField(
        label='رفع ملف JSON',
        help_text='اختر ملف JSON يحتوي على بيانات حضور الأساتذة'
    )
    create_daily_entries = forms.BooleanField(
        initial=True,
        required=False,
        label='إنشاء قيود يومية منفصلة',
        help_text='سيتم إنشاء قيد محاسبي منفصل لكل يوم حضور لكل أستاذ'
    )
