from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quick', '0006_academicyear_is_open_ended'),
    ]

    operations = [
        migrations.AddField(
            model_name='quickstudent',
            name='course_track',
            field=models.CharField(
                choices=[('INTENSIVE', 'مكثفات'), ('EXAM', 'امتحانية')],
                default='INTENSIVE',
                max_length=20,
                verbose_name='نوع الدورة',
            ),
        ),
    ]
