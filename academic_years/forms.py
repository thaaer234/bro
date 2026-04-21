from django import forms

from quick.models import AcademicYear
from accounts.models import Course
from .models import AcademicYearTransferBatch


class AcademicYearSelectionForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.none(),
        label="الفصل الدراسي",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        available_years = kwargs.pop("available_years", None)
        super().__init__(*args, **kwargs)
        queryset = available_years if available_years is not None else AcademicYear.objects.all()
        self.fields["academic_year"].queryset = queryset.order_by("-start_date", "-id")


class AcademicYearUnlockForm(forms.Form):
    password = forms.CharField(
        label="كلمة سر الفصل",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )


class AcademicYearAccessPolicyForm(forms.Form):
    requires_password = forms.BooleanField(required=False, label="يتطلب كلمة سر")
    password = forms.CharField(
        required=False,
        label="كلمة سر جديدة",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
        help_text="اترك الحقل فارغًا للإبقاء على كلمة السر الحالية.",
    )
    is_read_only = forms.BooleanField(required=False, label="قراءة فقط")
    is_archived = forms.BooleanField(required=False, label="مؤرشف")
    allow_reporting = forms.BooleanField(required=False, initial=True, label="السماح بالتقارير")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("requires_password") and not cleaned_data.get("password") and not getattr(self, "policy_has_password", False):
            self.add_error("password", "يجب إدخال كلمة سر عند تفعيل حماية الفصل لأول مرة.")
        return cleaned_data


class AcademicYearTransferBatchForm(forms.ModelForm):
    source_courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.none(),
        label="الدورات المراد ترحيلها",
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = AcademicYearTransferBatch
        fields = ["source_academic_year", "target_academic_year", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_academic_year"].queryset = AcademicYear.objects.order_by("-start_date", "-id")
        self.fields["target_academic_year"].queryset = AcademicYear.objects.order_by("-start_date", "-id")
        self.fields["source_courses"].queryset = Course.objects.filter(is_active=True, academic_year__isnull=False).order_by("name")

        source_academic_year = None
        raw_source = self.data.get("source_academic_year") if self.is_bound else self.initial.get("source_academic_year")
        if raw_source:
            try:
                source_academic_year = AcademicYear.objects.get(pk=raw_source)
            except (AcademicYear.DoesNotExist, ValueError, TypeError):
                source_academic_year = None
        if source_academic_year:
            self.fields["source_courses"].queryset = self.fields["source_courses"].queryset.filter(
                academic_year=source_academic_year
            )

    def clean(self):
        cleaned_data = super().clean()
        source_academic_year = cleaned_data.get("source_academic_year")
        target_academic_year = cleaned_data.get("target_academic_year")
        source_courses = cleaned_data.get("source_courses")

        if source_academic_year and target_academic_year and source_academic_year.pk == target_academic_year.pk:
            self.add_error("target_academic_year", "الفصل الهدف يجب أن يختلف عن الفصل المصدر.")

        if source_academic_year and source_courses:
            invalid_courses = [course for course in source_courses if course.academic_year_id != source_academic_year.pk]
            if invalid_courses:
                self.add_error("source_courses", "كل الدورات المختارة يجب أن تكون من الفصل المصدر.")

        return cleaned_data
