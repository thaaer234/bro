from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0005_systemreportcoursestats_account_balance_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserClickEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('path', models.CharField(blank=True, max_length=255)),
                ('page_title', models.CharField(blank=True, max_length=255)),
                ('element_tag', models.CharField(blank=True, max_length=40)),
                ('element_id', models.CharField(blank=True, max_length=120)),
                ('element_class', models.CharField(blank=True, max_length=255)),
                ('element_text', models.CharField(blank=True, max_length=255)),
                ('is_trusted', models.BooleanField(default=True)),
                ('session_key', models.CharField(blank=True, max_length=120)),
                ('client_x', models.IntegerField(blank=True, null=True)),
                ('client_y', models.IntegerField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='auth.user')),
            ],
            options={
                'verbose_name': 'سجل النقرات',
                'verbose_name_plural': 'سجلات النقرات',
                'ordering': ['-timestamp'],
            },
        ),
    ]
