from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import EmployeeAdvance

from .email_notifications import send_biometric_punch_email
from .models import (
    AttendancePolicy,
    BiometricDevice,
    BiometricLog,
    Employee,
    EmployeeAttendance,
    EmployeePayroll,
    EmployeePayrollLine,
    PayrollPeriod,
    Vacation,
)


def get_teacher_attendance_stats(teacher, date=None, year=None, month=None):
    from attendance.models import TeacherAttendance

    if date:
        attendance = TeacherAttendance.objects.filter(
            teacher=teacher,
            date=date,
            status='present'
        )
        return sum(att.total_sessions for att in attendance)

    if year and month:
        attendance = TeacherAttendance.objects.filter(
            teacher=teacher,
            date__year=year,
            date__month=month,
            status='present'
        )
        return sum(att.total_sessions for att in attendance)

    if year:
        attendance = TeacherAttendance.objects.filter(
            teacher=teacher,
            date__year=year,
            status='present'
        )
        return sum(att.total_sessions for att in attendance)

    return 0


def _seconds_between(start_dt, end_dt):
    if not start_dt or not end_dt or end_dt <= start_dt:
        return 0
    return int((end_dt - start_dt).total_seconds())


def _decimal(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or 0))


def _quantize_money(value):
    return _decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _apply_rounding(seconds, method):
    if not seconds:
        return 0
    if method == 'none':
        return seconds
    if method == 'minute':
        step = 60
    elif method == '5_minutes':
        step = 300
    elif method == '15_minutes':
        step = 900
    else:
        step = 60
    return int(round(seconds / step) * step)


def _employee_required_monthly_seconds(employee, shift, start_date, end_date):
    required_monthly_hours = int(getattr(employee, 'required_monthly_hours', 0) or 0)
    if required_monthly_hours > 0:
        return required_monthly_hours * 3600

    required_daily_seconds = shift.required_work_seconds if shift else 28800
    period_days = max((end_date - start_date).days + 1, 1)
    weekend_days = employee.get_weekend_day_numbers() if hasattr(employee, 'get_weekend_day_numbers') else set()
    work_days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() not in weekend_days:
            work_days += 1
        current += timedelta(days=1)
    return required_daily_seconds * max(work_days, 1)


class BiometricImportService:
    @classmethod
    @transaction.atomic
    def import_logs(cls, device, raw_logs):
        if isinstance(device, int):
            device = BiometricDevice.objects.get(pk=device)

        created_logs = []
        duplicate_count = 0
        unresolved_count = 0

        for item in raw_logs:
            device_user_id = str(item.get('device_user_id') or item.get('user_id') or '').strip()
            if not device_user_id:
                continue

            punch_time = item.get('punch_time')
            if isinstance(punch_time, str):
                punch_time = datetime.fromisoformat(punch_time)
            if timezone.is_naive(punch_time):
                punch_time = timezone.make_aware(punch_time)

            employee = Employee.objects.filter(biometric_user_id=device_user_id).first()
            if not employee:
                unresolved_count += 1

            raw_payload = item.get('raw_data') or {
                'device_user_id': device_user_id,
                'punch_time': punch_time.isoformat(),
                'punch_type': item.get('punch_type') or 'unknown',
            }

            try:
                with transaction.atomic():
                    log = BiometricLog.objects.create(
                        employee=employee,
                        device=device,
                        device_user_id=device_user_id,
                        punch_time=punch_time,
                        punch_type=item.get('punch_type') or 'unknown',
                        raw_data=raw_payload,
                    )
                created_logs.append(log)
            except IntegrityError:
                duplicate_count += 1

        device.last_synced_at = timezone.now()
        device.save(update_fields=['last_synced_at'])

        for log in created_logs:
            AttendanceGenerationService.sync_from_log(log)

        for log in created_logs:
            transaction.on_commit(lambda log=log: send_biometric_punch_email(log))

        return {
            'created': len(created_logs),
            'duplicates': duplicate_count,
            'unresolved': unresolved_count,
        }

    @classmethod
    @transaction.atomic
    def relink_employee_logs(cls, employee):
        biometric_user_id = str(getattr(employee, 'biometric_user_id', '') or '').strip()
        if not biometric_user_id:
            return {'linked_logs': 0, 'rebuilt_days': 0}

        logs_qs = BiometricLog.objects.filter(
            employee__isnull=True,
            device_user_id=biometric_user_id,
        ).order_by('punch_time')
        linked_logs = logs_qs.count()
        if not linked_logs:
            return {'linked_logs': 0, 'rebuilt_days': 0}

        logs_qs.update(employee=employee)
        affected_days = sorted({
            timezone.localtime(log.punch_time).date()
            for log in BiometricLog.objects.filter(
                employee=employee,
                device_user_id=biometric_user_id,
            ).order_by('punch_time')
        })
        for target_date in affected_days:
            AttendanceGenerationService.build_attendance_record(employee, target_date)

        return {
            'linked_logs': linked_logs,
            'rebuilt_days': len(affected_days),
        }


