from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("quick", "0015_quickcoursewithdrawal"),
        ("accounts", "0007_expenseentry_entry_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="academic_year",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="accounts_accounts",
                to="quick.academicyear",
                verbose_name="الفصل الدراسي / Academic Year",
            ),
        ),
        migrations.AddField(
            model_name="course",
            name="academic_year",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounts_courses",
                to="quick.academicyear",
                verbose_name="الفصل الدراسي / Academic Year",
            ),
        ),
        migrations.AddField(
            model_name="journalentry",
            name="academic_year",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounts_journal_entries",
                to="quick.academicyear",
                verbose_name="الفصل الدراسي / Academic Year",
            ),
        ),
        migrations.AddField(
            model_name="studentenrollment",
            name="academic_year",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounts_enrollments",
                to="quick.academicyear",
                verbose_name="الفصل الدراسي / Academic Year",
            ),
        ),
        migrations.AddField(
            model_name="studentreceipt",
            name="academic_year",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounts_receipts",
                to="quick.academicyear",
                verbose_name="الفصل الدراسي / Academic Year",
            ),
        ),
    ]

