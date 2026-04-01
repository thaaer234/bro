from datetime import timedelta

from django.db import migrations, models


def populate_end_date(apps, schema_editor):
    QuickCourseSession = apps.get_model('quick', 'QuickCourseSession')
    for session in QuickCourseSession.objects.all():
        total_days = getattr(session, 'total_days', 1) or 1
        session.end_date = session.start_date + timedelta(days=max(total_days, 1) - 1)
        if not getattr(session, 'min_capacity', None):
            session.min_capacity = 1
        session.save(update_fields=['end_date', 'min_capacity'])


class Migration(migrations.Migration):

    dependencies = [
        ('quick', '0010_quickcoursesession_quickcoursesessionenrollment_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='quickcoursesession',
            name='end_date',
            field=models.DateField(default='2026-04-01', verbose_name='تاريخ النهاية'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='quickcoursesession',
            name='min_capacity',
            field=models.PositiveIntegerField(default=1, verbose_name='الحد الأدنى للافتتاح'),
        ),
        migrations.RunPython(populate_end_date, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='quickcoursesession',
            name='total_days',
        ),
    ]