class AttendanceGenerationService:
    @classmethod
    def _apply_review_status(cls, attendance):
        has_exception = bool(attendance.late_seconds or attendance.early_leave_seconds)
        if has_exception:
            if attendance.review_status not in {'justified', 'unjustified'}:
                attendance.review_status = 'pending'
        elif attendance.review_status == 'pending':
            attendance.review_status = 'not_required'

    @classmethod
    def _populate_attendance_metrics(cls, attendance, shift, policy, check_in, check_out, notes, source='biometric'):
        worked_seconds = _seconds_between(check_in, check_out) if check_in and check_out else 0
        if shift.break_seconds and worked_seconds:
            worked_seconds = max(0, worked_seconds - shift.break_seconds)

        shift_start, shift_end = shift.get_bounds_for_date(attendance.date)
        grace_seconds = shift.grace_period_minutes * 60
        late_seconds = max(0, _seconds_between(shift_start, check_in) - grace_seconds) if check_in else shift.required_work_seconds
        early_leave_seconds = max(0, _seconds_between(check_out, shift_end)) if check_out and check_out < shift_end else 0
        absence_seconds = max(0, shift.required_work_seconds - worked_seconds)
        overtime_seconds = max(0, worked_seconds - shift.required_work_seconds)

        rounding_method = getattr(policy, 'rounding_method', 'minute')
        late_seconds = _apply_rounding(late_seconds, rounding_method)
        early_leave_seconds = _apply_rounding(early_leave_seconds, rounding_method)
        overtime_seconds = _apply_rounding(overtime_seconds, rounding_method)

        attendance.check_in = check_in
        attendance.check_out = check_out
        attendance.worked_seconds = worked_seconds
        attendance.late_seconds = late_seconds
        attendance.early_leave_seconds = early_leave_seconds
        attendance.overtime_seconds = overtime_seconds
        attendance.absence_seconds = absence_seconds
        attendance.source = source
        attendance.notes = notes

        if not check_in and not check_out:
            attendance.status = 'absent'
            attendance.review_status = 'not_required'
        elif absence_seconds >= shift.required_work_seconds:
            attendance.status = 'absent'
        elif late_seconds or early_leave_seconds:
            attendance.status = 'late'
        elif worked_seconds < shift.required_work_seconds:
            attendance.status = 'partial'
        else:
            attendance.status = 'present'

        cls._apply_review_status(attendance)
        return attendance
    @classmethod
    def sync_from_log(cls, log):
        target_date = timezone.localtime(log.punch_time).date()
        employee = log.employee or Employee.objects.filter(biometric_user_id=log.device_user_id).first()
        if not employee:
            return None
        return cls.build_attendance_record(employee, target_date)

    @classmethod
    def sync_range(cls, employee, start_date, end_date):
        current = start_date
        records = []
        while current <= end_date:
            records.append(cls.build_attendance_record(employee, current))
            current += timedelta(days=1)
        return records

    @classmethod
    def build_attendance_record(cls, employee, target_date):
        attendance, _ = EmployeeAttendance.objects.get_or_create(employee=employee, date=target_date)
        if attendance.is_manually_adjusted:
            return attendance

        shift = employee.effective_shift
        policy = employee.effective_attendance_policy
        day_start = timezone.make_aware(datetime.combine(target_date, time.min))
        next_day_start = day_start + timedelta(days=1)
        same_day_logs = list(
            employee.biometric_logs.filter(
                punch_time__gte=day_start,
                punch_time__lt=next_day_start,
            ).order_by('punch_time')
        )

        approved_vacation = Vacation.objects.filter(
            employee=employee,
            status='ظ…ظˆط§ظپظ‚',
            start_date__lte=target_date,
            end_date__gte=target_date,
        ).exists()
        if approved_vacation:
            attendance.check_in = None
            attendance.check_out = None
            attendance.worked_seconds = 0
            attendance.late_seconds = 0
            attendance.early_leave_seconds = 0
            attendance.overtime_seconds = 0
            attendance.absence_seconds = 0
            attendance.status = 'vacation'
            attendance.review_status = 'not_required'
            attendance.source = 'biometric'
            attendance.notes = 'تم تغطية اليوم بإجازة معتمدة.'
            attendance.save()
            return attendance

        is_weekend = target_date.weekday() in employee.get_weekend_day_numbers()
        if is_weekend and not same_day_logs:
            attendance.check_in = None
            attendance.check_out = None
            attendance.worked_seconds = 0
            attendance.late_seconds = 0
            attendance.early_leave_seconds = 0
            attendance.overtime_seconds = 0
            attendance.absence_seconds = 0
            attendance.status = 'weekend'
            attendance.review_status = 'not_required'
            attendance.source = 'biometric'
            attendance.notes = 'يوم عطلة أسبوعية حسب إعدادات ملف الموظف.'
            attendance.save()
            return attendance

        if not shift:
            if not same_day_logs:
                attendance.check_in = None
                attendance.check_out = None
                attendance.worked_seconds = 0
                attendance.late_seconds = 0
                attendance.early_leave_seconds = 0
                attendance.overtime_seconds = 0
                attendance.absence_seconds = 0
                attendance.status = 'absent'
                attendance.review_status = 'not_required'
                attendance.source = 'biometric'
                attendance.notes = 'لا يوجد شفت افتراضي ولا سجلات بصمة لهذا الموظف.'
                attendance.save()
                return attendance

            check_in = same_day_logs[0].punch_time
            check_out = same_day_logs[-1].punch_time if len(same_day_logs) > 1 else None
            attendance.check_in = check_in
            attendance.check_out = check_out
            attendance.worked_seconds = _seconds_between(check_in, check_out) if check_out else 0
            attendance.late_seconds = 0
            attendance.early_leave_seconds = 0
            attendance.overtime_seconds = 0
            attendance.absence_seconds = 0
            attendance.status = 'partial' if not check_out else 'present'
            attendance.review_status = 'not_required'
            attendance.source = 'biometric'
            attendance.notes = f'تم احتساب الدوام من {len(same_day_logs)} سجلات بصمة بدون شفت افتراضي.'
            attendance.save()
            return attendance

        shift_start, shift_end = shift.get_bounds_for_date(target_date)
        window_start = shift_start - timedelta(hours=4)
        window_end = shift_end + timedelta(hours=4)
        relevant_logs = list(
            employee.biometric_logs.filter(
                punch_time__gte=window_start,
                punch_time__lte=window_end,
            ).order_by('punch_time')
        )
        if not relevant_logs:
            attendance.check_in = None
            attendance.check_out = None
            attendance.worked_seconds = 0
            attendance.late_seconds = 0
            attendance.early_leave_seconds = 0
            attendance.overtime_seconds = 0
            attendance.absence_seconds = shift.required_work_seconds
            attendance.status = 'absent'
            attendance.review_status = 'not_required'
            attendance.source = 'biometric'
            attendance.notes = 'لا توجد سجلات بصمة ضمن نافذة الشفت لهذا اليوم.'
            attendance.save()
            return attendance

        check_in = relevant_logs[0].punch_time
        check_out = relevant_logs[-1].punch_time if len(relevant_logs) > 1 else None
        attendance = cls._populate_attendance_metrics(
            attendance=attendance,
            shift=shift,
            policy=policy,
            check_in=check_in,
            check_out=check_out,
            notes=f'تمت مزامنة الدوام من {len(relevant_logs)} سجلات بصمة.',
            source='biometric',
        )
        attendance.save()
        return attendance

    @classmethod
    def build_attendance(cls, employee, target_date):
        return cls.build_attendance_record(employee, target_date)
        shift = employee.effective_shift
        policy = employee.effective_attendance_policy
        same_day_logs = list(
            employee.biometric_logs.filter(
                punch_time__date=target_date
            ).order_by('punch_time')
        )
        logs = list(
            employee.biometric_logs.filter(
                punch_time__date__gte=target_date,
                punch_time__date__lte=target_date + timedelta(days=1)
            ).order_by('punch_time')
        )
        if not shift and same_day_logs:
            attendance, _ = EmployeeAttendance.objects.get_or_create(employee=employee, date=target_date)
            check_in = same_day_logs[0].punch_time
            check_out = same_day_logs[-1].punch_time if len(same_day_logs) > 1 else None
            attendance.check_in = check_in
            attendance.check_out = check_out
            attendance.worked_seconds = _seconds_between(check_in, check_out) if check_out else 0
            attendance.late_seconds = 0
            attendance.early_leave_seconds = 0
            attendance.overtime_seconds = 0
            attendance.absence_seconds = 0
            attendance.status = 'partial' if not check_out else 'present'
            attendance.review_status = 'not_required'
            attendance.source = 'biometric'
            attendance.notes = f'تم احتساب الدوام من {len(same_day_logs)} سجلات بصمة بدون شفت افتراضي.'
            attendance.save()
            return attendance
        if not shift:
            attendance, _ = EmployeeAttendance.objects.get_or_create(employee=employee, date=target_date)
            attendance.status = 'absent'
            attendance.notes = 'لا يوجد شفت افتراضي لهذا الموظف.'
            attendance.save()
            return attendance

        logs = list(
            employee.biometric_logs.filter(
                punch_time__date__gte=target_date,
                punch_time__date__lte=target_date + timedelta(days=1)
            ).order_by('punch_time')
        )
        shift_start, shift_end = shift.get_bounds_for_date(target_date)

        relevant_logs = [
            log for log in logs
            if shift_start - timedelta(hours=4) <= log.punch_time <= shift_end + timedelta(hours=4)
        ]

        approved_vacation = Vacation.objects.filter(
            employee=employee,
            status='موافق',
            start_date__lte=target_date,
            end_date__gte=target_date,
        ).exists()

        attendance, _ = EmployeeAttendance.objects.get_or_create(employee=employee, date=target_date)

        if approved_vacation:
            attendance.check_in = None
            attendance.check_out = None
            attendance.worked_seconds = 0
            attendance.late_seconds = 0
            attendance.early_leave_seconds = 0
            attendance.overtime_seconds = 0
            attendance.absence_seconds = 0
            attendance.status = 'vacation'
            attendance.review_status = 'not_required'
            attendance.notes = 'تم تغطية اليوم بإجازة معتمدة.'
            attendance.save()
            return attendance

        if not relevant_logs:
            attendance.check_in = None
            attendance.check_out = None
            attendance.worked_seconds = 0
            attendance.late_seconds = 0
            attendance.early_leave_seconds = 0
            attendance.overtime_seconds = 0
            attendance.absence_seconds = shift.required_work_seconds
            attendance.status = 'absent'
            attendance.review_status = 'not_required'
            attendance.notes = 'لا توجد سجلات بصمة لهذا اليوم.'
            attendance.save()
            return attendance

        check_in = relevant_logs[0].punch_time
        check_out = relevant_logs[-1].punch_time if len(relevant_logs) > 1 else None
        attendance = cls._populate_attendance_metrics(
            attendance=attendance,
            shift=shift,
            policy=policy,
            check_in=check_in,
            check_out=check_out,
            notes=f'طھظ…طھ ط§ظ„ظ…ط²ط§ظ…ظ†ط© ظ…ظ† {len(relevant_logs)} ط³ط¬ظ„ط§طھ ط¨طµظ…ط©.',
            source='biometric',
        )
        attendance.save()
        return attendance
        worked_seconds = _seconds_between(check_in, check_out) if check_out else 0
        if shift.break_seconds:
            worked_seconds = max(0, worked_seconds - shift.break_seconds)

        grace_seconds = shift.grace_period_minutes * 60
        late_seconds = max(0, _seconds_between(shift_start, check_in) - grace_seconds)
        early_leave_seconds = max(0, _seconds_between(check_out, shift_end)) if check_out and check_out < shift_end else 0
        absence_seconds = max(0, shift.required_work_seconds - worked_seconds)
        overtime_seconds = max(0, worked_seconds - shift.required_work_seconds)

        rounding_method = getattr(policy, 'rounding_method', 'minute')
        late_seconds = _apply_rounding(late_seconds, rounding_method)
        early_leave_seconds = _apply_rounding(early_leave_seconds, rounding_method)
        overtime_seconds = _apply_rounding(overtime_seconds, rounding_method)

        attendance.check_in = check_in
        attendance.check_out = check_out
        attendance.worked_seconds = worked_seconds
        attendance.late_seconds = late_seconds
        attendance.early_leave_seconds = early_leave_seconds
        attendance.overtime_seconds = overtime_seconds
        attendance.absence_seconds = absence_seconds
        if absence_seconds >= shift.required_work_seconds:
            attendance.status = 'absent'
        elif late_seconds or early_leave_seconds:
            attendance.status = 'late'
        elif worked_seconds < shift.required_work_seconds:
            attendance.status = 'partial'
        else:
            attendance.status = 'present'
        attendance.notes = f'تمت المزامنة من {len(relevant_logs)} سجلات بصمة.'
        attendance.save()
        return attendance
    @classmethod
    def apply_manual_adjustment(cls, attendance, *, check_in, check_out, review_status, review_notes, notes, manual_adjustment_reason, reviewer=None):
        shift = attendance.employee.effective_shift
        policy = attendance.employee.effective_attendance_policy

        if shift:
            attendance = cls._populate_attendance_metrics(
                attendance=attendance,
                shift=shift,
                policy=policy,
                check_in=check_in,
                check_out=check_out,
                notes=notes or attendance.notes,
                source='manual',
            )
        else:
            attendance.check_in = check_in
            attendance.check_out = check_out
            attendance.notes = notes or attendance.notes
            attendance.source = 'manual'

        attendance.review_status = review_status
        attendance.review_notes = review_notes
        attendance.reviewed_by = reviewer
        attendance.reviewed_at = timezone.now() if reviewer else attendance.reviewed_at
        attendance.is_manually_adjusted = True
        attendance.manual_adjustment_reason = manual_adjustment_reason
        attendance.save()
        return attendance


