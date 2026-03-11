from django import forms
from .models import Student, Account
from django.forms import DateInput
from accounts.models import StudentReceipt, Studentenrollment

class StudentForm(forms.ModelForm):
    REQUIRED_FIELDS = {
        'full_name',
        'gender',
        'branch',
        'birth_date',
        'student_number',
        'nationality',
        'tase3',
        'father_name',
        'father_job',
        'father_phone',
        'mother_name',
        'mother_job',
        'mother_phone',
        'address',
        'home_phone',
        'previous_school',
        'how_knew_us',
    }
    account = forms.ModelChoiceField(
        queryset=Account.objects.none(),  # سيتم تعبئته في الـ view
        required=False,
        label="الحساب المالي",
        help_text="اختر الحساب المالي المرتبط بالطالب"
    )
    class Meta:
        model = Student
        fields = '__all__'
        widgets = {
            'birth_date': DateInput(attrs={'type': 'date'}),
            'registration_date': DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'discount_percent': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'discount_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'discount_reason': forms.TextInput(),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'branch': forms.Select(attrs={'class': 'form-control'}),
            'how_knew_us': forms.Select(attrs={'class': 'form-control'}),
            'student_type': forms.Select(attrs={'class': 'form-control'}),
            'academic_level': forms.Select(attrs={'class': 'form-control'}),
            'registration_status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'full_name': 'الاسم الكامل للطالب',
            'gender': 'الجنس',
            'branch': 'الصف الدراسي',
            'birth_date': 'تاريخ الميلاد',
            'tase3': 'مجموع الصف التاسع',
            'disease': 'الأمراض أو الحالات الصحية',
            'student_number': 'رقم الطالب',
            'nationality': 'الجنسية',
            'registration_date': 'تاريخ التسجيل',
            'father_name': 'اسم الأب',
            'father_job': 'مهنة الأب',
            'father_phone': 'هاتف الأب',
            'mother_name': 'اسم الأم',
            'mother_job': 'مهنة الأم',
            'mother_phone': 'هاتف الأم',
            'address': 'العنوان',
            'home_phone': 'هاتف المنزل',
            'previous_school': 'المدرسة السابقة',
            'elementary_school': 'المدرسة الابتدائية',
            'how_knew_us': 'كيفية معرفة المعهد',
            'notes': 'ملاحظات',
            'discount_percent': 'نسبة الحسم الافتراضي %',
            'discount_amount': 'قيمة الحسم الافتراضي',
            'discount_reason': 'سبب الحسم',
            'email': 'البريد الإلكتروني',
            'phone': 'رقم الهاتف',
            'is_active': 'نشط',
            'student_type': 'نوع الطالب',
            'academic_level': 'المستوى الأكاديمي', 
            'registration_status': 'الحالة التسجيلية',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # جعل الحقول المطلوبة فقط الأساسية
        for field_name, field in self.fields.items():
            field.required = field_name in self.REQUIRED_FIELDS
            field.widget.attrs.update({'class': 'form-control'})
        
        # إزالة حقل added_by من النموذج لأنه سيتم تعبئته تلقائيًا
        if 'added_by' in self.fields:
            self.fields.pop('added_by')
        
        # إزالة حقل account من النموذج لأنه سيتم إنشاؤه تلقائيًا
        if 'account' in self.fields:
            self.fields.pop('account')
            
        # تخصيص خيارات القوائم المنسدلة
        self.fields['gender'].choices = [
            ('', 'اختر الجنس'),
            ('male', 'ذكر'),
            ('female', 'أنثى')
        ]
        
        self.fields['branch'].choices = [
            ('', 'اختر الصف الدراسي'),
            ('أدبي', 'الأدبي'),
            ('علمي', 'العلمي'),
            ('تاسع', 'الصف التاسع')
        ]
        
        self.fields['how_knew_us'].choices = [
            ('', 'اختر طريقة المعرفة'),
            ('friend', 'صديق'),
            ('social', 'وسائل التواصل الاجتماعي'),
            ('ad', 'إعلان'),
            ('ads', 'إعلانات طرقية'),
            ('other', 'أخرى')
        ]
        # تعبئة خيارات الحسابات إذا كانت متاحة في الـ context
        if 'account' in self.fields:
            from accounts.models import Account
            self.fields['account'].queryset = Account.objects.filter(
                account_type__in=['ASSET', 'LIABILITY'],
                is_active=True
            ).order_by('code')
    def clean(self):
        cleaned_data = super().clean()

        def is_missing(value):
            if value is None:
                return True
            if isinstance(value, str) and not value.strip():
                return True
            return False

        for name in self.REQUIRED_FIELDS:
            if is_missing(cleaned_data.get(name)):
                self.add_error(name, 'هذا الحقل مطلوب.')

        full_name = cleaned_data.get('full_name')
        student_number = cleaned_data.get('student_number')

        if full_name:
            check_full_name = True
            if self.instance and self.instance.pk:
                current_full_name = (self.instance.full_name or '').strip()
                if current_full_name.lower() == full_name.strip().lower():
                    check_full_name = False
            if check_full_name:
                existing_student = Student.objects.filter(
                    full_name__iexact=full_name
                ).exclude(pk=self.instance.pk if self.instance else None)
                if existing_student.exists():
                    raise forms.ValidationError({
                        'full_name': f'اسم الطالب مسجل مسبقا: {existing_student.first().student_number}'
                    })

        if student_number:
            check_student_number = True
            if self.instance and self.instance.pk:
                current_student_number = (self.instance.student_number or '').strip()
                if current_student_number == student_number.strip():
                    check_student_number = False
            if check_student_number:
                existing_student = Student.objects.filter(
                    student_number=student_number
                ).exclude(pk=self.instance.pk if self.instance else None)
                if existing_student.exists():
                    raise forms.ValidationError({
                        'student_number': f'رقم الطالب مسجل مسبقا: {existing_student.first().full_name}'
                    })

        return cleaned_data

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name')
        if full_name and len(full_name.strip()) < 2:
            raise forms.ValidationError('الاسم قصير جدا')
        return full_name.strip() if full_name else full_name

    def clean_student_number(self):
        student_number = self.cleaned_data.get('student_number')
        if not student_number:
            if self.instance and self.instance.pk:
                return ''
            raise forms.ValidationError('رقم الطالب مطلوب')
        return student_number.strip()

    def _clean_phone_digits(self, field_name, label):
        value = (self.cleaned_data.get(field_name) or '').strip()
        digits = ''.join(ch for ch in value if ch.isdigit())
        if len(digits) != 10:
            raise forms.ValidationError(f'{label} يجب أن يكون 10 أرقام.')
        return digits

    def clean_father_phone(self):
        return self._clean_phone_digits('father_phone', 'هاتف الأب')

    def clean_mother_phone(self):
        return self._clean_phone_digits('mother_phone', 'هاتف الأم')

    def clean_home_phone(self):
        value = (self.cleaned_data.get('home_phone') or '').strip()
        if value in ('لا يوجد', 'لا يوجد.'):
            return value
        digits = ''.join(ch for ch in value if ch.isdigit())
        if len(digits) != 7:
            raise forms.ValidationError('هاتف المنزل يجب أن يكون 7 أرقام أو كلمة لا يوجد.')
        return digits

