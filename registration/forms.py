from django import forms
from .models import UserProfile, PasswordResetRequest

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'address', 'profile_picture']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }

class PasswordResetRequestForm(forms.Form):
    reason = forms.CharField(
        label='سبب طلب تعديل كلمة المرور',
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 3, 
            'placeholder': 'اذكر سبب طلبك لتعديل كلمة المرور'
        })
    )

class PasswordResetConfirmForm(forms.Form):
    code = forms.CharField(
        label='الكود',
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'أدخل الكود الذي أعطاك إياه المشرف'
        })
    )
    new_password = forms.CharField(
        label='كلمة المرور الجديدة',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    confirm_password = forms.CharField(
        label='تأكيد كلمة المرور',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError('كلمات المرور غير متطابقة')
        
        return cleaned_data
class SuperUserApproveForm(forms.Form):
    duration = forms.ChoiceField(
        label='مدة الصلاحية',
        choices=[
            (1, 'ساعة واحدة'),
            (6, '6 ساعات'),
            (24, '24 ساعة'),
            (168, 'أسبوع'),
        ],
        initial=24,
        widget=forms.Select(attrs={'class': 'form-control'})
    )