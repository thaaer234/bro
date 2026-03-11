from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='teacherattendance',
            name='half_session_count',
            field=models.PositiveIntegerField(
                default=0,
                verbose_name='عدد أنصاف الجلسات',
                help_text='عدد أنصاف الجلسات (كل نصف جلسة = 0.5 جلسة)'
            ),
        ),
    ]