from django import forms
from django.forms.widgets import CheckboxSelectMultiple

class MobileLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'اسم الطالب أو المدرّس',
            'class': 'form-control'
        })
    )
    password = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'رقم الهاتف',
            'class': 'form-control'
        })
    )
