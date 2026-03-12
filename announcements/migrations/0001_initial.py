from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("students", "0005_studentwarning"),
        ("employ", "0005_teacher_hourly_rate_literary_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Announcement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="عنوان التعميم")),
                ("message", models.TextField(verbose_name="نص التعميم")),
                ("audience_type", models.CharField(choices=[("user", "المستخدمون"), ("student", "الطلاب"), ("parent", "أهالي الطلاب"), ("teacher", "المدرسون")], max_length=20, verbose_name="الفئة المستهدفة")),
                ("is_active", models.BooleanField(default=True, verbose_name="مفعل")),
                ("show_as_popup", models.BooleanField(default=True, verbose_name="إظهار منبثقاً على الويب")),
                ("starts_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="يبدأ العرض في")),
                ("ends_at", models.DateTimeField(blank=True, null=True, verbose_name="ينتهي العرض في")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_announcements", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"], "verbose_name": "تعميم", "verbose_name_plural": "التعاميم"},
        ),
        migrations.CreateModel(
            name="AnnouncementReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("login_role", models.CharField(blank=True, default="", max_length=20, verbose_name="صفة الدخول")),
                ("first_seen_at", models.DateTimeField(blank=True, null=True, verbose_name="أول ظهور")),
                ("read_at", models.DateTimeField(blank=True, null=True, verbose_name="وقت القراءة")),
                ("dismissed_at", models.DateTimeField(blank=True, null=True, verbose_name="وقت الإغلاق")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("announcement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="receipts", to="announcements.announcement")),
                ("recipient_student", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="announcement_receipts", to="students.student")),
                ("recipient_teacher", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="announcement_receipts", to="employ.teacher")),
                ("recipient_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="announcement_receipts", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at", "-created_at"], "verbose_name": "سجل قراءة تعميم", "verbose_name_plural": "سجلات قراءة التعاميم"},
        ),
        migrations.AddIndex(
            model_name="announcementreceipt",
            index=models.Index(fields=["announcement", "recipient_user"], name="announcement_announc_5da581_idx"),
        ),
        migrations.AddIndex(
            model_name="announcementreceipt",
            index=models.Index(fields=["announcement", "recipient_student", "login_role"], name="announcement_announc_37395f_idx"),
        ),
        migrations.AddIndex(
            model_name="announcementreceipt",
            index=models.Index(fields=["announcement", "recipient_teacher"], name="announcement_announc_f6a6b1_idx"),
        ),
    ]
