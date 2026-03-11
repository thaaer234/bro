from django import forms
from django.core.exceptions import ValidationError
from .models import AcademicYear, QuickCourse, QuickStudent, QuickEnrollment
from students.models import Student

class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'year', 'start_date', 'end_date', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

class QuickCourseForm(forms.ModelForm):
    class Meta:
        model = QuickCourse
        fields = ['name', 'name_ar', 'course_type', 'academic_year', 'price', 
                 'duration_weeks', 'hours_per_week', 'description', 'cost_center', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class QuickStudentForm(forms.ModelForm):
    gender = forms.ChoiceField(
        choices=[('', '---')] + list(Student.Gender.choices),
        required=False,
        label='الجنس'
    )
    course_track = forms.ChoiceField(
        choices=[
            ('', 'مكثفات (افتراضي)'),
            ('EXAM', 'امتحانية'),
        ],
        required=False,
        label='نوع الدورة'
    )
    class Meta:
        model = QuickStudent
        fields = ['full_name', 'phone', 'student_type', 'course_track', 'academic_year', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        student = getattr(self.instance, 'student', None)
        if student:
            self.fields['gender'].initial = student.gender
        if getattr(self.instance, 'course_track', None) == 'EXAM':
            self.fields['course_track'].initial = 'EXAM'
        else:
            self.fields['course_track'].initial = ''
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise ValidationError('يرجى إدخال رقم هاتف صالح.')

        if not phone.isdigit():
            raise ValidationError('يجب أن يحتوي رقم الهاتف على أرقام فقط.')

        if len(phone) != 10:
            raise ValidationError('رقم الهاتف يجب أن يتكون من 10 أرقام.')

        return phone

    def clean(self):
        cleaned = super().clean()
        phone = cleaned.get('phone')
        full_name = cleaned.get('full_name')
        course_track = cleaned.get('course_track') or 'INTENSIVE'
        cleaned['course_track'] = course_track
        if phone and full_name:
            existing_student = Student.objects.filter(
                phone=phone,
                full_name__iexact=full_name.strip()
            ).first()
            current_student = getattr(getattr(self.instance, 'student', None), 'pk', None)
            if existing_student and existing_student.pk != current_student:
                error = 'هذا الطالب موجود من قبل.'
                self.add_error('full_name', error)
                self.add_error('phone', error)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=commit)
        gender = self.cleaned_data.get('gender', '')
        student = getattr(instance, 'student', None)
        if student is not None:
            if student.gender != (gender or ''):
                student.gender = gender or ''
                if commit:
                    student.save(update_fields=['gender'])
        return instance

class QuickEnrollmentForm(forms.ModelForm):
    class Meta:
        model = QuickEnrollment
        fields = ['student', 'course', 'enrollment_date', 'net_amount', 
                 'discount_percent', 'discount_amount', 'payment_method']
        widgets = {
            'enrollment_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = QuickStudent.objects.filter(is_active=True)
        self.fields['course'].queryset = QuickCourse.objects.filter(is_active=True)
        
        # تعبئة net_amount تلقائياً من سعر الدورة
        if 'course' in self.data:
            try:
                course_id = int(self.data.get('course'))
                course = QuickCourse.objects.get(id=course_id)
                self.fields['net_amount'].initial = course.price
            except (ValueError, TypeError, QuickCourse.DoesNotExist):
                pass
        elif self.instance and self.instance.course:
            self.fields['net_amount'].initial = self.instance.course.price
