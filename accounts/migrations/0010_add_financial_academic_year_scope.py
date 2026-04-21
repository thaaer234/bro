from django.db import migrations, models
import django.db.models.deletion


def backfill_financial_academic_year_scope(apps, schema_editor):
    AccountingPeriod = apps.get_model("accounts", "AccountingPeriod")
    ExpenseEntry = apps.get_model("accounts", "ExpenseEntry")
    EmployeeAdvance = apps.get_model("accounts", "EmployeeAdvance")
    Budget = apps.get_model("accounts", "Budget")

    for expense in ExpenseEntry.objects.filter(academic_year__isnull=True):
        year_id = None
        if expense.journal_entry_id:
            year_id = getattr(expense.journal_entry, "academic_year_id", None)
        if not year_id and expense.account_id:
            year_id = getattr(expense.account, "academic_year_id", None)
        if year_id:
            expense.academic_year_id = year_id
            expense.save(update_fields=["academic_year"])

    for advance in EmployeeAdvance.objects.filter(academic_year__isnull=True):
        year_id = None
        if advance.journal_entry_id:
            year_id = getattr(advance.journal_entry, "academic_year_id", None)
        if year_id:
            advance.academic_year_id = year_id
            advance.save(update_fields=["academic_year"])

    for period in AccountingPeriod.objects.filter(academic_year__isnull=True):
        linked_budget = (
            Budget.objects.filter(period_id=period.pk, account__academic_year__isnull=False)
            .select_related("account")
            .first()
        )
        if linked_budget and linked_budget.account.academic_year_id:
            period.academic_year_id = linked_budget.account.academic_year_id
            period.save(update_fields=["academic_year"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_backfill_academic_year_scope"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountingperiod",
            name="academic_year",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounts_periods",
                to="quick.academicyear",
                verbose_name="Academic Year",
            ),
        ),
        migrations.AddField(
            model_name="employeeadvance",
            name="academic_year",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounts_advances",
                to="quick.academicyear",
                verbose_name="Academic Year",
            ),
        ),
        migrations.AddField(
            model_name="expenseentry",
            name="academic_year",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="accounts_expenses",
                to="quick.academicyear",
                verbose_name="Academic Year",
            ),
        ),
        migrations.RunPython(backfill_financial_academic_year_scope, noop_reverse),
    ]