class LivePayrollService:
    @classmethod
    def preview_for_period(cls, employee, year, month):
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        return cls.preview(employee, start_date, end_date)

    @classmethod
    def preview(cls, employee, start_date, end_date):
        shift = employee.effective_shift
        rule = employee.effective_salary_rule
        policy = employee.effective_attendance_policy
        attendances = list(
            EmployeeAttendance.objects.filter(
                employee=employee,
                date__gte=start_date,
                date__lte=end_date,
            ).order_by('date')
        )

        if not attendances and shift:
            AttendanceGenerationService.sync_range(employee, start_date, end_date)
            attendances = list(
                EmployeeAttendance.objects.filter(
                    employee=employee,
                    date__gte=start_date,
                    date__lte=end_date,
                ).order_by('date')
            )

        base_salary = _decimal(employee.salary)
        total_worked_seconds = sum(item.worked_seconds for item in attendances)
        total_late_seconds = sum(item.late_seconds for item in attendances)
        total_early_leave_seconds = sum(item.early_leave_seconds for item in attendances)
        present_count = sum(1 for item in attendances if item.status == 'present')
        late_count = sum(1 for item in attendances if item.status == 'late')
        partial_count = sum(1 for item in attendances if item.status == 'partial')
        absent_count = sum(1 for item in attendances if item.status == 'absent')
        vacation_attendance_count = sum(1 for item in attendances if item.status == 'vacation')
        deductible_attendances = [
            item for item in attendances
            if item.review_status in {'not_required', 'unjustified'}
        ]
        deductible_late_seconds = sum(item.late_seconds for item in deductible_attendances)
        deductible_early_leave_seconds = sum(item.early_leave_seconds for item in deductible_attendances)
        pending_review_count = sum(1 for item in attendances if item.review_status == 'pending')
        total_overtime_seconds = sum(item.overtime_seconds for item in attendances)
        total_absence_seconds = sum(item.absence_seconds for item in attendances)

        advances = list(
            EmployeeAdvance.objects.filter(
                employee=employee,
                is_repaid=False,
                date__gte=start_date,
                date__lte=end_date,
            )
        )
        approved_vacations = list(
            Vacation.objects.filter(
                employee=employee,
                status='موافق',
                start_date__lte=end_date,
                end_date__gte=start_date,
            )
        )

        salary_type = getattr(employee, 'payroll_method', '') or (getattr(rule, 'salary_type', 'monthly') if rule else 'monthly')
        salary_type_display = dict(getattr(rule, 'SALARY_TYPE_CHOICES', [])).get(salary_type, salary_type) if rule else 'شهري'
        required_daily_seconds = shift.required_work_seconds if shift else 28800
        period_days = max((end_date - start_date).days + 1, 1)
        required_period_seconds = _employee_required_monthly_seconds(employee, shift, start_date, end_date)
        payable_days = present_count + late_count + partial_count
        hourly_rate = _decimal(getattr(employee, 'hourly_rate', 0))
        overtime_hourly_rate = _decimal(getattr(employee, 'overtime_hourly_rate', 0))

        if salary_type == 'hourly':
            gross_salary = hourly_rate * (Decimal(total_worked_seconds) / Decimal('3600'))
        elif salary_type == 'mixed':
            gross_salary = base_salary + (hourly_rate * (Decimal(total_worked_seconds) / Decimal('3600')))
        else:
            gross_salary = base_salary

        hourly_basis = hourly_rate
        hourly_basis_source = 'manual' if hourly_basis else 'derived'
        if not hourly_basis:
            if required_period_seconds:
                hourly_basis = base_salary / (Decimal(required_period_seconds) / Decimal('3600')) if base_salary else Decimal('0')
            elif base_salary:
                hourly_basis = base_salary / Decimal('30') / Decimal('8')
                hourly_basis_source = 'estimated'
            else:
                hourly_basis_source = 'missing'

        overtime_multiplier = getattr(rule, 'overtime_multiplier', Decimal('1.00')) if rule else Decimal('1.00')
        if rule and rule.max_overtime_seconds:
            total_overtime_seconds = min(total_overtime_seconds, rule.max_overtime_seconds)
        overtime_basis = overtime_hourly_rate or (hourly_basis * overtime_multiplier)
        overtime_amount = overtime_basis * (Decimal(total_overtime_seconds) / Decimal('3600'))

        late_deduction = Decimal('0')
        if not rule or rule.late_deduction_enabled:
            late_deduction = hourly_basis * (Decimal(deductible_late_seconds + deductible_early_leave_seconds) / Decimal('3600'))

        absence_deduction = Decimal('0')
        if not rule or rule.absence_deduction_enabled:
            if salary_type in {'monthly', 'mixed'} and required_period_seconds:
                absence_deduction = gross_salary * (Decimal(total_absence_seconds) / Decimal(required_period_seconds))
            else:
                absence_deduction = hourly_basis * (Decimal(total_absence_seconds) / Decimal('3600'))

        deductions_total = late_deduction + absence_deduction
        if rule and rule.max_deduction_amount:
            deductions_total = min(deductions_total, rule.max_deduction_amount)
            original_total = late_deduction + absence_deduction
            if original_total > 0:
                scale = deductions_total / original_total
                late_deduction *= scale
                absence_deduction *= scale

        advance_amount = sum((adv.outstanding_amount for adv in advances), Decimal('0.00'))
        tax_total = (gross_salary * _decimal(getattr(rule, 'tax_percent', 0)) / Decimal('100')) if rule else Decimal('0.00')
        insurance_total = (gross_salary * _decimal(getattr(rule, 'insurance_percent', 0)) / Decimal('100')) if rule else Decimal('0.00')
        compensation_total = Decimal('0.00')

        gross_salary = _quantize_money(gross_salary)
        overtime_amount = _quantize_money(overtime_amount)
        late_deduction = _quantize_money(late_deduction)
        absence_deduction = _quantize_money(absence_deduction)
        deductions_total = _quantize_money(deductions_total)
        advance_amount = _quantize_money(advance_amount)
        tax_total = _quantize_money(tax_total)
        insurance_total = _quantize_money(insurance_total)
        compensation_total = _quantize_money(compensation_total)
        gross_before_deductions = _quantize_money(gross_salary + overtime_amount + compensation_total)
        withheld_total = _quantize_money(deductions_total + advance_amount + tax_total + insurance_total)
        net_salary = _quantize_money(gross_salary + overtime_amount + compensation_total - deductions_total - advance_amount - tax_total - insurance_total)

        return {
            'employee': employee,
            'start_date': start_date,
            'end_date': end_date,
            'base_salary': _quantize_money(base_salary),
            'gross_salary': gross_salary,
            'gross_before_deductions': gross_before_deductions,
            'overtime_total': overtime_amount,
            'deductions_total': deductions_total,
            'late_deduction_total': late_deduction,
            'absence_deduction_total': absence_deduction,
            'advances_total': advance_amount,
            'tax_total': tax_total,
            'insurance_total': insurance_total,
            'compensation_total': compensation_total,
            'withheld_total': withheld_total,
            'net_salary': net_salary,
            'attendance_count': len(attendances),
            'vacation_count': len(approved_vacations),
            'present_count': present_count,
            'late_count': late_count,
            'partial_count': partial_count,
            'absent_count': absent_count,
            'payable_days': payable_days,
            'period_days': period_days,
            'worked_seconds': total_worked_seconds,
            'late_seconds': total_late_seconds,
            'early_leave_seconds': total_early_leave_seconds,
            'deductible_late_seconds': deductible_late_seconds,
            'deductible_early_leave_seconds': deductible_early_leave_seconds,
            'pending_review_count': pending_review_count,
            'overtime_seconds': total_overtime_seconds,
            'absence_seconds': total_absence_seconds,
            'required_period_seconds': required_period_seconds,
            'salary_type': salary_type,
            'salary_type_display': salary_type_display,
            'hourly_basis': _quantize_money(hourly_basis),
            'hourly_basis_source': hourly_basis_source,
            'salary_rule': rule,
            'attendance_policy': policy,
            'shift': shift,
            'shift_name': shift.name if shift else '',
            'rule_name': rule.name if rule else '',
            'policy_name': policy.name if policy else '',
            'department_name': employee.department.name if employee.department else '',
            'biometric_user_id': employee.biometric_user_id or '',
            'advances': advances,
            'vacations': approved_vacations,
            'attendances': attendances,
            'lines': [
                ('راتب أساسي', gross_salary),
                ('إضافي', overtime_amount),
                ('خصومات دوام', deductions_total),
                ('سلف', advance_amount),
                ('ضريبة', tax_total),
                ('تأمين', insurance_total),
            ],
        }


