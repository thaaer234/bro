from django import forms
from django.contrib.auth.models import User
from .models import TechnicalReport


class TechnicalReportStep1Form(forms.ModelForm):
    employee = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label="الموظف المشتكي",
        widget=forms.Select(attrs={'class': 'form-control form-select'})
    )
    
    class Meta:
        model = TechnicalReport
        fields = ['employee', 'job_title', 'department', 'incident_date', 'issue_description']
        widgets = {
            'job_title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: مطور ويب، محاسب'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: قسم البرمجة، الحسابات'}),
            'incident_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'issue_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'اكتب تفاصيل المشكلة الفنية بالتفصيل هنا...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prepopulate the queryset with readable names
        self.fields['employee'].label_from_instance = lambda obj: obj.get_full_name() or obj.username


class TechnicalReportStep2Form(forms.ModelForm):
    class Meta:
        model = TechnicalReport
        fields = ['issue_impact', 'code_solution', 'employee_instructions', 'recommendations']
        widgets = {
            'issue_impact': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4, 
                'placeholder': 'شرح كيفية تأثير المشكلة على سير العمل أو النظام...'
            }),
            'code_solution': forms.Textarea(attrs={
                'class': 'form-control font-monospace', 
                'rows': 8, 
                'placeholder': 'اكتب الحل البرمجي أو التعديل الفني (يمكنك تضمين أكواد برمجية هنا)...',
                'dir': 'ltr',
                'style': 'text-align: left;'
            }),
            'employee_instructions': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4, 
                'placeholder': 'خطوات مبسطة للموظف لتفادي المشكلة...'
            }),
            'recommendations': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4, 
                'placeholder': 'توصيات ومقترحات مستقبلية لتحسين هيكلية النظام...'
            }),
        }
