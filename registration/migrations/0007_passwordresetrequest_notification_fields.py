from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0006_alter_passwordchangehistory_new_password_hash_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='passwordresetrequest',
            name='approval_email_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='passwordresetrequest',
            name='approved_via_email_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='passwordresetrequest',
            name='last_notification_error',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='passwordresetrequest',
            name='whatsapp_delivery_status',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='passwordresetrequest',
            name='whatsapp_phone',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='passwordresetrequest',
            name='whatsapp_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
