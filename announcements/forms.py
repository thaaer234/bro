from django import forms

from .models import Announcement


PLACEHOLDER_HELP = {
    Announcement.AUDIENCE_USER: [
        "{name}",
        "{username}",
        "{email}",
        "{first_name}",
        "{last_name}",
    ],
    Announcement.AUDIENCE_STUDENT: [
        "{name}",
        "{student_name}",
        "{student_number}",
        "{student_phone}",
        "{branch}",
    ],
    Announcement.AUDIENCE_PARENT: [
        "{name}",
        "{parent_name}",
        "{student_name}",
        "{father_name}",
        "{mother_name}",
        "{parent_role}",
    ],
    Announcement.AUDIENCE_TEACHER: [
        "{name}",
        "{teacher_name}",
        "{phone_number}",
    ],
}


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = [
            "title",
            "message",
            "action_label",
            "action_url",
            "audience_type",
            "is_active",
            "show_as_popup",
            "starts_at",
            "ends_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "action_label": forms.TextInput(attrs={"class": "form-control"}),
            "action_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://example.com/path"}),
            "audience_type": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "show_as_popup": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "starts_at": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        audience_type = self.data.get("audience_type") if self.is_bound else (self.instance.audience_type or self.initial.get("audience_type"))
        self.fields["title"].help_text = self._build_help_text(audience_type)
        self.fields["message"].help_text = "يمكنك استخدام نفس المتغيرات داخل نص التعميم."
        self.fields["action_label"].help_text = "اختياري. مثال: طلب تعديل كلمة المرور"
        self.fields["action_url"].help_text = "اختياري. سيظهر زر رابط داخل التعميم."

    def _build_help_text(self, audience_type):
        placeholders = PLACEHOLDER_HELP.get(audience_type or Announcement.AUDIENCE_USER, [])
        return "المتغيرات المتاحة: " + " - ".join(placeholders)

    def clean(self):
        cleaned_data = super().clean()
        starts_at = cleaned_data.get("starts_at")
        ends_at = cleaned_data.get("ends_at")
        if starts_at and ends_at and ends_at < starts_at:
            self.add_error("ends_at", "تاريخ النهاية يجب أن يكون بعد تاريخ البداية.")
        return cleaned_data
