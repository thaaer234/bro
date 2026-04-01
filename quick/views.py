from django import forms 
from django.views.generic import ListView, CreateView, DeleteView, UpdateView
from django.views.generic.edit import FormView
from django.urls import reverse, reverse_lazy
from django.db.models import Q, Sum, Value, DecimalField, Count
from django.db.models.functions import Coalesce
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.auth.decorators import login_required  # â†گ ط£ط¶ظپ ظ‡ط°ط§ ط§ظ„ط³ط·ط±
from attendance.models import Attendance
from classroom.models import Classroomenrollment, Classroom
from django.http import JsonResponse, Http404, HttpResponse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, TemplateView, ListView, DetailView
# from .models import QuickStudent, QuickEnrollment, QuickCourse, AcademicYear
from django.contrib import messages
from django.utils.dateparse import parse_date
from .forms import (
    AcademicYearForm,
    QuickCourseForm,
    QuickClassroomForm,
    QuickCourseTimeOptionForm,
    QuickCourseSessionForm,
    QuickSessionAssignStudentsForm,
    QuickSessionAttendanceBulkForm,
    QuickSessionTransferForm,
    QuickStudentForm,
    QuickEnrollmentForm,
    _normalize_quick_name,
    _normalize_quick_phone,
)
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from itertools import combinations
from math import ceil
import time
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import urlencode
from django.db.models import Prefetch
from django.conf import settings
from django.db import transaction, connection, OperationalError, close_old_connections
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from accounts.models import Transaction, JournalEntry, Account, get_user_cash_account
from .models import (
    QuickCourse,
    QuickCourseTimeOption,
    QuickCourseSession,
    QuickCourseSessionAttendance,
    QuickCourseSessionEnrollment,
    QuickEnrollment,
    QuickReceiptPrintJob,
    QuickStudent,
    QuickStudentReceipt,
    AcademicYear,
)
from accounts.models import Course, CostCenter
from .services.receipt_printer import QuickReceiptPrinterError, print_many_receipts
from employ.decorators import require_superuser
User = get_user_model()


def _get_employee_cash_account(user):
    """Return the current user's cash account or raise."""
    if not user or not getattr(user, 'is_authenticated', False):
        raise ValueError('user must be authenticated to fetch cash account')
    cash_account = get_user_cash_account(user, fallback_code='121')
    if not cash_account:
        raise ValueError('Cash account missing for the current user')
    return cash_account


def _process_quick_refund(student, enrollment, refund_amount, refund_reason, user):
    """Apply a refund for a quick student enrollment and create the journal entry."""
    if refund_amount <= 0:
        raise ValueError('ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ظ…ط³طھط±ط¯ ظٹط¬ط¨ ط£ظ† ظٹظƒظˆظ† ط£ظƒط¨ط± ظ…ظ† ط§ظ„طµظپط±')

    receipts_data = _adjust_quick_receipts_for_refund(student, enrollment, refund_amount)
    actual_refund = receipts_data['refunded_amount']

    if actual_refund <= 0:
        raise ValueError('ظ„ط§ ظٹظˆط¬ط¯ ظ…ط¨ط§ظ„ط؛ ظ…ط¯ظپظˆط¹ط© ظƒط§ظپظٹط© ظ„ظٹطھظ… ط§ط³طھط±ط¯ط§ط¯ظ‡ط§')

    cash_account = _get_employee_cash_account(user)
    description = f"استرداد مبلغ - {student.full_name} - {enrollment.course.name}"
    if refund_reason:
        description += f" - {refund_reason}"

    refund_entry = JournalEntry.objects.create(
        date=timezone.now().date(),
        description=description,
        entry_type='ADJUSTMENT',
        total_amount=actual_refund,
        created_by=user
    )

    Transaction.objects.create(
        journal_entry=refund_entry,
        account=student.ar_account,
        amount=actual_refund,
        is_debit=True,
        description=f"استرداد مبلغ - {enrollment.course.name}"
    )

    Transaction.objects.create(
        journal_entry=refund_entry,
        account=cash_account,
        amount=actual_refund,
        is_debit=False,
        description=f"استرداد نقدي - {student.full_name}"
    )

    refund_entry.post_entry(user)

    net_amount = enrollment.net_amount or Decimal('0.00')
    previous_balance = max(Decimal('0.00'), net_amount - receipts_data['previous_paid'])
    new_balance = max(Decimal('0.00'), net_amount - receipts_data['new_total_paid'])

    return {
        'refund_entry': refund_entry,
        'refund_amount': actual_refund,
        'previous_paid': receipts_data['previous_paid'],
        'new_total_paid': receipts_data['new_total_paid'],
        'previous_balance': previous_balance,
        'new_balance': new_balance
    }


def _adjust_quick_receipts_for_refund(student, enrollment, refund_amount):
    """Decrease QuickStudentReceipt paid amounts to match the refund target."""
    refund_amount = max(Decimal('0'), refund_amount or Decimal('0'))
    receipts_qs = QuickStudentReceipt.objects.filter(
        quick_student=student,
        quick_enrollment=enrollment,
        course=enrollment.course
    ).order_by('-date', '-id')

    total_paid = receipts_qs.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
    refundable = min(refund_amount, total_paid)

    remaining = refundable
    for receipt in receipts_qs:
        if remaining <= 0:
            break

        available = min(remaining, receipt.paid_amount)
        if available <= 0:
            continue

        receipt.paid_amount -= available
        receipt.save(update_fields=['paid_amount'])
        remaining -= available

    return {
        'previous_paid': total_paid,
        'new_total_paid': total_paid - refundable,
        'refunded_amount': refundable
    }


def _is_quick_legacy_withdrawal_account(account):
    if not account:
        return False
    code = str(getattr(account, 'code', '') or '')
    if code == '4201' or code.startswith('4201-'):
        return True
    account_text = ' '.join([
        code,
        str(getattr(account, 'name', '') or ''),
        str(getattr(account, 'name_ar', '') or ''),
    ]).casefold()
    return (
        account.account_type == 'REVENUE' and (
            'withdrawal' in account_text or
            'انسحاب' in account_text
        )
    )


def _get_legacy_withdrawal_amount(entry):
    amount = Decimal('0')
    for tx in entry.transactions.select_related('account').all():
        if tx.is_debit and _is_quick_legacy_withdrawal_account(tx.account):
            amount += tx.amount or Decimal('0')
    return amount


def _deactivate_quick_legacy_withdrawal_accounts():
    deactivated = []
    legacy_accounts = Account.objects.filter(
        Q(code='4201') |
        Q(code__startswith='4201-') |
        (
            Q(account_type='REVENUE') &
            (
                Q(name__icontains='Withdrawal') |
                Q(name_ar__icontains='انسحاب')
            )
        )
    ).order_by('-code')

    for account in legacy_accounts:
        try:
            live_balance = account.get_net_balance() or Decimal('0')
        except Exception:
            live_balance = account.balance or Decimal('0')

        if abs(live_balance) >= Decimal('0.01'):
            continue
        if not account.is_active:
            continue

        account.is_active = False
        account.save(update_fields=['is_active'])
        deactivated.append(account.code)

    return deactivated


def _find_quick_withdrawal_entries(enrollment):
    student = getattr(enrollment, 'student', None)
    course = getattr(enrollment, 'course', None)
    if not student or not course:
        return JournalEntry.objects.none()

    deferred_account = Account.get_or_create_quick_course_deferred_account(course)
    return JournalEntry.objects.filter(
        Q(description__icontains=student.full_name) &
        Q(description__icontains=course.name) &
        (
            (
                Q(transactions__account=deferred_account) &
                (
                    Q(transactions__description__icontains='عكس') |
                    Q(transactions__description__icontains='المدينة')
                )
            ) |
            (
                Q(transactions__account__code='4201') |
                Q(transactions__account__code__startswith='4201-') |
                (
                    Q(transactions__account__account_type='REVENUE') &
                    (
                        Q(transactions__account__name__icontains='Withdrawal') |
                        Q(transactions__account__name_ar__icontains='انسحاب')
                    )
                )
            )
        )
    ).distinct()


def _find_quick_generated_withdraw_fix_entries(enrollment):
    return JournalEntry.objects.filter(
        Q(description__icontains=f'[QUICK_WITHDRAW #{enrollment.id}]') |
        Q(description__icontains=f'[QUICK_WITHDRAW_FIX #{enrollment.id}]') |
        Q(description__icontains=f'[QUICK_WITHDRAW_CLEANUP #{enrollment.id}]')
    ).distinct()


def _cleanup_quick_withdrawal_entries(enrollment, user):
    cleaned = {
        'reversed_ids': [],
        'deleted_ids': [],
    }
    candidate_entries = {}
    for entry in _find_quick_withdrawal_entries(enrollment):
        candidate_entries[entry.id] = entry
    for entry in _find_quick_generated_withdraw_fix_entries(enrollment):
        candidate_entries[entry.id] = entry

    for entry in candidate_entries.values():
        entry_id = entry.id
        entry.delete()
        cleaned['deleted_ids'].append(entry_id)

    return cleaned


def _ensure_quick_enrollment_entry(enrollment, user=None):
    entry = JournalEntry.objects.filter(reference=f'QE-{enrollment.id}').first()
    if entry:
        return entry

    if user is not None:
        entry = enrollment.create_accrual_enrollment_entry(user)
        return _normalize_quick_enrollment_entry_arabic(entry, enrollment)

    return None


def _find_quick_enrollment_entry(enrollment):
    return JournalEntry.objects.filter(reference=f'QE-{enrollment.id}').first()


def _normalize_quick_enrollment_entry_arabic(entry, enrollment):
    if not entry or not enrollment:
        return entry

    entry.description = f"تسجيل سريع - {enrollment.student.full_name} في {enrollment.course.name}"
    entry.save(update_fields=['description'])

    for tx in entry.transactions.all():
        if tx.is_debit:
            tx.description = f"تسجيل سريع - {enrollment.student.full_name}"
        else:
            tx.description = f"إيرادات مؤجلة - {enrollment.course.name}"
        tx.save(update_fields=['description'])

    return entry


def _normalize_quick_receipt_entry_arabic(entry, receipt):
    if not entry or not receipt:
        return entry

    entry.description = f"إيصال سريع - {receipt.student_name} - {receipt.course_name}"
    entry.save(update_fields=['description'])

    for tx in entry.transactions.all():
        if tx.is_debit:
            tx.description = f"إيصال سريع - {receipt.student_name}"
        else:
            tx.description = f"تسديد ذمم - {receipt.course_name}"
        tx.save(update_fields=['description'])

    return entry


def _normalize_quick_withdrawal_entry_arabic(entry, enrollment, receipt=None):
    if not entry or not enrollment:
        return entry

    student_name = enrollment.student.full_name
    course_name = enrollment.course.name

    if receipt is None:
        entry.description = (
            f"[QUICK_WITHDRAW #{enrollment.id}] "
            f"عكس قيد تسجيل عند السحب - {student_name} - {course_name}"
        )
        entry.save(update_fields=['description'])

        for tx in entry.transactions.all():
            if tx.is_debit:
                tx.description = f"عكس تسجيل سريع - {course_name}"
            else:
                tx.description = f"عكس تسجيل سريع - {student_name}"
            tx.save(update_fields=['description'])
        return entry

    receipt_label = receipt.receipt_number or str(receipt.id)
    entry.description = (
        f"[QUICK_WITHDRAW #{enrollment.id}] "
        f"عكس قيد قبض عند السحب - {student_name} - {course_name} - إيصال {receipt_label}"
    )
    entry.save(update_fields=['description'])

    for tx in entry.transactions.all():
        if tx.is_debit:
            tx.description = f"عكس قبض سريع - {course_name}"
        else:
            tx.description = f"رد قبض سريع - {student_name}"
        tx.save(update_fields=['description'])

    return entry


def _make_journal_reference_available(entry, suffix='OLD'):
    if not entry or not entry.reference:
        return

    base_reference = entry.reference
    max_length = JournalEntry._meta.get_field('reference').max_length
    counter = 1
    while True:
        extra = f'-{suffix}{counter}'
        candidate = f'{base_reference[:max_length - len(extra)]}{extra}'
        if not JournalEntry.objects.exclude(id=entry.id).filter(reference=candidate).exists():
            entry.reference = candidate
            entry.save(update_fields=['reference'])
            return
        counter += 1


def _rebuild_quick_enrollment_entry(enrollment, user):
    entry = _find_quick_enrollment_entry(enrollment)
    if entry:
        if entry.is_posted:
            entry.reverse_entry(
                user,
                description=(
                    f"[QUICK_REG_CLEANUP #{enrollment.id}] "
                    f"إلغاء قيد تسجيل خاطئ - {enrollment.student.full_name} - {enrollment.course.name}"
                ),
            )
            _make_journal_reference_available(entry, suffix='REPLACED')
        else:
            entry.delete()
    entry = enrollment.create_accrual_enrollment_entry(user)
    return _normalize_quick_enrollment_entry_arabic(entry, enrollment)


def _fix_quick_receipt_entry(receipt, student_ar_account):
    if not receipt or not receipt.journal_entry_id:
        return False

    entry = receipt.journal_entry
    if not entry:
        return False

    credit_transactions = list(entry.transactions.filter(is_debit=False).select_related('account'))
    debit_transactions = list(entry.transactions.filter(is_debit=True).select_related('account'))

    if len(credit_transactions) != 1 or len(debit_transactions) != 1:
        return False

    credit_tx = credit_transactions[0]
    debit_tx = debit_transactions[0]
    expected_amount = receipt.paid_amount or Decimal('0')

    if debit_tx.amount != expected_amount or credit_tx.amount != expected_amount:
        return False

    if credit_tx.account_id == student_ar_account.id:
        return True

    credit_tx.account = student_ar_account
    credit_tx.save(update_fields=['account'])
    try:
        debit_tx.account.recalculate_tree_balances()
    except Exception:
        pass
    try:
        student_ar_account.recalculate_tree_balances()
    except Exception:
        pass
    return True


def _rebuild_quick_receipt_entry(receipt, user):
    if not receipt:
        return False

    entry = receipt.journal_entry
    if entry:
        if entry.is_posted:
            entry.reverse_entry(
                user,
                description=(
                    f"[QUICK_RECEIPT_CLEANUP #{receipt.id}] "
                    f"إلغاء قيد قبض خاطئ - {receipt.student_name} - {receipt.course_name}"
                ),
            )
            _make_journal_reference_available(entry, suffix='REPLACED')
        else:
            entry.delete()
        QuickStudentReceipt.objects.filter(id=receipt.id).update(journal_entry=None)
        receipt.journal_entry = None

    if (receipt.paid_amount or Decimal('0')) <= 0:
        return True

    entry = receipt.create_accrual_journal_entry(user)
    _normalize_quick_receipt_entry_arabic(entry, receipt)
    return True


def _cap_quick_enrollment_receipts_to_net(enrollment, user):
    target_total = max(Decimal('0'), enrollment.net_amount or Decimal('0'))
    receipts = list(
        QuickStudentReceipt.objects.filter(
            quick_student=enrollment.student,
            quick_enrollment=enrollment,
        ).select_related('journal_entry').order_by('-date', '-id')
    )

    current_total = sum((receipt.paid_amount or Decimal('0')) for receipt in receipts)
    overflow = current_total - target_total
    if overflow <= 0:
        return 0

    fixed = 0
    for receipt in receipts:
        if overflow <= 0:
            break

        current_paid = receipt.paid_amount or Decimal('0')
        if current_paid <= 0:
            continue

        reduction = min(current_paid, overflow)
        new_paid = current_paid - reduction
        QuickStudentReceipt.objects.filter(id=receipt.id).update(paid_amount=new_paid)
        receipt.paid_amount = new_paid
        _rebuild_quick_receipt_entry(receipt, user)
        overflow -= reduction
        fixed += 1

    return fixed


def _build_quick_withdrawal_entry(enrollment, user, refunded_amount, description):
    created_entries = []

    enrollment_entry = _find_quick_enrollment_entry(enrollment)
    if enrollment_entry and enrollment_entry.is_posted:
        reversed_entry = enrollment_entry.reverse_entry(
            user,
            description=(
                f"[QUICK_WITHDRAW #{enrollment.id}] "
                f"عكس قيد تسجيل عند السحب - {enrollment.student.full_name} - {enrollment.course.name}"
            ),
        )
        created_entries.append(
            _normalize_quick_withdrawal_entry_arabic(
                reversed_entry,
                enrollment,
            )
        )

    receipts = list(
        QuickStudentReceipt.objects.filter(
            quick_student=enrollment.student,
            quick_enrollment=enrollment,
        ).select_related('journal_entry').order_by('date', 'id')
    )
    for receipt in receipts:
        entry = receipt.journal_entry
        if not entry or not entry.is_posted:
            continue
        reversed_entry = entry.reverse_entry(
            user,
            description=(
                f"[QUICK_WITHDRAW #{enrollment.id}] "
                f"عكس قيد قبض عند السحب - {enrollment.student.full_name} - {enrollment.course.name} - إيصال {receipt.receipt_number or receipt.id}"
            ),
        )
        created_entries.append(
            _normalize_quick_withdrawal_entry_arabic(
                reversed_entry,
                enrollment,
                receipt=receipt,
            )
        )

    return created_entries


