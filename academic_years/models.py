from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import models


class AcademicYearAccess(models.Model):
    academic_year = models.OneToOneField(
        "quick.AcademicYear",
        on_delete=models.CASCADE,
        related_name="access_policy",
        verbose_name="الفصل الدراسي",
    )
    requires_password = models.BooleanField(default=False, verbose_name="يتطلب كلمة سر")
    password_hash = models.CharField(max_length=255, blank=True, verbose_name="كلمة السر المشفرة")
    is_read_only = models.BooleanField(default=False, verbose_name="قراءة فقط")
    is_archived = models.BooleanField(default=False, verbose_name="مؤرشف")
    allow_reporting = models.BooleanField(default=True, verbose_name="السماح بالتقارير")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "سياسة وصول الفصل"
        verbose_name_plural = "سياسات وصول الفصول"

    def __str__(self):
        return f"سياسة الوصول: {self.academic_year}"

    def clean(self):
        if self.requires_password and not self.password_hash:
            raise ValidationError("يجب تعيين كلمة سر إذا كان الفصل محميًا.")

    def set_password(self, raw_password: str):
        self.password_hash = make_password(raw_password)

    def clear_password(self):
        self.password_hash = ""

    def check_password(self, raw_password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)


class AcademicYearSystemState(models.Model):
    singleton_key = models.CharField(max_length=20, unique=True, default="default")
    active_academic_year = models.ForeignKey(
        "quick.AcademicYear",
        on_delete=models.PROTECT,
        related_name="system_state_entries",
        verbose_name="الفصل النشط",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_academic_year_system_states",
        verbose_name="تم التحديث بواسطة",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "حالة النظام للفصل"
        verbose_name_plural = "حالة النظام للفصول"

    def __str__(self):
        return f"الفصل النشط: {self.active_academic_year}"

    @classmethod
    def load(cls):
        return cls.objects.select_related("active_academic_year", "updated_by").first()


class AcademicYearStateLog(models.Model):
    ACTION_CREATED = "created"
    ACTION_ACTIVATED = "activated"
    ACTION_CLOSED = "closed"
    ACTION_REOPENED = "reopened"
    ACTION_PASSWORD_ENABLED = "password_enabled"
    ACTION_PASSWORD_DISABLED = "password_disabled"
    ACTION_READ_ONLY_ENABLED = "read_only_enabled"
    ACTION_READ_ONLY_DISABLED = "read_only_disabled"
    ACTION_UNLOCKED = "unlocked"

    ACTION_CHOICES = [
        (ACTION_CREATED, "إنشاء"),
        (ACTION_ACTIVATED, "تفعيل"),
        (ACTION_CLOSED, "إغلاق"),
        (ACTION_REOPENED, "إعادة فتح"),
        (ACTION_PASSWORD_ENABLED, "تفعيل كلمة السر"),
        (ACTION_PASSWORD_DISABLED, "إلغاء كلمة السر"),
        (ACTION_READ_ONLY_ENABLED, "تفعيل القراءة فقط"),
        (ACTION_READ_ONLY_DISABLED, "إلغاء القراءة فقط"),
        (ACTION_UNLOCKED, "فتح الفصل"),
    ]

    academic_year = models.ForeignKey(
        "quick.AcademicYear",
        on_delete=models.CASCADE,
        related_name="state_logs",
        verbose_name="الفصل الدراسي",
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name="الإجراء")
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="academic_year_logs",
        verbose_name="تم بواسطة",
    )
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "سجل حالة الفصل"
        verbose_name_plural = "سجل حالات الفصول"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.academic_year} - {self.get_action_display()}"


class AcademicYearTransferBatch(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_VALIDATED = "validated"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "مسودة"),
        (STATUS_VALIDATED, "تمت المعاينة"),
        (STATUS_COMPLETED, "مكتمل"),
        (STATUS_FAILED, "فشل"),
    ]

    source_academic_year = models.ForeignKey(
        "quick.AcademicYear",
        on_delete=models.PROTECT,
        related_name="outgoing_transfer_batches",
        verbose_name="الفصل المصدر",
    )
    target_academic_year = models.ForeignKey(
        "quick.AcademicYear",
        on_delete=models.PROTECT,
        related_name="incoming_transfer_batches",
        verbose_name="الفصل الهدف",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_academic_year_transfer_batches",
        verbose_name="أنشئ بواسطة",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name="الحالة")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")
    summary_json = models.JSONField(default=dict, blank=True, verbose_name="ملخص التنفيذ")
    executed_at = models.DateTimeField(null=True, blank=True, verbose_name="وقت التنفيذ")
    failure_reason = models.TextField(blank=True, verbose_name="سبب الفشل")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "دفعة ترحيل فصل"
        verbose_name_plural = "دفعات ترحيل الفصول"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.source_academic_year} -> {self.target_academic_year} ({self.get_status_display()})"


class AcademicYearTransferCourseItem(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PREVIEWED = "previewed"
    STATUS_COMPLETED = "completed"
    STATUS_SKIPPED = "skipped"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "بانتظار التنفيذ"),
        (STATUS_PREVIEWED, "تمت المعاينة"),
        (STATUS_COMPLETED, "مكتمل"),
        (STATUS_SKIPPED, "تم التخطي"),
        (STATUS_FAILED, "فشل"),
    ]

    batch = models.ForeignKey(
        AcademicYearTransferBatch,
        on_delete=models.CASCADE,
        related_name="course_items",
        verbose_name="دفعة الترحيل",
    )
    source_course = models.ForeignKey(
        "accounts.Course",
        on_delete=models.PROTECT,
        related_name="source_transfer_items",
        verbose_name="الدورة المصدر",
    )
    target_course = models.ForeignKey(
        "accounts.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="target_transfer_items",
        verbose_name="الدورة الهدف",
    )
    student_count = models.PositiveIntegerField(default=0, verbose_name="عدد الطلاب")
    enrollment_count = models.PositiveIntegerField(default=0, verbose_name="عدد التسجيلات")
    receipt_count = models.PositiveIntegerField(default=0, verbose_name="عدد الإيصالات")
    journal_entry_count = models.PositiveIntegerField(default=0, verbose_name="عدد القيود")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="الحالة")
    notes = models.TextField(blank=True, verbose_name="ملاحظات")

    class Meta:
        verbose_name = "عنصر دورة في الترحيل"
        verbose_name_plural = "عناصر الدورات في الترحيل"
        unique_together = ("batch", "source_course")
        ordering = ["id"]

    def __str__(self):
        return f"{self.batch_id} - {self.source_course}"


class AcademicYearTransferLog(models.Model):
    LEVEL_INFO = "info"
    LEVEL_WARNING = "warning"
    LEVEL_ERROR = "error"

    LEVEL_CHOICES = [
        (LEVEL_INFO, "معلومة"),
        (LEVEL_WARNING, "تحذير"),
        (LEVEL_ERROR, "خطأ"),
    ]

    batch = models.ForeignKey(
        AcademicYearTransferBatch,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="دفعة الترحيل",
    )
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default=LEVEL_INFO, verbose_name="المستوى")
    message = models.TextField(verbose_name="الرسالة")
    payload = models.JSONField(default=dict, blank=True, verbose_name="البيانات")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "سجل ترحيل"
        verbose_name_plural = "سجلات الترحيل"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.get_level_display()} - {self.batch_id}"
