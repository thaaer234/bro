from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employ', '0007_employeeattendance_is_manually_adjusted_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='annual_leave_days',
            field=models.PositiveIntegerField(default=14, verbose_name='الإجازات النظامية السنوية'),
        ),
        migrations.AddField(
            model_name='employee',
            name='hourly_rate',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='أجر الساعة'),
        ),
        migrations.AddField(
            model_name='employee',
            name='overtime_hourly_rate',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='أجر ساعة الإضافي'),
        ),
        migrations.AddField(
            model_name='employee',
            name='payroll_method',
            field=models.CharField(choices=[('monthly', 'شهري'), ('hourly', 'ساعي'), ('mixed', 'مختلط')], default='monthly', max_length=20, verbose_name='طريقة حساب الراتب'),
        ),
        migrations.AddField(
            model_name='employee',
            name='required_monthly_hours',
            field=models.PositiveIntegerField(default=0, verbose_name='الساعات المطلوبة شهريًا'),
        ),
        migrations.AddField(
            model_name='employee',
            name='sick_leave_days',
            field=models.PositiveIntegerField(default=7, verbose_name='الإجازات المرضية السنوية'),
        ),
        migrations.AddField(
            model_name='employee',
            name='weekend_days',
            field=models.CharField(blank=True, default='4,5', max_length=20, verbose_name='أيام العطلة الأسبوعية'),
        ),
    ]
