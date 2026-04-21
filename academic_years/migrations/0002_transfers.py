from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0009_backfill_academic_year_scope"),
        ("academic_years", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademicYearTransferBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("draft", "مسودة"), ("validated", "تمت المعاينة"), ("completed", "مكتمل"), ("failed", "فشل")], default="draft", max_length=20, verbose_name="الحالة")),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات")),
                ("summary_json", models.JSONField(blank=True, default=dict, verbose_name="ملخص التنفيذ")),
                ("executed_at", models.DateTimeField(blank=True, null=True, verbose_name="وقت التنفيذ")),
                ("failure_reason", models.TextField(blank=True, verbose_name="سبب الفشل")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_academic_year_transfer_batches", to=settings.AUTH_USER_MODEL, verbose_name="أنشئ بواسطة")),
                ("source_academic_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_transfer_batches", to="quick.academicyear", verbose_name="الفصل المصدر")),
                ("target_academic_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="incoming_transfer_batches", to="quick.academicyear", verbose_name="الفصل الهدف")),
            ],
            options={
                "verbose_name": "دفعة ترحيل فصل",
                "verbose_name_plural": "دفعات ترحيل الفصول",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="AcademicYearTransferLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("level", models.CharField(choices=[("info", "معلومة"), ("warning", "تحذير"), ("error", "خطأ")], default="info", max_length=20, verbose_name="المستوى")),
                ("message", models.TextField(verbose_name="الرسالة")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="البيانات")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="logs", to="academic_years.academicyeartransferbatch", verbose_name="دفعة الترحيل")),
            ],
            options={
                "verbose_name": "سجل ترحيل",
                "verbose_name_plural": "سجلات الترحيل",
                "ordering": ["created_at", "id"],
            },
        ),
        migrations.CreateModel(
            name="AcademicYearTransferCourseItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("student_count", models.PositiveIntegerField(default=0, verbose_name="عدد الطلاب")),
                ("enrollment_count", models.PositiveIntegerField(default=0, verbose_name="عدد التسجيلات")),
                ("receipt_count", models.PositiveIntegerField(default=0, verbose_name="عدد الإيصالات")),
                ("journal_entry_count", models.PositiveIntegerField(default=0, verbose_name="عدد القيود")),
                ("status", models.CharField(choices=[("pending", "بانتظار التنفيذ"), ("previewed", "تمت المعاينة"), ("completed", "مكتمل"), ("skipped", "تم التخطي"), ("failed", "فشل")], default="pending", max_length=20, verbose_name="الحالة")),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات")),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="course_items", to="academic_years.academicyeartransferbatch", verbose_name="دفعة الترحيل")),
                ("source_course", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="source_transfer_items", to="accounts.course", verbose_name="الدورة المصدر")),
                ("target_course", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="target_transfer_items", to="accounts.course", verbose_name="الدورة الهدف")),
            ],
            options={
                "verbose_name": "عنصر دورة في الترحيل",
                "verbose_name_plural": "عناصر الدورات في الترحيل",
                "ordering": ["id"],
                "unique_together": {("batch", "source_course")},
            },
        ),
    ]

