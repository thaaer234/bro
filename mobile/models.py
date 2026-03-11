from decimal import Decimal

from django.db import models
from django.utils import timezone


class MobileNotification(models.Model):
    TYPE_CHOICES = [
        ("attendance", "حضور"),
        ("payment", "دفع"),
        ("warning", "إنذار"),
        ("exam", "اختبار"),
        ("test_assignment", "تسميع"),
    ]

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="mobile_notifications",
        verbose_name="الطالب",
    )
    teacher = models.ForeignKey(
        "employ.Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="المدرس",
    )
    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        verbose_name="نوع الإشعار",
    )
    title = models.CharField(max_length=200, verbose_name="العنوان")
    message = models.TextField(verbose_name="الرسالة")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="تاريخ الإنشاء")
    is_read = models.BooleanField(default=False, verbose_name="تم قراءته")

    class Meta:
        verbose_name = "إشعار موبايل"
        verbose_name_plural = "إشعارات الموبايل"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.full_name} - {self.title}"


class MobileDeviceToken(models.Model):
    USER_TYPES = [
        ("teacher", "Teacher"),
        ("parent", "Parent"),
        ("student", "Student"),
    ]

    LOGIN_ROLES = [
        ("teacher", "Teacher"),
        ("student", "Student"),
        ("father", "Father"),
        ("mother", "Mother"),
        ("parent", "Parent"),
    ]

    user_type = models.CharField(max_length=20, choices=USER_TYPES, null=True, blank=True)
    user_id = models.PositiveIntegerField(null=True, blank=True)
    login_role = models.CharField(max_length=20, choices=LOGIN_ROLES, null=True, blank=True)
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=20, default="android")
    device_id = models.CharField(max_length=255, blank=True)
    device_name = models.CharField(max_length=100, blank=True)
    app_version = models.CharField(max_length=50, blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user_type", "user_id"]),
        ]
        verbose_name = "Mobile Device Token"
        verbose_name_plural = "Mobile Device Tokens"

    def __str__(self):
        return f"{self.user_type}#{self.user_id} - {self.platform}"


class ListeningTest(models.Model):
    teacher = models.ForeignKey(
        "employ.Teacher",
        on_delete=models.CASCADE,
        related_name="listening_tests",
        verbose_name="المدرس",
    )
    title = models.CharField(max_length=200, verbose_name="عنوان الاختبار")
    description = models.TextField(blank=True, verbose_name="وصف")
    max_grade = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("10.00"),
        verbose_name="??????? ??????",
    )
    classroom = models.ForeignKey(
        "classroom.Classroom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="listening_tests",
        verbose_name="الشعبة",
    )
    students = models.ManyToManyField(
        "students.Student",
        through="ListeningTestAssignment",
        verbose_name="الطلاب",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإنشاء")

    class Meta:
        verbose_name = "اختبار تسميع"
        verbose_name_plural = "اختبارات التسميع"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.teacher.full_name}"


class ListeningTestAssignment(models.Model):
    test = models.ForeignKey(
        ListeningTest,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="اختبار",
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        related_name="listening_assignments",
        verbose_name="الطالب",
    )
    is_listened = models.BooleanField(default=False, verbose_name="تم التسميع")
    grade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="العلامة"
    )
    note = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="ملاحظة"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإعلان")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخر تحديث")

    class Meta:
        verbose_name = "حالة تسميع"
        verbose_name_plural = "حالات التسميع"
        unique_together = ("test", "student")

    def __str__(self):
        status = "تم التسميع" if self.is_listened else "لم يتم"
        return f"{self.student.full_name} - {self.test.title} ({status})"
