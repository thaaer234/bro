from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('quick', '0012_quickcoursesession_room_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='QuickManualSortingSelection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('selected_at', models.DateTimeField(auto_now=True)),
                ('enrollment', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='manual_sorting_selection', to='quick.quickenrollment')),
                ('selected_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quick_manual_sorting_selections', to=settings.AUTH_USER_MODEL)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manual_sorting_selections', to='quick.quickcoursesession')),
            ],
            options={
                'verbose_name': 'تثبيت فرز شبه يدوي',
                'verbose_name_plural': 'تثبيتات الفرز شبه اليدوي',
                'ordering': ['-selected_at', 'id'],
            },
        ),
    ]