def _get_quick_enrollment_paid_total(enrollment, student=None):
    """Return the paid total for one specific quick enrollment only."""
    if not enrollment:
        return Decimal('0')

    filters = {
        'quick_enrollment': enrollment,
    }
    if student is not None:
        filters['quick_student'] = student

    return QuickStudentReceipt.objects.filter(
        **filters
    ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')


def _normalize_phone(phone):
    if not phone:
        return ''
    digits = ''.join(ch for ch in str(phone) if ch.isdigit())
    return digits


def _build_regular_phone_set():
    from students.models import Student
    phones = set()
    regular_students = Student.objects.filter(quick_student_profile__isnull=True)
    for student in regular_students:
        for value in (student.phone, student.father_phone, student.mother_phone, student.home_phone):
            normalized = _normalize_phone(value)
            if normalized:
                phones.add(normalized)
    return phones


def _safe_sheet_title(title, existing_titles):
    base = (title or '').strip() or 'Sheet'
    if len(base) > 31:
        base = base[:31]
    name = base
    counter = 1
    while name in existing_titles:
        suffix = f"_{counter}"
        name = f"{base[:31 - len(suffix)]}{suffix}"
        counter += 1
    return name


def _format_money(value):
    try:
        return Decimal(value)
    except Exception:
        return Decimal('0')


def _normalize_quick_student_name(name):
    return ' '.join((name or '').split()).casefold()


def _get_quick_enrollment_entry(enrollment):
    if not enrollment:
        return None
    return JournalEntry.objects.filter(reference=f'QE-{enrollment.id}').first()


def _retarget_journal_account(entry, old_account, new_account):
    if not entry or not old_account or not new_account or old_account == new_account:
        return False

    updated = False
    for tx in entry.transactions.select_related('account').all():
        if tx.account_id != old_account.id:
            continue
        tx.account = new_account
        tx.save(update_fields=['account'])
        updated = True

    if updated:
        old_account.recalculate_tree_balances()
        new_account.recalculate_tree_balances()
    return updated


def _retarget_all_account_transactions(old_account, new_account):
    if not old_account or not new_account or old_account == new_account:
        return 0

    updated = 0
    for tx in Transaction.objects.filter(account=old_account).select_related('journal_entry'):
        tx.account = new_account
        tx.save(update_fields=['account'])
        updated += 1

    if updated:
        old_account.recalculate_tree_balances()
        new_account.recalculate_tree_balances()
    return updated


def _reverse_quick_enrollment_entry(enrollment, student_account, user, note=''):
    entry = _get_quick_enrollment_entry(enrollment)
    if not entry:
        return None

    deferred_account = Account.get_or_create_quick_course_deferred_account(enrollment.course)
    description = f'إلغاء تسجيل مكرر لطالب سريع - {enrollment.student.full_name} - {enrollment.course.name}'
    if note:
        description = f'{description} - {note}'

    reversing_entry = JournalEntry.objects.create(
        date=timezone.now().date(),
        description=description,
        entry_type='ADJUSTMENT',
        total_amount=enrollment.net_amount or Decimal('0'),
        created_by=user,
    )
    Transaction.objects.create(
        journal_entry=reversing_entry,
        account=deferred_account,
        amount=enrollment.net_amount or Decimal('0'),
        is_debit=True,
        description=f'عكس إيراد مؤجل - {enrollment.course.name}',
    )
    Transaction.objects.create(
        journal_entry=reversing_entry,
        account=student_account,
        amount=enrollment.net_amount or Decimal('0'),
        is_debit=False,
        description=f'عكس ذمة تسجيل مكرر - {enrollment.student.full_name}',
    )
    reversing_entry.post_entry(user)
    return reversing_entry


def _reverse_quick_receipt_entry(receipt, student_account, user, note=''):
    if not receipt or not receipt.journal_entry_id or (receipt.paid_amount or Decimal('0')) <= 0:
        return None

    entry = receipt.journal_entry
    if not entry or not entry.is_posted:
        return None

    cash_account = None
    for tx in entry.transactions.select_related('account').all():
        if tx.is_debit:
            cash_account = tx.account
            break

    if not cash_account:
        return None

    description = f'إلغاء إيصال مكرر لطالب سريع - {receipt.student_name} - {receipt.course_name or "-"}'
    if note:
        description = f'{description} - {note}'

    reversing_entry = JournalEntry.objects.create(
        date=timezone.now().date(),
        description=description,
        entry_type='ADJUSTMENT',
        total_amount=receipt.paid_amount or Decimal('0'),
        created_by=user,
    )
    Transaction.objects.create(
        journal_entry=reversing_entry,
        account=student_account,
        amount=receipt.paid_amount or Decimal('0'),
        is_debit=True,
        description=f'عكس تسديد ذمة لإيصال مكرر - {receipt.course_name or "-"}',
    )
    Transaction.objects.create(
        journal_entry=reversing_entry,
        account=cash_account,
        amount=receipt.paid_amount or Decimal('0'),
        is_debit=False,
        description=f'عكس قبض إيصال مكرر - {receipt.student_name}',
    )
    reversing_entry.post_entry(user)
    return reversing_entry


def _pick_merge_target(students):
    return sorted(
        students,
        key=lambda student: (
            not student.is_active,
            student.created_at or timezone.now(),
            student.id,
        )
    )[0]


def _merge_quick_students_by_name(normalized_name, user):
    _configure_sqlite_busy_timeout()

    students = list(
        QuickStudent.objects.select_related('student', 'academic_year', 'created_by')
        .filter(full_name__isnull=False)
        .order_by('created_at', 'id')
    )
    matched_students = [
        student for student in students
        if _normalize_quick_student_name(student.full_name) == normalized_name
    ]
    if len(matched_students) < 2:
        raise ValueError('لم يعد يوجد سجلات مكررة لهذا الاسم.')

    target = _pick_merge_target(matched_students)
    sources = [student for student in matched_students if student.id != target.id]
    target_ar = Account.get_or_create_quick_student_ar_account(target)

    touched_accounts = {target_ar.id: target_ar}
    target_enrollments = {
        enrollment.course_id: enrollment
        for enrollment in QuickEnrollment.objects.select_related('course').filter(student=target)
    }

    merged_enrollments = 0
    merged_receipts = 0
    reversed_duplicates = 0
    deactivated_sources = []

    with transaction.atomic():
        for source in sources:
            source_ar = Account.get_or_create_quick_student_ar_account(source)
            touched_accounts[source_ar.id] = source_ar
            deleted_receipt_ids = set()

            source_receipts = list(
                QuickStudentReceipt.objects.select_related('course', 'quick_enrollment', 'journal_entry')
                .filter(quick_student=source)
                .order_by('date', 'id')
            )
            source_receipts_by_enrollment = defaultdict(list)
            source_orphan_receipts = []
            for receipt in source_receipts:
                if receipt.quick_enrollment_id:
                    source_receipts_by_enrollment[receipt.quick_enrollment_id].append(receipt)
                else:
                    source_orphan_receipts.append(receipt)

            enrollment_map = {}
            source_enrollments = list(
                QuickEnrollment.objects.select_related('course')
                .filter(student=source)
                .order_by('enrollment_date', 'id')
            )
            for enrollment in source_enrollments:
                existing = target_enrollments.get(enrollment.course_id)
                source_receipt_total = sum(
                    (receipt.paid_amount or Decimal('0')) for receipt in source_receipts_by_enrollment.get(enrollment.id, [])
                )

                if existing:
                    _reverse_quick_enrollment_entry(
                        enrollment=enrollment,
                        student_account=source_ar,
                        user=user,
                        note='دمج حسابات الطلاب السريعين',
                    )
                    duplicate_receipts = list(source_receipts_by_enrollment.get(enrollment.id, []))
                    duplicate_orphan_receipts = [
                        receipt for receipt in source_orphan_receipts
                        if receipt.course_id == enrollment.course_id
                    ]
                    for duplicate_receipt in duplicate_receipts + duplicate_orphan_receipts:
                        _reverse_quick_receipt_entry(
                            receipt=duplicate_receipt,
                            student_account=source_ar,
                            user=user,
                            note='دمج حسابات الطلاب السريعين',
                        )
                        if duplicate_receipt in source_orphan_receipts:
                            source_orphan_receipts.remove(duplicate_receipt)
                        deleted_receipt_ids.add(duplicate_receipt.id)
                        duplicate_receipt.delete()

                    reversed_duplicates += 1
                    enrollment_map[enrollment.id] = existing
                    continue

                QuickEnrollment.objects.filter(pk=enrollment.pk).update(student=target)
                enrollment.student = target
                entry = _get_quick_enrollment_entry(enrollment)
                _retarget_journal_account(entry, source_ar, target_ar)
                target_enrollments[enrollment.course_id] = enrollment
                enrollment_map[enrollment.id] = enrollment
                merged_enrollments += 1

            for receipt in source_receipts:
                if receipt.id in deleted_receipt_ids:
                    continue
                target_enrollment = None
                if receipt.quick_enrollment_id:
                    target_enrollment = enrollment_map.get(receipt.quick_enrollment_id)
                elif receipt.course_id:
                    target_enrollment = target_enrollments.get(receipt.course_id)

                QuickStudentReceipt.objects.filter(pk=receipt.pk).update(
                    quick_student=target,
                    student_name=target.full_name,
                    quick_enrollment=target_enrollment,
                )
                receipt.quick_student = target
                receipt.student_name = target.full_name
                receipt.quick_enrollment = target_enrollment
                _retarget_journal_account(receipt.journal_entry, source_ar, target_ar)
                merged_receipts += 1

            _retarget_all_account_transactions(source_ar, target_ar)
            QuickReceiptPrintJob.objects.filter(quick_student=source).update(quick_student=target)

            source_notes = ((source.notes or '').strip() + f'\n[MERGED_INTO #{target.id}]').strip()
            QuickStudent.objects.filter(pk=source.pk).update(
                is_active=False,
                notes=source_notes,
            )
            source.is_active = False
            source.notes = source_notes

            if getattr(source, 'student', None):
                source_student_notes = ((source.student.notes or '').strip() + f'\nQuick merged into #{target.id}').strip()
                type(source.student).objects.filter(pk=source.student.pk).update(
                    is_active=False,
                    notes=source_student_notes,
                )
                source.student.is_active = False
                source.student.notes = source_student_notes

            source_id = source.pk
            source.delete()
            deactivated_sources.append(source_id)

        if getattr(target, 'student', None):
            updated_fields = []
            if not target.student.phone and target.phone:
                target.student.phone = target.phone
                updated_fields.append('phone')
            if not target.student.full_name and target.full_name:
                target.student.full_name = target.full_name
                updated_fields.append('full_name')
            if updated_fields:
                type(target.student).objects.filter(pk=target.student.pk).update(
                    **{field: getattr(target.student, field) for field in updated_fields}
                )

    for account in touched_accounts.values():
        try:
            account.recalculate_tree_balances()
        except Exception:
            continue

    return {
        'target': target,
        'sources': deactivated_sources,
        'merged_enrollments': merged_enrollments,
        'merged_receipts': merged_receipts,
        'reversed_duplicates': reversed_duplicates,
    }


def _merge_quick_students_by_name_with_retry(normalized_name, user, attempts=3):
    last_error = None
    for attempt in range(attempts):
        try:
            return _merge_quick_students_by_name(normalized_name, user)
        except OperationalError as exc:
            if 'database is locked' not in str(exc).lower():
                raise
            last_error = exc
            connection.close()
            time.sleep(0.75 * (attempt + 1))
    if last_error:
        raise last_error


def _configure_sqlite_busy_timeout(timeout_ms=30000):
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            cursor.execute(f'PRAGMA busy_timeout = {int(timeout_ms)}')


def _get_duplicate_groups(search_query='', scope='active'):
    include_inactive = scope == 'all'

    enrollment_queryset = (
        QuickEnrollment.objects.select_related('course')
        .prefetch_related(
            Prefetch(
                'quickstudentreceipt_set',
                queryset=QuickStudentReceipt.objects.select_related('created_by', 'journal_entry').order_by('date', 'id')
            )
        )
        .annotate(
            paid_total=Coalesce(
                Sum('quickstudentreceipt__paid_amount'),
                Value(Decimal('0')),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )
        .order_by('course__name', 'id')
    )

    students_queryset = (
        QuickStudent.objects.select_related('student', 'academic_year', 'created_by')
        .prefetch_related(
            Prefetch('enrollments', queryset=enrollment_queryset),
            Prefetch(
                'quickstudentreceipt_set',
                queryset=QuickStudentReceipt.objects.select_related(
                    'created_by', 'journal_entry', 'course', 'quick_enrollment'
                ).order_by('date', 'id')
            )
        )
        .order_by('full_name', 'id')
    )
    if not include_inactive:
        students_queryset = students_queryset.filter(is_active=True)

    grouped_students = defaultdict(list)
    for quick_student in students_queryset:
        normalized_name = _normalize_quick_student_name(quick_student.full_name)
        if normalized_name:
            grouped_students[normalized_name].append(quick_student)

    duplicate_groups = []
    normalized_search = _normalize_quick_student_name(search_query)

    for normalized_name, students in grouped_students.items():
        if len(students) < 2:
            continue
        if normalized_search and normalized_search not in normalized_name:
            continue

        members = []
        group_balance = Decimal('0')
        group_remaining = Decimal('0')
        group_enrollments = 0

        for quick_student in students:
            enrollments_data = []
            student_remaining = Decimal('0')
            account_created_by = '-'
            if quick_student.created_by:
                account_created_by = quick_student.created_by.get_full_name() or quick_student.created_by.username or '-'
            all_student_receipts = list(quick_student.quickstudentreceipt_set.all())
            used_receipt_ids = set()
            enrollments = list(quick_student.enrollments.all())
            enrollment_entry_refs = {f'QE-{enrollment.id}': enrollment for enrollment in enrollments}
            journal_entries = {
                entry.reference: entry
                for entry in JournalEntry.objects.filter(reference__in=enrollment_entry_refs.keys()).select_related('created_by')
            }

            for enrollment in enrollments:
                net_amount = enrollment.net_amount or Decimal('0')
                paid_amount = enrollment.paid_total or Decimal('0')
                remaining_amount = max(Decimal('0'), net_amount - paid_amount)
                student_remaining += remaining_amount
                group_enrollments += 1
                enrollment_created_by = '-'
                receipt_rows = []

                enrollment_entry = journal_entries.get(f'QE-{enrollment.id}')
                if enrollment_entry and enrollment_entry.created_by:
                    enrollment_created_by = (
                        enrollment_entry.created_by.get_full_name()
                        or enrollment_entry.created_by.username
                        or '-'
                    )

                receipts = [
                    receipt for receipt in all_student_receipts
                    if receipt.quick_enrollment_id == enrollment.id
                    or (
                        receipt.quick_enrollment_id is None
                        and receipt.course_id == enrollment.course_id
                    )
                ]
                if enrollment_created_by == '-' and receipts:
                    first_receipt_creator = receipts[0].created_by
                    if first_receipt_creator:
                        enrollment_created_by = (
                            first_receipt_creator.get_full_name()
                            or first_receipt_creator.username
                            or '-'
                        )

                for receipt in receipts:
                    receipt_created_by = '-'
                    if receipt.created_by:
                        receipt_created_by = receipt.created_by.get_full_name() or receipt.created_by.username or '-'
                    used_receipt_ids.add(receipt.id)
                    receipt_rows.append({
                        'receipt_number': receipt.receipt_number or '-',
                        'date': receipt.date,
                        'paid_amount': receipt.paid_amount or Decimal('0'),
                        'amount': receipt.amount or Decimal('0'),
                        'is_printed': receipt.is_printed,
                        'created_by': receipt_created_by,
                    })

                enrollments_data.append({
                    'course_name': enrollment.course.name if enrollment.course else '-',
                    'enrollment_date': enrollment.enrollment_date,
                    'net_amount': net_amount,
                    'paid_amount': paid_amount,
                    'remaining_amount': remaining_amount,
                    'is_completed': enrollment.is_completed,
                    'registered_by': enrollment_created_by,
                    'receipts': receipt_rows,
                    'has_receipts': bool(receipt_rows),
                    'receipts_count': len(receipt_rows),
                })

            orphan_receipts = []
            for receipt in all_student_receipts:
                if receipt.id in used_receipt_ids:
                    continue
                receipt_created_by = '-'
                if receipt.created_by:
                    receipt_created_by = receipt.created_by.get_full_name() or receipt.created_by.username or '-'
                orphan_receipts.append({
                    'receipt_number': receipt.receipt_number or '-',
                    'date': receipt.date,
                    'course_name': receipt.course_name or (receipt.course.name if receipt.course else '-'),
                    'paid_amount': receipt.paid_amount or Decimal('0'),
                    'amount': receipt.amount or Decimal('0'),
                    'is_printed': receipt.is_printed,
                    'created_by': receipt_created_by,
                })

            account_balance = quick_student.balance
            group_balance += account_balance
            group_remaining += student_remaining

            members.append({
                'student': quick_student,
                'account_created_by': account_created_by,
                'account_balance': account_balance,
                'remaining_total': student_remaining,
                'enrollments': enrollments_data,
                'enrollments_count': len(enrollments_data),
                'orphan_receipts': orphan_receipts,
                'has_orphan_receipts': bool(orphan_receipts),
            })

        members.sort(key=lambda item: item['student'].id)
        duplicate_groups.append({
            'display_name': students[0].full_name,
            'normalized_name': normalized_name,
            'students': members,
            'duplicate_count': len(members),
            'group_balance': group_balance,
            'group_remaining': group_remaining,
            'group_enrollments': group_enrollments,
        })

    duplicate_groups.sort(key=lambda item: (-item['duplicate_count'], item['display_name']))
    return duplicate_groups


def _build_quick_accounting_fix_rows():
    rows = []
    enrollments = (
        QuickEnrollment.objects.select_related('student', 'course')
        .order_by('-updated_at', '-id')
    )

    for enrollment in enrollments:
        issues = []
        suggested_actions = []
        linked_entry = _find_quick_enrollment_entry(enrollment)
        registration_ok = False
        receipts_ok = True
        withdrawal_ok = not enrollment.is_completed
        fixable_receipt_ids = []

        if not linked_entry:
            issues.append('قيد التسجيل مفقود')
            suggested_actions.append('إنشاء قيد التسجيل')
        else:
            student_ar = enrollment.student.ar_account
            deferred_account = Account.get_or_create_quick_course_deferred_account(enrollment.course)
            debit_ok = linked_entry.transactions.filter(
                account=student_ar,
                is_debit=True,
                amount=enrollment.net_amount or Decimal('0'),
            ).exists()
            credit_ok = linked_entry.transactions.filter(
                account=deferred_account,
                is_debit=False,
                amount=enrollment.net_amount or Decimal('0'),
            ).exists()
            registration_ok = debit_ok and credit_ok
            if not registration_ok:
                issues.append('قيد التسجيل لا يطابق الخطة المطلوبة')
                suggested_actions.append('إعادة بناء قيد التسجيل')

        receipts = list(
            QuickStudentReceipt.objects.filter(
                quick_student=enrollment.student,
                quick_enrollment=enrollment,
            ).select_related('journal_entry')
        )
        retained_amount = sum((receipt.paid_amount or Decimal('0')) for receipt in receipts)
        receipt_count = len(receipts)
        audited_receipts = 0
        receipt_issue_count = 0
        for receipt in receipts:
            audited_receipts += 1
            if not receipt.journal_entry_id:
                receipts_ok = False
                receipt_issue_count += 1
                issues.append(f'إيصال #{receipt.id} بدون قيد قبض')
                fixable_receipt_ids.append(receipt.id)
                continue

            receipt_entry = receipt.journal_entry
            credit_ok = receipt_entry.transactions.filter(
                account=enrollment.student.ar_account,
                is_debit=False,
                amount=receipt.paid_amount or Decimal('0'),
            ).exists()
            debit_ok = receipt_entry.transactions.filter(
                is_debit=True,
                amount=receipt.paid_amount or Decimal('0'),
            ).exclude(account=enrollment.student.ar_account).exists()
            if not (credit_ok and debit_ok):
                receipts_ok = False
                receipt_issue_count += 1
                issues.append(f'إيصال #{receipt.id} لا يطابق قيد القبض المطلوب')
                if receipt.journal_entry_id:
                    fixable_receipt_ids.append(receipt.id)

        legacy_entries = list(_find_quick_withdrawal_entries(enrollment))
        refunded_amount = sum((_get_legacy_withdrawal_amount(entry) for entry in legacy_entries), Decimal('0'))

        correction_amount = retained_amount + refunded_amount
        existing_fix_entries = list(_find_quick_generated_withdraw_fix_entries(enrollment))
        already_fixed = bool(existing_fix_entries)

        if enrollment.is_completed and correction_amount > 0:
            if refunded_amount > 0 and retained_amount > 0:
                issues.append('سحب قديم جزئي لم يُستكمل بالكامل وفق الطريقة الجديدة')
            elif refunded_amount > 0:
                issues.append('سحب قديم أبقى أثراً على الدورة أو على حساب الانسحاب القديم')
            elif retained_amount > 0:
                issues.append('سحب قديم لم يصفّر الدفعات المسجلة بالكامل')
            if already_fixed:
                suggested_actions.append('إلغاء قيود السحب القديمة وإعادة إنشائها')
            else:
                suggested_actions.append('إنشاء قيد تصحيح سحب')
            withdrawal_ok = False
        elif enrollment.is_completed:
            if not legacy_entries and not existing_fix_entries and (enrollment.net_amount or Decimal('0')) > 0:
                issues.append('تسجيل مسحوب بدون قيد سحب واضح')
                suggested_actions.append('إنشاء قيد سحب مفقود')
                withdrawal_ok = False
            else:
                withdrawal_ok = True

        if not enrollment.is_completed and retained_amount > (enrollment.net_amount or Decimal('0')):
            issues.append('إجمالي المقبوض أكبر من صافي التسجيل')
            suggested_actions.append('تصحيح مبالغ القبض الزائدة')

        if not suggested_actions and issues:
            suggested_actions.append('مراجعة يدوية')

        rows.append({
            'enrollment': enrollment,
            'missing_entry': not bool(linked_entry),
            'legacy_entries': legacy_entries,
            'legacy_entries_count': len(legacy_entries),
            'existing_fix_entries_count': len(existing_fix_entries),
            'has_legacy_withdrawal': refunded_amount > 0,
            'retained_amount': retained_amount,
            'refunded_amount': refunded_amount,
            'correction_amount': correction_amount,
            'already_fixed': already_fixed,
            'issues': issues,
            'suggested_actions': suggested_actions,
            'is_compliant': not issues,
            'registration_ok': registration_ok,
            'receipts_ok': receipts_ok,
            'withdrawal_ok': withdrawal_ok,
            'receipt_count': receipt_count,
            'audited_receipts': audited_receipts,
            'receipt_issue_count': receipt_issue_count,
            'fixable_receipt_ids': fixable_receipt_ids,
        })

    return rows


def _apply_quick_accounting_fixes(user):
    rows = _build_quick_accounting_fix_rows()
    fixed_links = 0
    fixed_withdrawals = 0
    fixed_receipts = 0
    created_entries = []
    errors = []
    cleaned_withdraw_entries = 0
    deactivated_legacy_accounts = []

    for row in rows:
        enrollment = row['enrollment']
        success = False
        last_exc = None
        for attempt in range(3):
            try:
                close_old_connections()
                _configure_sqlite_busy_timeout()
                with transaction.atomic():
                    if row['missing_entry'] or not row['registration_ok']:
                        if row['missing_entry']:
                            entry = _ensure_quick_enrollment_entry(enrollment, user=user)
                        else:
                            entry = _rebuild_quick_enrollment_entry(enrollment, user=user)
                        if entry:
                            fixed_links += 1

                    if row['fixable_receipt_ids']:
                        for receipt in QuickStudentReceipt.objects.filter(id__in=row['fixable_receipt_ids']).select_related('journal_entry'):
                            if not receipt.journal_entry_id:
                                if _rebuild_quick_receipt_entry(receipt, user):
                                    fixed_receipts += 1
                                continue

                            student_ar = enrollment.student.ar_account
                            if _fix_quick_receipt_entry(receipt, student_ar):
                                fixed_receipts += 1
                            elif _rebuild_quick_receipt_entry(receipt, user):
                                fixed_receipts += 1

                    if enrollment.is_completed and row['correction_amount'] > 0:
                        if row['retained_amount'] > 0:
                            _adjust_quick_receipts_for_refund(
                                enrollment.student,
                                enrollment,
                                row['retained_amount'],
                            )

                        cleanup_result = _cleanup_quick_withdrawal_entries(enrollment, user)
                        cleaned_withdraw_entries += (
                            len(cleanup_result['reversed_ids']) +
                            len(cleanup_result['deleted_ids'])
                        )

                        description = (
                            f"[QUICK_WITHDRAW #{enrollment.id}] "
                            f"تصحيح سحب طالب سريع - {enrollment.student.full_name} - {enrollment.course.name}"
                        )

                        entries = _build_quick_withdrawal_entry(
                            enrollment=enrollment,
                            user=user,
                            refunded_amount=row['retained_amount'],
                            description=description,
                        )
                        created_entries.extend(entry.id for entry in entries)
                        fixed_withdrawals += len(entries)
                    elif enrollment.is_completed and 'تسجيل مسحوب بدون قيد سحب واضح' in row['issues']:
                        description = (
                            f"[QUICK_WITHDRAW #{enrollment.id}] "
                            f"إنشاء قيد سحب مفقود - {enrollment.student.full_name} - {enrollment.course.name}"
                        )
                        entries = _build_quick_withdrawal_entry(
                            enrollment=enrollment,
                            user=user,
                            refunded_amount=row['retained_amount'],
                            description=description,
                        )
                        created_entries.extend(entry.id for entry in entries)
                        fixed_withdrawals += len(entries)

                    if (
                        not enrollment.is_completed and
                        'إجمالي المقبوض أكبر من صافي التسجيل' in row['issues']
                    ):
                        fixed_receipts += _cap_quick_enrollment_receipts_to_net(enrollment, user)
                success = True
                connection.close()
                break
            except OperationalError as exc:
                last_exc = exc
                if 'database is locked' not in str(exc).lower():
                    break
                close_old_connections()
                connection.close()
                time.sleep(1.5 * (attempt + 1))
            except Exception as exc:
                last_exc = exc
                break

        if not success and last_exc:
            errors.append(f'{enrollment.student.full_name} / {enrollment.course.name}: {last_exc}')

    if cleaned_withdraw_entries:
        Account.rebuild_all_balances()

    deactivated_legacy_accounts = _deactivate_quick_legacy_withdrawal_accounts()

    return {
        'fixed_links': fixed_links,
        'fixed_withdrawals': fixed_withdrawals,
        'fixed_receipts': fixed_receipts,
        'cleaned_withdraw_entries': cleaned_withdraw_entries,
        'deactivated_legacy_accounts': deactivated_legacy_accounts,
        'created_entries': created_entries,
        'errors': errors,
    }


def _build_quick_withdrawal_fix_rows():
    rows = []
    for row in _build_quick_accounting_fix_rows():
        enrollment = row['enrollment']
        needs_fix = (
            row['legacy_entries_count'] > 0 or
            (enrollment.is_completed and row['correction_amount'] > 0) or
            (enrollment.is_completed and 'تسجيل مسحوب بدون قيد سحب واضح' in row['issues']) or
            row['existing_fix_entries_count'] > 0
        )
        if not needs_fix:
            continue

        rows.append(row)

    return rows


def _apply_quick_withdrawal_fixes(user):
    rows = _build_quick_withdrawal_fix_rows()
    fixed_withdrawals = 0
    cleaned_withdraw_entries = 0
    created_entries = []
    errors = []

    for row in rows:
        enrollment = row['enrollment']
        success = False
        last_exc = None
        for attempt in range(3):
            try:
                close_old_connections()
                _configure_sqlite_busy_timeout()
                with transaction.atomic():
                    if enrollment.is_completed and row['retained_amount'] > 0:
                        _adjust_quick_receipts_for_refund(
                            enrollment.student,
                            enrollment,
                            row['retained_amount'],
                        )

                    cleanup_result = _cleanup_quick_withdrawal_entries(enrollment, user)
                    cleaned_withdraw_entries += (
                        len(cleanup_result['reversed_ids']) +
                        len(cleanup_result['deleted_ids'])
                    )

                    if enrollment.is_completed:
                        entries = _build_quick_withdrawal_entry(
                            enrollment=enrollment,
                            user=user,
                            refunded_amount=row['retained_amount'],
                            description=(
                                f"[QUICK_WITHDRAW #{enrollment.id}] "
                                f"تصحيح سحب طالب سريع - {enrollment.student.full_name} - {enrollment.course.name}"
                            ),
                        )
                        created_entries.extend(entry.id for entry in entries)
                        fixed_withdrawals += len(entries)
                success = True
                connection.close()
                break
            except OperationalError as exc:
                last_exc = exc
                if 'database is locked' not in str(exc).lower():
                    break
                close_old_connections()
                connection.close()
                time.sleep(1.5 * (attempt + 1))
            except Exception as exc:
                last_exc = exc
                break

        if not success and last_exc:
            errors.append(f'{enrollment.student.full_name} / {enrollment.course.name}: {last_exc}')

    if cleaned_withdraw_entries:
        Account.rebuild_all_balances()

    deactivated_legacy_accounts = _deactivate_quick_legacy_withdrawal_accounts()

    return {
        'rows_count': len(rows),
        'fixed_withdrawals': fixed_withdrawals,
        'cleaned_withdraw_entries': cleaned_withdraw_entries,
        'deactivated_legacy_accounts': deactivated_legacy_accounts,
        'created_entries': created_entries,
        'errors': errors,
    }


def _append_quick_course_statement_rows(rows, course_name, student_name, student_phone, source_label, entry):
    transactions = list(entry.transactions.all())
    transactions.sort(key=lambda transaction: (transaction.is_debit, transaction.id))

    created_by = "-"
    if entry.created_by:
        created_by = entry.created_by.get_full_name() or entry.created_by.username or "-"

    posted_by = "-"
    if entry.posted_by:
        posted_by = entry.posted_by.get_full_name() or entry.posted_by.username or "-"

    for transaction in transactions:
        account_name = transaction.account.name_ar or transaction.account.name
        rows.append({
            'course_name': course_name,
            'student_name': student_name or "-",
            'student_phone': student_phone or "-",
            'entry_reference': entry.reference,
            'entry_date': entry.date.strftime('%Y-%m-%d') if entry.date else "-",
            'entry_type': entry.get_entry_type_display(),
            'entry_source': source_label,
            'entry_description': entry.description,
            'account_code': transaction.account.code,
            'account_name': account_name,
            'transaction_description': transaction.description or entry.description,
            'debit': transaction.amount if transaction.is_debit else Decimal('0'),
            'credit': transaction.amount if not transaction.is_debit else Decimal('0'),
            'entry_total': entry.total_amount or Decimal('0'),
            'posted_status': 'مرحل' if entry.is_posted else 'غير مرحل',
            'created_by': created_by,
            'posted_by': posted_by,
        })


def _build_quick_course_statement_rows(courses):
    courses = list(courses)
    rows_by_course = defaultdict(list)
    added_entry_ids = defaultdict(set)

    if not courses:
        return rows_by_course

    enrollments = list(
        QuickEnrollment.objects.filter(course__in=courses)
        .select_related('student', 'course')
        .order_by('course__name', 'student__full_name', 'id')
    )
    enrollment_ref_map = {f"QE-{enrollment.id}": enrollment for enrollment in enrollments}

    receipts = list(
        QuickStudentReceipt.objects.filter(course__in=courses, journal_entry__isnull=False)
        .select_related('quick_student', 'course')
        .order_by('course__name', 'date', 'id')
    )
    receipt_entry_ids = {receipt.journal_entry_id for receipt in receipts if receipt.journal_entry_id}

    journal_entries = JournalEntry.objects.filter(
        Q(reference__in=enrollment_ref_map.keys()) | Q(id__in=receipt_entry_ids)
    ).select_related(
        'created_by', 'posted_by'
    ).prefetch_related(
        Prefetch('transactions', queryset=Transaction.objects.select_related('account').order_by('id'))
    )

    entries_by_reference = {entry.reference: entry for entry in journal_entries}
    entries_by_id = {entry.id: entry for entry in journal_entries}

    for enrollment in enrollments:
        entry = entries_by_reference.get(f"QE-{enrollment.id}")
        if not entry:
            continue
        added_entry_ids[enrollment.course_id].add(entry.id)
        _append_quick_course_statement_rows(
            rows_by_course[enrollment.course_id],
            course_name=enrollment.course.name,
            student_name=enrollment.student.full_name,
            student_phone=enrollment.student.phone,
            source_label='قيد تسجيل',
            entry=entry,
        )

    for receipt in receipts:
        entry = entries_by_id.get(receipt.journal_entry_id)
        if not entry:
            continue
        added_entry_ids[receipt.course_id].add(entry.id)
        _append_quick_course_statement_rows(
            rows_by_course[receipt.course_id],
            course_name=receipt.course.name if receipt.course else (receipt.course_name or "-"),
            student_name=receipt.student_name or getattr(receipt.quick_student, 'full_name', "-"),
            student_phone=getattr(receipt.quick_student, 'phone', "-"),
            source_label='قيد قبض',
            entry=entry,
        )

    adjustment_entries = list(
        JournalEntry.objects.filter(entry_type='ADJUSTMENT')
        .select_related('created_by', 'posted_by')
        .prefetch_related(
            Prefetch('transactions', queryset=Transaction.objects.select_related('account').order_by('id'))
        )
        .order_by('date', 'id')
    )

    for enrollment in enrollments:
        student_name = enrollment.student.full_name or ""
        course_name = enrollment.course.name or ""
        description_prefixes = [
            ("استرداد مبلغ - ", "قيد استرداد"),
            ("سحب طالب سريع ", "قيد سحب"),
            ("ط§ط³طھط±ط¯ط§ط¯ ظ…ط¨ظ„ط؛ - ", "قيد استرداد"),
            ("ط³ط­ط¨ ط·ط§ظ„ط¨ ط³ط±ظٹط¹ ", "قيد سحب"),
        ]

        for entry in adjustment_entries:
            if entry.id in added_entry_ids[enrollment.course_id]:
                continue

            description = entry.description or ""
            matched_source = None
            for prefix, source_label in description_prefixes:
                if prefix in {"استرداد مبلغ - ", "ط§ط³طھط±ط¯ط§ط¯ ظ…ط¨ظ„ط؛ - "} and description.startswith(f"{prefix}{student_name} - {course_name}"):
                    matched_source = source_label
                    break
                if prefix in {"سحب طالب سريع ", "ط³ط­ط¨ ط·ط§ظ„ط¨ ط³ط±ظٹط¹ "} and description.startswith(f"{prefix}{student_name} من {course_name}"):
                    matched_source = source_label
                    break
                if prefix == "ط³ط­ط¨ ط·ط§ظ„ط¨ ط³ط±ظٹط¹ " and description.startswith(f"{prefix}{student_name} ظ…ظ† {course_name}"):
                    matched_source = source_label
                    break

            if not matched_source:
                continue

            added_entry_ids[enrollment.course_id].add(entry.id)
            _append_quick_course_statement_rows(
                rows_by_course[enrollment.course_id],
                course_name=course_name,
                student_name=student_name,
                student_phone=enrollment.student.phone,
                source_label=matched_source,
                entry=entry,
            )

    return rows_by_course


def export_quick_course_statement_excel(request):
    """Export quick course journal entries with student names per course."""
    course_type, _, report_label = _get_outstanding_course_type(request)
    academic_year_id = request.GET.get('academic_year')

    courses_qs = QuickCourse.objects.filter(is_active=True).select_related('academic_year').order_by('name')
    if course_type != 'ALL':
        courses_qs = courses_qs.filter(course_type=course_type)
    if academic_year_id:
        courses_qs = courses_qs.filter(academic_year_id=academic_year_id)

    courses = list(courses_qs)
    rows_by_course = _build_quick_course_statement_rows(courses)

    workbook = Workbook()
    workbook.remove(workbook.active)

    title_font = Font(bold=True, size=16, color="FFFFFF")
    header_font = Font(bold=True, color="FFFFFF")
    normal_font = Font(size=11)
    center = Alignment(horizontal="center", vertical="center")
    right = Alignment(horizontal="right", vertical="center")
    header_fill = PatternFill("solid", fgColor="1F4E78")
    subheader_fill = PatternFill("solid", fgColor="D9E1F2")
    thin = Side(style="thin", color="B7B7B7")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    columns = [
        ("#", 6),
        ("الدورة", 24),
        ("الطالب", 24),
        ("الهاتف", 16),
        ("مصدر القيد", 14),
        ("رقم القيد", 16),
        ("تاريخ القيد", 14),
        ("نوع القيد", 18),
        ("بيان القيد", 34),
        ("رمز الحساب", 14),
        ("اسم الحساب", 24),
        ("بيان الحركة", 34),
        ("مدين", 14),
        ("دائن", 14),
        ("إجمالي القيد", 14),
        ("الحالة", 12),
        ("أنشئ بواسطة", 18),
        ("رُحّل بواسطة", 18),
    ]

    def write_sheet(ws, title, rows, include_course_name):
        ws.sheet_view.rightToLeft = True
        visible_columns = columns if include_course_name else [col for col in columns if col[0] != "الدورة"]
        total_cols = len(visible_columns)

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
        title_cell = ws.cell(row=1, column=1, value="كشف حساب الدورات السريعة")
        title_cell.font = title_font
        title_cell.alignment = center
        title_cell.fill = header_fill

        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_cols)
        meta_cell = ws.cell(row=2, column=1, value=f"الدورة/التصنيف: {title} | عدد الحركات: {len(rows)}")
        meta_cell.alignment = right
        meta_cell.fill = subheader_fill

        for col_idx, (label, width) in enumerate(visible_columns, start=1):
            cell = ws.cell(row=4, column=col_idx, value=label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = border
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        for row_idx, row in enumerate(rows, start=5):
            values = [
                row_idx - 4,
                row['course_name'],
                row['student_name'],
                row['student_phone'],
                row['entry_source'],
                row['entry_reference'],
                row['entry_date'],
                row['entry_type'],
                row['entry_description'],
                row['account_code'],
                row['account_name'],
                row['transaction_description'],
                row['debit'],
                row['credit'],
                row['entry_total'],
                row['posted_status'],
                row['created_by'],
                row['posted_by'],
            ]
            if not include_course_name:
                values.pop(1)

            for col_idx, value in enumerate(values, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.font = normal_font
                cell.border = border
                cell.alignment = center if col_idx in (1, 6, 7) else right
                header_label = visible_columns[col_idx - 1][0]
                if header_label in {"مدين", "دائن", "إجمالي القيد"}:
                    cell.number_format = '#,##0.00'

        ws.freeze_panes = 'A5'

    combined_rows = []
    for course in courses:
        combined_rows.extend(rows_by_course.get(course.id, []))

    all_sheet = workbook.create_sheet("كل الدورات")
    write_sheet(all_sheet, report_label, combined_rows, include_course_name=True)

    existing_titles = {all_sheet.title}
    for course in courses:
        sheet_name = _safe_sheet_title(course.name, existing_titles)
        existing_titles.add(sheet_name)
        course_sheet = workbook.create_sheet(sheet_name)
        write_sheet(course_sheet, course.name, rows_by_course.get(course.id, []), include_course_name=False)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    timestamp = timezone.now().strftime('%Y%m%d_%H%M')
    response['Content-Disposition'] = f'attachment; filename="كشف_حساب_الدورات_السريعة_{report_label}_{timestamp}.xlsx"'
    workbook.save(response)
    return response


def export_quick_outstanding_excel(request):
    """Export quick courses outstanding report with per-course sheets."""
    course_type, _, report_label = _get_outstanding_course_type(request)
    academic_year_id = request.GET.get('academic_year')
    courses_qs = QuickCourse.objects.filter(is_active=True)
    if course_type != 'ALL':
        courses_qs = courses_qs.filter(course_type=course_type)
    if academic_year_id:
        courses_qs = courses_qs.filter(academic_year_id=academic_year_id)
    courses = list(courses_qs)

    enrollments = list((
        QuickEnrollment.objects
        .filter(course__in=courses)
        .select_related('student', 'course', 'student__created_by', 'student__student')
        .order_by('course__name', 'student__full_name')
    ))

    paid_map = {}
    receipt_totals = QuickStudentReceipt.objects.filter(
        course__in=courses
    ).values('quick_student_id', 'course_id').annotate(total=Sum('paid_amount'))
    for row in receipt_totals:
        paid_map[(row['quick_student_id'], row['course_id'])] = row['total'] or Decimal('0')

    regular_phone_set = _build_regular_phone_set()

    def student_type_label(quick_student):
        phone = _normalize_phone(quick_student.phone)
        return "ط·ط§ظ„ط¨ ظ…ط¹ظ‡ط¯" if phone and phone in regular_phone_set else "ط®ط§ط±ط¬ظٹ"

    def registered_by_label(quick_student):
        user = quick_student.created_by
        if not user:
            return "-"
        return user.get_full_name() or user.username or "-"

    workbook = Workbook()
    workbook.remove(workbook.active)

    title_font = Font(bold=True, size=16, color="FFFFFF")
    header_font = Font(bold=True, color="FFFFFF")
    normal_font = Font(size=11)
    center = Alignment(horizontal="center", vertical="center")
    right = Alignment(horizontal="right", vertical="center")
    header_fill = PatternFill("solid", fgColor="1F4E78")
    subheader_fill = PatternFill("solid", fgColor="D9E1F2")
    thin = Side(style="thin", color="B7B7B7")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def write_sheet(ws, course_label, rows, include_course_col):
        ws.sheet_view.rightToLeft = True
        columns = [
            ("#", 6),
            ("ط§ط³ظ… ط§ظ„ط·ط§ظ„ط¨", 28),
            ("ط±ظ‚ظ… ط§ظ„ظ‡ط§طھظپ", 16),
            ("ظ†ظˆط¹ ط§ظ„ط·ط§ظ„ط¨", 14),
            ("ط§ظ„ظ…ط³ط¬ظ„", 18),
            ("طھط§ط±ظٹط® ط§ظ„طھط³ط¬ظٹظ„", 14),
        ]
        if include_course_col:
            columns.insert(1, ("ط§ظ„ط¯ظˆط±ط©", 26))
        columns.extend([
            ("ط¥ط¬ظ…ط§ظ„ظٹ ط§ظ„ط¯ظˆط±ط©", 16),
            ("ط§ظ„ظ…ط¯ظپظˆط¹", 14),
            ("ط§ظ„ظ…طھط¨ظ‚ظٹ", 14),
        ])

        total_cols = len(columns)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
        ws.cell(row=1, column=1, value="طھظ‚ط±ظٹط± ط§ظ„ظ…طھط¨ظ‚ظٹ - ط§ظ„ط¯ظˆط±ط§طھ ط§ظ„ط³ط±ظٹط¹ط©").font = title_font
        ws.cell(row=1, column=1).alignment = center
        ws.cell(row=1, column=1).fill = header_fill

        internal_count = sum(1 for r in rows if r['student_type'] == "ط·ط§ظ„ط¨ ظ…ط¹ظ‡ط¯")
        external_count = sum(1 for r in rows if r['student_type'] == "ط®ط§ط±ط¬ظٹ")
        total_paid = sum(r['paid'] for r in rows)
        total_remaining = sum(r['remaining'] for r in rows)

        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_cols)
        ws.cell(
            row=2,
            column=1,
            value=f"ط§ظ„ط¯ظˆط±ط©: {course_label} | ط§ط­طµط§ط¦ظٹط©: ط·ط§ظ„ط¨ ظ…ط¹ظ‡ط¯ {internal_count} | ط®ط§ط±ط¬ظٹ {external_count}"
        ).alignment = right
        ws.cell(row=2, column=1).fill = subheader_fill

        ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=total_cols)
        ws.cell(
            row=3,
            column=1,
            value=f"ط¥ط¬ظ…ط§ظ„ظٹ ط§ظ„ط·ظ„ط§ط¨: {len(rows)} | ط¥ط¬ظ…ط§ظ„ظٹ ط§ظ„ظ…ط¯ظپظˆط¹: {total_paid} | ط¥ط¬ظ…ط§ظ„ظٹ ط§ظ„ظ…طھط¨ظ‚ظٹ: {total_remaining}"
        ).alignment = right
        ws.cell(row=3, column=1).fill = subheader_fill

        for col_idx, (label, width) in enumerate(columns, start=1):
            cell = ws.cell(row=4, column=col_idx, value=label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = border
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        row_idx = 5
        for idx, row in enumerate(rows, start=1):
            values = [
                idx,
                row['student_name'],
                row['phone'],
                row['student_type'],
                row['registered_by'],
                row['enrollment_date'],
            ]
            if include_course_col:
                values.insert(1, row['course_name'])
            values.extend([row['net_amount'], row['paid'], row['remaining']])

            for col_idx, value in enumerate(values, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.font = normal_font
                cell.border = border
                if col_idx in (1,):
                    cell.alignment = center
                else:
                    cell.alignment = right
                if col_idx >= len(values) - 2:
                    cell.number_format = '#,##0'
            row_idx += 1

    def build_rows(enrollments):
        rows = []
        for enrollment in enrollments:
            student = enrollment.student
            paid = _format_money(paid_map.get((student.id, enrollment.course_id), Decimal('0')))
            net_amount = _format_money(enrollment.net_amount or Decimal('0'))
            remaining = max(Decimal('0'), net_amount - paid)
            rows.append({
                'course_name': enrollment.course.name,
                'student_name': student.full_name,
                'phone': student.phone or "-",
                'student_type': student_type_label(student),
                'registered_by': registered_by_label(student),
                'enrollment_date': enrollment.enrollment_date.strftime('%Y-%m-%d') if enrollment.enrollment_date else "-",
                'net_amount': net_amount,
                'paid': paid,
                'remaining': remaining,
            })
        return rows

    all_rows = build_rows(enrollments)
    all_sheet = workbook.create_sheet("ظƒظ„ ط§ظ„ط¯ظˆط±ط§طھ")
    write_sheet(all_sheet, "ظƒظ„ ط§ظ„ط¯ظˆط±ط§طھ", all_rows, include_course_col=True)

    existing_titles = {all_sheet.title}
    for course in courses:
        course_enrollments = [e for e in enrollments if e.course_id == course.id]
        sheet_name = _safe_sheet_title(course.name, existing_titles)
        existing_titles.add(sheet_name)
        ws = workbook.create_sheet(sheet_name)
        write_sheet(ws, course.name, build_rows(course_enrollments), include_course_col=False)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    timestamp = timezone.now().strftime('%Y%m%d_%H%M')
    response['Content-Disposition'] = f'attachment; filename="طھظ‚ط±ظٹط±_ط§ظ„ط¯ظˆط±ط§طھ_ط§ظ„ط³ط±ظٹط¹ط©_{report_label}_{timestamp}.xlsx"'
    workbook.save(response)
    return response

# ------------------------------
# Quick outstanding helpers
def _get_outstanding_course_type(request):
    course_type = request.GET.get('course_type') or 'INTENSIVE'
    valid_course_types = {value for value, _ in QuickCourse.COURSE_TYPE_CHOICES}
    if course_type != 'ALL' and course_type not in valid_course_types:
        course_type = 'INTENSIVE'

    label_map = {value: label for value, label in QuickCourse.COURSE_TYPE_CHOICES}
    report_label_map = {
        'INTENSIVE': 'المكثفات',
        'EXAM': 'الامتحانيات',
        'REGULAR': 'العادية',
        'WEEKEND': 'نهاية الأسبوع',
    }

    if course_type == 'ALL':
        label = 'كل الدورات'
        report_label = 'كل الدورات'
    else:
        label = label_map.get(course_type, course_type)
        report_label = report_label_map.get(course_type, label)

    return course_type, label, report_label


def _get_outstanding_date_range(request):
    start_date = parse_date(request.GET.get('start_date') or '')
    end_date = parse_date(request.GET.get('end_date') or '')

    if start_date and end_date and start_date > end_date:
        start_date, end_date = end_date, start_date

    return start_date, end_date


def _get_course_type_options():
    options = [{'value': 'ALL', 'label': 'كل الدورات'}]
    for value, label in QuickCourse.COURSE_TYPE_CHOICES:
        options.append({'value': value, 'label': label})
    return options


def _build_quick_outstanding_course_summary(courses, include_zero_outstanding=False, start_date=None, end_date=None):
    courses = list(courses)
    course_map = {
        course.id: {
            'course': course,
            'total_students': 0,
            'male_students': 0,
            'female_students': 0,
            'unknown_students': 0,
            'paid_students': 0,
            'outstanding_students': 0,
            'total_outstanding': Decimal('0.00'),
            'total_paid': Decimal('0.00'),
        }
        for course in courses
    }

    enrollments_qs = QuickEnrollment.objects.filter(course__in=courses, is_completed=False)
    if start_date:
        enrollments_qs = enrollments_qs.filter(enrollment_date__gte=start_date)
    if end_date:
        enrollments_qs = enrollments_qs.filter(enrollment_date__lte=end_date)

    enrollments = list(enrollments_qs.select_related('course', 'student__student'))
    if enrollments:
        receipt_totals = QuickStudentReceipt.objects.filter(
            quick_enrollment_id__in=[enrollment.id for enrollment in enrollments]
        ).values('quick_enrollment_id').annotate(total=Sum('paid_amount'))
        paid_map = {
            row['quick_enrollment_id']: (row['total'] or Decimal('0'))
            for row in receipt_totals
        }
    else:
        paid_map = {}

    for enrollment in enrollments:
        net_amount = enrollment.net_amount or Decimal('0')
        paid_total = paid_map.get(enrollment.id, Decimal('0'))
        remaining = max(Decimal('0'), net_amount - paid_total)

        stats = course_map.get(enrollment.course_id)
        if not stats:
            continue

        stats['total_students'] += 1
        student_gender = getattr(getattr(enrollment.student, 'student', None), 'gender', None)
        if student_gender == 'male':
            stats['male_students'] += 1
        elif student_gender == 'female':
            stats['female_students'] += 1
        else:
            stats['unknown_students'] += 1
        if remaining > 0:
            stats['outstanding_students'] += 1
            stats['total_outstanding'] += remaining
        else:
            stats['paid_students'] += 1
        stats['total_paid'] += paid_total

    course_data = list(course_map.values())
    if not include_zero_outstanding:
        course_data = [row for row in course_data if row['outstanding_students'] > 0]

    totals = {
        'total_courses': len(course_data),
        'total_male_students': sum(row['male_students'] for row in course_data),
        'total_female_students': sum(row['female_students'] for row in course_data),
        'total_unknown_students': sum(row['unknown_students'] for row in course_data),
        'total_outstanding_students': sum(row['outstanding_students'] for row in course_data),
        'total_outstanding_amount': sum(row['total_outstanding'] for row in course_data),
        'total_paid_students': sum(row['paid_students'] for row in course_data),
        'total_students': sum(row['total_students'] for row in course_data),
        'total_paid_amount': sum(row['total_paid'] for row in course_data),
    }

    return course_data, totals


def _build_quick_outstanding_rows(courses, start_date=None, end_date=None):
    courses = list(courses)
    if not courses:
        return [], {'grouped_courses': [], 'totals': {'total_students': 0, 'total_courses': 0, 'total_outstanding': Decimal('0')}}

    enrollments_qs = QuickEnrollment.objects.filter(course__in=courses, is_completed=False)
    if start_date:
        enrollments_qs = enrollments_qs.filter(enrollment_date__gte=start_date)
    if end_date:
        enrollments_qs = enrollments_qs.filter(enrollment_date__lte=end_date)

    enrollments = list(
        enrollments_qs.select_related('course', 'student').order_by(
            'enrollment_date', 'course__name', 'student__full_name', 'id'
        )
    )

    paid_map = {}
    if enrollments:
        paid_rows = QuickStudentReceipt.objects.filter(
            quick_enrollment_id__in=[enrollment.id for enrollment in enrollments]
        ).values('quick_enrollment_id').annotate(total=Sum('paid_amount'))
        paid_map = {
            row['quick_enrollment_id']: (row['total'] or Decimal('0'))
            for row in paid_rows
        }

    today = timezone.localdate()
    rows = []
    grouped_map = {}

    for enrollment in enrollments:
        net_amount = enrollment.net_amount or Decimal('0')
        paid_total = paid_map.get(enrollment.id, Decimal('0'))
        remaining = max(Decimal('0'), net_amount - paid_total)
        if remaining <= 0:
            continue

        enrollment_date = enrollment.enrollment_date
        days_since = (today - enrollment_date).days if enrollment_date else 0
        row = {
            'enrollment_id': enrollment.id,
            'course_id': enrollment.course_id,
            'course_name': enrollment.course.name,
            'student_id': enrollment.student_id,
            'student_name': enrollment.student.full_name,
            'phone': enrollment.student.phone,
            'enrollment_date': enrollment_date,
            'days_since_enrollment': max(days_since, 0),
            'net_amount': net_amount,
            'paid_amount': paid_total,
            'remaining': remaining,
        }
        rows.append(row)

        course_bucket = grouped_map.setdefault(enrollment.course_id, {
            'course': enrollment.course,
            'date_groups': {},
            'total_students': 0,
            'total_outstanding': Decimal('0'),
        })
        date_bucket = course_bucket['date_groups'].setdefault(enrollment_date, {
            'date': enrollment_date,
            'students': [],
            'total_students': 0,
            'total_outstanding': Decimal('0'),
            'max_days_since_enrollment': 0,
        })
        date_bucket['students'].append(row)
        date_bucket['total_students'] += 1
        date_bucket['total_outstanding'] += remaining
        date_bucket['max_days_since_enrollment'] = max(date_bucket['max_days_since_enrollment'], row['days_since_enrollment'])
        course_bucket['total_students'] += 1
        course_bucket['total_outstanding'] += remaining

    grouped_courses = []
    for course_bucket in grouped_map.values():
        grouped_courses.append({
            'course': course_bucket['course'],
            'date_groups': sorted(course_bucket['date_groups'].values(), key=lambda item: item['date']),
            'total_students': course_bucket['total_students'],
            'total_outstanding': course_bucket['total_outstanding'],
        })

    grouped_courses.sort(key=lambda item: item['course'].name)
    return rows, {
        'grouped_courses': grouped_courses,
        'totals': {
            'total_students': len(rows),
            'total_courses': len(grouped_courses),
            'total_outstanding': sum(row['remaining'] for row in rows),
        }
    }


def _withdraw_quick_enrollment(enrollment, user, withdrawal_reason='', refund_amount=None):
    student = enrollment.student
    if enrollment.is_completed:
        raise ValueError('هذه الدورة مسحوبة مسبقاً')

    with transaction.atomic():
        paid_total = QuickStudentReceipt.objects.filter(
            quick_student=student,
            quick_enrollment=enrollment,
            course=enrollment.course
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')

        refund_amount = paid_total
        refund_result = _adjust_quick_receipts_for_refund(student, enrollment, refund_amount)
        actual_refund = refund_result['refunded_amount']

        description = f"سحب طالب سريع {student.full_name} من {enrollment.course.name}"
        if withdrawal_reason:
            description = f"{description} - {withdrawal_reason}"

        created_entries = _build_quick_withdrawal_entry(
            enrollment=enrollment,
            user=user,
            refunded_amount=actual_refund,
            description=description,
        )

        enrollment.is_completed = True
        enrollment.completion_date = timezone.now().date()
        enrollment.save(update_fields=['is_completed', 'completion_date'])

    return {
        'actual_refund': actual_refund,
        'student_name': student.full_name,
        'course_name': enrollment.course.name,
        'created_entry_ids': [entry.id for entry in created_entries],
    }


def _snapshot_outstanding_totals(totals):
    return {
        'total_courses': int(totals.get('total_courses', 0) or 0),
        'total_students': int(totals.get('total_students', 0) or 0),
        'total_paid_students': int(totals.get('total_paid_students', 0) or 0),
        'total_outstanding_students': int(totals.get('total_outstanding_students', 0) or 0),
        'total_paid_amount': float(totals.get('total_paid_amount', 0) or 0),
        'total_outstanding_amount': float(totals.get('total_outstanding_amount', 0) or 0),
    }


def _build_outstanding_comparison(current_totals, previous_totals):
    if not previous_totals:
        return None

    def make_item(label, key, improve_when):
        current_value = current_totals.get(key, 0)
        previous_value = previous_totals.get(key, 0)
        delta = current_value - previous_value
        if delta > 0:
            trend = 'ط²ظٹط§ط¯ط©'
        elif delta < 0:
            trend = 'ظ†ظ‚طµط§ظ†'
        else:
            trend = 'ط«ط¨ط§طھ'

        if improve_when == 'up':
            improved = delta > 0
        elif improve_when == 'down':
            improved = delta < 0
        else:
            improved = None

        return {
            'label': label,
            'current': current_value,
            'previous': previous_value,
            'delta': delta,
            'trend': trend,
            'improved': improved,
        }

    items = [
        make_item('ط¥ط¬ظ…ط§ظ„ظٹ ط§ظ„ط·ظ„ط§ط¨', 'total_students', None),
        make_item('ط§ظ„ط·ظ„ط§ط¨ ط§ظ„ظ…ط³ط¯ط¯ظٹظ†', 'total_paid_students', 'up'),
        make_item('ط§ظ„ط·ظ„ط§ط¨ ط؛ظٹط± ط§ظ„ظ…ط³ط¯ط¯ظٹظ†', 'total_outstanding_students', 'down'),
        make_item('ط¥ط¬ظ…ط§ظ„ظٹ ط§ظ„ظ…ط¯ظپظˆط¹', 'total_paid_amount', 'up'),
        make_item('ط¥ط¬ظ…ط§ظ„ظٹ ط§ظ„ظ…طھط¨ظ‚ظٹ', 'total_outstanding_amount', 'down'),
    ]

    improvement_count = sum(1 for item in items if item['improved'] is True)
    decline_count = sum(1 for item in items if item['improved'] is False)

    return {
        'items': items,
        'improvement_count': improvement_count,
        'decline_count': decline_count,
        'total_tracked': improvement_count + decline_count,
    }


class QuickOutstandingCoursesPrintView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/outstanding_course_print.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course_type, course_type_label, report_label = _get_outstanding_course_type(self.request)
        courses = QuickCourse.objects.filter(is_active=True).select_related('academic_year').order_by('name')
        if course_type != 'ALL':
            courses = courses.filter(course_type=course_type)
        course_data, totals = _build_quick_outstanding_course_summary(courses, include_zero_outstanding=True)
        course_data = sorted(
            course_data,
            key=lambda row: (-row['total_students'], row['course'].name)
        )
        current_snapshot = _snapshot_outstanding_totals(totals)
        previous_snapshot = self.request.session.get('quick_outstanding_report_snapshot')
        previous_time = self.request.session.get('quick_outstanding_report_timestamp')
        comparison = _build_outstanding_comparison(current_snapshot, previous_snapshot)

        context.update({
            'courses': course_data,
            'totals': totals,
            'print_date': timezone.now().strftime('%Y-%m-%d %H:%M'),
            'comparison': comparison,
            'previous_report_time': previous_time,
            'course_type': course_type,
            'course_type_label': course_type_label,
            'course_type_report_label': report_label,
        })

        self.request.session['quick_outstanding_report_snapshot'] = current_snapshot
        self.request.session['quick_outstanding_report_timestamp'] = timezone.now().strftime('%Y-%m-%d %H:%M')
        return context

    
 # ط§ظ„ظپطµظˆظ„ ط§ظ„ط¯ط±ط§ط³ظٹط©
class AcademicYearListView(LoginRequiredMixin, ListView):
    model = AcademicYear
    template_name = 'quick/academic_year_list.html'
    context_object_name = 'academic_years'
    
    def get_queryset(self):
        return AcademicYear.objects.all().order_by('-start_date')

class AcademicYearCreateView(LoginRequiredMixin, CreateView):
    model = AcademicYear
    form_class = AcademicYearForm
    template_name = 'quick/academic_year_form.html'
    success_url = reverse_lazy('quick:academic_year_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'طھظ… ط¥ط¶ط§ظپط© ط§ظ„ظپطµظ„ ط§ظ„ط¯ط±ط§ط³ظٹ ط¨ظ†ط¬ط§ط­')
        return super().form_valid(form)

class CloseAcademicYearView(LoginRequiredMixin, DetailView):
    model = AcademicYear
    template_name = 'quick/academic_year_close.html'
    
    def post(self, request, *args, **kwargs):
        academic_year = self.get_object()
        password = request.POST.get('password')
        
        # ط§ظ„طھط­ظ‚ظ‚ ظ…ظ† ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط±
        if not request.user.check_password(password):
            messages.error(request, 'ظƒظ„ظ…ط© ط§ظ„ظ…ط±ظˆط± ط؛ظٹط± طµط­ظٹط­ط©')
            return render(request, self.template_name, {'academic_year': academic_year})
        
        academic_year.is_closed = True
        academic_year.closed_by = request.user
        academic_year.closed_at = timezone.now()
        academic_year.save()
        
        messages.success(request, 'طھظ… ط¥ط؛ظ„ط§ظ‚ ط§ظ„ظپطµظ„ ط§ظ„ط¯ط±ط§ط³ظٹ ط¨ظ†ط¬ط§ط­')
        return redirect('quick:academic_year_list')

# ط§ظ„ط¯ظˆط±ط§طھ ط§ظ„ط³ط±ظٹط¹ط©
class QuickCourseListView(LoginRequiredMixin, ListView):
    model = QuickCourse
    template_name = 'quick/quick_course_list.html'
    context_object_name = 'courses'
    
    def get_queryset(self):
        return (
            QuickCourse.objects.filter(is_active=True)
            .select_related('academic_year')
            .annotate(
                enrollments_count=Count(
                    'enrollments',
                    filter=Q(enrollments__is_completed=False, enrollments__student__is_active=True),
                    distinct=True,
                ),
                sessions_count=Count('sessions', filter=Q(sessions__is_active=True), distinct=True),
            )
            .order_by('-created_at')
        )


class QuickClassroomListView(LoginRequiredMixin, ListView):
    model = Classroom
    template_name = 'quick/quick_classroom_list.html'
    context_object_name = 'classrooms'

    def get_queryset(self):
        return Classroom.objects.filter(class_type='course').order_by('name', 'id')


class QuickClassroomCreateView(LoginRequiredMixin, CreateView):
    model = Classroom
    form_class = QuickClassroomForm
    template_name = 'quick/quick_classroom_form.html'
    success_url = reverse_lazy('quick:classroom_list')

    def form_valid(self, form):
        messages.success(self.request, 'تمت إضافة كلاس/قاعة للدورات السريعة.')
        return super().form_valid(form)


class QuickClassroomUpdateView(LoginRequiredMixin, UpdateView):
    model = Classroom
    form_class = QuickClassroomForm
    template_name = 'quick/quick_classroom_form.html'
    success_url = reverse_lazy('quick:classroom_list')

    def get_queryset(self):
        return Classroom.objects.filter(class_type='course')

    def form_valid(self, form):
        messages.success(self.request, 'تم تحديث بيانات الصف/القاعة.')
        return super().form_valid(form)


class QuickStudentIntersectionView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/student_intersections.html'

    def _get_selected_course_ids(self):
        selected_ids = []
        seen_ids = set()

        for raw_value in self.request.GET.getlist('course_ids'):
            try:
                course_id = int(raw_value)
            except (TypeError, ValueError):
                continue
            if course_id not in seen_ids:
                selected_ids.append(course_id)
                seen_ids.add(course_id)

        add_course_raw = self.request.GET.get('add_course')
        if add_course_raw:
            try:
                add_course_id = int(add_course_raw)
            except (TypeError, ValueError):
                add_course_id = None
            if add_course_id and add_course_id not in seen_ids:
                selected_ids.append(add_course_id)

        return selected_ids

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        selected_course_ids = self._get_selected_course_ids()
        courses_queryset = (
            QuickCourse.objects.filter(is_active=True)
            .select_related('academic_year')
            .annotate(
                active_students_count=Count(
                    'enrollments',
                    filter=Q(enrollments__is_completed=False, enrollments__student__is_active=True),
                    distinct=True,
                )
            )
            .order_by('-academic_year__start_date', 'name')
        )

        courses_map = {course.id: course for course in courses_queryset}
        selected_courses = [courses_map[course_id] for course_id in selected_course_ids if course_id in courses_map]
        selected_course_ids = [course.id for course in selected_courses]

        intersection_ids = None
        for course_id in selected_course_ids:
            course_student_ids = set(
                QuickEnrollment.objects.filter(
                    course_id=course_id,
                    is_completed=False,
                    student__is_active=True,
                ).values_list('student_id', flat=True)
            )
            if intersection_ids is None:
                intersection_ids = course_student_ids
            else:
                intersection_ids &= course_student_ids

        matching_student_ids = sorted(intersection_ids) if intersection_ids else []
        matching_students = []
        if matching_student_ids:
            matching_students = list(
                QuickStudent.objects.filter(id__in=matching_student_ids, is_active=True)
                .select_related('student', 'academic_year')
                .annotate(
                    total_active_courses=Count(
                        'enrollments',
                        filter=Q(enrollments__is_completed=False),
                        distinct=True,
                    ),
                    matched_courses_count=Count(
                        'enrollments',
                        filter=Q(enrollments__course_id__in=selected_course_ids, enrollments__is_completed=False),
                        distinct=True,
                    ),
                )
                .order_by('full_name', 'id')
            )

        selected_course_entries = []
        for index, course in enumerate(selected_courses):
            remaining_ids = [str(course_id) for i, course_id in enumerate(selected_course_ids) if i != index]
            remove_url = reverse('quick:student_intersections')
            if remaining_ids:
                remove_url = f"{remove_url}?{urlencode([('course_ids', course_id) for course_id in remaining_ids])}"
            selected_course_entries.append({
                'course': course,
                'remove_url': remove_url,
            })

        available_courses = [course for course in courses_queryset if course.id not in selected_course_ids]

        context.update({
            'selected_courses': selected_course_entries,
            'selected_course_ids': selected_course_ids,
            'available_courses': available_courses,
            'matching_students': matching_students,
            'matching_students_count': len(matching_students),
            'selected_courses_count': len(selected_courses),
            'total_available_courses': courses_queryset.count(),
            'has_selection': bool(selected_courses),
            'intersection_mode': 'single' if len(selected_courses) == 1 else 'multi',
            'is_exact_intersection': len(selected_courses) > 1,
        })
        return context

class QuickCourseCreateView(LoginRequiredMixin, CreateView):
    model = QuickCourse
    form_class = QuickCourseForm
    template_name = 'quick/quick_course_form.html'
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'طھظ… ط¥ط¶ط§ظپط© ط§ظ„ط¯ظˆط±ط© ط§ظ„ط³ط±ظٹط¹ط© ط¨ظ†ط¬ط§ط­')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('quick:course_detail', kwargs={'pk': self.object.pk})


def _quick_session_display_rows(course):
    today = timezone.localdate()
    sessions = list(
        course.sessions.filter(is_active=True)
        .prefetch_related('session_enrollments__enrollment__student')
        .order_by('start_date', 'start_time', 'title')
    )
    rows = []
    for session in sessions:
        rows.append({
            'session': session,
            'is_upcoming': session.start_date > today,
            'is_open': session.start_date <= today <= session.end_date,
            'is_finished': today > session.end_date,
            'attendance_taken_today': session.attendance_records.filter(attendance_date=today).count(),
        })
    return rows


def _dates_overlap(start_a, end_a, start_b, end_b):
    return start_a <= end_b and start_b <= end_a


def _times_overlap(start_a, end_a, start_b, end_b):
    if not end_a or not end_b:
        return start_a == start_b
    return start_a < end_b and start_b < end_a


def _session_conflicts_with_window(session, start_date, end_date, start_time, end_time):
    return (
        _dates_overlap(start_date, end_date, session.start_date, session.end_date)
        and _times_overlap(start_time, end_time, session.start_time, session.end_time)
    )


def _sessions_conflict(first_session, second_session):
    return _session_conflicts_with_window(
        second_session,
        first_session.start_date,
        first_session.end_date,
        first_session.start_time,
        first_session.end_time,
    )


def _build_quick_session_conflict_report(course_type='ALL', selected_course_ids=None):
    courses = QuickCourse.objects.filter(is_active=True).select_related('academic_year').order_by('name')
    if course_type != 'ALL':
        courses = courses.filter(course_type=course_type)
    if selected_course_ids:
        courses = courses.filter(id__in=selected_course_ids)

    course_list = list(courses)
    course_ids = [course.id for course in course_list]
    assignments = (
        QuickCourseSessionEnrollment.objects.filter(
            session__is_active=True,
            session__course_id__in=course_ids,
            enrollment__is_completed=False,
            enrollment__student__is_active=True,
        )
        .select_related(
            'enrollment__student',
            'session',
            'session__course',
            'session__course__academic_year',
        )
        .order_by(
            'enrollment__student__full_name',
            'session__start_date',
            'session__start_time',
            'session_id',
        )
    )

    assignments_by_student = defaultdict(list)
    for assignment in assignments:
        assignments_by_student[assignment.enrollment.student_id].append(assignment)

    conflict_rows = []
    grouped_students = []
    course_ids_with_conflicts = set()
    session_ids_with_conflicts = set()

    for student_assignments in assignments_by_student.values():
        student_conflicts = []
        for first_assignment, second_assignment in combinations(student_assignments, 2):
            first_session = first_assignment.session
            second_session = second_assignment.session
            if first_session.course_id == second_session.course_id:
                continue
            if not _sessions_conflict(first_session, second_session):
                continue

            overlap_start_date = max(first_session.start_date, second_session.start_date)
            overlap_end_date = min(first_session.end_date, second_session.end_date)
            overlap_start_time = max(first_session.start_time, second_session.start_time)
            if first_session.end_time and second_session.end_time:
                overlap_end_time = min(first_session.end_time, second_session.end_time)
            else:
                overlap_end_time = first_session.end_time or second_session.end_time

            row = {
                'student': first_assignment.enrollment.student,
                'first_assignment': first_assignment,
                'second_assignment': second_assignment,
                'first_session': first_session,
                'second_session': second_session,
                'overlap_start_date': overlap_start_date,
                'overlap_end_date': overlap_end_date,
                'overlap_start_time': overlap_start_time,
                'overlap_end_time': overlap_end_time,
            }
            conflict_rows.append(row)
            student_conflicts.append(row)
            course_ids_with_conflicts.update([first_session.course_id, second_session.course_id])
            session_ids_with_conflicts.update([first_session.id, second_session.id])

        if student_conflicts:
            grouped_students.append({
                'student': student_conflicts[0]['student'],
                'conflicts': student_conflicts,
                'conflicts_count': len(student_conflicts),
            })

    conflict_rows.sort(
        key=lambda row: (
            row['overlap_start_date'],
            row['overlap_start_time'],
            row['student'].full_name,
            row['first_session'].course.name,
        )
    )
    grouped_students.sort(
        key=lambda row: (-row['conflicts_count'], row['student'].full_name)
    )

    return {
        'courses': course_list,
        'grouped_students': grouped_students,
        'conflict_rows': conflict_rows,
        'unique_students_count': len(grouped_students),
        'unique_courses_count': len(course_ids_with_conflicts),
        'unique_sessions_count': len(session_ids_with_conflicts),
        'total_conflicts': len(conflict_rows),
    }


def _effective_capacity(option_max_capacity, room_max_capacity):
    limits = [value for value in [option_max_capacity, room_max_capacity] if value]
    return min(limits) if limits else 0


def _course_active_enrollment_count(course):
    return QuickEnrollment.objects.filter(
        course=course,
        is_completed=False,
        student__is_active=True,
    ).count()


def _find_available_room_for_option(option, needed_students=0):
    candidate_rooms = Classroom.objects.filter(class_type='course', is_active=True).order_by('name')
    room_rank = lambda room: (
        0 if _effective_capacity(option.max_capacity, getattr(room, 'max_capacity', 0)) >= needed_students else 1,
        -(_effective_capacity(option.max_capacity, getattr(room, 'max_capacity', 0)) or 0),
        room.name,
    )
    if option.preferred_room_id:
        candidate_rooms = sorted(
            list(candidate_rooms),
            key=lambda room: (
                0 if room.id == option.preferred_room_id else 1,
                *room_rank(room),
            )
        )
    else:
        candidate_rooms = sorted(list(candidate_rooms), key=room_rank)

    conflicting_sessions = QuickCourseSession.objects.filter(is_active=True).exclude(course=option.course)
    for room in candidate_rooms:
        room_conflict = conflicting_sessions.filter(room_id=room.id)
        room_has_overlap = any(
            _session_conflicts_with_window(
                session,
                option.start_date,
                option.end_date,
                option.start_time,
                option.end_time,
            )
            for session in room_conflict
        )
        if room_has_overlap:
            continue
        return room
    return option.preferred_room


def _student_has_conflict_for_session(student_id, session):
    other_sessions = (
        QuickCourseSession.objects.filter(
            is_active=True,
            session_enrollments__enrollment__student_id=student_id,
            session_enrollments__enrollment__is_completed=False,
            session_enrollments__enrollment__student__is_active=True,
        )
        .exclude(course=session.course)
        .distinct()
    )
    return any(_sessions_conflict(session, other_session) for other_session in other_sessions)


def _auto_assign_course_enrollments(course, user):
    sessions = list(
        course.sessions.filter(is_active=True)
        .order_by('start_date', 'start_time', 'id')
    )
    enrollments = list(
        QuickEnrollment.objects.filter(course=course, is_completed=False, student__is_active=True)
        .select_related('student')
        .order_by('enrollment_date', 'id')
    )

    QuickCourseSessionEnrollment.objects.filter(session__course=course).delete()

    assigned_count = 0
    unassigned_count = 0
    seats_used = {}

    for enrollment in enrollments:
        assigned = False
        for session in sessions:
            seats_used.setdefault(session.id, 0)
            if session.capacity and seats_used[session.id] >= session.capacity:
                continue
            if _student_has_conflict_for_session(enrollment.student_id, session):
                continue
            QuickCourseSessionEnrollment.objects.create(
                session=session,
                enrollment=enrollment,
                assigned_by=user,
            )
            seats_used[session.id] += 1
            assigned_count += 1
            assigned = True
            break
        if not assigned:
            unassigned_count += 1

    under_minimum = sum(1 for session in sessions if session.enrolled_count and not session.meets_minimum_capacity)
    empty_sessions = sum(1 for session in sessions if session.enrolled_count == 0)
    return {
        'assigned_count': assigned_count,
        'unassigned_count': unassigned_count,
        'under_minimum': under_minimum,
        'empty_sessions': empty_sessions,
    }


def _assign_enrollment_to_available_session(enrollment, user=None):
    sessions = (
        QuickCourseSession.objects.filter(course=enrollment.course, is_active=True)
        .order_by('start_date', 'start_time', 'id')
    )
    for session in sessions:
        if session.capacity and session.enrolled_count >= session.capacity:
            continue
        if _student_has_conflict_for_session(enrollment.student_id, session):
            continue
        assignment, _created = QuickCourseSessionEnrollment.objects.update_or_create(
            enrollment=enrollment,
            defaults={'session': session, 'assigned_by': user},
        )
        return assignment
    return None


def _generate_course_sessions_from_options(course, user):
    options = list(
        course.time_options.filter(is_active=True)
        .select_related('preferred_room')
        .order_by('priority', 'start_date', 'start_time', 'id')
    )

    QuickCourseSession.objects.filter(course=course).update(is_active=False)

    created_sessions = []
    skipped_options = []
    total_students = QuickEnrollment.objects.filter(course=course, is_completed=False, student__is_active=True).count()
    remaining_students = total_students
    remaining_options = len(options)
    for index, option in enumerate(options, start=1):
        target_students = ceil(remaining_students / remaining_options) if remaining_options else remaining_students
        room = _find_available_room_for_option(option, needed_students=target_students)
        if room is None and Classroom.objects.filter(class_type='course', is_active=True).exists():
            skipped_options.append(option.title)
            remaining_options -= 1
            continue
        room_capacity = getattr(room, 'max_capacity', 0) if room else 0
        effective_capacity = _effective_capacity(option.max_capacity, room_capacity)
        session = QuickCourseSession.objects.create(
            course=course,
            time_option=option,
            title=option.title or f"كلاس {index}",
            code=f"{course.id}-{index}",
            min_capacity=max(option.min_capacity or 1, getattr(room, 'min_capacity', 1) or 1),
            capacity=effective_capacity,
            start_date=option.start_date,
            end_date=option.end_date,
            start_time=option.start_time,
            end_time=option.end_time,
            meeting_days=option.meeting_days,
            room=room,
            room_name=(room.name if room else ''),
            notes=option.notes,
            is_active=True,
            created_by=user,
        )
        created_sessions.append(session)
        remaining_students = max(0, remaining_students - (effective_capacity or remaining_students))
        remaining_options -= 1
    return created_sessions, skipped_options


def _generate_schedule_for_courses(courses, user):
    summary = {
        'courses_processed': 0,
        'sessions_created': 0,
        'students_assigned': 0,
        'students_unassigned': 0,
        'courses_with_unassigned': [],
        'courses_without_sessions': [],
        'skipped_options': [],
    }
    ordered_courses = sorted(
        list(courses),
        key=lambda course: (-_course_active_enrollment_count(course), course.id),
    )
    for course in ordered_courses:
        created_sessions, skipped_options = _generate_course_sessions_from_options(course, user)
        assignment_result = _auto_assign_course_enrollments(course, user)
        summary['courses_processed'] += 1
        summary['sessions_created'] += len(created_sessions)
        summary['students_assigned'] += assignment_result['assigned_count']
        summary['students_unassigned'] += assignment_result['unassigned_count']
        if not created_sessions:
            summary['courses_without_sessions'].append(course.name)
        if assignment_result['unassigned_count']:
            summary['courses_with_unassigned'].append(course.name)
        summary['skipped_options'].extend(skipped_options)
    return summary


class QuickCourseDetailView(LoginRequiredMixin, DetailView):
    model = QuickCourse
    template_name = 'quick/quick_course_detail.html'
    context_object_name = 'course'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        active_enrollments = (
            QuickEnrollment.objects.filter(course=course, is_completed=False, student__is_active=True)
            .select_related('student')
            .order_by('student__full_name')
        )
        assigned_ids = set(
            QuickCourseSessionEnrollment.objects.filter(session__course=course).values_list('enrollment_id', flat=True)
        )
        context.update({
            'session_form': QuickCourseSessionForm(),
            'session_rows': _quick_session_display_rows(course),
            'active_enrollments': active_enrollments,
            'unassigned_enrollments': [enrollment for enrollment in active_enrollments if enrollment.id not in assigned_ids],
            'transfer_form': QuickSessionTransferForm(course=course),
            'sessions_manage_url': reverse('quick:course_sessions_manage', kwargs={'course_id': course.id}),
            'today': timezone.localdate(),
        })
        return context


class QuickCourseSessionsManageView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/quick_course_sessions_manage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = get_object_or_404(QuickCourse.objects.select_related('academic_year'), pk=self.kwargs['course_id'], is_active=True)
        active_enrollments = (
            QuickEnrollment.objects.filter(course=course, is_completed=False, student__is_active=True)
            .select_related('student')
            .order_by('enrollment_date', 'id')
        )
        assigned_ids = set(
            QuickCourseSessionEnrollment.objects.filter(session__course=course).values_list('enrollment_id', flat=True)
        )
        context.update({
            'course': course,
            'session_form': QuickCourseSessionForm(),
            'time_option_form': QuickCourseTimeOptionForm(),
            'time_options': course.time_options.filter(is_active=True).select_related('preferred_room').order_by('priority', 'start_date', 'start_time'),
            'session_rows': _quick_session_display_rows(course),
            'active_enrollments': active_enrollments,
            'unassigned_enrollments': [enrollment for enrollment in active_enrollments if enrollment.id not in assigned_ids],
            'transfer_form': QuickSessionTransferForm(course=course),
            'today': timezone.localdate(),
        })
        return context


class QuickCourseTimeOptionsManageView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/quick_course_time_options_manage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = get_object_or_404(QuickCourse.objects.select_related('academic_year'), pk=self.kwargs['course_id'], is_active=True)
        options = course.time_options.filter(is_active=True).select_related('preferred_room').order_by('priority', 'start_date', 'start_time')
        context.update({
            'course': course,
            'time_option_form': QuickCourseTimeOptionForm(),
            'time_options': options,
            'rooms': Classroom.objects.filter(class_type='course', is_active=True).order_by('name'),
        })
        return context


@login_required
@require_POST
def quick_course_add_session(request, course_id):
    course = get_object_or_404(QuickCourse, pk=course_id, is_active=True)
    form = QuickCourseSessionForm(request.POST)
    if form.is_valid():
        session = form.save(commit=False)
        session.course = course
        session.created_by = request.user
        session.save()
        messages.success(request, 'تمت إضافة كلاس جديد للدورة.')
    else:
        messages.error(request, 'تعذر حفظ الصف. يرجى مراجعة الحقول المدخلة.')
    return redirect('quick:course_sessions_manage', course_id=course.id)


@login_required
@require_POST
def quick_course_add_time_option(request, course_id):
    course = get_object_or_404(QuickCourse, pk=course_id, is_active=True)
    form = QuickCourseTimeOptionForm(request.POST)
    if form.is_valid():
        option = form.save(commit=False)
        option.course = course
        option.created_by = request.user
        option.save()
        messages.success(request, 'تمت إضافة وقت متاح للدورة.')
    else:
        error_parts = []
        for field_name, field_errors in form.errors.items():
            label = form.fields.get(field_name).label if field_name in form.fields else 'التحقق العام'
            for error in field_errors:
                error_parts.append(f"{label}: {error}")
        messages.error(
            request,
            'تعذر حفظ الوقت المتاح. ' + ' | '.join(error_parts[:4]) if error_parts else 'تعذر حفظ الوقت المتاح.',
        )
    return redirect('quick:course_time_options_manage', course_id=course.id)


@login_required
@require_POST
def quick_course_generate_schedule(request, course_id):
    course = get_object_or_404(QuickCourse, pk=course_id, is_active=True)
    created_sessions, skipped_options = _generate_course_sessions_from_options(course, request.user)
    result = _auto_assign_course_enrollments(course, request.user)
    if skipped_options:
        messages.warning(request, f"تم تخطي بعض الخيارات بسبب تعارض القاعات أو الطلاب: {', '.join(skipped_options[:5])}")
    messages.success(
        request,
        f"تم توليد {len(created_sessions)} كلاس وتوزيع {result['assigned_count']} طالب تلقائياً."
    )
    return redirect('quick:course_sessions_manage', course_id=course.id)


@login_required
@require_POST
def quick_generate_all_schedules(request):
    active_courses = QuickCourse.objects.filter(is_active=True)
    courses_without_time_options = list(
        active_courses.filter(
            enrollments__is_completed=False,
            enrollments__student__is_active=True,
        )
        .exclude(time_options__is_active=True)
        .distinct()
        .order_by('name')
        .values_list('name', flat=True)
    )
    courses = (
        active_courses.filter(time_options__is_active=True)
        .distinct()
        .order_by('id')
    )
    summary = _generate_schedule_for_courses(courses, request.user)
    if courses_without_time_options:
        messages.warning(
            request,
            'هذه الدورات لديها طلاب لكن لا يوجد لها أي وقت متاح فعّال: '
            + ', '.join(courses_without_time_options[:8])
        )
    if summary['skipped_options']:
        messages.warning(request, 'تم تخطي بعض الأوقات بسبب التعارض: ' + ', '.join(summary['skipped_options'][:8]))
    if summary['courses_without_sessions']:
        messages.warning(
            request,
            'تعذر توليد أي كلاس لبعض الدورات رغم وجود أوقات متاحة: '
            + ', '.join(summary['courses_without_sessions'][:8])
        )
    if summary['students_unassigned']:
        messages.error(
            request,
            f"بقي {summary['students_unassigned']} طالب بدون كلاس في الدورات التالية: "
            + ', '.join(summary['courses_with_unassigned'][:8])
        )
    else:
        messages.success(
            request,
            f"تم توليد برنامج {summary['courses_processed']} دورة وإنشاء {summary['sessions_created']} كلاس "
            f"وتوزيع {summary['students_assigned']} طالب بدون أي طلاب غير موزعين."
        )
    return redirect('quick:course_list')


@login_required
@require_POST
def quick_course_session_extend(request, session_id):
    session = get_object_or_404(QuickCourseSession, pk=session_id, is_active=True)
    session.end_date = session.end_date + timedelta(days=1)
    session.save(update_fields=['end_date', 'updated_at'])
    messages.success(request, f'تمت إضافة يوم دوام إلى {session.title}.')
    return redirect('quick:course_sessions_manage', course_id=session.course_id)


@login_required
@require_POST
def quick_course_session_assign_students(request, session_id):
    session = get_object_or_404(QuickCourseSession, pk=session_id, is_active=True)
    form = QuickSessionAssignStudentsForm(request.POST, session=session)
    if not form.is_valid():
        messages.error(request, 'تعذر توزيع الطلاب على الصف.')
        return redirect('quick:course_session_students', session_id=session.id)

    selected = list(form.cleaned_data['enrollment_ids'])
    if session.capacity and selected:
        remaining = max(0, session.capacity - session.enrolled_count)
        if len(selected) > remaining:
            messages.error(request, f'السعة المتبقية في الصف هي {remaining} طالب فقط.')
            return redirect('quick:course_session_students', session_id=session.id)

    created_count = 0
    for enrollment in selected:
        assignment, created = QuickCourseSessionEnrollment.objects.get_or_create(
            enrollment=enrollment,
            defaults={'session': session, 'assigned_by': request.user},
        )
        if not created and assignment.session_id != session.id:
            assignment.session = session
            assignment.assigned_by = request.user
            assignment.save(update_fields=['session', 'assigned_by'])
            created = True
        if created:
            created_count += 1

    messages.success(request, f'تم توزيع {created_count} طالب على الصف.')
    return redirect('quick:course_session_students', session_id=session.id)


@login_required
@require_POST
def quick_course_transfer_students(request, course_id):
    course = get_object_or_404(QuickCourse, pk=course_id, is_active=True)
    form = QuickSessionTransferForm(request.POST, course=course)
    if not form.is_valid():
        messages.error(request, 'تعذر نقل الطلاب بين الصفوف.')
        return redirect('quick:course_sessions_manage', course_id=course.id)

    source = form.cleaned_data['source_session']
    target = form.cleaned_data['target_session']
    enrollments = list(form.cleaned_data['enrollment_ids'])

    if target.capacity:
        remaining = max(0, target.capacity - target.enrolled_count)
        if len(enrollments) > remaining:
            messages.error(request, f'السعة المتبقية في الصف الهدف هي {remaining} طالب فقط.')
            return redirect('quick:course_sessions_manage', course_id=course.id)

    moved = 0
    for enrollment in enrollments:
        assignment = getattr(enrollment, 'session_assignment', None)
        if assignment and assignment.session_id == source.id:
            assignment.session = target
            assignment.assigned_by = request.user
            assignment.save(update_fields=['session', 'assigned_by'])
            moved += 1

    messages.success(request, f'تم نقل {moved} طالب إلى {target.title}.')
    return redirect('quick:course_sessions_manage', course_id=course.id)


@login_required
@require_POST
def quick_course_auto_assign_students(request, course_id):
    course = get_object_or_404(QuickCourse, pk=course_id, is_active=True)
    result = _auto_assign_course_enrollments(course, request.user)
    messages.success(
        request,
        f"تم التوزيع التلقائي لـ {result['assigned_count']} طالب. "
        f"غير الموزعين: {result['unassigned_count']} | "
        f"كلاسات دون الحد الأدنى: {result['under_minimum']}."
    )
    return redirect('quick:course_sessions_manage', course_id=course.id)


class QuickCourseSessionStudentsView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/quick_course_session_students.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = get_object_or_404(
            QuickCourseSession.objects.select_related('course', 'course__academic_year'),
            pk=self.kwargs['session_id'],
        )
        assignments = list(
            session.session_enrollments.select_related('enrollment__student')
            .order_by('enrollment__student__full_name')
        )
        context.update({
            'session': session,
            'course': session.course,
            'assignments': assignments,
            'assign_form': QuickSessionAssignStudentsForm(session=session),
            'today': timezone.localdate(),
        })
        return context


class QuickCourseAttendanceDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/quick_course_attendance_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        sessions = (
            QuickCourseSession.objects.filter(is_active=True)
            .select_related('course', 'course__academic_year')
            .prefetch_related('session_enrollments__enrollment__student')
            .order_by('start_date', 'start_time', 'course__name', 'title')
        )
        live_sessions = []
        upcoming_sessions = []
        archived_sessions = []
        for session in sessions:
            row = {
                'session': session,
                'assigned_count': session.enrolled_count,
                'attendance_taken_today': session.attendance_records.filter(attendance_date=today).count(),
                'current_day_number': session.get_day_number_for_date(min(today, session.end_date)) if today >= session.start_date else None,
            }
            if session.start_date <= today <= session.end_date:
                live_sessions.append(row)
            elif session.start_date > today:
                upcoming_sessions.append(row)
            else:
                archived_sessions.append(row)
        live_sessions.sort(key=lambda item: (item['session'].start_date, item['session'].start_time))
        upcoming_sessions.sort(key=lambda item: (item['session'].start_date, item['session'].start_time))
        archived_sessions.sort(key=lambda item: (item['session'].end_date, item['session'].start_time), reverse=True)
        context.update({
            'today': today,
            'live_sessions': live_sessions,
            'upcoming_sessions': upcoming_sessions,
            'archived_sessions': archived_sessions[:12],
        })
        return context


class QuickCourseAttendanceArchiveView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/quick_course_attendance_archive.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        archived_sessions = (
            QuickCourseSession.objects.filter(is_active=True, start_date__lt=today)
            .select_related('course', 'course__academic_year')
            .order_by('-start_date', '-start_time')
        )
        context['archived_sessions'] = [session for session in archived_sessions if session.is_finished]
        return context


class QuickCourseSessionAttendanceView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/quick_course_session_attendance.html'

    def _get_session(self):
        return get_object_or_404(
            QuickCourseSession.objects.select_related('course', 'course__academic_year'),
            pk=self.kwargs['session_id'],
        )

    def _resolve_attendance_date(self, session):
        today = timezone.localdate()
        raw_value = self.request.GET.get('date') or self.request.POST.get('attendance_date')
        attendance_date = parse_date(raw_value) if raw_value else today
        if attendance_date is None:
            attendance_date = today
        if attendance_date < session.start_date:
            attendance_date = session.start_date
        if attendance_date > today:
            attendance_date = today
        if attendance_date > session.end_date:
            attendance_date = session.end_date
        return attendance_date

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self._get_session()
        attendance_date = self._resolve_attendance_date(session)
        assignments = list(
            session.session_enrollments.select_related('enrollment__student')
            .order_by('enrollment__student__full_name')
        )
        records = {
            record.enrollment_id: record
            for record in session.attendance_records.filter(attendance_date=attendance_date)
        }
        form = QuickSessionAttendanceBulkForm(
            initial={'attendance_date': attendance_date},
            session=session,
            assignments=assignments,
        )
        for assignment in assignments:
            record = records.get(assignment.enrollment_id)
            if not record:
                continue
            prefix = f"student_{assignment.enrollment_id}"
            form.fields[f"{prefix}_status"].initial = record.status
            form.fields[f"{prefix}_notes"].initial = record.notes

        attendance_rows = []
        for assignment in assignments:
            prefix = f"student_{assignment.enrollment_id}"
            attendance_rows.append({
                'assignment': assignment,
                'status_field': form[f"{prefix}_status"],
                'notes_field': form[f"{prefix}_notes"],
            })

        context.update({
            'session': session,
            'course': session.course,
            'attendance_form': form,
            'assignments': assignments,
            'attendance_rows': attendance_rows,
            'attendance_date': attendance_date,
            'day_number': session.get_day_number_for_date(attendance_date),
            'today': timezone.localdate(),
            'can_take_attendance': attendance_date >= session.start_date,
            'max_attendance_date': min(timezone.localdate(), session.end_date),
        })
        return context

    def post(self, request, *args, **kwargs):
        session = self._get_session()
        attendance_date = self._resolve_attendance_date(session)
        assignments = list(
            session.session_enrollments.select_related('enrollment__student')
            .order_by('enrollment__student__full_name')
        )
        if attendance_date < session.start_date:
            messages.error(request, 'لا يمكن أخذ الحضور قبل بداية الصف.')
            return redirect('quick:course_session_attendance', session_id=session.id)

        form = QuickSessionAttendanceBulkForm(request.POST, session=session, assignments=assignments)
        if not form.is_valid():
            messages.error(request, 'تعذر حفظ الحضور.')
            return self.get(request, *args, **kwargs)

        day_number = session.get_day_number_for_date(attendance_date) or 1
        saved = 0
        for assignment in assignments:
            prefix = f"student_{assignment.enrollment_id}"
            status = form.cleaned_data.get(f"{prefix}_status") or 'present'
            notes = form.cleaned_data.get(f"{prefix}_notes", '')
            QuickCourseSessionAttendance.objects.update_or_create(
                session=session,
                enrollment=assignment.enrollment,
                attendance_date=attendance_date,
                defaults={
                    'day_number': day_number,
                    'status': status,
                    'notes': notes,
                    'created_by': request.user,
                },
            )
            saved += 1

        messages.success(request, f'تم حفظ حضور {saved} طالب لليوم رقم {day_number}.')
        return redirect(f"{reverse('quick:course_session_attendance', kwargs={'session_id': session.id})}?date={attendance_date.isoformat()}")


class QuickCourseSchedulePrintView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/quick_course_schedule_print.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_ids = []
        for raw_value in self.request.GET.getlist('course_ids'):
            try:
                selected_ids.append(int(raw_value))
            except (TypeError, ValueError):
                continue
        course_type = self.request.GET.get('course_type') or 'INTENSIVE'
        courses = QuickCourse.objects.filter(is_active=True, course_type=course_type).select_related('academic_year')
        if selected_ids:
            courses = courses.filter(id__in=selected_ids)
        sessions = (
            QuickCourseSession.objects.filter(course__in=courses, is_active=True)
            .select_related('course', 'course__academic_year')
            .order_by('start_date', 'start_time', 'course__name', 'title')
        )
        total_students = 0
        sessions_by_course = defaultdict(list)
        for session in sessions:
            assigned_count = session.enrolled_count
            total_students += assigned_count
            sessions_by_course[session.course_id].append({
                'session': session,
                'assigned_count': assigned_count,
                'seat_utilization': (
                    round((assigned_count / session.capacity) * 100)
                    if session.capacity else 0
                ),
            })
        course_cards = []
        for course in courses.order_by('name'):
            course_sessions = sessions_by_course.get(course.id, [])
            course_cards.append({
                'course': course,
                'sessions': course_sessions,
                'students_count': sum(item['assigned_count'] for item in course_sessions),
            })
        context.update({
            'courses': courses.order_by('name'),
            'sessions': sessions,
            'course_cards': course_cards,
            'selected_course_ids': selected_ids,
            'selected_course_type': course_type,
            'course_type_choices': QuickCourse.COURSE_TYPE_CHOICES,
            'total_courses': courses.count(),
            'total_sessions': sessions.count(),
            'total_students': total_students,
            'generated_at': timezone.localtime(),
        })
        return context


class QuickCourseConflictReportView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/quick_course_conflicts_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_ids = []
        for raw_value in self.request.GET.getlist('course_ids'):
            try:
                selected_ids.append(int(raw_value))
            except (TypeError, ValueError):
                continue
        course_type = self.request.GET.get('course_type') or 'ALL'
        report = _build_quick_session_conflict_report(
            course_type=course_type,
            selected_course_ids=selected_ids,
        )
        context.update({
            'available_courses': report['courses'],
            'grouped_students': report['grouped_students'],
            'conflict_rows': report['conflict_rows'],
            'unique_students_count': report['unique_students_count'],
            'unique_courses_count': report['unique_courses_count'],
            'unique_sessions_count': report['unique_sessions_count'],
            'total_conflicts': report['total_conflicts'],
            'selected_course_ids': selected_ids,
            'selected_course_type': course_type,
            'course_type_choices': [('ALL', 'كل الأنواع')] + list(QuickCourse.COURSE_TYPE_CHOICES),
            'generated_at': timezone.localtime(),
        })
        return context

# ط§ظ„ط·ظ„ط§ط¨ ط§ظ„ط³ط±ظٹط¹ظٹظ†
class QuickStudentListView(LoginRequiredMixin, ListView):
    model = QuickStudent
    template_name = 'quick/quick_student_list.html'
    context_object_name = 'students'
    
    def get_queryset(self):
        academic_year_id = self.request.GET.get('academic_year')
        gender = self.request.GET.get('gender')
        queryset = QuickStudent.objects.filter(is_active=True).select_related('student', 'academic_year')
        if academic_year_id:
            queryset = queryset.filter(academic_year_id=academic_year_id)
        if gender in ('male', 'female'):
            queryset = queryset.filter(student__gender=gender)
        elif gender == 'unknown':
            queryset = queryset.filter(Q(student__gender__isnull=True) | Q(student__gender=''))
        return queryset

    def post(self, request, *args, **kwargs):
        gender = request.POST.get('gender')
        student_ids = request.POST.getlist('student_ids')
        next_url = request.POST.get('next') or reverse('quick:student_list')

        if not student_ids:
            messages.warning(request, 'ظٹط±ط¬ظ‰ ط§ط®طھظٹط§ط± ط·ظ„ط§ط¨ ط£ظˆظ„ط§ظ‹.')
            return redirect(next_url)

        if gender not in ('male', 'female', 'unknown'):
            messages.error(request, 'ظ‚ظٹظ…ط© ط§ظ„ط¬ظ†ط³ ط؛ظٹط± طµط­ظٹط­ط©.')
            return redirect(next_url)

        gender_value = '' if gender == 'unknown' else gender
        queryset = QuickStudent.objects.filter(id__in=student_ids).select_related('student')
        updated_count = 0
        for quick_student in queryset:
            student = getattr(quick_student, 'student', None)
            if student and student.gender != gender_value:
                student.gender = gender_value
                student.save(update_fields=['gender'])
                updated_count += 1

        if gender_value:
            messages.success(request, f'طھظ… طھط­ط¯ظٹط« ط§ظ„ط¬ظ†ط³ ظ„ظ€ {updated_count} ط·ط§ظ„ط¨/ط·ط§ظ„ط¨ط©.')
        else:
            messages.success(request, f'طھظ… ط¥ط²ط§ظ„ط© طھط­ط¯ظٹط¯ ط§ظ„ط¬ظ†ط³ ظ„ظ€ {updated_count} ط·ط§ظ„ط¨/ط·ط§ظ„ط¨ط©.')
        return redirect(next_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # ط¥ط­طµط§ط¦ظٹط§طھ ط§ظ„ط±ط¨ط· ط§ظ„طھظ„ظ‚ط§ط¦ظٹ
        students = context['students']
        auto_assigned = students.filter(academic_year__isnull=False)
        unassigned = students.filter(academic_year__isnull=True)
        
        context.update({
            'academic_years': AcademicYear.objects.all().order_by('-start_date'),
            'auto_assigned_count': auto_assigned.count(),
            'unassigned_count': unassigned.count(),
        })
        return context


@require_superuser
def quick_duplicate_students_report(request):
    if request.method == 'POST':
        action = request.POST.get('action') or 'merge_one'
        group_key = _normalize_quick_student_name(request.POST.get('group_name'))
        search_query = (request.POST.get('q') or '').strip()
        scope = request.POST.get('scope') or 'active'

        if action == 'merge_all':
            duplicate_groups = _get_duplicate_groups(search_query=search_query, scope=scope)
            if not duplicate_groups:
                messages.info(request, 'لا توجد مجموعات مكررة مطابقة للفلتر الحالي.')
                return redirect(f"{reverse('quick:duplicate_students_report')}?{urlencode({'q': search_query, 'scope': scope})}")

            merged_groups = 0
            total_enrollments = 0
            total_receipts = 0
            total_reversed = 0
            failed_groups = []

            for group in duplicate_groups:
                try:
                    merge_result = _merge_quick_students_by_name_with_retry(group['normalized_name'], request.user)
                except Exception as exc:
                    failed_groups.append(f'{group["display_name"]}: {exc}')
                    continue

                merged_groups += 1
                total_enrollments += merge_result['merged_enrollments']
                total_receipts += merge_result['merged_receipts']
                total_reversed += merge_result['reversed_duplicates']

            if merged_groups:
                messages.success(
                    request,
                    f'تم الدمج الجماعي لـ {merged_groups} مجموعة، '
                    f'ونُقل {total_enrollments} تسجيل و{total_receipts} إيصال، '
                    f'مع عكس {total_reversed} تسجيل مكرر.'
                )
            if failed_groups:
                for error in failed_groups[:10]:
                    messages.error(request, f'فشل دمج السجلات المكررة: {error}')
        else:
            if not group_key:
                messages.error(request, 'لم يتم تحديد الاسم المطلوب دمجه.')
                return redirect(f"{reverse('quick:duplicate_students_report')}?{urlencode({'q': search_query, 'scope': scope})}")

            try:
                merge_result = _merge_quick_students_by_name_with_retry(group_key, request.user)
            except Exception as exc:
                messages.error(request, f'فشل دمج السجلات المكررة: {exc}')
            else:
                messages.success(
                    request,
                    'تم الدمج بنجاح إلى السجل '
                    f'#{merge_result["target"].id}، '
                    f'ونُقل {merge_result["merged_enrollments"]} تسجيل و{merge_result["merged_receipts"]} إيصال، '
                    f'مع عكس {merge_result["reversed_duplicates"]} تسجيل مكرر على نفس الدورة.'
                )

        return redirect(f"{reverse('quick:duplicate_students_report')}?{urlencode({'q': search_query, 'scope': scope})}")

    search_query = (request.GET.get('q') or '').strip()
    scope = request.GET.get('scope') or 'active'
    include_inactive = scope == 'all'

    enrollment_queryset = (
        QuickEnrollment.objects.select_related('course')
        .prefetch_related(
            Prefetch(
                'quickstudentreceipt_set',
                queryset=QuickStudentReceipt.objects.select_related('created_by', 'journal_entry').order_by('date', 'id')
            )
        )
        .annotate(
            paid_total=Coalesce(
                Sum('quickstudentreceipt__paid_amount'),
                Value(Decimal('0')),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )
        .order_by('course__name', 'id')
    )

    students_queryset = (
        QuickStudent.objects.select_related('student', 'academic_year', 'created_by')
        .prefetch_related(
            Prefetch('enrollments', queryset=enrollment_queryset),
            Prefetch(
                'quickstudentreceipt_set',
                queryset=QuickStudentReceipt.objects.select_related(
                    'created_by', 'journal_entry', 'course', 'quick_enrollment'
                ).order_by('date', 'id')
            )
        )
        .order_by('full_name', 'id')
    )
    if not include_inactive:
        students_queryset = students_queryset.filter(is_active=True)

    grouped_students = defaultdict(list)
    for quick_student in students_queryset:
        normalized_name = _normalize_quick_student_name(quick_student.full_name)
        if normalized_name:
            grouped_students[normalized_name].append(quick_student)

    duplicate_groups = []
    duplicate_records_count = 0
    total_balance = Decimal('0')
    total_remaining = Decimal('0')
    total_enrollments = 0
    normalized_search = _normalize_quick_student_name(search_query)

    for normalized_name, students in grouped_students.items():
        if len(students) < 2:
            continue
        if normalized_search and normalized_search not in normalized_name:
            continue

        members = []
        group_balance = Decimal('0')
        group_remaining = Decimal('0')
        group_enrollments = 0

        for quick_student in students:
            enrollments_data = []
            student_remaining = Decimal('0')
            account_created_by = '-'
            if quick_student.created_by:
                account_created_by = quick_student.created_by.get_full_name() or quick_student.created_by.username or '-'
            all_student_receipts = list(quick_student.quickstudentreceipt_set.all())
            used_receipt_ids = set()
            enrollments = list(quick_student.enrollments.all())
            enrollment_entry_refs = {f'QE-{enrollment.id}': enrollment for enrollment in enrollments}
            journal_entries = {
                entry.reference: entry
                for entry in JournalEntry.objects.filter(reference__in=enrollment_entry_refs.keys()).select_related('created_by')
            }

            for enrollment in enrollments:
                net_amount = enrollment.net_amount or Decimal('0')
                paid_amount = enrollment.paid_total or Decimal('0')
                remaining_amount = max(Decimal('0'), net_amount - paid_amount)
                student_remaining += remaining_amount
                group_enrollments += 1
                enrollment_created_by = '-'
                receipt_rows = []

                enrollment_entry = journal_entries.get(f'QE-{enrollment.id}')
                if enrollment_entry and enrollment_entry.created_by:
                    enrollment_created_by = (
                        enrollment_entry.created_by.get_full_name()
                        or enrollment_entry.created_by.username
                        or '-'
                    )

                receipts = [
                    receipt for receipt in all_student_receipts
                    if receipt.quick_enrollment_id == enrollment.id
                    or (
                        receipt.quick_enrollment_id is None
                        and receipt.course_id == enrollment.course_id
                    )
                ]
                if enrollment_created_by == '-' and receipts:
                    first_receipt_creator = receipts[0].created_by
                    if first_receipt_creator:
                        enrollment_created_by = (
                            first_receipt_creator.get_full_name()
                            or first_receipt_creator.username
                            or '-'
                        )

                for receipt in receipts:
                    receipt_created_by = '-'
                    if receipt.created_by:
                        receipt_created_by = receipt.created_by.get_full_name() or receipt.created_by.username or '-'
                    used_receipt_ids.add(receipt.id)
                    receipt_rows.append({
                        'id': receipt.id,
                        'receipt_number': receipt.receipt_number or '-',
                        'date': receipt.date,
                        'paid_amount': receipt.paid_amount or Decimal('0'),
                        'amount': receipt.amount or Decimal('0'),
                        'is_printed': receipt.is_printed,
                        'created_by': receipt_created_by,
                    })

                enrollments_data.append({
                    'course_name': enrollment.course.name if enrollment.course else '-',
                    'enrollment_date': enrollment.enrollment_date,
                    'net_amount': net_amount,
                    'paid_amount': paid_amount,
                    'remaining_amount': remaining_amount,
                    'is_completed': enrollment.is_completed,
                    'registered_by': enrollment_created_by,
                    'receipts': receipt_rows,
                    'has_receipts': bool(receipt_rows),
                    'receipts_count': len(receipt_rows),
                })

            orphan_receipts = []
            for receipt in all_student_receipts:
                if receipt.id in used_receipt_ids:
                    continue
                receipt_created_by = '-'
                if receipt.created_by:
                    receipt_created_by = receipt.created_by.get_full_name() or receipt.created_by.username or '-'
                orphan_receipts.append({
                    'id': receipt.id,
                    'receipt_number': receipt.receipt_number or '-',
                    'date': receipt.date,
                    'course_name': receipt.course_name or (receipt.course.name if receipt.course else '-'),
                    'paid_amount': receipt.paid_amount or Decimal('0'),
                    'amount': receipt.amount or Decimal('0'),
                    'is_printed': receipt.is_printed,
                    'created_by': receipt_created_by,
                })

            account_balance = quick_student.balance
            group_balance += account_balance
            group_remaining += student_remaining

            members.append({
                'student': quick_student,
                'account_created_by': account_created_by,
                'account_balance': account_balance,
                'remaining_total': student_remaining,
                'enrollments': enrollments_data,
                'enrollments_count': len(enrollments_data),
                'orphan_receipts': orphan_receipts,
                'has_orphan_receipts': bool(orphan_receipts),
            })

        members.sort(key=lambda item: item['student'].id)
        duplicate_groups.append({
            'display_name': students[0].full_name,
            'normalized_name': normalized_name,
            'students': members,
            'duplicate_count': len(members),
            'group_balance': group_balance,
            'group_remaining': group_remaining,
            'group_enrollments': group_enrollments,
        })

        duplicate_records_count += len(members)
        total_balance += group_balance
        total_remaining += group_remaining
        total_enrollments += group_enrollments

    duplicate_groups.sort(key=lambda item: (-item['duplicate_count'], item['display_name']))

    context = {
        'duplicate_groups': duplicate_groups,
        'search_query': search_query,
        'scope': scope,
        'duplicate_names_count': len(duplicate_groups),
        'duplicate_records_count': duplicate_records_count,
        'total_balance': total_balance,
        'total_remaining': total_remaining,
        'total_enrollments': total_enrollments,
    }
    return render(request, 'quick/quick_duplicate_students_report.html', context)


@require_superuser
def quick_duplicate_students_print(request):
    group_key = _normalize_quick_student_name(request.GET.get('name'))
    scope = request.GET.get('scope') or 'active'
    duplicate_groups = _get_duplicate_groups(scope=scope)
    group = next((item for item in duplicate_groups if item['normalized_name'] == group_key), None)
    if not group:
        raise Http404('Duplicate group not found')

    return render(request, 'quick/quick_duplicate_students_print.html', {
        'group': group,
        'scope': scope,
        'print_date': timezone.now(),
    })


@require_superuser
def quick_duplicate_students_full_print(request):
    search_query = (request.GET.get('q') or '').strip()
    scope = request.GET.get('scope') or 'active'
    duplicate_groups = _get_duplicate_groups(search_query=search_query, scope=scope)

    total_balance = sum((group['group_balance'] for group in duplicate_groups), Decimal('0'))
    total_remaining = sum((group['group_remaining'] for group in duplicate_groups), Decimal('0'))
    total_enrollments = sum((group['group_enrollments'] for group in duplicate_groups), 0)
    total_records = sum((group['duplicate_count'] for group in duplicate_groups), 0)

    return render(request, 'quick/quick_duplicate_students_full_print.html', {
        'duplicate_groups': duplicate_groups,
        'search_query': search_query,
        'scope': scope,
        'duplicate_names_count': len(duplicate_groups),
        'duplicate_records_count': total_records,
        'total_balance': total_balance,
        'total_remaining': total_remaining,
        'total_enrollments': total_enrollments,
        'print_date': timezone.now(),
    })


@require_superuser
def quick_accounting_fix_tool(request):
    if request.method == 'POST':
        result = _apply_quick_accounting_fixes(request.user)
        if result['fixed_links'] or result['fixed_withdrawals'] or result['fixed_receipts']:
            messages.success(
                request,
                f'تم تنفيذ التصحيح: ربط {result["fixed_links"]} قيد تسجيل '
                f'وتصحيح {result["fixed_receipts"]} قيد قبض '
                f'وإلغاء/تنظيف {result["cleaned_withdraw_entries"]} قيد سحب قديم '
                f'وإنشاء {result["fixed_withdrawals"]} قيد سحب جديد.'
            )
        else:
            messages.info(request, 'لم يتم العثور على قيود سريعة تحتاج تصحيحاً تلقائياً.')

        if result['deactivated_legacy_accounts']:
            messages.info(
                request,
                'تم تعطيل حسابات الانسحاب القديمة بدون حذف أي بيانات: '
                + ', '.join(result['deactivated_legacy_accounts'])
            )

        for error in result['errors'][:10]:
            messages.error(request, error)
        return redirect('quick:accounting_fix_tool')

    rows = _build_quick_accounting_fix_rows()
    issue_rows = [row for row in rows if row['issues']]
    context = {
        'rows': rows,
        'issue_rows': issue_rows,
        'audited_count': len(rows),
        'issues_count': len(issue_rows),
        'compliant_count': sum(1 for row in rows if row['is_compliant']),
        'missing_entry_count': sum(1 for row in rows if row['missing_entry']),
        'withdraw_fix_count': sum(
            1 for row in issue_rows
            if row['legacy_entries_count'] > 0 and row['correction_amount'] > 0
        ),
        'total_correction_amount': sum((row['correction_amount'] for row in issue_rows), Decimal('0')),
    }
    return render(request, 'quick/quick_accounting_fix_tool.html', context)


@require_superuser
def quick_withdrawal_fix_tool(request):
    if request.method == 'POST':
        result = _apply_quick_withdrawal_fixes(request.user)
        if result['fixed_withdrawals'] or result['cleaned_withdraw_entries']:
            messages.success(
                request,
                f'تم تنفيذ تصحيح قيود السحب: حذف/تنظيف {result["cleaned_withdraw_entries"]} قيد سحب قديم '
                f'وإنشاء {result["fixed_withdrawals"]} قيد عكس جديد.'
            )
        else:
            messages.info(request, 'لم يتم العثور على قيود سحب سريعة تحتاج تصحيحاً.')

        if result['deactivated_legacy_accounts']:
            messages.info(
                request,
                'تم تعطيل حسابات الانسحاب القديمة بدون حذف أي بيانات: '
                + ', '.join(result['deactivated_legacy_accounts'])
            )

        for error in result['errors'][:10]:
            messages.error(request, error)
        return redirect('quick:withdrawal_fix_tool')

    rows = _build_quick_withdrawal_fix_rows()
    context = {
        'rows': rows,
        'audited_count': len(rows),
        'legacy_count': sum(1 for row in rows if row['legacy_entries_count'] > 0),
        'retained_count': sum(1 for row in rows if row['retained_amount'] > 0),
        'missing_withdraw_count': sum(
            1 for row in rows if 'تسجيل مسحوب بدون قيد سحب واضح' in row['issues']
        ),
    }
    return render(request, 'quick/quick_withdrawal_fix_tool.html', context)


def _get_existing_quick_student_ar_account(student):
    if not student or not getattr(student, 'id', None):
        return None
    return Account.objects.filter(code=f'1252-{student.id:03d}').first()


def _get_quick_student_related_journal_entries(student):
    ar_account = _get_existing_quick_student_ar_account(student)
    if not ar_account:
        return JournalEntry.objects.none()

    entry_ids = Transaction.objects.filter(
        account=ar_account
    ).values_list('journal_entry_id', flat=True).distinct()
    return JournalEntry.objects.filter(id__in=entry_ids).distinct()


def _get_quick_student_delete_summary(student):
    enrollments_count = QuickEnrollment.objects.filter(student=student).count()
    receipts_count = QuickStudentReceipt.objects.filter(quick_student=student).count()
    print_jobs_count = QuickReceiptPrintJob.objects.filter(quick_student=student).count()
    journal_entries = _get_quick_student_related_journal_entries(student)
    journal_entries_count = journal_entries.count()
    transactions_count = Transaction.objects.filter(journal_entry__in=journal_entries).count()
    ar_account = _get_existing_quick_student_ar_account(student)

    return {
        'enrollments_count': enrollments_count,
        'receipts_count': receipts_count,
        'print_jobs_count': print_jobs_count,
        'journal_entries_count': journal_entries_count,
        'transactions_count': transactions_count,
        'ar_account_code': ar_account.code if ar_account else '-',
        'account_codes_display': ar_account.code if ar_account else '-',
    }


@login_required
def quick_delete_student(request, student_id):
    student = get_object_or_404(QuickStudent.objects.select_related('student'), pk=student_id)
    summary = _get_quick_student_delete_summary(student)

    if not request.user.is_superuser and not request.user.has_perm('quick.change_quickstudent'):
        if request.method == 'GET':
            return JsonResponse({'success': False, 'error': 'لا تملك صلاحية حذف الطلاب السريعين.'}, status=403)
        messages.error(request, 'لا تملك صلاحية حذف الطلاب السريعين.')
        return redirect('quick:student_profile', student_id=student.id)

    if request.method == 'GET':
        return JsonResponse({
            'success': True,
            'student_name': student.full_name,
            'summary': summary,
        })

    redirect_url = reverse('quick:student_list')
    linked_student = getattr(student, 'student', None)
    ar_account = _get_existing_quick_student_ar_account(student)
    journal_entries = list(_get_quick_student_related_journal_entries(student))

    with transaction.atomic():
        if journal_entries:
            JournalEntry.objects.filter(id__in=[entry.id for entry in journal_entries]).delete()

        student.delete()

        if linked_student:
            linked_student.delete()

        if ar_account and not Transaction.objects.filter(account=ar_account).exists():
            ar_account.delete()

    Account.rebuild_all_balances()

    messages.success(
        request,
        f'تم حذف الطالب السريع "{student.full_name}" مع {summary["enrollments_count"]} تسجيل، '
        f'{summary["receipts_count"]} إيصال، {summary["journal_entries_count"]} قيد، '
        f'و{summary["transactions_count"]} حركة مالية.'
    )
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'تم حذف الطالب السريع "{student.full_name}" مع كل البيانات المرتبطة به.',
        })
    return redirect(redirect_url)

class QuickStudentCreateView(LoginRequiredMixin, CreateView):
    model = QuickStudent
    form_class = QuickStudentForm
    template_name = 'quick/quick_student_form.html'

    def get_initial(self):
        initial = super().get_initial()
        active_year = AcademicYear.objects.filter(is_active=True).order_by('-start_date').first()
        if active_year:
            initial.setdefault('academic_year', active_year.id)
        return initial

    def form_valid(self, form):
        # ط¥ظ†ط´ط§ط، ط·ط§ظ„ط¨ ظ†ط¸ط§ظ…ظٹ ط£ظˆظ„ط§ظ‹
        from students.models import Student
        student = Student.objects.create(
            full_name=form.cleaned_data['full_name'],
            phone=form.cleaned_data['phone'],
            email='',
            gender=form.cleaned_data.get('gender', '') or '',
            is_active=True,
            added_by=self.request.user
        )
        
        form.instance.student = student
        form.instance.created_by = self.request.user
        messages.success(self.request, 'طھظ… ط¥ط¶ط§ظپط© ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط³ط±ظٹط¹ ط¨ظ†ط¬ط§ط­')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('quick:student_profile', kwargs={'student_id': self.object.pk})


@require_GET
@login_required
def quick_student_exists(request):
    field = (request.GET.get('field') or '').strip()
    value = (request.GET.get('value') or '').strip()
    exclude_id = request.GET.get('exclude_id')

    queryset = QuickStudent.objects.all().only('id', 'full_name', 'phone')
    if exclude_id and exclude_id.isdigit():
        queryset = queryset.exclude(pk=int(exclude_id))

    match = None
    if field == 'full_name' and value:
        normalized_value = _normalize_quick_name(value)
        match = next(
            (student for student in queryset if _normalize_quick_name(student.full_name) == normalized_value),
            None
        )
    elif field == 'phone' and value:
        normalized_value = _normalize_quick_phone(value)
        match = next(
            (student for student in queryset if _normalize_quick_phone(student.phone) == normalized_value),
            None
        )

    return JsonResponse({
        'exists': bool(match),
        'field': field,
        'full_name': match.full_name if match else '',
        'phone': match.phone if match else '',
        'id': match.id if match else None,
    })

class QuickStudentDetailView(LoginRequiredMixin, DetailView):
    model = QuickStudent
    template_name = 'quick/quick_student_detail.html'
    context_object_name = 'student'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['enrollments'] = QuickEnrollment.objects.filter(
            student=self.object
        ).select_related('course')
        return context

# ط§ظ„طھط³ط¬ظٹظ„ط§طھ ط§ظ„ط³ط±ظٹط¹ط©
class QuickEnrollmentCreateView(LoginRequiredMixin, CreateView):
    model = QuickEnrollment
    form_class = QuickEnrollmentForm
    template_name = 'quick/quick_enrollment_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        student_id = self.request.GET.get('student')
        course_id = self.request.GET.get('course')
        
        if student_id:
            initial['student'] = student_id
        if course_id:
            course = get_object_or_404(QuickCourse, id=course_id)
            initial['course'] = course_id
            initial['net_amount'] = course.price
        
        return initial
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # ط¥ظ†ط´ط§ط، ط§ظ„ظ‚ظٹط¯ ط§ظ„ظ…ط­ط§ط³ط¨ظٹ
        try:
            self.object.create_accrual_enrollment_entry(self.request.user)
            assignment = _assign_enrollment_to_available_session(self.object, self.request.user)
            if assignment is None:
                messages.warning(self.request, 'تم تسجيل الطالب لكن لا يوجد كلاس فيه شاغر حالياً لهذه الدورة.')
            messages.success(self.request, 'طھظ… طھط³ط¬ظٹظ„ ط§ظ„ط·ط§ظ„ط¨ ظˆط¥ظ†ط´ط§ط، ط§ظ„ظ‚ظٹط¯ ط§ظ„ظ…ط­ط§ط³ط¨ظٹ ط¨ظ†ط¬ط§ط­')
        except Exception as e:
            messages.warning(self.request, f'طھظ… ط§ظ„طھط³ط¬ظٹظ„ ظˆظ„ظƒظ† ط­ط¯ط« ط®ط·ط£ ظپظٹ ط§ظ„ظ‚ظٹط¯ ط§ظ„ظ…ط­ط§ط³ط¨ظٹ: {str(e)}')
        return response
    
    def get_success_url(self):
        return reverse_lazy('quick:student_detail', kwargs={'pk': self.object.student.pk})

# ط¨ط±ظˆظپط§ظٹظ„ ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط³ط±ظٹط¹
class QuickStudentProfileView(LoginRequiredMixin, DetailView):
    model = QuickStudent
    template_name = 'quick/quick_student_profile.html'
    context_object_name = 'student'
    
    def get_object(self):
        return get_object_or_404(QuickStudent, id=self.kwargs.get('student_id'))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()
        
        try:
            # âœ… ط¬ظ„ط¨ ط§ظ„طھط³ط¬ظٹظ„ط§طھ ط§ظ„ظ†ط´ط·ط© ظپظ‚ط·
            active_enrollments_queryset = QuickEnrollment.objects.filter(
                student=student, 
                is_completed=False
            ).select_related('course')
            
            # âœ… ط¥ظ†ط´ط§ط، ظ‚ط§ط¦ظ…ط© ط¨ط§ظ„ط¨ظٹط§ظ†ط§طھ ط§ظ„ظ…ط­ط³ظˆط¨ط© ظ„ظ„طھط³ط¬ظٹظ„ط§طھ ط§ظ„ظ†ط´ط·ط©
            enrollment_data = []
            for enrollment in active_enrollments_queryset:
                # ط§ط±ط¨ط· ط§ظ„ط¯ظپط¹ط§طھ ط¨ظ‡ط°ط§ ط§ظ„طھط³ط¬ظٹظ„ ظ†ظپط³ظ‡ ظ„ظ…ظ†ط¹ ط®ظ„ط· ط¥ظٹطµط§ظ„ط§طھ طھط³ط¬ظٹظ„ ط¢ط®ط±
                total_paid = _get_quick_enrollment_paid_total(enrollment, student)
                
                net_amount = enrollment.net_amount or Decimal('0.00')
                balance_due = max(Decimal('0.00'), net_amount - total_paid)
                
                enrollment_data.append({
                    'enrollment': enrollment,
                    'total_paid': total_paid,
                    'balance_due': balance_due,
                    'net_amount': net_amount,
                    'is_active': not enrollment.is_completed
                })
            
            # âœ… ط­ط³ط§ط¨ ط§ظ„ط¥ط¬ظ…ط§ظ„ظٹط§طھ
            total_paid = sum(item['total_paid'] for item in enrollment_data)
            total_due = sum(item['net_amount'] for item in enrollment_data)
            total_remaining = total_due - total_paid
            
            # âœ… ط¬ظ„ط¨ ط¬ظ…ظٹط¹ ط§ظ„ط¥ظٹطµط§ظ„ط§طھ ط§ظ„ط³ط±ظٹط¹ط©
            receipts = QuickStudentReceipt.objects.filter(
                quick_student=student
            ).select_related('course').order_by('-date', '-id')
            
            # âœ… ط§ظ„طھط­ظ‚ظ‚ ظ…ظ† ظˆط¬ظˆط¯ طھط³ط¬ظٹظ„ط§طھ ظ†ط´ط·ط©
            has_active_enrollments = len(enrollment_data) > 0
            
            context.update({
                'enrollment_data': enrollment_data,
                'active_enrollments': enrollment_data,
                'total_paid': total_paid,
                'total_due': total_due,
                'total_remaining': total_remaining,
                'receipts': receipts,
                'has_active_enrollments': has_active_enrollments,
                'delete_summary': _get_quick_student_delete_summary(student),
            })
            
        except Exception as e:
            messages.error(self.request, f'ط­ط¯ط« ط®ط·ط£ ظپظٹ طھط­ظ…ظٹظ„ ط§ظ„ط¨ظٹط§ظ†ط§طھ: {str(e)}')
            context.update({
                'enrollment_data': [],
                'active_enrollments': [],
                'total_paid': Decimal('0.00'),
                'total_due': Decimal('0.00'),
                'total_remaining': Decimal('0.00'),
                'receipts': [],
                'has_active_enrollments': False,
                'delete_summary': _get_quick_student_delete_summary(student),
            })
        
        return context
# ظƒط´ظپ ط­ط³ط§ط¨ ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط³ط±ظٹط¹
class QuickStudentStatementView(LoginRequiredMixin, DetailView):
    model = QuickStudent
    template_name = 'quick/quick_student_statement.html'
    context_object_name = 'student'
    
    def get_object(self):
        return get_object_or_404(QuickStudent, id=self.kwargs.get('student_id'))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()
        
        try:
            enrollments = list(
                QuickEnrollment.objects.filter(student=student)
                .select_related('course')
                .order_by('enrollment_date', 'id')
            )
            receipts = list(
                QuickStudentReceipt.objects.filter(quick_student=student)
                .select_related('course', 'quick_enrollment', 'journal_entry', 'created_by')
                .order_by('date', 'id')
            )

            enrollment_data = []
            per_course = []
            total_paid = Decimal('0.00')
            total_due = Decimal('0.00')

            entry_ids = set()
            enrollment_refs = {f'QE-{enrollment.id}' for enrollment in enrollments}
            if enrollment_refs:
                entry_ids.update(
                    JournalEntry.objects.filter(reference__in=enrollment_refs).values_list('id', flat=True)
                )

            for receipt in receipts:
                if receipt.journal_entry_id:
                    entry_ids.add(receipt.journal_entry_id)

            for enrollment in enrollments:
                total_enrollment_paid = _get_quick_enrollment_paid_total(enrollment, student)
                net_amount = enrollment.net_amount or Decimal('0.00')
                balance_due = max(Decimal('0.00'), net_amount - total_enrollment_paid)

                enrollment_data.append({
                    'enrollment': enrollment,
                    'total_paid': total_enrollment_paid,
                    'balance_due': balance_due,
                    'net_amount': net_amount,
                    'is_active': not enrollment.is_completed,
                })
                per_course.append({
                    'course': enrollment.course,
                    'price': net_amount,
                    'paid': total_enrollment_paid,
                    'outstanding': balance_due,
                    'is_completed': enrollment.is_completed,
                    'enrollment_id': enrollment.id,
                })

                total_paid += total_enrollment_paid
                total_due += net_amount

                entry_ids.update(
                    _find_quick_withdrawal_entries(enrollment).values_list('id', flat=True)
                )
                entry_ids.update(
                    _find_quick_generated_withdraw_fix_entries(enrollment).values_list('id', flat=True)
                )

            entry_ids.update(
                JournalEntry.objects.filter(description__icontains=student.full_name).values_list('id', flat=True)
            )

            journal_entries = list(
                JournalEntry.objects.filter(id__in=entry_ids)
                .select_related('created_by', 'posted_by')
                .prefetch_related('transactions__account')
                .order_by('date', 'id')
            )

            student_ar_account = getattr(student, 'ar_account', None)
            running_balance = Decimal('0.00')
            rows = []
            for entry in journal_entries:
                transactions = list(entry.transactions.select_related('account').all())
                transactions.sort(key=lambda tx: (not tx.is_debit, tx.id))
                for tx in transactions:
                    debit = tx.amount if tx.is_debit else Decimal('0.00')
                    credit = tx.amount if not tx.is_debit else Decimal('0.00')
                    if student_ar_account and tx.account_id == student_ar_account.id:
                        running_balance += debit - credit

                    rows.append({
                        'date': entry.date,
                        'ref': entry.reference or '-',
                        'desc': entry.description or tx.description or '-',
                        'account_code': tx.account.code,
                        'account_name': tx.account.name_ar or tx.account.name,
                        'tx_desc': tx.description or '-',
                        'debit': debit,
                        'credit': credit,
                        'balance': running_balance,
                        'created_by': (
                            entry.created_by.get_full_name()
                            or entry.created_by.username
                            if entry.created_by else '-'
                        ),
                        'entry_type': entry.get_entry_type_display(),
                    })

            total_remaining = max(Decimal('0.00'), total_due - total_paid)
            balance = student.balance

            context.update({
                'enrollment_data': enrollment_data,
                'active_enrollments': [row for row in enrollment_data if row['is_active']],
                'all_enrollments': enrollment_data,
                'total_paid': total_paid,
                'total_due': total_due,
                'total_remaining': total_remaining,
                'receipts': receipts,
                'has_active_enrollments': any(row['is_active'] for row in enrollment_data),
                'rows': rows,
                'per_course': per_course,
                'balance': balance,
                'entry_count': len(journal_entries),
            })
            
        except Exception as e:
            messages.error(self.request, f'ط­ط¯ط« ط®ط·ط£ ظپظٹ طھط­ظ…ظٹظ„ ط§ظ„ط¨ظٹط§ظ†ط§طھ: {str(e)}')
            context.update({
                'enrollment_data': [],
                'active_enrollments': [],
                'total_paid': Decimal('0.00'),
                'total_due': Decimal('0.00'),
                'total_remaining': Decimal('0.00'),
                'receipts': [],
                'has_active_enrollments': False,
                'rows': [],
                'per_course': [],
                'balance': Decimal('0.00'),
                'entry_count': 0,
            })
        
        return context

@require_POST
def update_quick_student_discount(request, student_id):
    """طھط­ط¯ظٹط« ط­ط³ظ… ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط³ط±ظٹط¹ ظˆطھط¹ط¯ظٹظ„ ط§ظ„ظ‚ظٹظˆط¯ ط§ظ„ظ…ط±طھط¨ط·ط©"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'ظٹط¬ط¨ طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„'})
    
    student = get_object_or_404(QuickStudent, id=student_id)
    
    try:
        from decimal import Decimal
        from django.db import transaction as db_transaction
        
        discount_percent = Decimal(request.POST.get('discount_percent', '0'))
        discount_amount = Decimal(request.POST.get('discount_amount', '0'))
        discount_reason = request.POST.get('discount_reason', '')
        
        # ط§ظ„طھط­ظ‚ظ‚ ظ…ظ† ظˆط¬ظˆط¯ طھط³ط¬ظٹظ„ط§طھ ظ†ط´ط·ط©
        active_enrollments = QuickEnrollment.objects.filter(
            student=student, 
            is_completed=False
        )
        
        if not active_enrollments.exists():
            return JsonResponse({
                'success': False,
                'error': 'ظ„ط§ طھظˆط¬ط¯ طھط³ط¬ظٹظ„ط§طھ ظ†ط´ط·ط© ظ„ظ„ط·ط§ظ„ط¨'
            })
        
        with db_transaction.atomic():
            # طھط­ط¯ظٹط« ط§ظ„طھط³ط¬ظٹظ„ط§طھ ط§ظ„ظ†ط´ط·ط© ط¨ط§ظ„ط®طµظ… ط§ظ„ط¬ط¯ظٹط¯
            updated_count = 0
            for enrollment in active_enrollments:
                enrollment.discount_percent = discount_percent
                enrollment.discount_amount = discount_amount
                enrollment.save()
                updated_count += 1
            
            # ط¥ط°ط§ طھط؛ظٹط± ط§ظ„ط®طµظ…طŒ ظ‚ظ… ط¨طھط­ط¯ظٹط« ط§ظ„ظ‚ظٹظˆط¯
            student.update_enrollment_discounts(request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'طھظ… طھط­ط¯ظٹط« ط§ظ„ط­ط³ظ… ظˆط§ظ„ظ‚ظٹظˆط¯ ط§ظ„ظ…ط­ط§ط³ط¨ظٹط© ظ„ظ€ {updated_count} طھط³ط¬ظٹظ„ ظ†ط´ط·'
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"ط­ط¯ط« ط®ط·ط£ ظپظٹ update_quick_student_discount: {str(e)}")
        
        return JsonResponse({
            'success': False,
            'error': f'ط­ط¯ط« ط®ط·ط£: {str(e)}'
        })

@require_POST
def quick_student_quick_receipt(request, student_id):
    """ط¥ظ†ط´ط§ط، ط¥ظٹطµط§ظ„ ظپظˆط±ظٹ ظ„ظ„ط·ط§ظ„ط¨ ط§ظ„ط³ط±ظٹط¹"""
    from decimal import Decimal
    from django.db.models import Sum
    from .models import QuickStudentReceipt
    
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'ظٹط¬ط¨ طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„'}, status=401)
    
    student = get_object_or_404(QuickStudent, id=student_id)
    try:
        # Parse inputs
        course_id = request.POST.get('course_id')
        enrollment_id = request.POST.get('enrollment_id')
        amount = Decimal(request.POST.get('amount', '0'))
        paid_amount = Decimal(request.POST.get('paid_amount', '0'))
        discount_percent = Decimal(request.POST.get('discount_percent', '0'))
        discount_amount = Decimal(request.POST.get('discount_amount', '0'))
        receipt_date_str = request.POST.get('receipt_date')
        
        # âœ… ط§ظ„طھطµط­ظٹط­: ط¥ط°ط§ ظƒط§ظ† amount طµط؛ظٹط±ط§ظ‹ (ط£ظ‚ظ„ ظ…ظ† 1000) ظ†ط¹طھط¨ط±ظ‡ ظٹط­طھط§ط¬ ط£طµظپط§ط±
        if amount < 1000 and amount > 0:
            # ظ†ط¶ط±ط¨ ظپظٹ 1000 ظ„ط¥ط¶ط§ظپط© ط§ظ„ط£طµظپط§ط± ط§ظ„ظ…ظپظ‚ظˆط¯ط©
            amount = amount * 1000
        
        # ظ…ط¹ط§ظ„ط¬ط© طھط§ط±ظٹط® ط§ظ„ط¥ظٹطµط§ظ„
        if receipt_date_str:
            receipt_date = parse_date(receipt_date_str)
            if not receipt_date:
                return JsonResponse({'ok': False, 'error': 'طµظٹط؛ط© ط§ظ„طھط§ط±ظٹط® ط؛ظٹط± طµط­ظٹط­ط©'}, status=400)
        else:
            receipt_date = timezone.now().date()
            
    except (ValueError, TypeError, InvalidOperation) as e:
        return JsonResponse({'ok': False, 'error': f'ط®ط·ط£ ظپظٹ طھظ†ط³ظٹظ‚ ط§ظ„ط£ط±ظ‚ط§ظ…: {str(e)}'}, status=400)
    
    course = None
    remaining_amount = Decimal('0.00')
    enrollment = None
    
    try:
        if enrollment_id:
            enrollment = QuickEnrollment.objects.get(pk=enrollment_id, student=student)
            
            if enrollment.is_completed:
                return JsonResponse({'ok': False, 'error': 'ظ„ط§ ظٹظ…ظƒظ† ظ‚ط·ط¹ ط¥ظٹطµط§ظ„ ظ„ط¯ظˆط±ط© ظ…ط³ط­ظˆط¨ط©'}, status=400)
                
            course = enrollment.course

            if course_id and str(course.id) != str(course_id):
                return JsonResponse({'ok': False, 'error': 'ط§ظ„ط¯ظˆط±ط© ط§ظ„ظ…ط­ط¯ط¯ط© ظ„ط§ طھط·ط§ط¨ظ‚ طھط³ط¬ظٹظ„ ط§ظ„ط·ط§ظ„ط¨'}, status=400)
            
            if amount == 0:
                amount = enrollment.net_amount or Decimal('0.00')
            
            # ط§ط­ط³ط¨ ط§ظ„ظ…طھط¨ظ‚ظٹ ظ…ظ† ظ†ظپط³ ط§ظ„طھط³ط¬ظٹظ„ ظپظ‚ط·
            total_paid = _get_quick_enrollment_paid_total(enrollment, student)
            
            net_amount = enrollment.net_amount or Decimal('0.00')
            remaining_amount = max(Decimal('0.00'), net_amount - total_paid)
            
        elif course_id:
            course = QuickCourse.objects.get(pk=course_id)
            
            if amount == 0:
                amount = course.price or Decimal('0.00')
                
            # ط§ظ„ط¨ط­ط« ط¹ظ† enrollment ظ„ظ‡ط°ظ‡ ط§ظ„ط¯ظˆط±ط©
            enrollment = QuickEnrollment.objects.filter(
                student=student, 
                course=course,
                is_completed=False
            ).first()
            
            if enrollment:
                total_paid = _get_quick_enrollment_paid_total(enrollment, student)
                net_amount = enrollment.net_amount or Decimal('0.00')
                remaining_amount = max(Decimal('0.00'), net_amount - total_paid)
            else:
                remaining_amount = course.price or Decimal('0.00')
                
    except (QuickEnrollment.DoesNotExist, QuickCourse.DoesNotExist) as e:
        return JsonResponse({'ok': False, 'error': 'ط§ظ„ط¯ظˆط±ط© ط£ظˆ ط§ظ„طھط³ط¬ظٹظ„ ط؛ظٹط± ظ…ظˆط¬ظˆط¯'}, status=404)
    
    if paid_amount < 0:
        return JsonResponse({'ok': False, 'error': 'ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ظ…ط¯ظپظˆط¹ ط؛ظٹط± طµط§ظ„ط­'}, status=400)
    
    if paid_amount > remaining_amount:
        return JsonResponse({'ok': False, 'error': f'ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ظ…ط¯ظپظˆط¹ ({paid_amount}) ظٹطھط¬ط§ظˆط² ط§ظ„ظ…ط¨ظ„ط؛ ط§ظ„ظ…طھط¨ظ‚ظٹ ({remaining_amount})'}, status=400)
    
    # Create receipt - ط§ط³طھط®ط¯ط§ظ… QuickStudentReceipt ط§ظ„ط¬ط¯ظٹط¯
    try:
        receipt = QuickStudentReceipt.objects.create(
            date=receipt_date,
            quick_student=student,
            student_name=student.full_name,
            course=course,
            course_name=(course.name if course else ''),
            quick_enrollment=enrollment,
            amount=amount,
            paid_amount=paid_amount,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            payment_method='CASH',
            created_by=request.user,
        )
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'ظپط´ظ„ ظپظٹ ط¥ظ†ط´ط§ط، ط§ظ„ط¥ظٹطµط§ظ„: {str(e)}'}, status=500)
    
    journal_warning = None
    try:
        # ط¥ظ†ط´ط§ط، ط§ظ„ظ‚ظٹط¯ ط§ظ„ظ…ط­ط§ط³ط¨ظٹ
        receipt.create_accrual_journal_entry(request.user)
    except Exception as e:
        journal_warning = f"ط®ط·ط£ ظپظٹ ط§ظ„ظ‚ظٹط¯ ط§ظ„ظ…ط­ط§ط³ط¨ظٹ: {e}"
    
    new_remaining_amount = max(Decimal('0.00'), remaining_amount - paid_amount)
    
    from django.urls import reverse
    print_url = reverse('quick:quick_student_receipt_print', args=[receipt.id])
    return JsonResponse({
        'ok': True, 
        'receipt_id': receipt.id, 
        'print_url': print_url,
        'remaining_amount': float(new_remaining_amount),
        'warning': journal_warning
    })

@require_POST
def withdraw_quick_student(request, student_id):
    """ط³ط­ط¨ ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط³ط±ظٹط¹ ظ…ظ† ط§ظ„ط¯ظˆط±ط©"""
    student = get_object_or_404(QuickStudent, pk=student_id)
    
    if request.method == 'POST':
        enrollment_id = request.POST.get('enrollment_id')
        withdrawal_reason = request.POST.get('withdrawal_reason', '')
        refund_amount_raw = request.POST.get('refund_amount', '0')

        if not enrollment_id:
            messages.error(request, 'ظ„ظ… ظٹطھظ… طھط­ط¯ظٹط¯ طھط³ط¬ظٹظ„ ط§ظ„ط¯ظˆط±ط©')
            return redirect('quick:student_profile', student_id=student.id)

        try:
            enrollment = get_object_or_404(QuickEnrollment, pk=enrollment_id, student=student)

            if enrollment.is_completed:
                messages.error(request, 'ظ‡ط°ظ‡ ط§ظ„ط¯ظˆط±ط© ظ…ط³ط­ظˆط¨ط© ظ…ط³ط¨ظ‚ط§ظ‹')
                return redirect('quick:student_profile', student_id=student.id)

            paid_total = QuickStudentReceipt.objects.filter(
                quick_student=student,
                quick_enrollment=enrollment,
                course=enrollment.course
            ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')

            try:
                refund_amount = Decimal(refund_amount_raw or '0')
            except InvalidOperation:
                refund_amount = Decimal('0')

            if refund_amount <= 0 and paid_total > 0:
                refund_amount = paid_total

            refund_result = _adjust_quick_receipts_for_refund(student, enrollment, refund_amount)
            actual_refund = refund_result['refunded_amount']
            refund_note = f' ظˆط§ط³طھط±ط¯ {actual_refund:,.0f} ظ„.ط³' if actual_refund > 0 else ''

            if getattr(enrollment, 'enrollment_journal_entry_id', None):
                try:
                    enrollment.enrollment_journal_entry.reverse_entry(
                        request.user,
                        description=f"ط¥ظ„ط؛ط§ط، طھط³ط¬ظٹظ„ ط³ط±ظٹط¹ - {withdrawal_reason}" if withdrawal_reason else "ط¥ظ„ط؛ط§ط، طھط³ط¬ظٹظ„ ط³ط±ظٹط¹"
                    )
                except Exception:
                    pass

            description = f"سحب طالب سريع {student.full_name} من {enrollment.course.name}"
            if withdrawal_reason:
                description = f"{description} - {withdrawal_reason}"
            _build_quick_withdrawal_entry(
                enrollment=enrollment,
                user=request.user,
                refunded_amount=actual_refund,
                description=description,
            )

            enrollment.is_completed = True
            enrollment.completion_date = timezone.now().date()
            enrollment.save(update_fields=['is_completed', 'completion_date'])

            messages.success(request, f'طھظ… ط³ط­ط¨ ط§ظ„ط·ط§ظ„ط¨ ظ…ظ† ط¯ظˆط±ط© {enrollment.course.name}{refund_note} ط¨ظ†ط¬ط§ط­')
            return redirect('quick:student_profile', student_id=student.id)

        except Exception as e:
            print(f"ERROR in withdraw_quick_student: {str(e)}")
            messages.error(request, f'ط­ط¯ط« ط®ط·ط£ ط£ط«ظ†ط§ط، ط§ظ„ط³ط­ط¨: {str(e)}')
            return redirect('quick:student_profile', student_id=student.id)

@require_POST
def refund_quick_student(request, student_id):
    """ط§ط³طھط±ط¯ط§ط¯ ظ…ط¨ظ„ط؛ ظ„ظ„ط·ط§ظ„ط¨ ط§ظ„ط³ط±ظٹط¹"""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'ظٹط¬ط¨ طھط³ط¬ظٹظ„ ط§ظ„ط¯ط®ظˆظ„'}, status=401)
    
    student = get_object_or_404(QuickStudent, pk=student_id)
    
    try:
        enrollment_id = request.POST.get('enrollment_id')
        refund_amount = Decimal(request.POST.get('refund_amount', '0'))
        refund_reason = request.POST.get('refund_reason', '')
        
        if not enrollment_id:
            return JsonResponse({'ok': False, 'error': 'ظ„ظ… ظٹطھظ… طھط­ط¯ظٹط¯ ط§ظ„طھط³ط¬ظٹظ„'}, status=400)
        
        enrollment = get_object_or_404(QuickEnrollment, pk=enrollment_id, student=student)
        
        if enrollment.is_completed:
            return JsonResponse({'ok': False, 'error': 'ظ„ط§ ظٹظ…ظƒظ† ط§ط³طھط±ط¯ط§ط¯ ظ…ط¨ظ„ط؛ ظ„ط¯ظˆط±ط© ظ…ط³ط­ظˆط¨ط©'}, status=400)
        
        try:
            result = _process_quick_refund(
                student,
                enrollment,
                refund_amount,
                refund_reason,
                request.user
            )
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        except Exception as exc:
            import traceback
            print(f"ط®ط·ط£ ظپظٹ ط§ظ„ط§ط³طھط±ط¯ط§ط¯: {str(exc)}")
            print(traceback.format_exc())
            return JsonResponse({'ok': False, 'error': f'ط®ط·ط£ ظپظٹ ط§ظ„ط§ط³طھط±ط¯ط§ط¯: {str(exc)}'}, status=500)

        return JsonResponse({
            'ok': True,
            'message': f'طھظ… ط§ط³طھط±ط¯ط§ط¯ {result["refund_amount"]:,.0f} ظ„.ط³ ط¨ظ†ط¬ط§ط­',
            'new_balance': float(result['new_balance']),
            'previous_balance': float(result['previous_balance']),
            'new_paid': float(result['new_total_paid']),
            'previous_paid': float(result['previous_paid'])
        })

    except Exception as e:
        import traceback
        print(f"ط®ط·ط£ ظپظٹ ط§ظ„ط§ط³طھط±ط¯ط§ط¯: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'ok': False, 'error': f'ط­ط¯ط« ط®ط·ط£ ظپظٹ ط§ظ„ط§ط³طھط±ط¯ط§ط¯: {str(e)}'}, status=500)
# ط§ظ„طھظ‚ط§ط±ظٹط±
class QuickOutstandingCoursesView(LoginRequiredMixin, ListView):
    template_name = 'quick/outstanding_course_list.html'
    context_object_name = 'courses'
    
    def get_queryset(self):
        course_type, course_type_label, report_label = _get_outstanding_course_type(self.request)
        self._course_type = course_type
        self._course_type_label = course_type_label
        self._course_type_report_label = report_label
        courses = QuickCourse.objects.filter(is_active=True).select_related('academic_year').order_by('name')
        if course_type != 'ALL':
            courses = courses.filter(course_type=course_type)
        course_data, totals = _build_quick_outstanding_course_summary(courses, include_zero_outstanding=True)
        self._totals = totals
        return course_data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        totals = getattr(self, '_totals', {})
        context.update({
            'total_courses': totals.get('total_courses', 0),
            'total_outstanding_students': totals.get('total_outstanding_students', 0),
            'total_outstanding_amount': totals.get('total_outstanding_amount', Decimal('0')),
            'total_paid_amount': totals.get('total_paid_amount', Decimal('0')),
            'course_type': getattr(self, '_course_type', 'INTENSIVE'),
            'course_type_label': getattr(self, '_course_type_label', 'ظ…ظƒط«ظپط©'),
            'course_type_report_label': getattr(self, '_course_type_report_label', 'ط§ظ„ظ…ظƒط«ظپط§طھ'),
            'course_type_options': _get_course_type_options(),
        })
        total_courses = totals.get('total_courses', 0) or 0
        total_paid_amount = totals.get('total_paid_amount', Decimal('0'))
        context['average_paid_per_course'] = (
            (total_paid_amount / total_courses) if total_courses else Decimal('0')
        )
        return context


class QuickOutstandingCourseDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/outstanding_course_detail.html'

    def get_context_data(self, course_id=None, **kwargs):
        context = super().get_context_data(**kwargs)
        course_type, course_type_label, report_label = _get_outstanding_course_type(self.request)
        course = get_object_or_404(QuickCourse, pk=course_id)

        enrollments = QuickEnrollment.objects.filter(
            course=course,
            is_completed=False
        ).select_related('student')

        rows = []
        total_outstanding = Decimal('0.00')

        for enrollment in enrollments:
            net_amount = enrollment.net_amount or Decimal('0.00')
            total_paid = QuickStudentReceipt.objects.filter(
                quick_enrollment=enrollment
            ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')

            remaining = max(Decimal('0.00'), net_amount - total_paid)

            if remaining <= Decimal('0.00'):
                continue

            rows.append({
                'student_id': enrollment.student.id,
                'student_name': enrollment.student.full_name,
                'phone': enrollment.student.phone,
                'net_amount': net_amount,
                'paid_amount': total_paid,
                'remaining': remaining,
            })

            total_outstanding += remaining

        rows.sort(key=lambda r: r['remaining'], reverse=True)

        context.update({
            'course': course,
            'rows': rows,
            'total_students': len(rows),
            'total_outstanding': total_outstanding,
            'total_net_amount': sum(r['net_amount'] for r in rows),
            'total_paid_amount': sum(r['paid_amount'] for r in rows),
            'course_type': course_type,
            'course_type_label': course_type_label,
            'course_type_report_label': report_label,
        })
        return context


class QuickCourseStudentsView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/outstanding_course_students.html'

    def get_context_data(self, course_id=None, **kwargs):
        context = super().get_context_data(**kwargs)
        course_type, course_type_label, report_label = _get_outstanding_course_type(self.request)
        course = get_object_or_404(QuickCourse, pk=course_id)

        enrolled_students = self.get_students_from_enrollments(course)
        male_count = 0
        female_count = 0
        unknown_count = 0
        for item in enrolled_students:
            quick_student = item.get('student')
            gender = getattr(getattr(quick_student, 'student', None), 'gender', None)
            if gender == 'male':
                male_count += 1
            elif gender == 'female':
                female_count += 1
            else:
                unknown_count += 1

        if not enrolled_students:
            context.update({
                'course': course,
                'student_data': [],
                'total_students': 0,
                'fully_paid_count': 0,
                'outstanding_count': 0,
                'current_filter': 'all',
                'total_net_due': 0,
                'total_paid': 0,
                'total_remaining': 0,
                'all_students_count': 0,
                'students_without_receipts': 0,
                'male_count': 0,
                'female_count': 0,
                'unknown_count': 0,
                'course_type': course_type,
                'course_type_label': course_type_label,
                'course_type_report_label': report_label,
            })
            return context

        student_data, statistics = self.calculate_student_data(course, enrolled_students)
        filter_type = self.request.GET.get('filter', 'all')
        filtered_students, filtered_statistics = self.apply_filter(student_data, filter_type)

        context.update({
            'course': course,
            'student_data': filtered_students,
            'total_students': len(filtered_students),
            'fully_paid_count': statistics['fully_paid_count'],
            'outstanding_count': statistics['outstanding_count'],
            'current_filter': filter_type,
            'total_net_due': filtered_statistics['total_net_due'],
            'total_paid': filtered_statistics['total_paid'],
            'total_remaining': filtered_statistics['total_remaining'],
            'all_students_count': statistics['all_students_count'],
            'students_without_receipts': statistics['students_without_receipts'],
            'male_count': male_count,
            'female_count': female_count,
            'unknown_count': unknown_count,
            'course_type': course_type,
            'course_type_label': course_type_label,
            'course_type_report_label': report_label,
        })
        return context

    def get_students_from_enrollments(self, course):
        enrollments = QuickEnrollment.objects.filter(
            course=course,
            is_completed=False
        ).select_related('student')

        return [
            {'student': enrollment.student, 'enrollment': enrollment}
            for enrollment in enrollments
            if enrollment.student
        ]

    def calculate_student_data(self, course, students_with_enrollments):
        student_data = []
        statistics = {
            'total_net_due': Decimal('0'),
            'total_paid': Decimal('0'),
            'total_remaining': Decimal('0'),
            'students_without_receipts': 0,
            'fully_paid_count': 0,
            'outstanding_count': 0,
            'all_students_count': len(students_with_enrollments)
        }

        for item in students_with_enrollments:
            info = self.calculate_student_financial_info(item['student'], item['enrollment'])
            if not info:
                continue

            student_data.append(info)
            statistics['total_net_due'] += info['net_due']
            statistics['total_paid'] += info['paid_total']
            statistics['total_remaining'] += info['remaining']

            if not info['has_receipts']:
                statistics['students_without_receipts'] += 1

            if info['is_fully_paid']:
                statistics['fully_paid_count'] += 1
            else:
                statistics['outstanding_count'] += 1

        return student_data, statistics

    def calculate_student_financial_info(self, student, enrollment):
        try:
            course_price = enrollment.course.price or Decimal('0')
            net_due = enrollment.net_amount or Decimal('0')
            paid_total = self.calculate_paid_amount(enrollment)
            remaining = max(Decimal('0'), net_due - paid_total)
            discount_percent = enrollment.discount_percent or Decimal('0')
            is_fully_paid = (
                discount_percent >= Decimal('100')
                or net_due <= Decimal('0')
                or remaining <= Decimal('0')
            )
            has_receipts = paid_total > Decimal('0')
            is_free = net_due <= Decimal('0') or discount_percent >= Decimal('100')

            return {
                'student': student,
                'enrollment': enrollment,
                'course_price': course_price,
                'net_due': net_due,
                'paid_total': paid_total,
                'remaining': remaining,
                'is_fully_paid': is_fully_paid,
                'has_receipts': has_receipts,
                'is_free': is_free,
            }
        except Exception:
            return None

    def calculate_paid_amount(self, enrollment):
        total_paid = QuickStudentReceipt.objects.filter(
            quick_enrollment=enrollment
        ).aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
        return total_paid

    def apply_filter(self, student_data, filter_type):
        if filter_type == 'paid':
            filtered = [s for s in student_data if s['is_fully_paid']]
        elif filter_type == 'outstanding':
            filtered = [s for s in student_data if not s['is_fully_paid']]
        else:
            filtered = student_data

        filtered.sort(key=lambda x: (
            not x['is_fully_paid'],
            -x['remaining']
        ))

        filtered_statistics = {
            'total_net_due': sum(s['net_due'] for s in filtered),
            'total_paid': sum(s['paid_total'] for s in filtered),
            'total_remaining': sum(s['remaining'] for s in filtered)
        }

        return filtered, filtered_statistics


@login_required
def register_quick_course(request, student_id):
    """طھط³ط¬ظٹظ„ ط·ط§ظ„ط¨ ط³ط±ظٹط¹ ظپظٹ ط¯ظˆط±ط©"""
    student = get_object_or_404(QuickStudent, id=student_id)
    courses = QuickCourse.objects.filter(is_active=True, academic_year=student.academic_year)
    
    if request.method == 'POST':
        course_ids = request.POST.getlist('course_ids')
        if not course_ids:
            messages.error(request, 'ظٹط±ط¬ظ‰ ط§ط®طھظٹط§ط± ط¯ظˆط±ط© ظˆط§ط­ط¯ط© ط¹ظ„ظ‰ ط§ظ„ط£ظ‚ظ„')
            return redirect('quick:register_quick_course', student_id=student_id)

        seen = []
        for cid in course_ids:
            if cid and cid not in seen:
                seen.append(cid)

        available_courses = QuickCourse.objects.filter(
            id__in=seen,
            is_active=True,
            academic_year=student.academic_year
        )
        available_map = {str(course.id): course for course in available_courses}

        created_enrollments = 0
        created_receipts = []
        warnings = []

        for cid in seen:
            course = available_map.get(cid)
            if not course:
                continue

            existing = QuickEnrollment.objects.filter(student=student, course=course).exists()
            if existing:
                warnings.append(f'ط§ظ„طھط³ط¬ظٹظ„ ظ„ظ„ط¯ظˆط±ط© "{course.name}" ظ…ظˆط¬ظˆط¯ ظ…ط³ط¨ظ‚ط§ظ‹طŒ طھظ… طھط¬ط§ظ‡ظ„ظ‡ط§.')
                continue

            enrollment = QuickEnrollment.objects.create(
                student=student,
                course=course,
                enrollment_date=timezone.now().date(),
                net_amount=course.price,
                total_amount=course.price
            )
            created_enrollments += 1
            assignment = _assign_enrollment_to_available_session(enrollment, request.user)
            if assignment is None:
                warnings.append(f'الطالب سُجل في دورة {course.name} لكن لا يوجد كلاس متاح فيه شاغر حالياً.')

            try:
                enrollment.create_accrual_enrollment_entry(request.user)
            except Exception as exc:
                warnings.append(f'ط§ظ„ظ‚ظٹط¯ ط§ظ„ظ…ط­ط§ط³ط¨ظٹ ظ„ط¯ظˆط±ط© {course.name} ظ„ظ… ظٹظڈظ†ط¬ط²: {exc}')

            pay_full = request.POST.get(f'pay_full_{course.id}')
            if pay_full:
                try:
                    receipt = QuickStudentReceipt.objects.create(
                        date=timezone.now().date(),
                        quick_student=student,
                        student_name=student.full_name,
                        course=course,
                        course_name=course.name,
                        quick_enrollment=enrollment,
                        amount=enrollment.net_amount,
                        paid_amount=enrollment.net_amount,
                        payment_method='CASH',
                        created_by=request.user
                    )
                    receipt.create_accrual_journal_entry(request.user)
                    created_receipts.append(receipt.id)
                except Exception as exc:
                    warnings.append(f'ط¥ظ†ط´ط§ط، ط¥ظٹطµط§ظ„ ظ„ط¯ظˆط±ط© {course.name} ظپط´ظ„: {exc}')

        if created_enrollments:
            messages.success(request, f'طھظ… طھط³ط¬ظٹظ„ ط§ظ„ط·ط§ظ„ط¨ ظپظٹ {created_enrollments} ط¯ظˆط±ط©')
        if warnings:
            for warning in warnings:
                messages.warning(request, warning)

        if created_receipts:
            ids_str = ','.join(str(rid) for rid in created_receipts)
            query = urlencode({
                'print_receipts': ids_str
            })
            return redirect(f"{reverse('quick:student_profile', args=[student_id])}?{query}")

        return redirect('quick:student_profile', student_id=student_id)

    return render(request, 'quick/register_quick_course.html', {
        'student': student,
        'courses': courses,
        'print_receipts_url': None
    })
@login_required
def quick_multiple_receipt_print(request, student_id):
    """ط·ط¨ط§ط¹ط© ظ…ط¬ظ…ظˆط¹ط© ط¥ظٹطµط§ظ„ط§طھ ط¯ظپط¹ط© ظˆط§ط­ط¯ط©"""
    ids_param = request.GET.get('ids', '')
    if not ids_param:
        raise Http404('Missing receipt identifiers')

    try:
        receipt_ids = [int(pk.strip()) for pk in ids_param.split(',') if pk.strip()]
    except ValueError:
        raise Http404('Invalid receipt identifiers')

    receipts = QuickStudentReceipt.objects.filter(
        id__in=receipt_ids,
        quick_student_id=student_id
    ).order_by('id')

    if not receipts.exists():
        raise Http404('No receipts found')

    receipt_items = []
    for receipt in receipts:
        course_price = (receipt.amount + receipt.discount_amount) if receipt.discount_amount else receipt.amount
        net_due = receipt.amount
        remaining = max(Decimal('0.00'), course_price - (receipt.paid_amount or Decimal('0.00')))
        receipt_items.append({
            'receipt': receipt,
            'course_price': course_price,
            'discount_percent': receipt.discount_percent,
            'net_due': net_due,
            'remaining': remaining,
            'receipt_date': receipt.date,
        })

    student = QuickStudent.objects.filter(id=student_id).first()
    return render(request, 'quick/quick_multiple_receipt_print.html', {
        'receipts': receipt_items,
        'student': student,
        'return_url': reverse('quick:student_profile', args=[student_id]),
        'local_agent_url': settings.QUICK_LOCAL_AGENT_URL,
        'server_printer_enabled': (
            settings.QUICK_RECEIPT_PRINTER_ENABLED or settings.QUICK_RECEIPT_PRINTER_DUMMY
        ),
    })


def _build_quick_receipt_payload(receipts, student_id):
    items = []
    for receipt in receipts:
        course_name = receipt.course.name if receipt.course else (receipt.course_name or '-')
        student_name = receipt.quick_student.full_name if receipt.quick_student else (receipt.student_name or '-')
        net_due = receipt.quick_enrollment.net_amount if receipt.quick_enrollment else (receipt.amount or Decimal('0'))
        paid_amount = receipt.paid_amount or Decimal('0')
        remaining = max(Decimal('0'), net_due - paid_amount)
        items.append({
            'id': receipt.id,
            'number': receipt.receipt_number or str(receipt.id),
            'date': receipt.date.strftime('%Y-%m-%d') if receipt.date else '',
            'student': student_name,
            'course': course_name,
            'net_due': str(net_due),
            'paid_amount': str(paid_amount),
            'remaining': str(remaining),
            'discount_percent': str(receipt.discount_percent or Decimal('0')),
            'payment_method': receipt.get_payment_method_display(),
            'notes': receipt.notes or '',
        })

    return {
        'student_id': student_id,
        'count': len(items),
        'title': settings.QUICK_RECEIPT_PRINTER_TITLE,
        'receipts': items,
    }


def _validate_print_agent(request):
    configured = settings.QUICK_PRINT_AGENT_TOKEN
    provided = request.headers.get('X-Printer-Token', '').strip()
    return bool(configured) and provided == configured


@login_required
@require_POST
def quick_multiple_receipt_payload(request, student_id):
    ids_param = request.POST.get('ids', '')
    if not ids_param:
        return JsonResponse({'ok': False, 'error': 'لم يتم تحديد الإيصالات'}, status=400)

    try:
        receipt_ids = [int(pk.strip()) for pk in ids_param.split(',') if pk.strip()]
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'معرّفات الإيصالات غير صحيحة'}, status=400)

    receipts = list(
        QuickStudentReceipt.objects.filter(
            id__in=receipt_ids,
            quick_student_id=student_id
        ).select_related('quick_student', 'course', 'quick_enrollment').order_by('id')
    )
    if not receipts:
        return JsonResponse({'ok': False, 'error': 'لا توجد إيصالات للطباعة'}, status=404)

    return JsonResponse({
        'ok': True,
        'payload': _build_quick_receipt_payload(receipts, student_id),
    })


@login_required
@require_POST
def quick_multiple_receipt_enqueue_print(request, student_id):
    ids_param = request.POST.get('ids', '')
    if not ids_param:
        return JsonResponse({'ok': False, 'error': 'لم يتم تحديد الإيصالات'}, status=400)

    try:
        receipt_ids = [int(pk.strip()) for pk in ids_param.split(',') if pk.strip()]
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'معرّفات الإيصالات غير صحيحة'}, status=400)

    student = get_object_or_404(QuickStudent, id=student_id)
    receipts = list(
        QuickStudentReceipt.objects.filter(
            id__in=receipt_ids,
            quick_student_id=student_id
        ).select_related('quick_student', 'course', 'quick_enrollment').order_by('id')
    )
    if not receipts:
        return JsonResponse({'ok': False, 'error': 'لا توجد إيصالات للطباعة'}, status=404)

    job = QuickReceiptPrintJob.objects.create(
        created_by=request.user,
        quick_student=student,
        payload=_build_quick_receipt_payload(receipts, student_id),
        status=QuickReceiptPrintJob.STATUS_PENDING,
    )
    return JsonResponse({
        'ok': True,
        'job_id': job.id,
        'message': f'تم إنشاء مهمة الطباعة رقم {job.id}. سيقوم لابتوب الطباعة بسحبها تلقائياً.',
    })


@csrf_exempt
@require_GET
def quick_print_agent_next_job(request):
    if not _validate_print_agent(request):
        return JsonResponse({'ok': False, 'error': 'Unauthorized printer agent'}, status=403)

    with transaction.atomic():
        job = (
            QuickReceiptPrintJob.objects
            .select_for_update(skip_locked=True)
            .filter(status=QuickReceiptPrintJob.STATUS_PENDING)
            .order_by('created_at')
            .first()
        )
        if not job:
            return JsonResponse({'ok': True, 'job': None})

        job.status = QuickReceiptPrintJob.STATUS_PROCESSING
        job.picked_at = timezone.now()
        job.error_message = ''
        job.save(update_fields=['status', 'picked_at', 'error_message', 'updated_at'])

    return JsonResponse({
        'ok': True,
        'job': {
            'id': job.id,
            'payload': job.payload,
        }
    })


@csrf_exempt
@require_POST
def quick_print_agent_job_update(request, job_id):
    if not _validate_print_agent(request):
        return JsonResponse({'ok': False, 'error': 'Unauthorized printer agent'}, status=403)

    job = get_object_or_404(QuickReceiptPrintJob, id=job_id)
    status = request.POST.get('status', '').strip().lower()
    error_message = request.POST.get('error_message', '').strip()

    if status not in {QuickReceiptPrintJob.STATUS_COMPLETED, QuickReceiptPrintJob.STATUS_FAILED}:
        return JsonResponse({'ok': False, 'error': 'Invalid status'}, status=400)

    job.status = status
    job.error_message = error_message
    job.completed_at = timezone.now()
    job.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def quick_multiple_receipt_server_print(request, student_id):
    ids_param = request.POST.get('ids', '')
    if not ids_param:
        return JsonResponse({'ok': False, 'error': 'ظ„ظ… ظٹطھظ… طھط­ط¯ظٹط¯ ط§ظ„ط¥ظٹطµط§ظ„ط§طھ'}, status=400)

    try:
        receipt_ids = [int(pk.strip()) for pk in ids_param.split(',') if pk.strip()]
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'ظ…ط¹ط±ظ‘ظپط§طھ ط§ظ„ط¥ظٹطµط§ظ„ط§طھ ط؛ظٹط± طµط­ظٹط­ط©'}, status=400)

    receipts = list(
        QuickStudentReceipt.objects.filter(
            id__in=receipt_ids,
            quick_student_id=student_id
        ).select_related('quick_student', 'course', 'quick_enrollment').order_by('id')
    )
    if not receipts:
        return JsonResponse({'ok': False, 'error': 'ظ„ط§ طھظˆط¬ط¯ ط¥ظٹطµط§ظ„ط§طھ ظ„ظ„ط·ط¨ط§ط¹ط©'}, status=404)

    try:
        dummy_output = print_many_receipts(receipts)
    except QuickReceiptPrinterError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    response = {
        'ok': True,
        'printed_count': len(receipts),
        'message': f'طھظ… ط¥ط±ط³ط§ظ„ {len(receipts)} ط¥ظٹطµط§ظ„ ط¥ظ„ظ‰ ط·ط§ط¨ط¹ط© ط§ظ„ط³ظٹط±ظپط±',
    }
    if settings.QUICK_RECEIPT_PRINTER_DUMMY and dummy_output:
        response['dummy_preview'] = dummy_output.decode('utf-8', errors='ignore')[:4000]
    return JsonResponse(response)

def quick_student_receipt_print(request, receipt_id):
    """ط·ط¨ط§ط¹ط© ط¥ظٹطµط§ظ„ ط§ظ„ط·ط§ظ„ط¨ ط§ظ„ط³ط±ظٹط¹"""
    receipt = get_object_or_404(
        QuickStudentReceipt.objects.select_related('quick_student', 'course', 'quick_enrollment'),
        id=receipt_id
    )

    enrollment = receipt.quick_enrollment
    if enrollment:
        net_due = enrollment.net_amount or receipt.amount or Decimal('0.00')
        total_paid = _get_quick_enrollment_paid_total(enrollment, receipt.quick_student)
        remaining = max(Decimal('0.00'), net_due - total_paid)
    else:
        net_due = receipt.amount or Decimal('0.00')
        remaining = max(Decimal('0.00'), net_due - (receipt.paid_amount or Decimal('0.00')))

    course_price = (
        (net_due + (receipt.discount_amount or Decimal('0.00')))
        if receipt.discount_amount else net_due
    )
    context = {
        'receipt': receipt,
        'remaining': remaining,
        'course_price': course_price,
        'discount_percent': receipt.discount_percent,
        'net_due': net_due,
        'receipt_date': receipt.date,
    }
    
    return render(request, 'quick/quick_student_receipt_print.html', context)


# ظپظٹ quick/views.py - ط£ط¶ظپ ظ‡ط°ظ‡ ط§ظ„ط¯ط§ظ„ط© ظپظٹ ط§ظ„ظ†ظ‡ط§ظٹط©

@login_required
def auto_assign_academic_years(request):
    """ط±ط¨ط· ط¬ظ…ظٹط¹ ط§ظ„ط·ظ„ط§ط¨ ط¨ظپطµظˆظ„ظ‡ظ… ط§ظ„ط¯ط±ط§ط³ظٹط© طھظ„ظ‚ط§ط¦ظٹط§ظ‹"""
    from students.models import Student
    from quick.models import QuickStudent, AcademicYear
    
    # ط±ط¨ط· ط§ظ„ط·ظ„ط§ط¨ ط§ظ„ط³ط±ظٹط¹ظٹظ†
    quick_students = QuickStudent.objects.filter(academic_year__isnull=True)
    updated_count = 0
    
    for student in quick_students:
        academic_year = AcademicYear.objects.filter(
            start_date__lte=student.created_at.date(),
            end_date__gte=student.created_at.date(),
            is_active=True
        ).first()
        
        if academic_year:
            student.academic_year = academic_year
            student.save()
            updated_count += 1
    
    messages.success(request, f'طھظ… ط±ط¨ط· {updated_count} ط·ط§ظ„ط¨ ط³ط±ظٹط¹ طھظ„ظ‚ط§ط¦ظٹط§ظ‹ ط¨ط§ظ„ظپطµظˆظ„ ط§ظ„ط¯ط±ط§ط³ظٹط©')
    return redirect('quick:student_list')


# ظپظٹ ظ…ظ„ظپ views.py - طھط­ط¯ظٹط« ط¯ط§ظ„ط© ط§ظ„طھط¹ط¯ظٹظ„

class QuickStudentUpdateView(LoginRequiredMixin, UpdateView):
    model = QuickStudent
    form_class = QuickStudentForm
    template_name = 'quick/quick_student_update.html'
    context_object_name = 'student'
    
    def get_success_url(self):
        # âœ… ط§ظ„طھظˆط¬ظٹظ‡ ط¥ظ„ظ‰ ط¨ط±ظˆظپط§ظٹظ„ ط§ظ„ط·ط§ظ„ط¨ ط¨ط¯ظ„ط§ظ‹ ظ…ظ† ط§ظ„طھظپط§طµظٹظ„ ط§ظ„ط¨ط³ظٹط·ط©
        return reverse_lazy('quick:student_profile', kwargs={'student_id': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'طھظ… طھط­ط¯ظٹط« ط¨ظٹط§ظ†ط§طھ ط§ظ„ط·ط§ظ„ط¨ ط¨ظ†ط¬ط§ط­')
        return super().form_valid(form)




        # ط£ط¶ظپ ظ‡ط°ظ‡ ط§ظ„ظƒظ„ط§ط³ ظپظٹ ظ‚ط³ظ… "ط§ظ„ط¯ظˆط±ط§طھ ط§ظ„ط³ط±ظٹط¹ط©" ط¨ط¹ط¯ QuickCourseCreateView

class QuickCourseUpdateView(LoginRequiredMixin, UpdateView):
    model = QuickCourse
    form_class = QuickCourseForm
    template_name = 'quick/quick_course_form.html'  # ظ†ظپط³ ظ‚ط§ظ„ط¨ ط§ظ„ط¥ظ†ط´ط§ط،
    context_object_name = 'course'
    
    def get_success_url(self):
        return reverse('quick:course_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True  # ظ„ظ„طھظ…ظٹظٹط² ط¨ظٹظ† ط§ظ„طھط¹ط¯ظٹظ„ ظˆط§ظ„ط¥ط¶ط§ظپط©
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'طھظ… طھط­ط¯ظٹط« ط¨ظٹط§ظ†ط§طھ ط§ظ„ط¯ظˆط±ط© ط¨ظ†ط¬ط§ط­')
        return super().form_valid(form)

@require_POST

@require_POST
def withdraw_quick_student(request, student_id):
    """Withdraw quick student from course."""
    student = get_object_or_404(QuickStudent, pk=student_id)
    enrollment_id_raw = request.POST.get('enrollment_id')
    withdrawal_reason = request.POST.get('withdrawal_reason', '')
    refund_amount_raw = request.POST.get('refund_amount', '0')
    wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    enrollment_id = ''.join(ch for ch in str(enrollment_id_raw or '') if ch.isdigit())

    if not enrollment_id:
        error_message = 'لم يتم تحديد تسجيل الدورة'
        if wants_json:
            return JsonResponse({'success': False, 'error': error_message}, status=400)
        messages.error(request, error_message)
        return redirect('quick:student_profile', student_id=student.id)

    try:
        enrollment = get_object_or_404(QuickEnrollment, pk=enrollment_id, student=student)
        try:
            refund_amount = Decimal(refund_amount_raw or '0')
        except InvalidOperation:
            refund_amount = Decimal('0')

        result = _withdraw_quick_enrollment(
            enrollment=enrollment,
            user=request.user,
            withdrawal_reason=withdrawal_reason,
            refund_amount=refund_amount,
        )
        actual_refund = result['actual_refund']
        if wants_json:
            return JsonResponse({
                'success': True,
                'student_name': result['student_name'],
                'course_name': result['course_name'],
                'actual_refund': f'{actual_refund:,.0f}',
                'created_entry_ids': result.get('created_entry_ids', []),
            })
        refund_note = f' and refunded {actual_refund:,.0f} SYP' if actual_refund > 0 else ''
        messages.success(request, f'Student withdrawn from course {enrollment.course.name}{refund_note} successfully')
    except Exception as exc:
        print(f"ERROR in withdraw_quick_student override: {exc}")
        if wants_json:
            return JsonResponse({'success': False, 'error': str(exc)}, status=400)
        messages.error(request, f'Withdrawal error: {exc}')

    return redirect('quick:student_profile', student_id=student.id)


@login_required
@require_POST
def bulk_withdraw_quick_students(request, course_id):
    course = get_object_or_404(QuickCourse, pk=course_id, is_active=True)
    enrollment_ids = request.POST.getlist('enrollment_ids')
    withdrawal_reason = (request.POST.get('withdrawal_reason') or '').strip()

    if not enrollment_ids:
        messages.error(request, 'No students were selected for bulk withdrawal.')
        return redirect(reverse('quick:late_payment_course_detail', args=[course.id]))

    enrollments = list(
        QuickEnrollment.objects.filter(
            id__in=enrollment_ids,
            course=course,
            is_completed=False
        ).select_related('student', 'course')
    )

    if not enrollments:
        messages.error(request, 'No valid enrollments found for bulk withdrawal.')
        return redirect(reverse('quick:late_payment_course_detail', args=[course.id]))

    withdrawn = 0
    errors = []
    for enrollment in enrollments:
        try:
            with transaction.atomic():
                _withdraw_quick_enrollment(
                    enrollment=enrollment,
                    user=request.user,
                    withdrawal_reason=withdrawal_reason or 'Bulk withdrawal from outstanding page',
                    refund_amount=Decimal('0'),
                )
            withdrawn += 1
        except Exception as exc:
            errors.append(f'{enrollment.student.full_name}: {exc}')

    if withdrawn:
        messages.success(request, f'Withdrew {withdrawn} students from course {course.name}.')
    for error in errors[:5]:
        messages.error(request, error)

    query_string = urlencode({
        key: value for key, value in {
            'course_type': request.POST.get('course_type') or '',
            'start_date': request.POST.get('start_date') or '',
            'end_date': request.POST.get('end_date') or '',
        }.items() if value
    })
    redirect_url = reverse('quick:late_payment_course_detail', args=[course.id])
    if query_string:
        redirect_url = f'{redirect_url}?{query_string}'
    return redirect(redirect_url)


class QuickLatePaymentCoursesView(LoginRequiredMixin, ListView):
    template_name = 'quick/late_payment_course_list.html'
    context_object_name = 'courses'

    def get_queryset(self):
        course_type, course_type_label, report_label = _get_outstanding_course_type(self.request)
        start_date, end_date = _get_outstanding_date_range(self.request)
        self._course_type = course_type
        self._course_type_label = course_type_label
        self._course_type_report_label = report_label
        self._start_date = start_date
        self._end_date = end_date

        courses = QuickCourse.objects.filter(is_active=True).select_related('academic_year').order_by('name')
        if course_type != 'ALL':
            courses = courses.filter(course_type=course_type)

        course_data, totals = _build_quick_outstanding_course_summary(
            courses,
            include_zero_outstanding=False,
            start_date=start_date,
            end_date=end_date,
        )
        self._totals = totals
        return course_data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        totals = getattr(self, '_totals', {})
        total_courses = totals.get('total_courses', 0) or 0
        total_paid_amount = totals.get('total_paid_amount', Decimal('0'))
        context.update({
            'total_courses': total_courses,
            'total_outstanding_students': totals.get('total_outstanding_students', 0),
            'total_outstanding_amount': totals.get('total_outstanding_amount', Decimal('0')),
            'total_paid_amount': total_paid_amount,
            'course_type': getattr(self, '_course_type', 'INTENSIVE'),
            'course_type_label': getattr(self, '_course_type_label', ''),
            'course_type_report_label': getattr(self, '_course_type_report_label', ''),
            'course_type_options': _get_course_type_options(),
            'start_date': getattr(self, '_start_date', None),
            'end_date': getattr(self, '_end_date', None),
            'average_paid_per_course': (total_paid_amount / total_courses) if total_courses else Decimal('0'),
        })
        return context


class QuickLatePaymentCourseDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/late_payment_course_detail.html'

    def get_context_data(self, course_id=None, **kwargs):
        context = super().get_context_data(**kwargs)
        course_type, course_type_label, report_label = _get_outstanding_course_type(self.request)
        start_date, end_date = _get_outstanding_date_range(self.request)
        course = get_object_or_404(QuickCourse, pk=course_id)

        rows, detail_data = _build_quick_outstanding_rows([course], start_date=start_date, end_date=end_date)
        grouped_course = detail_data['grouped_courses'][0] if detail_data['grouped_courses'] else {
            'date_groups': [],
            'total_students': 0,
            'total_outstanding': Decimal('0'),
        }

        context.update({
            'course': course,
            'rows': rows,
            'date_groups': grouped_course['date_groups'],
            'total_students': grouped_course['total_students'],
            'total_outstanding': grouped_course['total_outstanding'],
            'total_net_amount': sum(r['net_amount'] for r in rows),
            'total_paid_amount': sum(r['paid_amount'] for r in rows),
            'course_type': course_type,
            'course_type_label': course_type_label,
            'course_type_report_label': report_label,
            'start_date': start_date,
            'end_date': end_date,
        })
        return context


class QuickLatePaymentCoursesPrintView(LoginRequiredMixin, TemplateView):
    template_name = 'quick/late_payment_course_print.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course_type, course_type_label, report_label = _get_outstanding_course_type(self.request)
        start_date, end_date = _get_outstanding_date_range(self.request)

        courses = QuickCourse.objects.filter(is_active=True).select_related('academic_year').order_by('name')
        if course_type != 'ALL':
            courses = courses.filter(course_type=course_type)

        course_data, totals = _build_quick_outstanding_course_summary(
            courses,
            include_zero_outstanding=False,
            start_date=start_date,
            end_date=end_date,
        )
        course_data = sorted(course_data, key=lambda row: (-row['outstanding_students'], row['course'].name))
        _, detail_data = _build_quick_outstanding_rows(
            [row['course'] for row in course_data],
            start_date=start_date,
            end_date=end_date,
        )

        current_snapshot = _snapshot_outstanding_totals(totals)
        previous_snapshot = self.request.session.get('quick_outstanding_report_snapshot')
        previous_time = self.request.session.get('quick_outstanding_report_timestamp')
        comparison = _build_outstanding_comparison(current_snapshot, previous_snapshot)

        context.update({
            'courses': course_data,
            'totals': totals,
            'detail_groups': detail_data['grouped_courses'],
            'print_date': timezone.now().strftime('%Y-%m-%d %H:%M'),
            'comparison': comparison,
            'previous_report_time': previous_time,
            'course_type': course_type,
            'course_type_label': course_type_label,
            'course_type_report_label': report_label,
            'start_date': start_date,
            'end_date': end_date,
        })

        self.request.session['quick_outstanding_report_snapshot'] = current_snapshot
        self.request.session['quick_outstanding_report_timestamp'] = timezone.now().strftime('%Y-%m-%d %H:%M')
        return context
