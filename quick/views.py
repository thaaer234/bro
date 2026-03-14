from django import forms 
from django.views.generic import ListView, CreateView, DeleteView, UpdateView
from django.views.generic.edit import FormView
from django.urls import reverse, reverse_lazy
from django.db.models import Q, Sum
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.auth.decorators import login_required  # ← أضف هذا السطر
from attendance.models import Attendance
from classroom.models import Classroomenrollment
from django.http import JsonResponse, Http404, HttpResponse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, TemplateView, ListView, DetailView
# from .models import QuickStudent, QuickEnrollment, QuickCourse, AcademicYear
from django.contrib import messages
from django.utils.dateparse import parse_date
from .forms import AcademicYearForm, QuickCourseForm, QuickStudentForm, QuickEnrollmentForm
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import urlencode
from django.db.models import Prefetch
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from accounts.models import Transaction, JournalEntry, Account, get_user_cash_account
from .models import QuickStudent, QuickEnrollment, QuickCourse, AcademicYear, QuickStudentReceipt
from accounts.models import Course, CostCenter
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
        raise ValueError('المبلغ المسترد يجب أن يكون أكبر من الصفر')

    receipts_data = _adjust_quick_receipts_for_refund(student, enrollment, refund_amount)
    actual_refund = receipts_data['refunded_amount']

    if actual_refund <= 0:
        raise ValueError('لا يوجد مبالغ مدفوعة كافية ليتم استردادها')

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
        ]

        for entry in adjustment_entries:
            if entry.id in added_entry_ids[enrollment.course_id]:
                continue

            description = entry.description or ""
            matched_source = None
            for prefix, source_label in description_prefixes:
                if prefix == "استرداد مبلغ - " and description.startswith(f"{prefix}{student_name} - {course_name}"):
                    matched_source = source_label
                    break
                if prefix == "سحب طالب سريع " and description.startswith(f"{prefix}{student_name} من {course_name}"):
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
        ("رُحل بواسطة", 18),
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
        return "طالب معهد" if phone and phone in regular_phone_set else "خارجي"

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
            ("اسم الطالب", 28),
            ("رقم الهاتف", 16),
            ("نوع الطالب", 14),
            ("المسجل", 18),
            ("تاريخ التسجيل", 14),
        ]
        if include_course_col:
            columns.insert(1, ("الدورة", 26))
        columns.extend([
            ("إجمالي الدورة", 16),
            ("المدفوع", 14),
            ("المتبقي", 14),
        ])

        total_cols = len(columns)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
        ws.cell(row=1, column=1, value="تقرير المتبقي - الدورات السريعة").font = title_font
        ws.cell(row=1, column=1).alignment = center
        ws.cell(row=1, column=1).fill = header_fill

        internal_count = sum(1 for r in rows if r['student_type'] == "طالب معهد")
        external_count = sum(1 for r in rows if r['student_type'] == "خارجي")
        total_paid = sum(r['paid'] for r in rows)
        total_remaining = sum(r['remaining'] for r in rows)

        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_cols)
        ws.cell(
            row=2,
            column=1,
            value=f"الدورة: {course_label} | احصائية: طالب معهد {internal_count} | خارجي {external_count}"
        ).alignment = right
        ws.cell(row=2, column=1).fill = subheader_fill

        ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=total_cols)
        ws.cell(
            row=3,
            column=1,
            value=f"إجمالي الطلاب: {len(rows)} | إجمالي المدفوع: {total_paid} | إجمالي المتبقي: {total_remaining}"
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
    all_sheet = workbook.create_sheet("كل الدورات")
    write_sheet(all_sheet, "كل الدورات", all_rows, include_course_col=True)

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
    response['Content-Disposition'] = f'attachment; filename="تقرير_الدورات_السريعة_{report_label}_{timestamp}.xlsx"'
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


def _get_course_type_options():
    options = [{'value': 'ALL', 'label': 'كل الدورات'}]
    for value, label in QuickCourse.COURSE_TYPE_CHOICES:
        options.append({'value': value, 'label': label})
    return options


def _build_quick_outstanding_course_summary(courses, include_zero_outstanding=False):
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

    enrollments = list(
        QuickEnrollment.objects.filter(course__in=courses, is_completed=False)
        .select_related('course', 'student__student')
    )
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
            trend = 'زيادة'
        elif delta < 0:
            trend = 'نقصان'
        else:
            trend = 'ثبات'

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
        make_item('إجمالي الطلاب', 'total_students', None),
        make_item('الطلاب المسددين', 'total_paid_students', 'up'),
        make_item('الطلاب غير المسددين', 'total_outstanding_students', 'down'),
        make_item('إجمالي المدفوع', 'total_paid_amount', 'up'),
        make_item('إجمالي المتبقي', 'total_outstanding_amount', 'down'),
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

    
 # الفصول الدراسية
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
        messages.success(self.request, 'تم إضافة الفصل الدراسي بنجاح')
        return super().form_valid(form)

class CloseAcademicYearView(LoginRequiredMixin, DetailView):
    model = AcademicYear
    template_name = 'quick/academic_year_close.html'
    
    def post(self, request, *args, **kwargs):
        academic_year = self.get_object()
        password = request.POST.get('password')
        
        # التحقق من كلمة المرور
        if not request.user.check_password(password):
            messages.error(request, 'كلمة المرور غير صحيحة')
            return render(request, self.template_name, {'academic_year': academic_year})
        
        academic_year.is_closed = True
        academic_year.closed_by = request.user
        academic_year.closed_at = timezone.now()
        academic_year.save()
        
        messages.success(request, 'تم إغلاق الفصل الدراسي بنجاح')
        return redirect('quick:academic_year_list')

# الدورات السريعة
class QuickCourseListView(LoginRequiredMixin, ListView):
    model = QuickCourse
    template_name = 'quick/quick_course_list.html'
    context_object_name = 'courses'
    
    def get_queryset(self):
        return QuickCourse.objects.filter(is_active=True)

class QuickCourseCreateView(LoginRequiredMixin, CreateView):
    model = QuickCourse
    form_class = QuickCourseForm
    template_name = 'quick/quick_course_form.html'
    success_url = reverse_lazy('quick:course_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'تم إضافة الدورة السريعة بنجاح')
        return super().form_valid(form)

# الطلاب السريعين
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
            messages.warning(request, 'يرجى اختيار طلاب أولاً.')
            return redirect(next_url)

        if gender not in ('male', 'female', 'unknown'):
            messages.error(request, 'قيمة الجنس غير صحيحة.')
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
            messages.success(request, f'تم تحديث الجنس لـ {updated_count} طالب/طالبة.')
        else:
            messages.success(request, f'تم إزالة تحديد الجنس لـ {updated_count} طالب/طالبة.')
        return redirect(next_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # إحصائيات الربط التلقائي
        students = context['students']
        auto_assigned = students.filter(academic_year__isnull=False)
        unassigned = students.filter(academic_year__isnull=True)
        
        context.update({
            'academic_years': AcademicYear.objects.all().order_by('-start_date'),
            'auto_assigned_count': auto_assigned.count(),
            'unassigned_count': unassigned.count(),
        })
        return context

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
        # إنشاء طالب نظامي أولاً
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
        messages.success(self.request, 'تم إضافة الطالب السريع بنجاح')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('quick:student_profile', kwargs={'student_id': self.object.pk})

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

# التسجيلات السريعة
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
        # إنشاء القيد المحاسبي
        try:
            self.object.create_accrual_enrollment_entry(self.request.user)
            messages.success(self.request, 'تم تسجيل الطالب وإنشاء القيد المحاسبي بنجاح')
        except Exception as e:
            messages.warning(self.request, f'تم التسجيل ولكن حدث خطأ في القيد المحاسبي: {str(e)}')
        return response
    
    def get_success_url(self):
        return reverse_lazy('quick:student_detail', kwargs={'pk': self.object.student.pk})

# بروفايل الطالب السريع
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
            # ✅ جلب التسجيلات النشطة فقط
            active_enrollments_queryset = QuickEnrollment.objects.filter(
                student=student, 
                is_completed=False
            ).select_related('course')
            
            # ✅ إنشاء قائمة بالبيانات المحسوبة للتسجيلات النشطة
            enrollment_data = []
            for enrollment in active_enrollments_queryset:
                # اربط الدفعات بهذا التسجيل نفسه لمنع خلط إيصالات تسجيل آخر
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
            
            # ✅ حساب الإجماليات
            total_paid = sum(item['total_paid'] for item in enrollment_data)
            total_due = sum(item['net_amount'] for item in enrollment_data)
            total_remaining = total_due - total_paid
            
            # ✅ جلب جميع الإيصالات السريعة
            receipts = QuickStudentReceipt.objects.filter(
                quick_student=student
            ).select_related('course').order_by('-date', '-id')
            
            # ✅ التحقق من وجود تسجيلات نشطة
            has_active_enrollments = len(enrollment_data) > 0
            
            context.update({
                'enrollment_data': enrollment_data,
                'active_enrollments': enrollment_data,
                'total_paid': total_paid,
                'total_due': total_due,
                'total_remaining': total_remaining,
                'receipts': receipts,
                'has_active_enrollments': has_active_enrollments,
            })
            
        except Exception as e:
            messages.error(self.request, f'حدث خطأ في تحميل البيانات: {str(e)}')
            context.update({
                'enrollment_data': [],
                'active_enrollments': [],
                'total_paid': Decimal('0.00'),
                'total_due': Decimal('0.00'),
                'total_remaining': Decimal('0.00'),
                'receipts': [],
                'has_active_enrollments': False,
            })
        
        return context
# كشف حساب الطالب السريع
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
            # ✅ جلب التسجيلات النشطة فقط
            active_enrollments_queryset = QuickEnrollment.objects.filter(
                student=student, 
                is_completed=False
            ).select_related('course')
            
            # ✅ إنشاء قائمة بالبيانات المحسوبة للتسجيلات النشطة
            enrollment_data = []
            for enrollment in active_enrollments_queryset:
                # اربط الدفعات بهذا التسجيل نفسه لمنع خلط إيصالات تسجيل آخر
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
            
            # ✅ حساب الإجماليات
            total_paid = sum(item['total_paid'] for item in enrollment_data)
            total_due = sum(item['net_amount'] for item in enrollment_data)
            total_remaining = total_due - total_paid
            
            # ✅ جلب جميع الإيصالات السريعة
            receipts = QuickStudentReceipt.objects.filter(
                quick_student=student
            ).select_related('course').order_by('-date', '-id')
            
            # ✅ التحقق من وجود تسجيلات نشطة
            has_active_enrollments = len(enrollment_data) > 0
            
            context.update({
                'enrollment_data': enrollment_data,
                'active_enrollments': enrollment_data,
                'total_paid': total_paid,
                'total_due': total_due,
                'total_remaining': total_remaining,
                'receipts': receipts,
                'has_active_enrollments': has_active_enrollments,
            })
            
        except Exception as e:
            messages.error(self.request, f'حدث خطأ في تحميل البيانات: {str(e)}')
            context.update({
                'enrollment_data': [],
                'active_enrollments': [],
                'total_paid': Decimal('0.00'),
                'total_due': Decimal('0.00'),
                'total_remaining': Decimal('0.00'),
                'receipts': [],
                'has_active_enrollments': False,
            })
        
        return context

@require_POST
def update_quick_student_discount(request, student_id):
    """تحديث حسم الطالب السريع وتعديل القيود المرتبطة"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'يجب تسجيل الدخول'})
    
    student = get_object_or_404(QuickStudent, id=student_id)
    
    try:
        from decimal import Decimal
        from django.db import transaction as db_transaction
        
        discount_percent = Decimal(request.POST.get('discount_percent', '0'))
        discount_amount = Decimal(request.POST.get('discount_amount', '0'))
        discount_reason = request.POST.get('discount_reason', '')
        
        # التحقق من وجود تسجيلات نشطة
        active_enrollments = QuickEnrollment.objects.filter(
            student=student, 
            is_completed=False
        )
        
        if not active_enrollments.exists():
            return JsonResponse({
                'success': False,
                'error': 'لا توجد تسجيلات نشطة للطالب'
            })
        
        with db_transaction.atomic():
            # تحديث التسجيلات النشطة بالخصم الجديد
            updated_count = 0
            for enrollment in active_enrollments:
                enrollment.discount_percent = discount_percent
                enrollment.discount_amount = discount_amount
                enrollment.save()
                updated_count += 1
            
            # إذا تغير الخصم، قم بتحديث القيود
            student.update_enrollment_discounts(request.user)
        
        return JsonResponse({
            'success': True,
            'message': f'تم تحديث الحسم والقيود المحاسبية لـ {updated_count} تسجيل نشط'
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"حدث خطأ في update_quick_student_discount: {str(e)}")
        
        return JsonResponse({
            'success': False,
            'error': f'حدث خطأ: {str(e)}'
        })

@require_POST
def quick_student_quick_receipt(request, student_id):
    """إنشاء إيصال فوري للطالب السريع"""
    from decimal import Decimal
    from django.db.models import Sum
    from .models import QuickStudentReceipt
    
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'يجب تسجيل الدخول'}, status=401)
    
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
        
        # ✅ التصحيح: إذا كان amount صغيراً (أقل من 1000) نعتبره يحتاج أصفار
        if amount < 1000 and amount > 0:
            # نضرب في 1000 لإضافة الأصفار المفقودة
            amount = amount * 1000
        
        # معالجة تاريخ الإيصال
        if receipt_date_str:
            receipt_date = parse_date(receipt_date_str)
            if not receipt_date:
                return JsonResponse({'ok': False, 'error': 'صيغة التاريخ غير صحيحة'}, status=400)
        else:
            receipt_date = timezone.now().date()
            
    except (ValueError, TypeError, InvalidOperation) as e:
        return JsonResponse({'ok': False, 'error': f'خطأ في تنسيق الأرقام: {str(e)}'}, status=400)
    
    course = None
    remaining_amount = Decimal('0.00')
    enrollment = None
    
    try:
        if enrollment_id:
            enrollment = QuickEnrollment.objects.get(pk=enrollment_id, student=student)
            
            if enrollment.is_completed:
                return JsonResponse({'ok': False, 'error': 'لا يمكن قطع إيصال لدورة مسحوبة'}, status=400)
                
            course = enrollment.course

            if course_id and str(course.id) != str(course_id):
                return JsonResponse({'ok': False, 'error': 'الدورة المحددة لا تطابق تسجيل الطالب'}, status=400)
            
            if amount == 0:
                amount = enrollment.net_amount or Decimal('0.00')
            
            # احسب المتبقي من نفس التسجيل فقط
            total_paid = _get_quick_enrollment_paid_total(enrollment, student)
            
            net_amount = enrollment.net_amount or Decimal('0.00')
            remaining_amount = max(Decimal('0.00'), net_amount - total_paid)
            
        elif course_id:
            course = QuickCourse.objects.get(pk=course_id)
            
            if amount == 0:
                amount = course.price or Decimal('0.00')
                
            # البحث عن enrollment لهذه الدورة
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
        return JsonResponse({'ok': False, 'error': 'الدورة أو التسجيل غير موجود'}, status=404)
    
    if paid_amount < 0:
        return JsonResponse({'ok': False, 'error': 'المبلغ المدفوع غير صالح'}, status=400)
    
    if paid_amount > remaining_amount:
        return JsonResponse({'ok': False, 'error': f'المبلغ المدفوع ({paid_amount}) يتجاوز المبلغ المتبقي ({remaining_amount})'}, status=400)
    
    # Create receipt - استخدام QuickStudentReceipt الجديد
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
        return JsonResponse({'ok': False, 'error': f'فشل في إنشاء الإيصال: {str(e)}'}, status=500)
    
    journal_warning = None
    try:
        # إنشاء القيد المحاسبي
        receipt.create_accrual_journal_entry(request.user)
    except Exception as e:
        journal_warning = f"خطأ في القيد المحاسبي: {e}"
    
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
    """سحب الطالب السريع من الدورة"""
    student = get_object_or_404(QuickStudent, pk=student_id)
    
    if request.method == 'POST':
        enrollment_id = request.POST.get('enrollment_id')
        withdrawal_reason = request.POST.get('withdrawal_reason', '')
        refund_amount_raw = request.POST.get('refund_amount', '0')

        if not enrollment_id:
            messages.error(request, 'لم يتم تحديد تسجيل الدورة')
            return redirect('quick:student_profile', student_id=student.id)

        try:
            enrollment = get_object_or_404(QuickEnrollment, pk=enrollment_id, student=student)

            if enrollment.is_completed:
                messages.error(request, 'هذه الدورة مسحوبة مسبقاً')
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
            refund_note = f' واسترد {actual_refund:,.0f} ل.س' if actual_refund > 0 else ''

            if getattr(enrollment, 'enrollment_journal_entry_id', None):
                try:
                    enrollment.enrollment_journal_entry.reverse_entry(
                        request.user,
                        description=f"إلغاء تسجيل سريع - {withdrawal_reason}" if withdrawal_reason else "إلغاء تسجيل سريع"
                    )
                except Exception:
                    pass

            returns_account, _ = Account.objects.get_or_create(
                code='4201',
                defaults={
                    'name': 'Withdrawal Revenue - Students',
                    'name_ar': 'إيرادات انسحاب طلاب',
                    'account_type': 'REVENUE',
                    'is_active': True,
                }
            )

            student_ar = student.ar_account

            new_total_paid = refund_result['new_total_paid']
            previous_paid = refund_result['previous_paid']
            due = max(Decimal('0.00'), (enrollment.net_amount or Decimal('0.00')) - previous_paid)
            entry_total = actual_refund + due

            entry = JournalEntry.objects.create(
                reference="",
                date=timezone.now().date(),
                description=f"سحب طالب سريع {student.full_name} من {enrollment.course.name}" + 
                           (f" - {withdrawal_reason}" if withdrawal_reason else ""),
                entry_type='ADJUSTMENT',
                total_amount=entry_total,
                created_by=request.user
            )

            if actual_refund > 0:
                cash_account = _get_employee_cash_account(request.user)
                Transaction.objects.create(
                    journal_entry=entry,
                    account=returns_account,
                    amount=actual_refund,
                    is_debit=True,
                    description=f"استرداد - {withdrawal_reason}" if withdrawal_reason else "استرداد مبلغ مدفوع"
                )
                Transaction.objects.create(
                    journal_entry=entry,
                    account=cash_account,
                    amount=actual_refund,
                    is_debit=False,
                    description=f"دفع استرداد للطالب {student.full_name}"
                )

            if due > 0:
                deferred_account = Account.get_or_create_quick_course_deferred_account(enrollment.course)
                if deferred_account and student_ar:
                    Transaction.objects.create(
                        journal_entry=entry,
                        account=deferred_account,
                        amount=due,
                        is_debit=True,
                        description="عكس إيرادات مؤجلة"
                    )
                    Transaction.objects.create(
                        journal_entry=entry,
                        account=student_ar,
                        amount=due,
                        is_debit=False,
                        description="عكس ذمم الطالب المدينة"
                    )

            entry.post_entry(request.user)

            enrollment.is_completed = True
            enrollment.completion_date = timezone.now().date()
            enrollment.save(update_fields=['is_completed', 'completion_date'])

            messages.success(request, f'تم سحب الطالب من دورة {enrollment.course.name}{refund_note} بنجاح')
            return redirect('quick:student_profile', student_id=student.id)

        except Exception as e:
            print(f"ERROR in withdraw_quick_student: {str(e)}")
            messages.error(request, f'حدث خطأ أثناء السحب: {str(e)}')
            return redirect('quick:student_profile', student_id=student.id)

@require_POST
def refund_quick_student(request, student_id):
    """استرداد مبلغ للطالب السريع"""
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'يجب تسجيل الدخول'}, status=401)
    
    student = get_object_or_404(QuickStudent, pk=student_id)
    
    try:
        enrollment_id = request.POST.get('enrollment_id')
        refund_amount = Decimal(request.POST.get('refund_amount', '0'))
        refund_reason = request.POST.get('refund_reason', '')
        
        if not enrollment_id:
            return JsonResponse({'ok': False, 'error': 'لم يتم تحديد التسجيل'}, status=400)
        
        enrollment = get_object_or_404(QuickEnrollment, pk=enrollment_id, student=student)
        
        if enrollment.is_completed:
            return JsonResponse({'ok': False, 'error': 'لا يمكن استرداد مبلغ لدورة مسحوبة'}, status=400)
        
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
            print(f"خطأ في الاسترداد: {str(exc)}")
            print(traceback.format_exc())
            return JsonResponse({'ok': False, 'error': f'خطأ في الاسترداد: {str(exc)}'}, status=500)

        return JsonResponse({
            'ok': True,
            'message': f'تم استرداد {result["refund_amount"]:,.0f} ل.س بنجاح',
            'new_balance': float(result['new_balance']),
            'previous_balance': float(result['previous_balance']),
            'new_paid': float(result['new_total_paid']),
            'previous_paid': float(result['previous_paid'])
        })

    except Exception as e:
        import traceback
        print(f"خطأ في الاسترداد: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'ok': False, 'error': f'حدث خطأ في الاسترداد: {str(e)}'}, status=500)
# التقارير
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
            'course_type_label': getattr(self, '_course_type_label', 'مكثفة'),
            'course_type_report_label': getattr(self, '_course_type_report_label', 'المكثفات'),
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
    """تسجيل طالب سريع في دورة"""
    student = get_object_or_404(QuickStudent, id=student_id)
    courses = QuickCourse.objects.filter(is_active=True, academic_year=student.academic_year)
    
    if request.method == 'POST':
        course_ids = request.POST.getlist('course_ids')
        if not course_ids:
            messages.error(request, 'يرجى اختيار دورة واحدة على الأقل')
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
                warnings.append(f'التسجيل للدورة "{course.name}" موجود مسبقاً، تم تجاهلها.')
                continue

            enrollment = QuickEnrollment.objects.create(
                student=student,
                course=course,
                enrollment_date=timezone.now().date(),
                net_amount=course.price,
                total_amount=course.price
            )
            created_enrollments += 1

            try:
                enrollment.create_accrual_enrollment_entry(request.user)
            except Exception as exc:
                warnings.append(f'القيد المحاسبي لدورة {course.name} لم يُنجز: {exc}')

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
                    warnings.append(f'إنشاء إيصال لدورة {course.name} فشل: {exc}')

        if created_enrollments:
            messages.success(request, f'تم تسجيل الطالب في {created_enrollments} دورة')
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
    """طباعة مجموعة إيصالات دفعة واحدة"""
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
        'return_url': reverse('quick:student_profile', args=[student_id])
    })

def quick_student_receipt_print(request, receipt_id):
    """طباعة إيصال الطالب السريع"""
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


# في quick/views.py - أضف هذه الدالة في النهاية

@login_required
def auto_assign_academic_years(request):
    """ربط جميع الطلاب بفصولهم الدراسية تلقائياً"""
    from students.models import Student
    from quick.models import QuickStudent, AcademicYear
    
    # ربط الطلاب السريعين
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
    
    messages.success(request, f'تم ربط {updated_count} طالب سريع تلقائياً بالفصول الدراسية')
    return redirect('quick:student_list')


# في ملف views.py - تحديث دالة التعديل

class QuickStudentUpdateView(LoginRequiredMixin, UpdateView):
    model = QuickStudent
    form_class = QuickStudentForm
    template_name = 'quick/quick_student_update.html'
    context_object_name = 'student'
    
    def get_success_url(self):
        # ✅ التوجيه إلى بروفايل الطالب بدلاً من التفاصيل البسيطة
        return reverse_lazy('quick:student_profile', kwargs={'student_id': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'تم تحديث بيانات الطالب بنجاح')
        return super().form_valid(form)




        # أضف هذه الكلاس في قسم "الدورات السريعة" بعد QuickCourseCreateView

class QuickCourseUpdateView(LoginRequiredMixin, UpdateView):
    model = QuickCourse
    form_class = QuickCourseForm
    template_name = 'quick/quick_course_form.html'  # نفس قالب الإنشاء
    context_object_name = 'course'
    
    def get_success_url(self):
        return reverse_lazy('quick:course_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True  # للتمييز بين التعديل والإضافة
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'تم تحديث بيانات الدورة بنجاح')
        return super().form_valid(form)
