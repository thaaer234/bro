from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mobile", "0004_rename_mobiledevi_user_ty_8d20c9_idx_mobile_mobi_user_ty_9178b4_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="listeningtest",
            name="max_grade",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("10.00"),
                max_digits=6,
                verbose_name="??????? ??????",
            ),
        ),
    ]
