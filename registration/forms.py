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
    username = forms.CharField(
        label='اسم المستخدم',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'أدخل اسم المستخدم الخاص بك',
        })
    )
    phone = forms.CharField(
        label='رقم الهاتف المرتبط بالحساب',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'أدخل رقم الهاتف المرتبط بحسابك (مثال: 05xxxxxxxxx)',
        })
    )
    reason = forms.CharField(
        label='سبب طلب تعديل كلمة المرور',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'اذكر سبب طلبك لتعديل كلمة المرور',
        })
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user and self.user.is_authenticated:
            self.fields['username'].required = False
            self.fields['username'].widget = forms.HiddenInput()
            self.fields['phone'].required = False
            self.fields['phone'].widget = forms.HiddenInput()
        else:
            self.fields['username'].required = True
            self.fields['phone'].required = True

    def clean(self):
        cleaned_data = super().clean()
        if not self.user or not self.user.is_authenticated:
            username = cleaned_data.get('username', '').strip()
            phone = cleaned_data.get('phone', '').strip()

            if not username:
                self.add_error('username', 'اسم المستخدم مطلوب لطلب إعادة التعيين')
                return cleaned_data
            if not phone:
                self.add_error('phone', 'رقم الهاتف مطلوب لطلب إعادة التعيين')
                return cleaned_data

            # Sanitize inputs to prevent SQL injection or malicious patterns
            import re
            username_clean = re.sub(r'[^\w\.-]', '', username)
            if username != username_clean:
                self.add_error('username', 'اسم المستخدم يحتوي على رموز غير صالحة')
                return cleaned_data

            phone_clean = re.sub(r'[^\d\+]', '', phone)
            if not phone_clean:
                self.add_error('phone', 'رقم الهاتف يجب أن يحتوي على أرقام فقط')
                return cleaned_data

            from django.contrib.auth.models import User
            try:
                target_user = User.objects.get(username=username)
            except User.DoesNotExist:
                raise forms.ValidationError('اسم المستخدم أو رقم الهاتف غير مطابق للبيانات المسجلة لدينا.')

            profile = getattr(target_user, 'profile', None)
            if not profile:
                raise forms.ValidationError('اسم المستخدم أو رقم الهاتف غير مطابق للبيانات المسجلة لدينا.')

            stored_phone = (profile.phone or '').strip()
            def normalize_phone(p):
                return re.sub(r'\D', '', p)

            if not stored_phone or normalize_phone(stored_phone) != normalize_phone(phone):
                raise forms.ValidationError('اسم المستخدم أو رقم الهاتف غير مطابق للبيانات المسجلة لدينا.')

            self.cleaned_target_user = target_user

        return cleaned_data


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
