# Generated manually for MobileDeviceToken
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("mobile", "0002_listeningtestassignment_grade_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MobileDeviceToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_type", models.CharField(choices=[("teacher", "Teacher"), ("parent", "Parent")], max_length=20)),
                ("user_id", models.PositiveIntegerField()),
                ("token", models.CharField(max_length=255, unique=True)),
                ("platform", models.CharField(default="android", max_length=20)),
                ("device_id", models.CharField(blank=True, max_length=255)),
                ("app_version", models.CharField(blank=True, max_length=50)),
                ("last_seen_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Mobile Device Token",
                "verbose_name_plural": "Mobile Device Tokens",
            },
        ),
        migrations.AddIndex(
            model_name="mobiledevicetoken",
            index=models.Index(fields=["user_type", "user_id"], name="mobiledevi_user_ty_8d20c9_idx"),
        ),
    ]
