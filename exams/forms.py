from django import forms
from django.forms import modelformset_factory 
from .models import Exam, ExamType, ExamGrade, StudentExam



class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'subject', 'exam_date', 'max_grade', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'اسم الاختبار (مثال: اختبار الفصل الأول, امتحان عملي...)'
            }),
            'subject': forms.Select(attrs={
                'class': 'form-control'
            }),
            'exam_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'max_grade': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 0.1,
                'placeholder': 'العلامة القصوى'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'ملاحظات عامة عن الاختبار'
            })
        }

class ExamGradesForm(forms.ModelForm):
    class Meta:
        model = ExamGrade
        fields = ['student', 'grade', 'notes']
        widgets = {
            'student': forms.HiddenInput(),
            'grade': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'placeholder': 'أدخل العلامة'
            }),
            'notes': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ملاحظات خاصة بالطالب'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grade'].required = False
        
        # إصلاح عرض القيم العشرية
        if self.instance and self.instance.grade is not None:
            # التحقق من القيمة 0
            grade_float = float(self.instance.grade)
            if grade_float == 0:
                self.initial['grade'] = 0  # عرض 0 كقيمة صحيحة
            elif grade_float.is_integer():
                self.initial['grade'] = int(grade_float)
            else:
                self.initial['grade'] = grade_float

ExamGradesFormSet = modelformset_factory(
    ExamGrade,
    form=ExamGradesForm,
    extra=0
)
class StudentExamForm(forms.ModelForm):
    class Meta:
        model = StudentExam
        fields = ['student', 'subject', 'exam_type', 'grade', 'notes', 'classroom']
        widgets = {
            'student': forms.HiddenInput(),
            'subject': forms.HiddenInput(),
            'exam_type': forms.HiddenInput(),
            'classroom': forms.HiddenInput(),
            'grade': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 0.1,
                'placeholder': 'أدخل العلامة'
            }),
            'notes': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'أدخل الملاحظات هنا'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grade'].required = False

StudentExamFormSet = modelformset_factory(
    StudentExam,
    form=StudentExamForm,
    extra=0
)

class ExamTypeForm(forms.ModelForm):
    class Meta:
        model = ExamType
        fields = ['name', 'max_grade', 'order']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'اسم الاختبار (مثال: اختبار 1, اختبار 2, مشروع...)'
            }),
            'max_grade': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 1,
                'placeholder': 'العلامة القصوى'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'ترتيب الظهور'
            })
        }

class CustomPrintForm(forms.Form):
    PRINT_CHOICES = [
        ('summary', 'الجدول الإجمالي للمجموع'),
        ('1', 'جدول 1'),
        ('2', 'جدول 2'),
        ('3', 'جدول 3'),
        ('midterm', 'جدول النصفي'),
        ('all', 'جميع الجداول معاً')
    ]
    
    tables = forms.MultipleChoiceField(
        choices=PRINT_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        initial=['summary'],
        label="اختر الجداول المطلوبة"
    )
    
    include_notes = forms.BooleanField(
        initial=True,
        required=False,
        label="تضمين الملاحظات"
    )
    
    include_signature = forms.BooleanField(
        initial=True,
        required=False,
        label="تضمين مكان التوقيع"
    )