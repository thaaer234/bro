from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('quick', '0014_quickcoursesessionattendanceguest'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='QuickCourseWithdrawal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('withdrawal_reason', models.TextField(blank=True, verbose_name='سبب السحب')),
                ('withdrawn_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='تاريخ السحب')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='withdrawn_students', to='quick.quickcourse', verbose_name='الدورة السريعة')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_withdrawals', to='quick.quickstudent', verbose_name='الطالب السريع')),
                ('withdrawn_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quick_course_withdrawals', to=settings.AUTH_USER_MODEL, verbose_name='تم السحب بواسطة')),
            ],
            options={
                'verbose_name': 'مسحوب من الدورات السريعة',
                'verbose_name_plural': 'المسحوبون من الدورات السريعة',
                'ordering': ['-withdrawn_at', '-id'],
                'unique_together': {('student', 'course')},
            },
        ),
    ]
