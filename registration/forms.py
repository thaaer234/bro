from django import forms

from .models import UserProfile


class UserProfileForm(forms.ModelForm):
    username = forms.CharField(
        label='اسم المستخدم',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    first_name = forms.CharField(
        label='الاسم الأول',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    last_name = forms.CharField(
        label='اسم العائلة',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    email = forms.EmailField(
        label='البريد الإلكتروني',
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = UserProfile
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'address', 'profile_picture']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = getattr(self.instance, 'user', None)
        if user:
            self.fields['username'].initial = user.username
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        user = getattr(self.instance, 'user', None)
        if not username:
            raise forms.ValidationError('اسم المستخدم مطلوب')
        if user and user.__class__.objects.exclude(pk=user.pk).filter(username=username).exists():
            raise forms.ValidationError('اسم المستخدم مستخدم من قبل')
        return username

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.username = self.cleaned_data.get('username', '').strip()
        user.first_name = self.cleaned_data.get('first_name', '').strip()
        user.last_name = self.cleaned_data.get('last_name', '').strip()
        user.email = self.cleaned_data.get('email', '').strip()

        if commit:
            user.save(update_fields=['username', 'first_name', 'last_name', 'email'])
            profile.save()
            self.save_m2m()
        return profile


class PasswordResetRequestForm(forms.Form):
    reason = forms.CharField(
        label='سبب طلب تعديل كلمة المرور',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'اذكر سبب طلبك لتعديل كلمة المرور',
        })
    )


class PasswordResetConfirmForm(forms.Form):
    code = forms.CharField(
        label='الكود',
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'أدخل الكود الذي أعطاك إياه المشرف',
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
