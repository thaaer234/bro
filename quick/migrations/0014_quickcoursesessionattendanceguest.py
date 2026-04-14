from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('quick', '0013_quickmanualsortingselection'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='QuickCourseSessionAttendanceGuest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('attendance_date', models.DateField(verbose_name='تاريخ الحضور')),
                ('day_number', models.PositiveIntegerField(default=1, verbose_name='رقم اليوم')),
                ('full_name', models.CharField(max_length=200, verbose_name='الاسم')),
                ('status', models.CharField(choices=[('present', 'حاضر'), ('absent', 'غائب')], default='present', max_length=20, verbose_name='الحالة')),
                ('notes', models.CharField(blank=True, max_length=255, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_quick_guest_attendance', to=settings.AUTH_USER_MODEL)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guest_attendance_records', to='quick.quickcoursesession')),
            ],
            options={
                'verbose_name': 'حضور اسم إضافي لجلسة سريعة',
                'verbose_name_plural': 'حضور الأسماء الإضافية للجلسات السريعة',
                'ordering': ['attendance_date', 'id'],
            },
        ),
    ]
