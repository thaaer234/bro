from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("announcements", "0002_rename_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="announcement",
            name="action_label",
            field=models.CharField(blank=True, default="", max_length=120, verbose_name="نص الزر"),
        ),
        migrations.AddField(
            model_name="announcement",
            name="action_url",
            field=models.URLField(blank=True, default="", verbose_name="رابط الزر"),
        ),
    ]
