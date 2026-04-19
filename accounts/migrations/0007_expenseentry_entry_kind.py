from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_costcenter_opening_balance'),
    ]

    operations = [
        migrations.AddField(
            model_name='expenseentry',
            name='entry_kind',
            field=models.CharField(
                choices=[('EXPENSE', 'مصروف'), ('FOLLOWUP_REVENUE', 'إيراد طلاب المتابعة')],
                default='EXPENSE',
                max_length=30,
                verbose_name='نوع الحركة / Entry Kind',
            ),
        ),
    ]
