
"""
Management command to fix AR account hierarchy for students and courses.

Usage:
  python manage.py fix_ar_hierarchy --model yourapp.Account --commit

By default it's a dry-run. Add --commit to apply changes.
You MUST provide --model in the form "<app_label>.<ModelName>", e.g. "finance.Account".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

CODE_PATTERN = re.compile(r"^(?P<root>\d{4})-(?P<course_id>\d{3})(?:-(?P<student_id>\d{3}))?$")
AR_ROOT_CODE = "1251"


@dataclass
class Change:
    pk: int
    code: str
    field: str
    old: Optional[str]
    new: Optional[str]


class Command(BaseCommand):
    help = "Fix Accounts Receivable (AR) parent relationships for course and student accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            required=True,
            help='Dotted model path "<app_label>.<ModelName>", e.g. "finance.Account"',
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Apply the changes (otherwise runs in dry-run mode).",
        )
        parser.add_argument(
            "--create-parent",
            action="store_true",
            help=f'Create AR parent with code "{AR_ROOT_CODE}" if missing.',
        )
        parser.add_argument(
            "--normalize-names",
            action="store_true",
            help="Normalize account names to AR-friendly defaults (optional).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="How many objects to save per transaction when committing.",
        )

    def handle(self, *args, **options):
        model_path = options["model"]
        commit = options["commit"]
        create_parent = options["create-parent"]
        normalize_names = options["normalize-names"]
        batch_size = options["batch_size"]

        app_label, model_name = self._split_model_path(model_path)
        Account = apps.get_model(app_label, model_name)
        if Account is None:
            raise CommandError(f"Could not load model from '{model_path}'.")

        # Ensure AR parent exists
        ar_parent = Account.objects.filter(code=AR_ROOT_CODE).first()
        if ar_parent is None:
            if not create_parent:
                raise CommandError(
                    f'AR parent with code "{AR_ROOT_CODE}" not found. Use --create-parent to create it.'
                )
            ar_parent = Account(
                code=AR_ROOT_CODE,
                name="Accounts Receivable - Students",
                name_ar="ذمم الطلاب المدينة",
                account_type="ASSET",
                is_active=True,
            )
            if commit:
                ar_parent.save()
            self.stdout.write(self.style.WARNING(f'Created AR parent "{AR_ROOT_CODE}" (commit={commit}).'))

        planned: list[Change] = []

        # 1) Fix course accounts: parent must be ar_parent
        course_qs = Account.objects.filter(is_course_account=True).only("id", "code", "name", "name_ar", "parent")
        for acc in course_qs.iterator():
            if acc.parent_id != getattr(ar_parent, "id", None):
                planned.append(Change(acc.id, acc.code, "parent", getattr(acc.parent, "code", None), ar_parent.code))
            if normalize_names:
                # Normalize names if they look like "Deferred Revenue" etc.
                expected_name = f"Accounts Receivable - {getattr(acc, 'course_name', '') or acc.code}"
                expected_name_ar = f"ذمم طلاب دورة {getattr(acc, 'course_name', '') or acc.code}"
                if getattr(acc, "name", None) and acc.name != expected_name:
                    planned.append(Change(acc.id, acc.code, "name", acc.name, expected_name))
                if getattr(acc, "name_ar", None) and acc.name_ar != expected_name_ar:
                    planned.append(Change(acc.id, acc.code, "name_ar", acc.name_ar, expected_name_ar))

        # 2) Fix student accounts: parent must be the related course account 1251-<course_id>
        student_qs = Account.objects.filter(is_student_account=True).only("id", "code", "parent", "name", "name_ar")
        missing_course = 0
        for acc in student_qs.iterator():
            course_code = self._derive_course_code(acc.code)
            if not course_code:
                self.stdout.write(self.style.WARNING(f"Skip (unrecognized code): {acc.code}"))
                continue

            course_acc = Account.objects.filter(code=course_code).only("id", "code").first()
            if not course_acc:
                missing_course += 1
                self.stdout.write(self.style.WARNING(f"Course account not found for student {acc.code} -> {course_code}"))
                continue

            if acc.parent_id != course_acc.id:
                planned.append(Change(acc.id, acc.code, "parent", getattr(acc.parent, "code", None), course_code))

            if normalize_names:
                # Normalize student names if needed
                student_name = getattr(acc, "student_name", None)
                if student_name:
                    expected_name = f"AR - {student_name}"
                    expected_name_ar = f"ذمة {student_name}"
                    if getattr(acc, "name", None) and acc.name != expected_name:
                        planned.append(Change(acc.id, acc.code, "name", acc.name, expected_name))
                    if getattr(acc, "name_ar", None) and acc.name_ar != expected_name_ar:
                        planned.append(Change(acc.id, acc.code, "name_ar", acc.name_ar, expected_name_ar))

        # Summarize
        parent_changes = [c for c in planned if c.field == "parent"]
        name_changes = [c for c in planned if c.field in ("name", "name_ar")]
        self.stdout.write(self.style.MIGRATE_HEADING("Planned changes:"))
        self.stdout.write(f"  Parent fixes: {len(parent_changes)}")
        self.stdout.write(f"  Name fixes:   {len(name_changes)}")
        self.stdout.write(f"  Student accounts with missing course: {missing_course}")

        if not commit:
            self.stdout.write(self.style.WARNING("Dry-run mode. No changes were saved. Use --commit to apply."))
            return

        # Apply in batches inside transactions
        self._apply(Account, planned, ar_parent, batch_size)

        self.stdout.write(self.style.SUCCESS("Done."))

    def _apply(self, Account, planned: list[Change], ar_parent, batch_size: int):
        # Group changes by account pk to apply consistently
        by_pk: dict[int, dict[str, Change]] = {}
        for ch in planned:
            by_pk.setdefault(ch.pk, {})[ch.field] = ch

        pks = list(by_pk.keys())
        total = len(pks)
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            chunk = pks[start:end]
            with transaction.atomic():
                accs = {a.id: a for a in Account.objects.select_for_update().filter(id__in=chunk)}
                for pk in chunk:
                    acc = accs.get(pk)
                    if not acc:
                        continue
                    fields_to_save = []
                    changes = by_pk[pk]
                    if "parent" in changes:
                        new_parent_code = changes["parent"].new
                        if new_parent_code == AR_ROOT_CODE:
                            parent_obj = Account.objects.filter(code=AR_ROOT_CODE).first()
                        else:
                            parent_obj = Account.objects.filter(code=new_parent_code).first()
                        if parent_obj and acc.parent_id != parent_obj.id:
                            acc.parent = parent_obj
                            fields_to_save.append("parent")
                    if "name" in changes:
                        acc.name = changes["name"].new
                        fields_to_save.append("name")
                    if "name_ar" in changes:
                        acc.name_ar = changes["name_ar"].new
                        fields_to_save.append("name_ar")
                    if fields_to_save:
                        acc.save(update_fields=list(set(fields_to_save)))

            print(f"Applied {end} / {total} accounts...")

    def _split_model_path(self, path: str) -> Tuple[str, str]:
        if "." not in path:
            raise CommandError('Invalid --model. Expected "<app_label>.<ModelName>"')
        app_label, model_name = path.split(".", 1)
        return app_label, model_name

    def _derive_course_code(self, code: str) -> Optional[str]:
        m = CODE_PATTERN.match(code or "")
        if not m:
            return None
        root = m.group("root")
        course_id = m.group("course_id")
        if root != AR_ROOT_CODE or not course_id:
            return None
        return f"{root}-{course_id}"
