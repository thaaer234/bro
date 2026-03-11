from django import forms
from .models import Attendance , TeacherAttendance




class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['student', 'classroom', 'date', 'status', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
        labels = {
            'student': 'الطالب',
            'classroom': 'الشعبة',
            'date': 'التاريخ',
            'status': 'حالة الحضور',
            'notes': 'ملاحظات',
        }
        
        
class TeacherAttendanceForm(forms.ModelForm):
    class Meta:
        model = TeacherAttendance
        fields = ['teacher', 'branch', 'date', 'status', 'session_count', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'session_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        labels = {
            'teacher': 'المدرس',
            'date': 'التاريخ',
            'status': 'حالة الحضور',
            'session_count': 'عدد الجلسات',
            'notes': 'ملاحظات',
        }        
