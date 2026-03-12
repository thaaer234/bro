from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class AnnouncementQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        return self.filter(
            is_active=True,
            starts_at__lte=now,
        ).filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now))


class Announcement(models.Model):
    AUDIENCE_USER = "user"
    AUDIENCE_STUDENT = "student"
    AUDIENCE_PARENT = "parent"
    AUDIENCE_TEACHER = "teacher"
    AUDIENCE_CHOICES = [
        (AUDIENCE_USER, "المستخدمون"),
        (AUDIENCE_STUDENT, "الطلاب"),
        (AUDIENCE_PARENT, "أهالي الطلاب"),
        (AUDIENCE_TEACHER, "المدرسون"),
    ]

    title = models.CharField(max_length=200, verbose_name="عنوان التعميم")
    message = models.TextField(verbose_name="نص التعميم")
    action_label = models.CharField(max_length=120, blank=True, default="", verbose_name="نص الزر")
    action_url = models.URLField(blank=True, default="", verbose_name="رابط الزر")
    audience_type = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, verbose_name="الفئة المستهدفة")
    is_active = models.BooleanField(default=True, verbose_name="مفعل")
    show_as_popup = models.BooleanField(default=True, verbose_name="إظهار منبثقاً على الويب")
    starts_at = models.DateTimeField(default=timezone.now, verbose_name="يبدأ العرض في")
    ends_at = models.DateTimeField(null=True, blank=True, verbose_name="ينتهي العرض في")
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_announcements")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AnnouncementQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "تعميم"
        verbose_name_plural = "التعاميم"

    def __str__(self):
        return f"{self.title} - {self.get_audience_type_display()}"

    @property
    def read_count(self):
        return self.receipts.filter(read_at__isnull=False).count()

    @property
    def dismiss_count(self):
        return self.receipts.filter(dismissed_at__isnull=False).count()


class AnnouncementReceipt(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="receipts")
    recipient_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.CASCADE, related_name="announcement_receipts"
    )
    recipient_student = models.ForeignKey(
        "students.Student", null=True, blank=True, on_delete=models.CASCADE, related_name="announcement_receipts"
    )
    recipient_teacher = models.ForeignKey(
        "employ.Teacher", null=True, blank=True, on_delete=models.CASCADE, related_name="announcement_receipts"
    )
    login_role = models.CharField(max_length=20, blank=True, default="", verbose_name="صفة الدخول")
    first_seen_at = models.DateTimeField(null=True, blank=True, verbose_name="أول ظهور")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت القراءة")
    dismissed_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت الإغلاق")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        verbose_name = "سجل قراءة تعميم"
        verbose_name_plural = "سجلات قراءة التعاميم"
        indexes = [
            models.Index(fields=["announcement", "recipient_user"]),
            models.Index(fields=["announcement", "recipient_student", "login_role"]),
            models.Index(fields=["announcement", "recipient_teacher"]),
        ]

    def __str__(self):
        return f"{self.announcement.title} - {self.recipient_label}"

    @property
    def recipient_label(self):
        if self.recipient_user_id:
            return self.recipient_user.get_username()
        if self.recipient_teacher_id:
            return self.recipient_teacher.full_name
        if self.recipient_student_id:
            role = f" ({self.login_role})" if self.login_role else ""
            return f"{self.recipient_student.full_name}{role}"
        return "-"
