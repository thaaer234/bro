from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('quick', '0008_alter_quickcourse_course_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='QuickReceiptPrintJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payload', models.JSONField(default=dict)),
                ('status', models.CharField(choices=[('pending', 'قيد الانتظار'), ('processing', 'قيد المعالجة'), ('completed', 'تمت الطباعة'), ('failed', 'فشلت الطباعة')], default='pending', max_length=20)),
                ('error_message', models.TextField(blank=True)),
                ('picked_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quick_print_jobs', to=settings.AUTH_USER_MODEL)),
                ('quick_student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='print_jobs', to='quick.quickstudent')),
            ],
            options={
                'verbose_name': 'مهمة طباعة إيصالات سريعة',
                'verbose_name_plural': 'مهام طباعة الإيصالات السريعة',
                'ordering': ['status', 'created_at'],
            },
        ),
    ]
