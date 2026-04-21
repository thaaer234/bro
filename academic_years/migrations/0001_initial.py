from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("quick", "0015_quickcoursewithdrawal"),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademicYearAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("requires_password", models.BooleanField(default=False, verbose_name="يتطلب كلمة سر")),
                ("password_hash", models.CharField(blank=True, max_length=255, verbose_name="كلمة السر المشفرة")),
                ("is_read_only", models.BooleanField(default=False, verbose_name="قراءة فقط")),
                ("is_archived", models.BooleanField(default=False, verbose_name="مؤرشف")),
                ("allow_reporting", models.BooleanField(default=True, verbose_name="السماح بالتقارير")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("academic_year", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="access_policy", to="quick.academicyear", verbose_name="الفصل الدراسي")),
            ],
            options={
                "verbose_name": "سياسة وصول الفصل",
                "verbose_name_plural": "سياسات وصول الفصول",
            },
        ),
        migrations.CreateModel(
            name="AcademicYearStateLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("created", "إنشاء"), ("activated", "تفعيل"), ("closed", "إغلاق"), ("reopened", "إعادة فتح"), ("password_enabled", "تفعيل كلمة السر"), ("password_disabled", "إلغاء كلمة السر"), ("read_only_enabled", "تفعيل القراءة فقط"), ("read_only_disabled", "إلغاء القراءة فقط"), ("unlocked", "فتح الفصل")], max_length=50, verbose_name="الإجراء")),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("academic_year", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="state_logs", to="quick.academicyear", verbose_name="الفصل الدراسي")),
                ("performed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="academic_year_logs", to=settings.AUTH_USER_MODEL, verbose_name="تم بواسطة")),
            ],
            options={
                "verbose_name": "سجل حالة الفصل",
                "verbose_name_plural": "سجل حالات الفصول",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="AcademicYearSystemState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton_key", models.CharField(default="default", max_length=20, unique=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("active_academic_year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="system_state_entries", to="quick.academicyear", verbose_name="الفصل النشط")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_academic_year_system_states", to=settings.AUTH_USER_MODEL, verbose_name="تم التحديث بواسطة")),
            ],
            options={
                "verbose_name": "حالة النظام للفصل",
                "verbose_name_plural": "حالة النظام للفصول",
            },
        ),
    ]

