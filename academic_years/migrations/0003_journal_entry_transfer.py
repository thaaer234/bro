from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0009_backfill_academic_year_scope"),
        ("academic_years", "0002_transfers"),
    ]

    operations = [
        migrations.CreateModel(
            name="JournalEntryTransferBatch",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "مسودة"),
                            ("validated", "تمت المعاينة"),
                            ("completed", "مكتمل"),
                            ("failed", "فشل"),
                        ],
                        default="draft",
                        max_length=20,
                        verbose_name="الحالة",
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات")),
                (
                    "summary_json",
                    models.JSONField(blank=True, default=dict, verbose_name="ملخص التنفيذ"),
                ),
                (
                    "executed_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="وقت التنفيذ"
                    ),
                ),
                (
                    "failure_reason",
                    models.TextField(blank=True, verbose_name="سبب الفشل"),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_journal_entry_transfer_batches",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="أنشئ بواسطة",
                    ),
                ),
                (
                    "target_academic_year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="incoming_journal_entry_transfer_batches",
                        to="quick.academicyear",
                        verbose_name="الفصل الهدف",
                    ),
                ),
            ],
            options={
                "verbose_name": "دفعة نقل قيود",
                "verbose_name_plural": "دفعات نقل القيود",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="JournalEntryTransferItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "بانتظار التنفيذ"),
                            ("previewed", "تمت المعاينة"),
                            ("completed", "مكتمل"),
                            ("skipped", "تم التخطي"),
                            ("failed", "فشل"),
                        ],
                        default="pending",
                        max_length=20,
                        verbose_name="الحالة",
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="ملاحظات")),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "batch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="journal_entry_items",
                        to="academic_years.journalentrytransferbatch",
                        verbose_name="دفعة الترحيل",
                    ),
                ),
                (
                    "source_journal_entry",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="outgoing_transfer_items",
                        to="accounts.journalentry",
                        verbose_name="القيد المصدر",
                    ),
                ),
                (
                    "target_journal_entry",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="incoming_transfer_items",
                        to="accounts.journalentry",
                        verbose_name="القيد الهدف",
                    ),
                ),
            ],
            options={
                "verbose_name": "عنصر قيد في الترحيل",
                "verbose_name_plural": "عناصر القيود في الترحيل",
                "ordering": ["id"],
                "unique_together": {("batch", "source_journal_entry")},
            },
        ),
    ]