class PayrollGenerationService:
    @classmethod
    @transaction.atomic
    def generate_period(cls, period):
        if isinstance(period, int):
            period = PayrollPeriod.objects.get(pk=period)

        period.status = 'processing'
        period.save(update_fields=['status'])

        payrolls = []
        employees = Employee.objects.select_related('salary_rule', 'attendance_policy', 'default_shift').filter(
            employment_status='active'
        )

        for employee in employees:
            preview = LivePayrollService.preview(employee, period.start_date, period.end_date)
            payroll, _ = EmployeePayroll.objects.update_or_create(
                employee=employee,
                period=period,
                defaults={
                    'gross_salary': preview['gross_salary'],
                    'deductions_total': preview['deductions_total'],
                    'overtime_total': preview['overtime_total'],
                    'advances_total': preview['advances_total'],
                    'tax_total': preview['tax_total'],
                    'insurance_total': preview['insurance_total'],
                    'compensation_total': preview['compensation_total'],
                    'net_salary': preview['net_salary'],
                }
            )
            payroll.lines.all().delete()

            line_map = [
                ('base_salary', 'الراتب الأساسي', preview['gross_salary']),
                ('overtime', 'الإضافي', preview['overtime_total']),
                ('late_deduction', 'خصومات الدوام', -preview['deductions_total']),
                ('advance_deduction', 'السلف', -preview['advances_total']),
                ('tax', 'الضريبة', -preview['tax_total']),
                ('insurance', 'التأمين', -preview['insurance_total']),
                ('adjustment', 'الصافي', preview['net_salary']),
            ]
            for line_type, title, amount in line_map:
                EmployeePayrollLine.objects.create(
                    payroll=payroll,
                    line_type=line_type,
                    title=title,
                    amount=amount,
                )
            payrolls.append(payroll)

        period.status = 'closed'
        period.save(update_fields=['status'])
        return payrolls


class AttendanceReportService:
    @classmethod
    def summary_for_month(cls, year, month):
        rows = EmployeeAttendance.objects.filter(date__year=year, date__month=month).select_related('employee__user')
        grouped = defaultdict(lambda: {
            'attendance_days': 0,
            'worked_seconds': 0,
            'late_seconds': 0,
            'absence_seconds': 0,
            'overtime_seconds': 0,
        })
        for row in rows:
            bucket = grouped[row.employee_id]
            bucket['employee'] = row.employee
            bucket['attendance_days'] += 1
            bucket['worked_seconds'] += row.worked_seconds
            bucket['late_seconds'] += row.late_seconds
            bucket['absence_seconds'] += row.absence_seconds
            bucket['overtime_seconds'] += row.overtime_seconds
        return list(grouped.values())
