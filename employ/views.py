from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View, TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse, HttpResponseForbidden
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.decorators import method_decorator
from django.utils.html import escape
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.core.exceptions import FieldDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string 
from django.contrib.staticfiles import finders
from django.conf import settings

from accounts.models import ExpenseEntry, EmployeeAdvance, Account, TeacherAdvance, get_or_create_employee_cash_account
from accounts.forms import EmployeeAdvanceForm
from attendance.models import TeacherAttendance

from .models import (
    AttendancePolicy,
    BiometricDevice,
    BiometricLog,
    Department,
    Employee,
    EmployeeAttendance,
    EmployeePayroll,
    EmployeePermission,
    EmployeeSalaryRule,
    HRHoliday,
    JobTitle,
    ManualTeacherSalary,
    PayrollPeriod,
    Shift,
    Teacher,
    Vacation,
)
from .forms import (
    AdminVacationForm,
    AttendanceFilterForm,
    AttendancePolicyForm,
    EmployeeAttendanceUpdateForm,
    BiometricDeviceForm,
    BiometricImportForm,
    DepartmentForm,
    JobTitleForm,
    EmployeeProfileForm,
    EmployeeRegistrationForm,
    EmployeeSalaryRuleForm,
    HRHolidayForm,
    PayrollPeriodForm,
    ShiftForm,
    TeacherForm,
)
from .services import (
    AttendanceGenerationService,
    AttendanceReportService,
    BiometricImportService,
    LivePayrollService,
    PayrollGenerationService,
)
from .biometric_sync import BiometricAutoSyncService
from .email_notifications import send_weekly_biometric_summary
try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None
try:
    from weasyprint import HTML
    from weasyprint.urls import default_url_fetcher
    WEASYPRINT_AVAILABLE = True
except Exception:
    HTML = None
    default_url_fetcher = None
    WEASYPRINT_AVAILABLE = False
import os
import tempfile
import io
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from urllib.parse import quote


# -----------------------------
# أدوات مساعدة
# -----------------------------
def _employee_full_name(employee):
    """إرجاع اسم الموظف للعرض بأولوية: Employee.full_name -> User.get_full_name -> username"""
    if not employee:
        return ''
    name_attr = getattr(employee, 'full_name', None)
    if name_attr:
        return name_attr
    user = getattr(employee, 'user', None)
    if user:
        full_name = user.get_full_name()
        return full_name if full_name else user.get_username()
    return str(employee)


def _safe_period_int(value, default, min_value=None, max_value=None):
    """Parse year/month query values safely, including thousands separators like 2.026."""
    if value in (None, ''):
        parsed_value = default
    else:
        try:
            parsed_value = int(value)
        except (TypeError, ValueError):
            normalized = str(value).strip().translate(str.maketrans('', '', '., \u066c'))
            parsed_value = int(normalized) if normalized.isdigit() else default

    if min_value is not None and parsed_value < min_value:
        return default
    if max_value is not None and parsed_value > max_value:
        return default
    return parsed_value


def _same_day_last_year(target_date):
    try:
        return target_date.replace(year=target_date.year - 1)
    except ValueError:
        return target_date.replace(year=target_date.year - 1, day=28)


def _safe_date_param(value, default):
    if not value:
        return default
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return default


def _seconds_between(start, end):
    if not start or not end:
        return 0
    return max(0, int((end - start).total_seconds()))


def _attendance_metrics_from_employee_shift(attendance):
    employee = attendance.employee
    shift = employee.effective_shift if employee else None
    check_in = attendance.check_in
    check_out = attendance.check_out
    worked_seconds = _seconds_between(check_in, check_out) if check_in and check_out else 0

    if not shift:
        return {
            'worked_seconds': worked_seconds,
            'late_seconds': attendance.late_seconds or 0,
            'early_leave_seconds': attendance.early_leave_seconds or 0,
            'overtime_seconds': attendance.overtime_seconds or 0,
            'absence_seconds': attendance.absence_seconds or 0,
            'required_work_seconds': 0,
        }

    shift_start, shift_end = shift.get_bounds_for_date(attendance.date)
    break_seconds = getattr(shift, 'break_seconds', 0) or 0
    required_work_seconds = getattr(shift, 'required_work_seconds', 0) or employee.get_required_daily_seconds()
    grace_seconds = (getattr(shift, 'grace_period_minutes', 0) or 0) * 60
    policy = employee.effective_attendance_policy
    rounding_method = getattr(policy, 'rounding_method', 'minute') if policy else 'minute'

    late_seconds = max(0, _seconds_between(shift_start, check_in) - grace_seconds) if check_in else 0
    early_leave_seconds = _seconds_between(check_out, shift_end) if check_out and check_out < shift_end else 0
    overtime_seconds = _seconds_between(shift_end, check_out) if check_out and check_out > shift_end else 0
    worked_seconds = max(0, worked_seconds - break_seconds)
    absence_seconds = max(0, required_work_seconds - worked_seconds)

    def apply_rounding(seconds):
        if seconds <= 0:
            return 0
        if rounding_method == 'none':
            return seconds
        if rounding_method == '5_minutes':
            unit = 300
        elif rounding_method == '15_minutes':
            unit = 900
        else:
            unit = 60
        return int(round(seconds / unit) * unit)

    return {
        'worked_seconds': worked_seconds,
        'late_seconds': apply_rounding(late_seconds),
        'early_leave_seconds': apply_rounding(early_leave_seconds),
        'overtime_seconds': apply_rounding(overtime_seconds),
        'absence_seconds': absence_seconds,
        'required_work_seconds': required_work_seconds,
    }


def _employee_shift_label(employee):
    shift = employee.effective_shift if employee else None
    if not shift:
        return '-'
    start_time = getattr(shift, 'start_time', None)
    end_time = getattr(shift, 'end_time', None)
    if start_time and end_time:
        return f'{start_time:%H:%M} - {end_time:%H:%M}'
    return str(shift)


def _date_range(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _holiday_from_list(target_date, holidays):
    for holiday in holidays:
        if holiday.start_date <= target_date <= holiday.end_date:
            return holiday
    return None


def _overlap_days(start_a, end_a, start_b, end_b):
    start = max(start_a, start_b)
    end = min(end_a, end_b)
    if start > end:
        return 0
    return (end - start).days + 1


# خريطة المجموعات بحسب بادئة كود الصلاحية
GROUP_PREFIXES = {
    'students_': 'students',
    'teachers_': 'teachers',
    'attendance_': 'attendance',
    'classroom_': 'classroom',
    'quick_students_': 'quick_students',
    'exams_': 'exams',
    'errors_': 'errors',
    'registration_': 'registration',
    'courses_': 'courses',
    'accounting_': 'accounting',
    'hr_': 'hr',
    'admin_': 'admin',
    'reports_': 'reports',
    'course_accounting_': 'course_accounting',
    'inventory_': 'inventory',
    'assets_': 'inventory',
    'marketing_': 'marketing',
    'quality_': 'quality',
}


def _empty_permission_groups():
    """نضمن وجود جميع المفاتيح دائماً (حتى لو كانت القوائم فارغة)."""
    return {
        'sidebar_links': [],
        'students': [],
        'teachers': [],
        'attendance': [],
        'classroom': [],
        'quick_students': [],
        'exams': [],
        'errors': [],
        'pages': [],
        'registration': [],
        'courses': [],
        'accounting': [],
        'hr': [],
        'admin': [],
        'reports': [],
        'course_accounting': [],
        'inventory': [],
        'marketing': [],
        'quality': [],
    }


def _group_for_code(code: str):
    sidebar_codes = {
        'admin_dashboard', 'reports_dashboard', 'admin_system_report',
        'announcements_view', 'technical_services_view', 'manuals_view',
        'sitemap_view', 'students_course_audit', 'students_manual_sorting',
        'academic_years_select', 'academic_years_manage', 'students_view',
        'quick_students_view', 'teachers_view', 'accounting_dashboard',
        'accounting_view', 'reports_financial', 'attendance_view',
        'attendance_teacher_view', 'classroom_view', 'exams_view',
        'hr_dashboard', 'hr_view', 'courses_view', 'admin_users',
        'accounting_receipts', 'accounting_expenses'
    }
    if code in sidebar_codes:
        return 'sidebar_links'

    """استخرج اسم المجموعة من بادئة كود الصلاحية."""
    for prefix, group in GROUP_PREFIXES.items():
        if code.startswith(prefix):
            return group
    return None


# -----------------------------
# إدارة صلاحيات الموظف
# -----------------------------
class EmployeePermissionsView(LoginRequiredMixin, View):
    template_name = 'employ/employee_permissions.html'

    def get(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)

        # الصلاحيات الممنوحة حاليًا
        granted = set(
            employee.permissions.filter(is_granted=True).values_list('permission', flat=True)
        )

        # بناء القوائم
        permission_groups = _empty_permission_groups()

        for code, label in EmployeePermission.PERMISSION_CHOICES:
            group = _group_for_code(code)
            if not group:
                continue
            permission_groups[group].append({
                'code': code,
                'label': label,
                'is_granted': code in granted
            })

        cash_account = employee.get_cash_account()
        cash_account_balance = cash_account.get_net_balance() if cash_account else Decimal('0.00')

        return render(request, self.template_name, {
            'employee': employee,
            'permission_groups': permission_groups,
            'cash_account': cash_account,
            'cash_account_balance': cash_account_balance
        })




    @transaction.atomic
    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)

        # الصلاحيات المختارة
        selected_codes = set(request.POST.getlist('permissions'))

        # ببساطة: فعّل ما تم تحديده، وعطّل الباقي
        existing = {ep.permission: ep for ep in employee.permissions.all()}

        for code, _label in EmployeePermission.PERMISSION_CHOICES:
            should_grant = code in selected_codes
            if code in existing:
                ep = existing[code]
                if ep.is_granted != should_grant:
                    ep.is_granted = should_grant
                    ep.granted_by = request.user if should_grant else ep.granted_by
                    ep.save(update_fields=['is_granted', 'granted_by'])
            else:
                if should_grant:
                    EmployeePermission.objects.create(
                        employee=employee,
                        permission=code,
                        is_granted=True,
                        granted_by=request.user
                    )

        messages.success(request, f'تم تحديث صلاحيات الموظف { _employee_full_name(employee) } بنجاح.')
        return redirect('employ:employee_permissions', pk=pk)


class CreateEmployeeCashAccountView(LoginRequiredMixin, View):
    def post(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk)
        employee_name = _employee_full_name(employee) or employee.user.get_username()

        try:
            account, created = get_or_create_employee_cash_account(employee)
            if created:
                messages.success(
                    request,
                    f'Created cash account {account.code} for {employee_name}.'
                )
            else:
                messages.info(
                    request,
                    f'Cash account {account.code} for {employee_name} already exists.'
                )
        except Exception as exc:
            messages.error(
                request,
                f'Failed to create cash account: {exc}'
            )

        return redirect('employ:employee_permissions', pk=employee.pk)


# -----------------------------
# سلف الموظفين
# -----------------------------
class EmployeeAdvanceListView(LoginRequiredMixin, ListView):
    model = EmployeeAdvance
    template_name = 'employ/employee_advance_list.html'
    context_object_name = 'advances'

    def get_queryset(self):
        return EmployeeAdvance.objects.select_related('employee__user', 'created_by').order_by('-date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        advances = self.get_queryset()
        context['total_advances'] = advances.count()
        context['outstanding_advances'] = advances.filter(is_repaid=False).count()
        context['total_outstanding_amount'] = sum(adv.outstanding_amount for adv in advances.filter(is_repaid=False))
        context['total_advance_amount'] = sum(adv.amount for adv in advances)
        return context


class EmployeeAdvanceCreateView(LoginRequiredMixin, CreateView):
    model = EmployeeAdvance
    form_class = EmployeeAdvanceForm
    template_name = 'employ/employee_advance_form.html'
    success_url = reverse_lazy('employ:employee_advance_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        # قيد محاسبي
        try:
            self.object.create_advance_journal_entry(self.request.user)
            messages.success(
                self.request,
                f'تم إنشاء سلفة للموظف {self.object.employee.user.get_full_name()} بمبلغ {self.object.amount} ل.س'
            )
        except Exception as e:
            messages.error(self.request, f'خطأ في إنشاء القيد المحاسبي: {e}')
        return response


class EmployeeAdvanceDetailView(LoginRequiredMixin, DetailView):
    model = EmployeeAdvance
    template_name = 'employ/employee_advance_detail.html'
    context_object_name = 'advance'


class EmployeeAdvanceRepayView(LoginRequiredMixin, View):
    def post(self, request, pk):
        advance = get_object_or_404(EmployeeAdvance, pk=pk)
        display_name = advance.employee.user.get_full_name() or advance.employee.user.get_username()

        try:
            repayment_amount = Decimal(str(request.POST.get('repayment_amount', '0')))
        except (ValueError, InvalidOperation):
            repayment_amount = Decimal('0')

        if repayment_amount <= 0:
            messages.error(request, 'يجب إدخال مبلغ سداد صحيح.')
            return redirect('employ:employee_advance_detail', pk=pk)

        if repayment_amount > advance.outstanding_amount:
            messages.error(request, 'مبلغ السداد أكبر من المبلغ المتبقي.')
            return redirect('employ:employee_advance_detail', pk=pk)

        try:
            advance.create_repayment_entry(repayment_amount, request.user)
            messages.success(request, f'تم تسجيل سداد سلفة {display_name} بنجاح.')
        except Exception as e:
            messages.error(request, f'تعذر تسجيل السداد: {e}')

        return redirect('employ:employee_advance_detail', pk=pk)


# -----------------------------
# المدرّسون
# -----------------------------
class teachers(LoginRequiredMixin, ListView):
    model = Teacher
    template_name = 'employ/teachers.html'
    context_object_name = 'teachers'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teachers = context.get('teachers') or context.get('object_list') or Teacher.objects.all()

        today = timezone.now().date()
        current_year = today.year
        current_month = today.month

        # فترة الراتب الافتراضية
        if today.day >= 25:
            period_date = today
        else:
            period_date = today.replace(day=1) - timedelta(days=1)

        salary_year = period_date.year
        salary_month = period_date.month

        teachers_data = []
        paid_count = 0
        unpaid_count = 0

        for teacher in teachers:
            monthly_sessions = teacher.get_monthly_sessions(salary_year, salary_month)
            salary_amount = teacher.calculate_monthly_salary(salary_year, salary_month)
            
            # التحقق من الرواتب اليدوية المدفوعة
            salary_status = ManualTeacherSalary.objects.filter(
                teacher=teacher,
                year=salary_year,
                month=salary_month,
                is_paid=True
            ).exists()

            paid_count += 1 if salary_status else 0
            unpaid_count += 0 if salary_status else 1

            teachers_data.append({
                'teacher': teacher,
                'monthly_sessions': monthly_sessions,
                'calculated_salary': salary_amount,
                'salary_status': salary_status,
            })

        today_sessions = (TeacherAttendance.objects
                          .filter(date=today, status='present')
                          .aggregate(total=Sum('session_count'))['total'] or 0)

        context.update({
            'today': today,
            'salary_year': salary_year,
            'salary_month': salary_month,
            'salary_period_label': f"{salary_year}/{salary_month:02d}",
            'salary_period_is_current': (salary_year == current_year and salary_month == current_month),
            'teachers_data': teachers_data,
            'paid_count': paid_count,
            'unpaid_count': unpaid_count,
            'today_sessions': today_sessions,
        })
        return context


def _prepare_teacher_cards(teachers):
    for teacher in teachers:
        try:
            teacher.branch_display = teacher.get_branch_display()
        except Exception:
            teacher.branch_display = getattr(teacher, 'branch', '')


def _teacher_cards_pdf_link_callback(uri, rel):
    if uri.startswith('http://') or uri.startswith('https://'):
        return uri

    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ''))
    elif uri.startswith(settings.STATIC_URL):
        path = finders.find(uri.replace(settings.STATIC_URL, ''))
    else:
        path = finders.find(uri)

    if not path:
        return uri

    if isinstance(path, (list, tuple)):
        path = path[0]
    return path


def _register_pdf_fonts():
    try:
        font_regular = finders.find('font/Cairo-400.ttf')
        font_bold = finders.find('font/Cairo-600.ttf') or font_regular
        font_black = finders.find('font/Cairo-800.ttf') or font_bold or font_regular

        if font_regular:
            pdfmetrics.registerFont(TTFont('Cairo', font_regular))
        if font_bold and font_bold != font_regular:
            pdfmetrics.registerFont(TTFont('Cairo-Bold', font_bold))
        if font_black and font_black not in (font_regular, font_bold):
            pdfmetrics.registerFont(TTFont('Cairo-Black', font_black))

        if font_regular:
            registerFontFamily(
                'Cairo',
                normal='Cairo',
                bold='Cairo-Bold' if font_bold else 'Cairo',
                italic='Cairo',
                boldItalic='Cairo-Bold' if font_bold else 'Cairo',
            )
    except Exception:
        pass


def _teacher_weasyprint_url_fetcher(url):
    if not default_url_fetcher:
        return None

    if url.startswith(settings.STATIC_URL):
        path = finders.find(url.replace(settings.STATIC_URL, ''))
    elif url.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, url.replace(settings.MEDIA_URL, ''))
    else:
        return default_url_fetcher(url)

    if not path:
        return default_url_fetcher(url)

    if isinstance(path, (list, tuple)):
        path = path[0]

    return default_url_fetcher(f'file://{path}')


def _inline_css_vars(html):
    css_vars = {
        'ink': '#0e1424',
        'muted': '#9fa6b6',
        'paper': '#ffffff',
        'line': '#d8e0ef',
        'purple': '#513996',
        'purple-dark': '#4f2f86',
        'purple-light': '#6b4aa7',
        'gold': '#f0a22b',
        'teal': '#0b6c8e',
        'grid': 'rgba(255, 255, 255, 0.08)',
        'card-width': '100mm',
        'card-height': '60mm',
    }

    for key, value in css_vars.items():
        html = html.replace(f'var(--{key})', value)
    return html


class TeacherCardsPrintView(LoginRequiredMixin, TemplateView):
    template_name = 'employ/teacher_cards_print.html'
    app_download_url = 'https://yaman2.pythonanywhere.com/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        should_generate = self.request.GET.get('generate') == '1'
        teachers = []

        if should_generate:
            teachers = list(Teacher.objects.all().order_by('full_name'))

        _prepare_teacher_cards(teachers)

        per_page = 8
        pages = [teachers[i:i + per_page] for i in range(0, len(teachers), per_page)]
        if should_generate and not pages:
            pages = [[]]

        context.update({
            'should_generate': should_generate,
            'pages': pages,
            'teachers_total': len(teachers),
            'app_download_url': self.app_download_url,
            'app_qr_url': f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={quote(self.app_download_url)}",
            'pdf': False,
        })
        return context


def teacher_cards_print_pdf(request):
    should_generate = request.GET.get('generate') == '1'
    teachers = []

    if should_generate:
        teachers = list(Teacher.objects.all().order_by('full_name'))

    _prepare_teacher_cards(teachers)

    per_page = 8
    pages = [teachers[i:i + per_page] for i in range(0, len(teachers), per_page)]
    if should_generate and not pages:
        pages = [[]]

    app_download_url = 'https://yaman2.pythonanywhere.com/'
    context = {
        'should_generate': should_generate,
        'pages': pages,
        'teachers_total': len(teachers),
        'app_download_url': app_download_url,
        'app_qr_url': f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={quote(app_download_url)}",
        'pdf': True,
    }

    html = render_to_string('employ/teacher_cards_print.html', context, request=request)
    tmp_dir = os.path.join(settings.BASE_DIR, '_tmp_pdf')
    os.makedirs(tmp_dir, exist_ok=True)
    os.environ['TMP'] = tmp_dir
    os.environ['TEMP'] = tmp_dir
    tempfile.tempdir = tmp_dir

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=\"teacher_cards.pdf\"'

    if WEASYPRINT_AVAILABLE:
        pdf_bytes = HTML(
            string=html,
            base_url=request.build_absolute_uri('/'),
            url_fetcher=_teacher_weasyprint_url_fetcher,
        ).write_pdf()
        response.write(pdf_bytes)
        return response

    _register_pdf_fonts()
    html = _inline_css_vars(html)
    pisa.CreatePDF(html, dest=response, link_callback=_teacher_cards_pdf_link_callback, encoding='UTF-8')
    return response


class CreateTeacherView(LoginRequiredMixin, CreateView):
    model = Teacher
    form_class = TeacherForm
    template_name = 'employ/teacher_form.html'
    success_url = reverse_lazy('employ:teachers')

    def form_valid(self, form):
        messages.success(self.request, 'تم إنشاء بيانات المعلم بنجاح.')
        return super().form_valid(form)

class TeacherUpdateView(LoginRequiredMixin, UpdateView):
    model = Teacher
    form_class = TeacherForm
    template_name = 'employ/teacher_form.html'
    success_url = reverse_lazy('employ:teachers')

    def form_valid(self, form):
        teacher = form.save(commit=False)
        academic_year = form.cleaned_data.get('academic_year')
        
        if academic_year:
            from employ.models import TeacherAcademicSalaryRate
            from decimal import Decimal
            rate_obj, _ = TeacherAcademicSalaryRate.objects.get_or_create(
                teacher=teacher,
                academic_year=academic_year
            )
            rate_obj.hourly_rate_scientific = form.cleaned_data.get('hourly_rate_scientific') or Decimal('0.00')
            rate_obj.hourly_rate_literary = form.cleaned_data.get('hourly_rate_literary') or Decimal('0.00')
            rate_obj.hourly_rate_ninth = form.cleaned_data.get('hourly_rate_ninth') or Decimal('0.00')
            rate_obj.hourly_rate_preparatory = form.cleaned_data.get('hourly_rate_preparatory') or Decimal('0.00')
            rate_obj.hourly_rate = form.cleaned_data.get('hourly_rate') or Decimal('0.00')
            rate_obj.monthly_salary = form.cleaned_data.get('monthly_salary') or Decimal('0.00')
            rate_obj.salary_type = form.cleaned_data.get('salary_type') or 'hourly'
            rate_obj.save()
            
            # Restore original default base rates to base teacher
            if teacher.pk:
                original = Teacher.objects.get(pk=teacher.pk)
                teacher.hourly_rate_scientific = original.hourly_rate_scientific
                teacher.hourly_rate_literary = original.hourly_rate_literary
                teacher.hourly_rate_ninth = original.hourly_rate_ninth
                teacher.hourly_rate_preparatory = original.hourly_rate_preparatory
                teacher.hourly_rate = original.hourly_rate
                teacher.monthly_salary = original.monthly_salary
                teacher.salary_type = original.salary_type
                
        teacher.save()
        form.save_m2m()
        messages.success(self.request, 'تم تحديث بيانات المعلم بنجاح.')
        from django.shortcuts import redirect
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.object
        
        # Serialize year-specific rates
        import json
        rates_data = {}
        for rate in teacher.academic_salary_rates.all():
            rates_data[rate.academic_year_id] = {
                'scientific': float(rate.hourly_rate_scientific),
                'literary': float(rate.hourly_rate_literary),
                'ninth': float(rate.hourly_rate_ninth),
                'preparatory': float(rate.hourly_rate_preparatory),
                'hourly_rate': float(rate.hourly_rate),
                'monthly_salary': float(rate.monthly_salary),
                'salary_type': rate.salary_type,
            }
        context['rates_json'] = json.dumps(rates_data)
        return context


# -----------------------------
# الموارد البشرية (قائمة الموظفين)
# -----------------------------
class hr(ListView):
    template_name = 'employ/hr.html'
    model = Employee
    context_object_name = 'employees'

    def get_queryset(self):
        queryset = Employee.objects.select_related(
            'user', 'department', 'job_title', 'default_shift', 'salary_rule'
        ).all()
        position = self.request.GET.get('position')
        search = self.request.GET.get('search')
        department = self.request.GET.get('department')

        if position:
            queryset = queryset.filter(position=position)

        if department:
            queryset = queryset.filter(department_id=department)

        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(employee_code__icontains=search) |
                Q(biometric_user_id__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        month_start = today.replace(day=1)
        pending_reviews = EmployeeAttendance.objects.filter(review_status='pending')
        active_employees = context['employees'].filter(employment_status='active')
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['employee_count'] = context['employees'].count()
        context['active_employee_count'] = active_employees.count()
        context['biometric_ready_count'] = context['employees'].exclude(biometric_user_id__isnull=True).exclude(biometric_user_id='').count()
        context['missing_biometric_count'] = active_employees.filter(Q(biometric_user_id__isnull=True) | Q(biometric_user_id='')).count()
        context['pending_reviews_count'] = pending_reviews.count()
        context['pending_early_leave_count'] = pending_reviews.filter(early_leave_seconds__gt=0).count()
        context['monthly_absent_count'] = EmployeeAttendance.objects.filter(date__gte=month_start, date__lte=today, status='absent').count()
        context['monthly_overtime_seconds'] = EmployeeAttendance.objects.filter(date__gte=month_start, date__lte=today).aggregate(total=Sum('overtime_seconds'))['total'] or 0
        context['open_vacations_count'] = Vacation.objects.filter(start_date__lte=today, end_date__gte=today).count()
        return context


class EmployeeCreateView(CreateView):
    form_class = EmployeeRegistrationForm
    template_name = 'employ/employee_form.html'
    success_url = reverse_lazy('employ:hr')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['job_titles_json'] = list(
            JobTitle.objects.filter(is_active=True).select_related('department').order_by('name').values(
                'id', 'name', 'department_id'
            )
        )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)  # self.object = created User
        messages.success(self.request, f'تم تسجيل الموظف {self.object.get_full_name() or self.object.username} بنجاح.')
        return response


class EmployeeUpdateView(UpdateView):
    model = Employee
    form_class = EmployeeProfileForm
    template_name = 'employ/employee_update.html'
    success_url = reverse_lazy('employ:hr')

    def get_context_data(self, **kwargs):
        from django.contrib.auth.forms import SetPasswordForm
        context = super().get_context_data(**kwargs)
        context['password_form'] = SetPasswordForm(self.object.user)
        context['job_titles_json'] = list(
            JobTitle.objects.filter(is_active=True).select_related('department').order_by('name').values(
                'id', 'name', 'department_id'
            )
        )
        return context

    def form_valid(self, form):
        # تغيير كلمة المرور إن طُلب
        if 'change_password' in self.request.POST:
            from django.contrib.auth.forms import SetPasswordForm
            password_form = SetPasswordForm(self.object.user, self.request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(self.request, 'تم تغيير كلمة المرور بنجاح.')
            else:
                messages.error(self.request, 'خطأ في تغيير كلمة المرور.')
            return redirect(self.success_url)

        response = super().form_valid(form)
        messages.success(self.request, 'تم تحديث بيانات الموظف بنجاح.')
        return response


class EmployeeDeleteView(DeleteView):
    model = Employee
    success_url = reverse_lazy('employ:hr')

    def delete(self, request, *args, **kwargs):
        employee = self.get_object()
        employee_name = employee.user.get_full_name() or employee.user.get_username()

        # حذف المستخدم سيحذف الموظف (on_delete=CASCADE)
        employee.user.delete()

        messages.success(request, f'تم حذف الموظف {employee_name} بنجاح.')
        return HttpResponseRedirect(self.success_url)


def select_employee(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        return redirect('employ:employee_update', pk=employee_id)

    employees = Employee.objects.select_related('user').all()
    return render(request, 'employ/select_employee.html', {'employees': employees})


class EmployeeProfileView(LoginRequiredMixin, DetailView):
    model = Employee
    template_name = 'employ/employee_profile.html'
    context_object_name = 'employee'

    def _get_period_from_request(self):
        today = timezone.now().date()
        year_param = self.request.GET.get('year')
        month_param = self.request.GET.get('month')

        def sanitize(value, default, low=1, high=12):
            try:
                ivalue = int(value)
                if low <= ivalue <= high:
                    return ivalue
            except (TypeError, ValueError):
                pass
            return default

        if year_param is not None or month_param is not None:
            year = sanitize(year_param, today.year, low=1900, high=2100)
            month = sanitize(month_param, today.month)
            period_date = today.replace(year=year, month=month, day=1)
        else:
            period_date = today
            year = today.year
            month = today.month
        return today, period_date, year, month

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = context['employee']
        today, period_date, salary_year, salary_month = self._get_period_from_request()

        # التحقق من وجود حقل employee في ExpenseEntry قبل استخدامه
        try:
            # التحقق من وجود الحقل أولاً
            ExpenseEntry._meta.get_field('employee')
            salary_qs = ExpenseEntry.objects.filter(employee=employee).select_related(
                'journal_entry'
            ).prefetch_related('journal_entry__transactions__account').order_by('-date', '-created_at')
            period_salary_qs = salary_qs.filter(date__year=salary_year, date__month=salary_month)
        except FieldDoesNotExist:
            # إذا لم يكن الحقل موجوداً، نستخدم فلتر بديل أو نعيد queryset فارغ
            salary_qs = ExpenseEntry.objects.none()
            period_salary_qs = ExpenseEntry.objects.none()

        salary_amount = employee.salary or Decimal('0')
        period_paid_total = period_salary_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        period_advances = list(EmployeeAdvance.objects.filter(
            employee=employee,
            is_repaid=False,
            date__year=salary_year,
            date__month=salary_month
        ))
        period_advance_outstanding = sum((adv.outstanding_amount for adv in period_advances), Decimal('0'))
        period_paid_total += period_advance_outstanding

        salary_status = period_salary_qs.exists() or (salary_amount > 0 and period_advance_outstanding >= salary_amount)
        salary_total_paid = salary_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        last_salary_payment = salary_qs.first()

        period_remaining_amount = salary_amount - period_paid_total
        if period_remaining_amount < Decimal('0'):
            period_remaining_amount = Decimal('0')

        salary_entries = []
        for payment in salary_qs[:10]:
            debit_account = None
            if payment.journal_entry:
                try:
                    debit_tx = payment.journal_entry.transactions.filter(is_debit=True).select_related('account').first()
                    if debit_tx and hasattr(debit_tx, 'account'):
                        debit_account = debit_tx.account
                except Exception:
                    debit_account = None
            salary_entries.append({
                'entry': payment,
                'debit_account': debit_account,
            })

        salary_account_code = f"501-{employee.pk:04d}"
        salary_account = Account.objects.filter(code=salary_account_code).first()

        vacations_qs = Vacation.objects.filter(employee=employee).order_by('-start_date')
        status_totals = dict(vacations_qs.values('status').annotate(total=Count('id')).values_list('status', 'total'))
        vacations_list = list(vacations_qs)
        vacation_status_breakdown = [
            {'code': code, 'label': label, 'count': status_totals.get(code, 0)}
            for code, label in Vacation.STATUS_CHOICES
        ]
        vacations_total = len(vacations_list)
        vacations_current_year = sum(1 for vac in vacations_list if vac.start_date.year == today.year)
        upcoming_vacations = [vac for vac in vacations_list if vac.start_date >= today][:5]
        pending_status = Vacation.STATUS_CHOICES[0][0] if Vacation.STATUS_CHOICES else None
        pending_vacations_count = status_totals.get(pending_status, 0) if pending_status else 0

        advances_qs = EmployeeAdvance.objects.filter(employee=employee).order_by('-date')
        advances_list = list(advances_qs)
        advance_outstanding_total = sum((adv.outstanding_amount for adv in advances_list), Decimal('0'))
        outstanding_advances = [adv for adv in advances_list if not adv.is_repaid]
        live_preview = LivePayrollService.preview_for_period(employee, salary_year, salary_month)
        recent_attendance = list(
            EmployeeAttendance.objects.filter(employee=employee).order_by('-date')[:10]
        )

        months = [
            (1, 'كانون الثاني'), (2, 'شباط'), (3, 'آذار'), (4, 'نيسان'),
            (5, 'أيار'), (6, 'حزيران'), (7, 'تموز'), (8, 'آب'),
            (9, 'أيلول'), (10, 'تشرين الأول'), (11, 'تشرين الثاني'), (12, 'كانون الأول')
        ]

        context.update({
            'salary_year': salary_year,
            'salary_month': salary_month,
            'salary_period_label': f"{salary_year}/{salary_month:02d}",
            'salary_period_is_current': (salary_year == today.year and salary_month == today.month),
            'salary_amount': salary_amount,
            'salary_status': salary_status,
            'salary_total_paid': salary_total_paid,
            'salary_period_paid_total': period_paid_total,
            'salary_period_remaining': period_remaining_amount,
            'salary_period_advance_outstanding': period_advance_outstanding,
            'salary_entries': salary_entries,
            'last_salary_payment': last_salary_payment,
            'salary_account': salary_account,
            'salary_account_code': salary_account_code,
            'vacations': vacations_list,
            'salary_period_advances': period_advances,
            'display_name': _employee_full_name(employee),
            'vacations_total': vacations_total,
            'vacations_current_year': vacations_current_year,
            'vacation_status_breakdown': vacation_status_breakdown,
            'vacation_pending_count': pending_vacations_count,
            'upcoming_vacations': upcoming_vacations,
            'advances': advances_list,
            'advances_total': len(advances_list),
            'advance_outstanding_total': advance_outstanding_total,
            'outstanding_advances_count': len(outstanding_advances),
            'recent_attendance': recent_attendance,
            'live_preview': live_preview,
            'weekend_days_display': employee.weekend_days_display,
            'months': months,
            'today': today,
        })
        return context


# -----------------------------
# الإجازات
# -----------------------------
class VacationListView(ListView):
    model = Vacation
    template_name = 'employ/vacation_list.html'
    context_object_name = 'vacations'

    def get_queryset(self):
        queryset = Vacation.objects.select_related('employee__user').all()

        # فلاتر
        employee_name = self.request.GET.get('employee_name')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if employee_name:
            queryset = queryset.filter(employee__user__first_name__icontains=employee_name) | queryset.filter(
                employee__user__last_name__icontains=employee_name
            )

        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(end_date__lte=end_date)

        return queryset.order_by('-start_date')


class VacationCreateView(CreateView):
    model = Vacation
    form_class = AdminVacationForm
    template_name = 'employ/vacation_form.html'
    success_url = reverse_lazy('employ:vacation_list')

    def get_initial(self):
        initial = super().get_initial()
        employee_id = self.request.GET.get('employee')
        if employee_id:
            try:
                initial['employee'] = Employee.objects.get(pk=employee_id)
            except Employee.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'تم تسجيل الإجازة بنجاح.')
        return response


class VacationUpdateView(UpdateView):
    model = Vacation
    form_class = AdminVacationForm
    template_name = 'employ/vacation_form.html'
    success_url = reverse_lazy('employ:vacation_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'تم تحديث الإجازة بنجاح.')
        return response


# -----------------------------
# إدارة رواتب المدرسين (عرض)
# -----------------------------
class SalaryManagementView(TemplateView):
    template_name = 'employ/salary_management.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        selected_year = _safe_period_int(self.request.GET.get('year'), timezone.now().year)
        selected_month = _safe_period_int(self.request.GET.get('month'), timezone.now().month, min_value=1, max_value=12)

        months = [
            (1, 'كانون الثاني'), (2, 'شباط'), (3, 'آذار'), (4, 'نيسان'),
            (5, 'أيار'), (6, 'حزيران'), (7, 'تموز'), (8, 'آب'),
            (9, 'أيلول'), (10, 'تشرين الأول'), (11, 'تشرين الثاني'), (12, 'كانون الأول')
        ]

        teachers = Teacher.objects.all()
        teachers_salary_data = []
        total_calculated_amount = Decimal('0.00')
        paid_count = 0
        unpaid_count = 0

        for teacher in teachers:
            monthly_sessions = teacher.get_monthly_sessions(selected_year, selected_month)
            calculated_salary = teacher.calculate_monthly_salary(selected_year, selected_month)
            
            # التحقق من الرواتب اليدوية المدفوعة
            salary_status = ManualTeacherSalary.objects.filter(
                teacher=teacher,
                year=selected_year,
                month=selected_month,
                is_paid=True
            ).exists()

            teachers_salary_data.append({
                'teacher': teacher,
                'monthly_sessions': monthly_sessions,
                'calculated_salary': calculated_salary,
                'salary_status': salary_status
            })

            total_calculated_amount += calculated_salary
            if salary_status:
                paid_count += 1
            else:
                unpaid_count += 1

        context.update({
            'teachers_salary_data': teachers_salary_data,
            'selected_year': selected_year,
            'selected_month': selected_month,
            'months': months,
            'total_calculated_amount': total_calculated_amount,
            'paid_count': paid_count,
            'unpaid_count': unpaid_count,
            'today': timezone.now().date()
        })

        return context


# -----------------------------
# Teacher Profile View
# -----------------------------
class TeacherProfileView(DetailView):
    model = Teacher
    template_name = 'employ/teacher_profile.html'
    context_object_name = 'teacher'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.get_object()
        today = timezone.now().date()
        latest_attendance_date = (TeacherAttendance.objects.filter(teacher=teacher)
                                  .order_by('-date')
                                  .values_list('date', flat=True)
                                  .first())
        attendance_date = latest_attendance_date or today
        
        # الحضور اليومي
        daily_attendance_entries = TeacherAttendance.objects.filter(
            teacher=teacher, 
            date=attendance_date
        ).order_by('branch')
        
        # الحضور الشهري (هذا الشهر)
        monthly_attendance = TeacherAttendance.objects.filter(
            teacher=teacher,
            date__year=attendance_date.year,
            date__month=attendance_date.month
        )
        
        # الحضور السنوي (هذه السنة)
        yearly_attendance = TeacherAttendance.objects.filter(
            teacher=teacher,
            date__year=attendance_date.year
        )
        
        # إحصائيات شهرية مفصلة
        monthly_present = monthly_attendance.filter(status='present')
        monthly_present_days = monthly_present.count()
        monthly_total_sessions = sum(att.total_sessions for att in monthly_present)
        
        # إحصائيات سنوية مفصلة
        yearly_present = yearly_attendance.filter(status='present')
        yearly_present_days = yearly_present.count()
        yearly_total_sessions = sum(att.total_sessions for att in yearly_present)
        
        # حساب متوسط الجلسات اليومية
        avg_daily_sessions_monthly = 0
        if monthly_present_days > 0:
            avg_daily_sessions_monthly = monthly_total_sessions / monthly_present_days
        
        avg_daily_sessions_yearly = 0
        if yearly_present_days > 0:
            avg_daily_sessions_yearly = yearly_total_sessions / yearly_present_days
        
        # حساب نسبة الحضور
        attendance_rate_monthly = 0
        if monthly_attendance.count() > 0:
            attendance_rate_monthly = (monthly_present_days / monthly_attendance.count()) * 100
        
        attendance_rate_yearly = 0
        if yearly_attendance.count() > 0:
            attendance_rate_yearly = (yearly_present_days / yearly_attendance.count()) * 100
        
        context.update({
            'today': today,
            'daily_attendance_date': attendance_date,
            'daily_attendance_entries': daily_attendance_entries,
            'labels': self._get_labels(),
            
            # إحصائيات شهرية مفصلة
            'monthly_stats': {
                'total_days': monthly_attendance.count(),
                'present_days': monthly_present_days,
                'absent_days': monthly_attendance.filter(status='absent').count(),
                'late_days': monthly_attendance.filter(status='late').count(),
                'total_sessions': monthly_total_sessions,
                'avg_daily_sessions': round(avg_daily_sessions_monthly, 1),
                'attendance_rate': round(attendance_rate_monthly, 1),
            },
            
            # إحصائيات سنوية مفصلة
            'yearly_stats': {
                'total_days': yearly_attendance.count(),
                'present_days': yearly_present_days,
                'absent_days': yearly_attendance.filter(status='absent').count(),
                'late_days': yearly_attendance.filter(status='late').count(),
                'total_sessions': yearly_total_sessions,
                'avg_daily_sessions': round(avg_daily_sessions_yearly, 1),
                'attendance_rate': round(attendance_rate_yearly, 1),
            },
            
            # قائمة الحضور الأخيرة (10 أيام)
            'recent_attendance': TeacherAttendance.objects.filter(
                teacher=teacher
            ).order_by('-date')[:10],
            
            # جلب جميع أيام الحضور للسنة الحالية
            'all_attendance_days': TeacherAttendance.objects.filter(
                teacher=teacher,
                date__year=today.year
            ).order_by('-date'),
            
            # إحصائيات الحضور حسب الشهور
            'monthly_attendance_stats': self.get_monthly_attendance_stats(teacher, today.year),
        })
        
        # الرواتب اليدوية
        selected_year = self.request.GET.get('year', attendance_date.year)
        try:
            selected_year = int(selected_year)
        except:
            selected_year = attendance_date.year

        branch_monthly_tables = self.get_branch_monthly_tables(teacher)
        branch_hourly_rates = self.get_branch_hourly_rates(teacher)
        advance_account = teacher.get_teacher_advance_account()
        advance_account_balance = advance_account.get_net_balance() if advance_account else Decimal('0.00')
        
        manual_salaries = ManualTeacherSalary.objects.filter(
            teacher=teacher,
            year=selected_year
        ).order_by('-month')
        
        # حساب الإجماليات
        total_gross_year = sum(s.gross_salary for s in manual_salaries)
        total_advances_year = sum(s.advance_deduction for s in manual_salaries)
        total_net_year = sum(s.net_salary for s in manual_salaries)
        
        # الرواتب المدفوعة
        paid_salaries = manual_salaries.filter(is_paid=True)
        total_paid_year = sum(s.net_salary for s in paid_salaries)
        paid_count_year = paid_salaries.count()
        
        # المتبقي للدفع
        total_remaining = total_net_year - total_paid_year
        
        # السلف المعلقة
        total_advances_outstanding = teacher.get_total_advances()
        
        # نطاق السنوات
        current_year = today.year
        years_range = range(current_year - 5, current_year + 2)
        
        # إضافة بيانات الرواتب
        context.update({
            'manual_salaries': manual_salaries,
            'selected_year': selected_year,
            'years_range': years_range,
            'total_gross_year': total_gross_year,
            'total_advances_year': total_advances_year,
            'total_net_year': total_net_year,
            'total_paid_year': total_paid_year,
            'paid_count_year': paid_count_year,
            'total_remaining': total_remaining,
            'total_advances_outstanding': total_advances_outstanding,
            'branch_monthly_tables': branch_monthly_tables,
            'branch_hourly_rates': branch_hourly_rates,
            'advance_account': advance_account,
            'advance_account_balance': advance_account_balance,
        })
        
        # إضافة حسابات الشراكة المتقدمة
        if teacher.is_partner:
            from accounts.models import Account
            current_academic_year = getattr(self.request, 'current_academic_year', None)
            
            def get_group_accounts(prefix, exclude_prefixes=None):
                qs = Account.objects.filter(code__startswith=prefix, is_active=True)
                if exclude_prefixes:
                    for ex in exclude_prefixes:
                        qs = qs.exclude(code__startswith=ex)
                
                accounts_list = []
                for acc in qs.order_by('code'):
                    balance = acc.get_rollup_balance(academic_year=current_academic_year)
                    accounts_list.append({
                        'id': acc.id,
                        'code': acc.code,
                        'name': acc.name_ar or acc.name,
                        'balance': balance,
                        'account_type': acc.account_type,
                    })
                return accounts_list

            partner_account_code = f"301-{teacher.pk:04d}"
            partner_account = Account.objects.filter(code=partner_account_code).first()
            partner_account_data = None
            if partner_account:
                partner_account_data = {
                    'id': partner_account.id,
                    'code': partner_account.code,
                    'name': partner_account.name_ar or partner_account.name,
                    'balance': partner_account.get_rollup_balance(academic_year=current_academic_year),
                    'account_type': partner_account.account_type,
                }

            context['partner_financial_data'] = {
                'partner_account': partner_account_data,
                'cash_accounts': get_group_accounts('10'),
                'deposit_accounts': get_group_accounts('122'),
                'employee_cashboxes': get_group_accounts('121'),
                'assets_accounts': get_group_accounts('1', exclude_prefixes=['10', '12']),
                'revenue_accounts': get_group_accounts('4'),
                'expense_accounts': get_group_accounts('5'),
            }
            
        return context
    
    def get_monthly_attendance_stats(self, teacher, year):
        """الحصول على إحصائيات الحضور لكل شهر في السنة"""
        from django.db.models import Count, Sum
        from django.db.models.functions import ExtractMonth
        
        stats = []
        month_names = {
            1: 'كانون الثاني', 2: 'شباط', 3: 'آذار', 4: 'نيسان',
            5: 'أيار', 6: 'حزيران', 7: 'تموز', 8: 'آب',
            9: 'أيلول', 10: 'تشرين الأول', 11: 'تشرين الثاني', 12: 'كانون الأول'
        }
        
        for month_num in range(1, 13):
            monthly_data = TeacherAttendance.objects.filter(
                teacher=teacher,
                date__year=year,
                date__month=month_num
            )
            
            present_days = monthly_data.filter(status='present').count()
            total_days = monthly_data.count()
            
            if total_days > 0:
                attendance_rate = (present_days / total_days) * 100
                total_sessions = sum(att.total_sessions for att in monthly_data.filter(status='present'))
                
                stats.append({
                    'month': month_num,
                    'month_name': month_names.get(month_num, f'شهر {month_num}'),
                    'present_days': present_days,
                    'total_days': total_days,
                    'attendance_rate': round(attendance_rate, 1),
                    'total_sessions': total_sessions,
                    'avg_sessions': round(total_sessions / present_days, 1) if present_days > 0 else 0,
                })
        
        return stats

    def _get_teacher_branches(self, teacher):
        branches = teacher.get_branches_list()
        return branches or [Teacher.BranchChoices.SCIENTIFIC]

    def _get_attendance_branches(self, teacher, year=None):
        qs = TeacherAttendance.objects.filter(teacher=teacher)
        if year is not None:
            qs = qs.filter(date__year=year)
        branches = list(qs.values_list('branch', flat=True).distinct())
        return branches

    def _branch_label(self, branch):
        try:
            return Teacher.BranchChoices(branch).label
        except Exception:
            return branch

    def _branch_title(self, branch):
        title_map = {
            Teacher.BranchChoices.SCIENTIFIC: 'البكالوريا العلمي',
            Teacher.BranchChoices.LITERARY: 'البكالوريا الأدبي',
            Teacher.BranchChoices.NINTH_GRADE: 'التاسع',
            Teacher.BranchChoices.PREPARATORY: 'التمهيدي',
        }
        return title_map.get(branch, self._branch_label(branch))

    def _get_labels(self):
        return {
            'profile_title': '\u0645\u0644\u0641 \u0627\u0644\u0623\u0633\u062a\u0627\u0630',
            'attendance_button': '\u062d\u0636\u0648\u0631 \u0627\u0644\u0623\u0633\u062a\u0627\u0630',
            'advance_button': '\u0633\u0644\u0641\u0629 \u062c\u062f\u064a\u062f\u0629',
            'salary_button': '\u0625\u0636\u0627\u0641\u0629 \u0631\u0627\u062a\u0628',
            'basic_info': '\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0623\u0633\u0627\u0633\u064a\u0629',
            'phone_number': '\u0631\u0642\u0645 \u0627\u0644\u0647\u0627\u062a\u0641',
            'not_set': '\u063a\u064a\u0631 \u0645\u062d\u062f\u062f',
            'hire_date': '\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u062a\u0639\u064a\u064a\u0646',
            'salary_type': '\u0646\u0648\u0639 \u0627\u0644\u0631\u0627\u062a\u0628',
            'hourly_rate_general': '\u0627\u0644\u0633\u0627\u0639\u0629 \u0627\u0644\u0639\u0627\u0645\u0629',
            'notes': '\u0645\u0644\u0627\u062d\u0638\u0627\u062a',
            'hourly_rate_by_branch': '\u0633\u0639\u0631 \u0627\u0644\u0633\u0627\u0639\u0629 \u062d\u0633\u0628 \u0627\u0644\u0641\u0631\u0639',
            'no_branches': '\u0644\u0627 \u064a\u0648\u062c\u062f \u0641\u0631\u0648\u0639 \u0645\u062d\u062f\u062f\u0629',
            'daily_attendance': '\u0627\u0644\u062d\u0636\u0648\u0631 \u0627\u0644\u064a\u0648\u0645\u064a',
            'course_or_branch': '\u0646\u0648\u0639 \u0627\u0644\u062f\u0648\u0631\u0629/\u0627\u0644\u0641\u0631\u0639',
            'status': '\u0627\u0644\u062d\u0627\u0644\u0629',
            'session_count': '\u0639\u062f\u062f \u0627\u0644\u062c\u0644\u0633\u0627\u062a',
            'half_sessions': '\u0623\u0646\u0635\u0627\u0641 \u062c\u0644\u0633\u0627\u062a',
            'total': '\u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a',
            'wage': '\u0627\u0644\u0623\u062c\u0631',
            'no_daily_attendance': '\u0644\u0627 \u064a\u0648\u062c\u062f \u062d\u0636\u0648\u0631 \u0645\u0633\u062c\u0644 \u0644\u0647\u0630\u0627 \u0627\u0644\u064a\u0648\u0645.',
            'monthly_attendance_by_branch': '\u0627\u0644\u062d\u0636\u0648\u0631 \u0627\u0644\u0634\u0647\u0631\u064a \u062d\u0633\u0628 \u0627\u0644\u0641\u0631\u0639',
            'year': '\u0627\u0644\u0633\u0646\u0629',
            'hourly_rate': '\u0633\u0639\u0631 \u0627\u0644\u0633\u0627\u0639\u0629',
            'month': '\u0627\u0644\u0634\u0647\u0631',
            'due_amount': '\u0627\u0644\u0623\u062c\u0631 \u0627\u0644\u0645\u0633\u062a\u062d\u0642',
            'no_monthly_attendance': '\u0644\u0627 \u064a\u0648\u062c\u062f \u062d\u0636\u0648\u0631 \u0634\u0647\u0631\u064a \u0645\u0633\u062c\u0644 \u0644\u0647\u0630\u0647 \u0627\u0644\u0633\u0646\u0629.',
            'monthly_formula': '\u0627\u0644\u0623\u062c\u0631 \u0627\u0644\u0645\u0633\u062a\u062d\u0642 = \u0639\u062f\u062f \u0627\u0644\u062c\u0644\u0633\u0627\u062a \u00d7 \u0633\u0639\u0631 \u0627\u0644\u0633\u0627\u0639\u0629',
            'advance_balance_title': '\u0631\u0635\u064a\u062f \u0633\u0644\u0641 \u0627\u0644\u0645\u062f\u0631\u0633 (\u0645\u0646 \u0645\u064a\u0632\u0627\u0646 \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629)',
            'account': '\u0627\u0644\u062d\u0633\u0627\u0628',
            'balance': '\u0627\u0644\u0631\u0635\u064a\u062f',
            'no_advance_account': '\u0644\u0627 \u064a\u0648\u062c\u062f \u062d\u0633\u0627\u0628 \u0633\u0644\u0641\u0629 \u0644\u0647\u0630\u0627 \u0627\u0644\u0645\u062f\u0631\u0633.',
            'currency': '\u0644.\u0633',
        }

    def get_branch_monthly_tables(self, teacher, year=None):
        month_names = dict(ManualTeacherSalary.MONTH_CHOICES)
        tables = []
        branches = self._get_attendance_branches(teacher, year) or self._get_teacher_branches(teacher)
        for branch in branches:
            hourly_rate = teacher.get_hourly_rate_for_branch(branch, date=timezone.now().date())
            rows = []
            monthly_qs = TeacherAttendance.objects.filter(
                teacher=teacher,
                branch=branch,
                status='present'
            )
            if year:
                monthly_qs = monthly_qs.filter(date__year=year)

            monthly_totals = {}
            for att in monthly_qs:
                key = (att.date.year, att.date.month)
                monthly_totals[key] = monthly_totals.get(key, Decimal('0.00')) + att.total_sessions

            for (year_num, month_num) in sorted(monthly_totals.keys()):
                total_sessions = monthly_totals[(year_num, month_num)]
                if total_sessions <= 0:
                    continue
                total_salary = total_sessions * (hourly_rate or Decimal('0.00'))
                month_name = month_names.get(month_num, str(month_num))
                rows.append({
                    'month': month_num,
                    'month_name': month_name,
                    'month_label': f"{month_name} - {year_num}",
                    'total_sessions': total_sessions,
                    'total_salary': total_salary,
                })
            if rows:
                tables.append({
                    'branch': branch,
                    'branch_label': self._branch_label(branch),
                    'branch_title': self._branch_title(branch),
                    'hourly_rate': hourly_rate,
                    'rows': rows,
                })
        return tables

    def get_branch_hourly_rates(self, teacher):
        items = []
        branches = self._get_teacher_branches(teacher)
        for branch in branches:
            items.append({
                'branch': branch,
                'branch_label': self._branch_label(branch),
                'branch_title': self._branch_title(branch),
                'hourly_rate': teacher.get_hourly_rate_for_branch(branch, date=timezone.now().date()),
            })
        return items


class TeacherDeleteView(LoginRequiredMixin, DeleteView):
    model = Teacher
    template_name = 'employ/teacher_confirm_delete.html'
    success_url = reverse_lazy('employ:teachers')

    def delete(self, request, *args, **kwargs):
        teacher = self.get_object()
        messages.success(request, f'تم حذف بيانات المعلم {teacher.full_name}.')
        return super().delete(request, *args, **kwargs)


# -----------------------------
# سلف المدرس
# -----------------------------
class TeacherAdvanceCreateView(LoginRequiredMixin, CreateView):
    model = TeacherAdvance
    template_name = 'employ/teacher_advance_form.html'
    fields = ['date', 'amount', 'purpose']
    
    def get_queryset(self):
        return TeacherAdvance.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['teacher'] = get_object_or_404(Teacher, pk=self.kwargs['teacher_id'])
        context['advance'] = None
        return context

    def form_valid(self, form):
        teacher = get_object_or_404(Teacher, pk=self.kwargs['teacher_id'])
        
        advance = form.save(commit=False)
        advance.teacher = teacher
        advance.created_by = self.request.user
        advance.save()

        try:
            advance.create_advance_journal_entry(self.request.user)
            messages.success(self.request, f'تم إنشاء سلفة للمدرس {teacher.full_name} بمبلغ {advance.amount} ل.س')
        except Exception as e:
            messages.error(self.request, f'خطأ في إنشاء القيد المحاسبي: {e}')

        return redirect('employ:teacher_profile', pk=teacher.pk)


class TeacherAdvanceUpdateView(LoginRequiredMixin, UpdateView):
    model = TeacherAdvance
    template_name = 'employ/teacher_advance_form.html'
    fields = ['date', 'amount', 'purpose']

    def get_queryset(self):
        teacher = get_object_or_404(Teacher, pk=self.kwargs['teacher_id'])
        return TeacherAdvance.objects.filter(teacher=teacher)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['teacher'] = self.object.teacher
        context['advance'] = self.object
        return context

    def form_valid(self, form):
        advance = form.save()
        try:
            advance.sync_advance_journal_entry(self.request.user)
            messages.success(
                self.request,
                f'تم تحديث سلفة المدرس {advance.teacher.full_name} إلى {advance.amount} ل.س.'
            )
        except Exception as exc:
            messages.error(self.request, f'حدث خطأ أثناء تحديث القيد المحاسبي: {exc}')

        return redirect('employ:teacher_advance_list', teacher_id=advance.teacher.pk)


class TeacherAdvanceListView(LoginRequiredMixin, ListView):
    template_name = 'employ/teacher_advance_list.html'
    context_object_name = 'advances'

    def get_queryset(self):
        from accounts.models import TeacherAdvance
        teacher = get_object_or_404(Teacher, pk=self.kwargs['teacher_id'])
        return (TeacherAdvance.objects
                .filter(teacher=teacher)
                .select_related('teacher')
                .order_by('-date', '-created_at'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = get_object_or_404(Teacher, pk=self.kwargs['teacher_id'])
        advances = context['advances']
        context.update({
            'teacher': teacher,
            'total_advances': advances.count(),
            'outstanding_count': advances.filter(is_repaid=False).count(),
            'total_amount': sum(a.amount for a in advances),
            'total_outstanding_amount': sum(a.outstanding_amount for a in advances if not a.is_repaid),
        })
        return context


class HRSettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'employ/hr_settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'departments': Department.objects.order_by('name'),
            'job_titles': JobTitle.objects.select_related('department').order_by('name'),
            'shifts': Shift.objects.order_by('name'),
            'attendance_policies': AttendancePolicy.objects.order_by('name'),
            'salary_rules': EmployeeSalaryRule.objects.order_by('name'),
            'holidays': HRHoliday.objects.order_by('-start_date', 'name'),
            'department_form': DepartmentForm(),
            'job_title_form': JobTitleForm(),
            'shift_form': ShiftForm(),
            'policy_form': AttendancePolicyForm(),
            'salary_rule_form': EmployeeSalaryRuleForm(),
            'holiday_form': HRHolidayForm(),
            'settings_stats': {
                'departments': Department.objects.count(),
                'job_titles': JobTitle.objects.count(),
                'shifts': Shift.objects.filter(is_active=True).count(),
                'attendance_policies': AttendancePolicy.objects.filter(is_active=True).count(),
                'salary_rules': EmployeeSalaryRule.objects.filter(is_active=True).count(),
                'holidays': HRHoliday.objects.filter(is_active=True).count(),
            },
        })
        return context


class DepartmentCreateView(LoginRequiredMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    success_url = reverse_lazy('employ:hr_settings')

    def form_valid(self, form):
        messages.success(self.request, 'تم حفظ القسم بنجاح.')
        return super().form_valid(form)


class ShiftCreateView(LoginRequiredMixin, CreateView):
    model = Shift
    form_class = ShiftForm
    success_url = reverse_lazy('employ:hr_settings')

    def form_valid(self, form):
        messages.success(self.request, 'تم حفظ الشفت بنجاح.')
        return super().form_valid(form)


class JobTitleCreateView(LoginRequiredMixin, CreateView):
    model = JobTitle
    form_class = JobTitleForm
    success_url = reverse_lazy('employ:hr_settings')

    def form_valid(self, form):
        messages.success(self.request, 'تم حفظ المسمى الوظيفي بنجاح.')
        return super().form_valid(form)


class AttendancePolicyCreateView(LoginRequiredMixin, CreateView):
    model = AttendancePolicy
    form_class = AttendancePolicyForm
    success_url = reverse_lazy('employ:hr_settings')

    def form_valid(self, form):
        messages.success(self.request, 'تم حفظ سياسة الدوام بنجاح.')
        return super().form_valid(form)


class HRHolidayCreateView(LoginRequiredMixin, CreateView):
    model = HRHoliday
    form_class = HRHolidayForm
    success_url = reverse_lazy('employ:hr_settings')

    def form_valid(self, form):
        messages.success(self.request, 'تم حفظ العطلة الرسمية بنجاح.')
        return super().form_valid(form)


class SalaryRuleCreateView(LoginRequiredMixin, CreateView):
    model = EmployeeSalaryRule
    form_class = EmployeeSalaryRuleForm
    success_url = reverse_lazy('employ:hr_settings')

    def form_valid(self, form):
        messages.success(self.request, 'تم حفظ قاعدة الراتب بنجاح.')
        return super().form_valid(form)


class BiometricDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'employ/biometric_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pending_reviews = EmployeeAttendance.objects.filter(review_status='pending')
        context.update({
            'devices': BiometricDevice.objects.order_by('name'),
            'logs': BiometricLog.objects.select_related('employee__user', 'device').order_by('-punch_time')[:100],
            'device_form': BiometricDeviceForm(),
            'import_form': BiometricImportForm(),
            'unlinked_logs_count': BiometricLog.objects.filter(employee__isnull=True).count(),
            'pending_reviews_count': pending_reviews.count(),
            'pending_early_leave_count': pending_reviews.filter(early_leave_seconds__gt=0).count(),
            'biometric_driver_available': BiometricAutoSyncService.is_available(),
            'biometric_driver_name': BiometricAutoSyncService.DRIVER_NAME,
        })
        return context


class BiometricDeviceCreateView(LoginRequiredMixin, CreateView):
    model = BiometricDevice
    form_class = BiometricDeviceForm
    success_url = reverse_lazy('employ:biometric_dashboard')

    def form_valid(self, form):
        messages.success(self.request, 'تم حفظ جهاز البصمة بنجاح.')
        return super().form_valid(form)


class BiometricImportView(LoginRequiredMixin, View):
    def post(self, request):
        form = BiometricImportForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'تعذر استيراد السجلات. تحقق من البيانات المدخلة.')
            return redirect('employ:biometric_dashboard')

        try:
            raw_logs_text = (form.cleaned_data['raw_logs'] or '').strip()
            if not raw_logs_text:
                messages.error(request, 'حقل سجلات البصمة فارغ. الاستيراد اليدوي يحتاج JSON صالح، أما الربط التلقائي فيحتاج تثبيت موصل الجهاز.')
                return redirect('employ:biometric_dashboard')
            raw_logs = json.loads(raw_logs_text)
            result = BiometricImportService.import_logs(form.cleaned_data['device'], raw_logs)
            messages.success(
                request,
                f"تمت مزامنة {result['created']} سجل، وتجاهل {result['duplicates']} مكرر، و{result['unresolved']} غير مربوط بموظف."
            )
        except Exception as exc:
            messages.error(request, f'فشل استيراد سجلات البصمة: {exc}')
        return redirect('employ:biometric_dashboard')


class BiometricWeeklySummaryEmailView(LoginRequiredMixin, View):
    def post(self, request):
        sent, report = send_weekly_biometric_summary()
        if sent:
            messages.success(
                request,
                f"تم إرسال ملخص بصمات الأسبوع إلى البريد الإلكتروني. عدد البصمات: {report['logs_count']}."
            )
        else:
            messages.error(request, 'تعذر إرسال ملخص بصمات الأسبوع. تحقق من إعدادات البريد الإلكتروني والمستلمين.')
        return redirect('employ:biometric_dashboard')


@method_decorator(csrf_exempt, name='dispatch')
class BiometricPushApiView(View):
    http_method_names = ['post']

    def _extract_token(self, request):
        auth_header = (request.headers.get('Authorization') or '').strip()
        if auth_header.lower().startswith('bearer '):
            return auth_header[7:].strip()
        return (
            request.headers.get('X-Biometric-Token')
            or request.GET.get('token')
            or request.POST.get('token')
            or ''
        ).strip()

    def _is_authorized(self, request):
        configured_token = (getattr(settings, 'BIOMETRIC_PUSH_TOKEN', '') or '').strip()
        provided_token = self._extract_token(request)
        return bool(configured_token) and bool(provided_token) and constant_time_compare(provided_token, configured_token)

    def post(self, request):
        if not self._is_authorized(request):
            return JsonResponse(
                {'ok': False, 'error': 'unauthorized', 'detail': 'Invalid or missing biometric push token.'},
                status=403,
            )

        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse(
                {'ok': False, 'error': 'invalid_json', 'detail': 'Request body must be valid JSON.'},
                status=400,
            )

        raw_logs = payload.get('logs')
        if not isinstance(raw_logs, list) or not raw_logs:
            return JsonResponse(
                {'ok': False, 'error': 'missing_logs', 'detail': 'Payload must include a non-empty logs list.'},
                status=400,
            )

        device = None
        device_id = payload.get('device_id')
        device_serial = str(payload.get('device_serial') or '').strip()
        if device_id:
            device = BiometricDevice.objects.filter(pk=device_id, active=True).first()
        if device is None and device_serial:
            device = BiometricDevice.objects.filter(serial=device_serial, active=True).first()
        if device is None:
            return JsonResponse(
                {'ok': False, 'error': 'device_not_found', 'detail': 'No active biometric device matched the payload.'},
                status=404,
            )

        try:
            result = BiometricImportService.import_logs(device, raw_logs)
        except Exception as exc:
            return JsonResponse(
                {'ok': False, 'error': 'import_failed', 'detail': str(exc)},
                status=500,
            )

        return JsonResponse({
            'ok': True,
            'device': {
                'id': device.pk,
                'name': device.name,
                'serial': device.serial,
            },
            **result,
        })


class EmployeeAttendanceListView(LoginRequiredMixin, ListView):
    model = EmployeeAttendance
    template_name = 'employ/attendance_list.html'
    context_object_name = 'records'

    def get_queryset(self):
        queryset = EmployeeAttendance.objects.select_related('employee__user').order_by('-date', 'employee__user__first_name')
        self.filter_form = AttendanceFilterForm(self.request.GET or None)
        if self.filter_form.is_valid():
            employee = self.filter_form.cleaned_data.get('employee')
            start_date = self.filter_form.cleaned_data.get('start_date')
            end_date = self.filter_form.cleaned_data.get('end_date')
            status = self.filter_form.cleaned_data.get('status')
            review_status = self.filter_form.cleaned_data.get('review_status')
            if employee:
                queryset = queryset.filter(employee=employee)
            if start_date:
                queryset = queryset.filter(date__gte=start_date)
            if end_date:
                queryset = queryset.filter(date__lte=end_date)
            if status:
                queryset = queryset.filter(status=status)
            if review_status:
                queryset = queryset.filter(review_status=review_status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pending_reviews = EmployeeAttendance.objects.filter(review_status='pending')
        context['filter_form'] = getattr(self, 'filter_form', AttendanceFilterForm())
        context['today'] = timezone.now().date()
        context['pending_reviews_count'] = pending_reviews.count()
        context['pending_early_leave_count'] = pending_reviews.filter(early_leave_seconds__gt=0).count()
        return context


class EmployeeAttendanceRebuildView(LoginRequiredMixin, View):
    def post(self, request):
        employee_id = request.POST.get('employee')
        target_date = request.POST.get('date')
        employee = get_object_or_404(Employee, pk=employee_id)
        target_date = datetime.fromisoformat(target_date).date() if target_date else timezone.now().date()
        AttendanceGenerationService.build_attendance_record(employee, target_date)
        messages.success(request, 'تمت إعادة احتساب الدوام من سجلات البصمة.')
        return redirect('employ:attendance_list')


class EmployeeAttendanceUpdateView(LoginRequiredMixin, UpdateView):
    model = EmployeeAttendance
    form_class = EmployeeAttendanceUpdateForm
    template_name = 'employ/attendance_update.html'
    success_url = reverse_lazy('employ:attendance_list')

    def form_valid(self, form):
        attendance = self.get_object()
        AttendanceGenerationService.apply_manual_adjustment(
            attendance,
            check_in=form.cleaned_data.get('check_in'),
            check_out=form.cleaned_data.get('check_out'),
            review_status=form.cleaned_data.get('review_status'),
            review_notes=form.cleaned_data.get('review_notes'),
            notes=form.cleaned_data.get('notes'),
            manual_adjustment_reason=form.cleaned_data.get('manual_adjustment_reason'),
            reviewer=self.request.user,
        )
        messages.success(self.request, 'تم تحديث سجل الدوام وربط القرار الإداري به.')
        return redirect(self.get_success_url())


class EmployeeAttendanceEmailDecisionView(LoginRequiredMixin, View):
    ACTIONS = {
        'forgive': 'مسامحة',
        'charge': 'محاسبة',
        'count_overtime': 'حسبان الإضافي',
        'deny_overtime': 'حرمان الإضافي',
    }

    def get(self, request, pk, action):
        allowed_users = set(getattr(settings, 'BIOMETRIC_DECISION_USERNAMES', ['thaaer', 'ammar']))
        if allowed_users and request.user.username not in allowed_users:
            return HttpResponseForbidden('هذا القرار محصور بحسابات HR المخولة.')

        attendance = get_object_or_404(EmployeeAttendance.objects.select_related('employee__user'), pk=pk)
        label = self.ACTIONS.get(action)
        if not label:
            messages.error(request, 'قرار غير معروف.')
            return redirect('employ:attendance_update', pk=attendance.pk)

        now = timezone.now()
        note = f'{label} من رابط البريد بواسطة {request.user.get_username()} بتاريخ {now:%Y-%m-%d %H:%M}.'

        if action == 'forgive':
            attendance.review_status = 'justified'
            attendance.review_notes = note
            attendance.reviewed_by = request.user
            attendance.reviewed_at = now
            attendance.save(update_fields=['review_status', 'review_notes', 'reviewed_by', 'reviewed_at', 'updated_at'])
            messages.success(request, 'تم اعتماد المسامحة ولن يدخل التأخير أو الخروج المبكر في الحسم.')
        elif action == 'charge':
            attendance.review_status = 'unjustified'
            attendance.review_notes = note
            attendance.reviewed_by = request.user
            attendance.reviewed_at = now
            attendance.save(update_fields=['review_status', 'review_notes', 'reviewed_by', 'reviewed_at', 'updated_at'])
            messages.success(request, 'تم اعتماد المحاسبة وسيدخل التأخير أو الخروج المبكر في حساب الرواتب.')
        elif action == 'count_overtime':
            attendance.review_notes = note
            attendance.reviewed_by = request.user
            attendance.reviewed_at = now
            attendance.save(update_fields=['review_notes', 'reviewed_by', 'reviewed_at', 'updated_at'])
            messages.success(request, 'تم تثبيت حسبان الإضافي كما هو في سجل الدوام.')
        elif action == 'deny_overtime':
            attendance.overtime_seconds = 0
            attendance.review_notes = note
            attendance.reviewed_by = request.user
            attendance.reviewed_at = now
            attendance.is_manually_adjusted = True
            attendance.manual_adjustment_reason = note
            attendance.source = 'manual'
            attendance.save(update_fields=[
                'overtime_seconds',
                'review_notes',
                'reviewed_by',
                'reviewed_at',
                'is_manually_adjusted',
                'manual_adjustment_reason',
                'source',
                'updated_at',
            ])
            messages.success(request, 'تم حرمان الإضافي وتصفير ساعاته في سجل الدوام حتى لا تدخل في الراتب.')

        if request.GET.get('email') == '1':
            employee_name = escape(attendance.employee.full_name)
            action_label = {
                'forgive': 'مسامحة',
                'charge': 'محاسبة',
                'count_overtime': 'احتساب الإضافي',
                'deny_overtime': 'حرمان الإضافي',
            }.get(action, label)
            edit_url = reverse('employ:attendance_update', kwargs={'pk': attendance.pk})
            return HttpResponse(f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>تم تثبيت القرار</title>
  <style>
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; background:#f3f6f9; font-family:'Segoe UI',Tahoma,Arial,sans-serif; color:#172033; }}
    main {{ width:min(520px, calc(100vw - 32px)); background:#fff; border:1px solid #dbe3ec; border-radius:14px; padding:28px; box-shadow:0 18px 46px rgba(15,23,42,.10); }}
    h1 {{ margin:0 0 10px; font-size:24px; }}
    p {{ margin:0 0 18px; line-height:1.9; color:#475569; }}
    .actions {{ display:flex; gap:10px; flex-wrap:wrap; }}
    a, button {{ border:0; border-radius:8px; padding:10px 14px; font-weight:700; text-decoration:none; cursor:pointer; font-family:inherit; }}
    a {{ background:#132f4c; color:#fff; }}
    button {{ background:#e2e8f0; color:#172033; }}
  </style>
</head>
<body>
  <main>
    <h1>تم تثبيت القرار</h1>
    <p>تم تطبيق إجراء <strong>{escape(action_label)}</strong> على سجل دوام <strong>{employee_name}</strong> بتاريخ <strong>{attendance.date}</strong>.</p>
    <div class="actions">
      <a href="{edit_url}">عرض السجل</a>
      <button type="button" onclick="window.close()">إغلاق</button>
    </div>
  </main>
</body>
</html>
""")

        return redirect('employ:attendance_update', pk=attendance.pk)


class AttendanceSummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'employ/attendance_summary.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_year = _safe_period_int(self.request.GET.get('year'), timezone.now().year)
        selected_month = _safe_period_int(self.request.GET.get('month'), timezone.now().month, min_value=1, max_value=12)
        context.update({
            'selected_year': selected_year,
            'selected_month': selected_month,
            'summary_rows': AttendanceReportService.summary_for_month(selected_year, selected_month),
        })
        return context


class PayrollDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'employ/payroll_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_year = _safe_period_int(self.request.GET.get('year'), timezone.now().year)
        selected_month = _safe_period_int(self.request.GET.get('month'), timezone.now().month, min_value=1, max_value=12)
        employees = Employee.objects.select_related('user', 'salary_rule', 'default_shift').filter(employment_status='active')
        previews = [LivePayrollService.preview_for_period(employee, selected_year, selected_month) for employee in employees]
        previews.sort(key=lambda item: ((item.get('department_name') or ''), item['employee'].full_name))
        payroll_periods = PayrollPeriod.objects.order_by('-start_date')
        context.update({
            'selected_year': selected_year,
            'selected_month': selected_month,
            'months': [
                (1, 'كانون الثاني'),
                (2, 'شباط'),
                (3, 'آذار'),
                (4, 'نيسان'),
                (5, 'أيار'),
                (6, 'حزيران'),
                (7, 'تموز'),
                (8, 'آب'),
                (9, 'أيلول'),
                (10, 'تشرين الأول'),
                (11, 'تشرين الثاني'),
                (12, 'كانون الأول'),
            ],
            'previews': previews,
            'periods': payroll_periods[:12],
            'period_form': PayrollPeriodForm(),
            'employee_payrolls': EmployeePayroll.objects.select_related('employee__user', 'period').order_by('-generated_at')[:50],
            'payroll_totals': {
                'gross_salary': sum((item['gross_salary'] for item in previews), Decimal('0.00')),
                'overtime_total': sum((item['overtime_total'] for item in previews), Decimal('0.00')),
                'deductions_total': sum((item['deductions_total'] for item in previews), Decimal('0.00')),
                'advances_total': sum((item['advances_total'] for item in previews), Decimal('0.00')),
                'tax_total': sum((item['tax_total'] for item in previews), Decimal('0.00')),
                'insurance_total': sum((item['insurance_total'] for item in previews), Decimal('0.00')),
                'net_salary': sum((item['net_salary'] for item in previews), Decimal('0.00')),
            },
        })
        return context


class EmployeePayrollSlipView(LoginRequiredMixin, TemplateView):
    template_name = 'employ/employee_payroll_slip.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = get_object_or_404(
            Employee.objects.select_related('user', 'department', 'job_title', 'default_shift', 'salary_rule'),
            pk=kwargs['pk'],
        )
        selected_year = _safe_period_int(self.request.GET.get('year'), timezone.now().year)
        selected_month = _safe_period_int(self.request.GET.get('month'), timezone.now().month, min_value=1, max_value=12)
        preview = LivePayrollService.preview_for_period(employee, selected_year, selected_month)
        context.update({
            'employee': employee,
            'preview': preview,
            'selected_year': selected_year,
            'selected_month': selected_month,
            'generated_at': timezone.now(),
        })
        return context


class PayrollPeriodCreateView(LoginRequiredMixin, CreateView):
    model = PayrollPeriod
    form_class = PayrollPeriodForm
    success_url = reverse_lazy('employ:payroll_dashboard')

    def form_valid(self, form):
        messages.success(self.request, 'تم إنشاء فترة الرواتب بنجاح.')
        return super().form_valid(form)


class PayrollGenerateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        period = get_object_or_404(PayrollPeriod, pk=pk)
        payrolls = PayrollGenerationService.generate_period(period)
        messages.success(request, f'تم إنشاء مسير الرواتب للفترة بعدد {len(payrolls)} موظف.')
        return redirect('employ:payroll_dashboard')


class EmployeeReportsView(LoginRequiredMixin, TemplateView):
    template_name = 'employ/reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        default_start_date = _same_day_last_year(today)
        start_date = _safe_date_param(self.request.GET.get('start_date'), default_start_date)
        end_date = _safe_date_param(self.request.GET.get('end_date'), today)
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        selected_report = self.request.GET.get('report', 'overview')
        if selected_report not in {
            'overview', 'missing', 'late', 'overtime', 'early', 'holiday',
            'no_late', 'absence', 'punch_types', 'commitment',
            'unusual_overtime', 'leaves', 'employee_pages', 'ideas',
        }:
            selected_report = 'overview'
        overtime_threshold_hours = _safe_period_int(self.request.GET.get('overtime_threshold_hours'), 20, min_value=1)
        overtime_threshold_seconds = overtime_threshold_hours * 3600

        attendance_qs = (
            EmployeeAttendance.objects
            .filter(date__gte=start_date, date__lte=end_date)
            .select_related(
                'employee__user',
                'employee__department',
                'employee__job_title',
                'employee__default_shift',
                'employee__attendance_policy',
            )
            .order_by('-date', 'employee__user__first_name')
        )
        attendance_rows = list(attendance_qs)
        attendance_employee_ids = {row.employee_id for row in attendance_rows}
        employees_by_id = Employee.objects.select_related(
            'user',
            'department',
            'job_title',
            'default_shift',
            'attendance_policy',
        ).filter(
            Q(employment_status='active') | Q(pk__in=attendance_employee_ids)
        ).in_bulk()

        ranking_map = {}
        for employee in employees_by_id.values():
            employee.report_shift_label = _employee_shift_label(employee)
            ranking_map[employee.pk] = {
                'employee': employee,
                'attendance_days': 0,
                'missing_punch_days': 0,
                'late_days': 0,
                'early_leave_days': 0,
                'overtime_days': 0,
                'worked_seconds': 0,
                'late_seconds': 0,
                'early_leave_seconds': 0,
                'overtime_seconds': 0,
                'absence_seconds': 0,
                'required_work_seconds': 0,
                'absent_days': 0,
                'present_days': 0,
                'complete_days': 0,
                'incomplete_days': 0,
                'missing_check_in_days': 0,
                'missing_check_out_days': 0,
                'missing_both_days': 0,
            }

        missing_punch_rows = []
        late_detail_rows = []
        overtime_detail_rows = []
        early_leave_detail_rows = []
        absence_detail_rows = []
        attendance_details_by_employee = {employee_id: [] for employee_id in employees_by_id}
        for attendance in attendance_rows:
            attendance.employee.report_shift_label = getattr(
                attendance.employee,
                'report_shift_label',
                _employee_shift_label(attendance.employee),
            )
            metrics = _attendance_metrics_from_employee_shift(attendance)
            attendance.worked_seconds = metrics['worked_seconds']
            attendance.late_seconds = metrics['late_seconds']
            attendance.early_leave_seconds = metrics['early_leave_seconds']
            attendance.overtime_seconds = metrics['overtime_seconds']
            attendance.absence_seconds = metrics['absence_seconds']
            attendance.required_work_seconds_report = metrics.get('required_work_seconds', 0)
            has_check_in = bool(attendance.check_in)
            has_check_out = bool(attendance.check_out)
            attendance.report_is_absent = (not has_check_in and not has_check_out) or attendance.status == 'absent'
            attendance.report_status_label = 'غياب' if attendance.report_is_absent else attendance.get_status_display()

            bucket = ranking_map.setdefault(attendance.employee_id, {
                'employee': attendance.employee,
                'attendance_days': 0,
                'missing_punch_days': 0,
                'late_days': 0,
                'early_leave_days': 0,
                'overtime_days': 0,
                'worked_seconds': 0,
                'late_seconds': 0,
                'early_leave_seconds': 0,
                'overtime_seconds': 0,
                'absence_seconds': 0,
                'required_work_seconds': 0,
                'absent_days': 0,
                'present_days': 0,
                'complete_days': 0,
                'incomplete_days': 0,
                'missing_check_in_days': 0,
                'missing_check_out_days': 0,
                'missing_both_days': 0,
            })
            bucket['attendance_days'] += 1
            bucket['worked_seconds'] += metrics['worked_seconds']
            bucket['late_seconds'] += metrics['late_seconds']
            bucket['early_leave_seconds'] += metrics['early_leave_seconds']
            bucket['overtime_seconds'] += metrics['overtime_seconds']
            bucket['absence_seconds'] += metrics['absence_seconds']
            bucket['required_work_seconds'] += metrics.get('required_work_seconds', 0)
            if has_check_in or has_check_out:
                bucket['present_days'] += 1
            if attendance.report_is_absent:
                bucket['absent_days'] += 1
                absence_detail_rows.append(attendance)

            is_complete_day = (
                has_check_in and has_check_out
                and metrics['late_seconds'] == 0
                and metrics['early_leave_seconds'] == 0
            )
            if is_complete_day:
                bucket['complete_days'] += 1
            else:
                bucket['incomplete_days'] += 1

            if not has_check_in and not has_check_out:
                bucket['missing_both_days'] += 1
            elif not has_check_in:
                bucket['missing_check_in_days'] += 1
            elif not has_check_out:
                bucket['missing_check_out_days'] += 1

            if not attendance.check_in or not attendance.check_out:
                bucket['missing_punch_days'] += 1
                missing_punch_rows.append(attendance)
            if metrics['late_seconds'] > 0:
                bucket['late_days'] += 1
                late_detail_rows.append(attendance)
            if metrics['early_leave_seconds'] > 0:
                bucket['early_leave_days'] += 1
                early_leave_detail_rows.append(attendance)
            if metrics['overtime_seconds'] > 0:
                bucket['overtime_days'] += 1
                overtime_detail_rows.append(attendance)
            attendance_details_by_employee.setdefault(attendance.employee_id, []).append(attendance)

        ranking_rows = sorted(
            ranking_map.values(),
            key=lambda row: row['employee'].full_name or '',
        )
        late_report_rows = sorted(
            ranking_rows,
            key=lambda row: (row['late_seconds'], row['late_days']),
            reverse=True,
        )
        overtime_report_rows = sorted(
            ranking_rows,
            key=lambda row: (row['overtime_seconds'], row['overtime_days']),
            reverse=True,
        )
        early_leave_report_rows = sorted(
            ranking_rows,
            key=lambda row: (row['early_leave_seconds'], row['early_leave_days']),
            reverse=True,
        )
        missing_summary_rows = sorted(
            [row for row in ranking_rows if row['missing_punch_days'] > 0],
            key=lambda row: row['missing_punch_days'],
            reverse=True,
        )
        no_late_rows = sorted(
            [row for row in ranking_rows if row['attendance_days'] > 0 and row['late_seconds'] == 0],
            key=lambda row: row['employee'].full_name or '',
        )
        absence_report_rows = sorted(
            ranking_rows,
            key=lambda row: (row['absent_days'], row['absence_seconds']),
            reverse=True,
        )
        punch_type_rows = sorted(
            [row for row in ranking_rows if row['missing_punch_days'] > 0],
            key=lambda row: (row['missing_punch_days'], row['missing_both_days']),
            reverse=True,
        )
        commitment_rows = []
        for row in ranking_rows:
            attendance_days = row['attendance_days']
            row['commitment_rate'] = round((row['complete_days'] / attendance_days) * 100, 1) if attendance_days else 0
            commitment_rows.append(row)
        commitment_rows = sorted(
            commitment_rows,
            key=lambda row: (row['commitment_rate'], row['complete_days']),
            reverse=True,
        )
        unusual_overtime_rows = sorted(
            [row for row in ranking_rows if row['overtime_seconds'] > overtime_threshold_seconds],
            key=lambda row: row['overtime_seconds'],
            reverse=True,
        )
        attendance_by_employee_date = {
            (row.employee_id, row.date): row
            for row in attendance_rows
        }
        official_holidays = list(
            HRHoliday.objects.filter(
                is_active=True,
                start_date__lte=end_date,
                end_date__gte=start_date,
            ).order_by('start_date', 'name')
        )
        holiday_report_rows = []
        holiday_detail_rows = []
        for employee in employees_by_id.values():
            weekend_days = employee.get_weekend_day_numbers()
            summary = {
                'employee': employee,
                'holiday_days': 0,
                'official_holiday_days': 0,
                'weekend_days': 0,
                'worked_holiday_days': 0,
                'overtime_seconds': 0,
            }
            for target_date in _date_range(start_date, end_date):
                official_holiday = _holiday_from_list(target_date, official_holidays)
                is_weekend = target_date.weekday() in weekend_days
                if not official_holiday and not is_weekend:
                    continue

                attendance = attendance_by_employee_date.get((employee.pk, target_date))
                overtime_seconds = getattr(attendance, 'overtime_seconds', 0) if attendance else 0
                has_punch = bool(attendance and (attendance.check_in or attendance.check_out))
                holiday_name = official_holiday.name if official_holiday else 'عطلة أسبوعية'
                holiday_type = 'رسمية' if official_holiday else 'أسبوعية'

                summary['holiday_days'] += 1
                summary['official_holiday_days'] += 1 if official_holiday else 0
                summary['weekend_days'] += 1 if is_weekend and not official_holiday else 0
                summary['worked_holiday_days'] += 1 if has_punch else 0
                summary['overtime_seconds'] += overtime_seconds or 0
                holiday_detail_rows.append({
                    'date': target_date,
                    'employee': employee,
                    'holiday_name': holiday_name,
                    'holiday_type': holiday_type,
                    'attendance': attendance,
                    'has_punch': has_punch,
                    'overtime_seconds': overtime_seconds or 0,
                })
            holiday_report_rows.append(summary)
        holiday_report_rows = sorted(
            holiday_report_rows,
            key=lambda row: (row['holiday_days'], row['worked_holiday_days'], row['overtime_seconds']),
            reverse=True,
        )
        holiday_detail_rows = sorted(
            holiday_detail_rows,
            key=lambda row: (row['date'], row['employee'].full_name or ''),
        )
        vacations = list(
            Vacation.objects.select_related('employee__user', 'employee__department', 'employee__job_title').filter(
                start_date__lte=end_date,
                end_date__gte=start_date,
            )
        )
        vacation_days_by_employee = {}
        vacation_detail_rows = []
        for vacation in vacations:
            days = _overlap_days(vacation.start_date, vacation.end_date, start_date, end_date)
            if days <= 0:
                continue
            vacation_days_by_employee[vacation.employee_id] = vacation_days_by_employee.get(vacation.employee_id, 0) + days
            vacation_detail_rows.append({
                'employee': vacation.employee,
                'vacation': vacation,
                'days': days,
            })
        leave_report_rows = []
        for employee in employees_by_id.values():
            used_days = vacation_days_by_employee.get(employee.pk, 0)
            annual_days = employee.annual_leave_days or 0
            leave_report_rows.append({
                'employee': employee,
                'annual_days': annual_days,
                'used_days': used_days,
                'remaining_days': max(annual_days - used_days, 0),
            })
        leave_report_rows = sorted(leave_report_rows, key=lambda row: row['used_days'], reverse=True)

        holiday_detail_by_employee = {}
        for row in holiday_detail_rows:
            holiday_detail_by_employee.setdefault(row['employee'].pk, []).append(row)

        employee_page_rows = []
        for row in ranking_rows:
            employee = row['employee']
            employee_attendances = sorted(attendance_details_by_employee.get(employee.pk, []), key=lambda item: item.date)
            employee_holidays = holiday_detail_by_employee.get(employee.pk, [])
            holiday_days_except_friday = sum(1 for item in employee_holidays if item['date'].weekday() != 4)
            friday_attendances = [
                item for item in employee_attendances
                if item.date.weekday() == 4 and (item.check_in or item.check_out)
            ]
            missing_attendances = [
                item for item in employee_attendances
                if not item.check_in or not item.check_out
            ]
            exception_attendances = [
                item for item in employee_attendances
                if item.report_is_absent or item.late_seconds or item.early_leave_seconds or item.overtime_seconds or not item.check_in or not item.check_out
            ]
            required_seconds = row.get('required_work_seconds') or 0
            worked_seconds = row.get('worked_seconds') or 0
            employee_page_rows.append({
                'employee': employee,
                'summary': row,
                'attendances': employee_attendances,
                'exception_attendances': exception_attendances,
                'friday_attendances': friday_attendances,
                'missing_attendances': missing_attendances,
                'holidays': employee_holidays,
                'holidays_except_friday': holiday_days_except_friday,
                'friday_worked_days': len(friday_attendances),
                'missing_punch_days': row['missing_punch_days'],
                'commitment_rate': row.get('commitment_rate', 0),
                'work_completion_rate': round((worked_seconds / required_seconds) * 100, 1) if required_seconds else 0,
                'vacation_used_days': vacation_days_by_employee.get(employee.pk, 0),
                'vacation_remaining_days': max((employee.annual_leave_days or 0) - vacation_days_by_employee.get(employee.pk, 0), 0),
            })

        month_rows = AttendanceReportService.summary_for_month(today.year, today.month)
        late_total = sum(row['late_seconds'] for row in ranking_rows)
        early_leave_total = sum(row['early_leave_seconds'] for row in ranking_rows)
        overtime_total = sum(row['overtime_seconds'] for row in ranking_rows)
        absence_total = sum(row['absence_seconds'] for row in ranking_rows)
        context.update({
            'today': today,
            'start_date': start_date,
            'end_date': end_date,
            'selected_report': selected_report,
            'month_rows': month_rows,
            'absent_count': sum(1 for row in attendance_rows if getattr(row, 'report_is_absent', False)),
            'late_count': sum(1 for row in attendance_rows if row.late_seconds > 0),
            'early_leave_count': sum(1 for row in attendance_rows if row.early_leave_seconds > 0),
            'missing_punch_count': len(missing_punch_rows),
            'missing_punch_employee_count': len({row.employee_id for row in missing_punch_rows}),
            'overtime_total': overtime_total,
            'late_total': late_total,
            'early_leave_total': early_leave_total,
            'absence_total': absence_total,
            'missing_punch_rows': missing_punch_rows,
            'missing_punch_total_count': len(missing_punch_rows),
            'missing_punch_limit': None,
            'missing_summary_rows': missing_summary_rows,
            'late_report_rows': late_report_rows,
            'overtime_report_rows': overtime_report_rows,
            'early_leave_report_rows': early_leave_report_rows,
            'late_detail_rows': late_detail_rows,
            'overtime_detail_rows': overtime_detail_rows,
            'early_leave_detail_rows': early_leave_detail_rows,
            'holiday_report_rows': holiday_report_rows,
            'holiday_detail_rows': holiday_detail_rows,
            'holiday_total_days': sum(row['holiday_days'] for row in holiday_report_rows),
            'holiday_worked_days': sum(row['worked_holiday_days'] for row in holiday_report_rows),
            'no_late_rows': no_late_rows,
            'absence_report_rows': absence_report_rows,
            'absence_detail_rows': absence_detail_rows,
            'punch_type_rows': punch_type_rows,
            'commitment_rows': commitment_rows,
            'unusual_overtime_rows': unusual_overtime_rows,
            'overtime_threshold_hours': overtime_threshold_hours,
            'leave_report_rows': leave_report_rows,
            'vacation_detail_rows': vacation_detail_rows,
            'employee_page_rows': employee_page_rows,
            'hr_report_ideas': [
                'تقرير الموظفين بدون أي تأخير خلال الفترة.',
                'تقرير الغياب المتكرر حسب الموظف والقسم.',
                'تقرير نقص البصمات حسب الموظف: دخول ناقص، خروج ناقص، أو الاثنين.',
                'تقرير الالتزام بالدوام: أيام مكتملة مقابل أيام ناقصة لكل موظف.',
                'تقرير الإضافي غير المعتاد للموظفين الذين تجاوزوا حد معين.',
                'تقرير الإجازات السنوية والمستهلك والمتبقي لكل موظف.',
            ],
            'recent_payrolls': EmployeePayroll.objects.select_related('employee__user', 'period').order_by('-generated_at')[:20],
            'recent_advances': EmployeeAdvance.objects.select_related('employee__user').order_by('-date')[:20],
        })
        return context


class EmployeeReportsPrintView(EmployeeReportsView):
    template_name = 'employ/reports_print.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_report = self.request.GET.get('report', 'all')
        if selected_report not in {
            'all', 'missing', 'late', 'overtime', 'early', 'holiday',
            'no_late', 'absence', 'punch_types', 'commitment',
            'unusual_overtime', 'leaves', 'employee_pages',
        }:
            selected_report = 'all'
        context.update({
            'selected_report': selected_report,
            'generated_at': timezone.now(),
        })
        return context


def no_permission(request):
    return render(request, "503.html", status=503)


def require_employee_perm(permission_code):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            # تنفيذ الكود الخاص بالصلاحية
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# -----------------------------
# إدارة حسابات السلف للأساتذة
# -----------------------------
class CreateTeacherAdvanceAccountView(View):
    """إنشاء حساب سلفة للمدرس يدوياً فقط"""
    
    def post(self, request, pk):
        teacher = get_object_or_404(Teacher, pk=pk)
        
        # التحقق إذا كان الحساب موجوداً
        existing_account = teacher.get_teacher_advance_account()
        if existing_account:
            messages.info(request, f'حساب السلفة للمدرس {teacher.full_name} موجود بالفعل')
            return redirect('employ:teacher_profile', pk=teacher.pk)
        
        # إنشاء الحساب يدوياً
        from accounts.models import Account
        try:
            # كود الحساب: 121-5XXX حيث XXX هو ID المدرس
            account_code = f"121-5{teacher.pk:03d}"
            
            account, created = Account.objects.get_or_create(
                code=account_code,
                defaults={
                    'name': f'Teacher Advance - {teacher.full_name}',
                    'name_ar': f'سلف أستاذ - {teacher.full_name}',
                    'account_type': 'ASSET',
                    'is_active': True,
                }
            )
            
            if created:
                messages.success(request, f'تم إنشاء حساب سلفة للمدرس {teacher.full_name}: {account.code}')
            else:
                messages.info(request, f'حساب السلفة موجود مسبقاً: {account.code}')
                
        except Exception as e:
            messages.error(request, f'خطأ في إنشاء حساب السلفة: {e}')
        
        return redirect('employ:teacher_profile', pk=teacher.pk)

import re
from decimal import Decimal, InvalidOperation
# -----------------------------
# إدارة الرواتب اليدوية
# -----------------------------
class AddManualSalaryView(LoginRequiredMixin, View):
    """إضافة راتب يدوي للمدرس"""
    
    template_name = 'employ/add_manual_salary.html'

    def _redirect_with_period(self, teacher_pk, year, month):
        url = reverse('employ:add_manual_salary', kwargs={'pk': teacher_pk})
        return redirect(f'{url}?year={year}&month={month}')
    
    def get(self, request, pk):
        teacher = get_object_or_404(Teacher, pk=pk)
        
        # حساب السلف غير المسددة
        total_advances = teacher.get_total_advances()
        
        # الشهور المتاحة
        current_year = date.today().year
        years_range = range(current_year - 5, current_year + 2)
        selected_year = request.GET.get('year')
        selected_month = request.GET.get('month')
        selected_year = _safe_period_int(selected_year, date.today().year)
        selected_month = _safe_period_int(selected_month, date.today().month, min_value=1, max_value=12)
        total_advances = teacher.get_total_advances(selected_year, selected_month)
        auto_gross_salary = teacher.calculate_monthly_salary(selected_year, selected_month)
        max_advance_deduction = min(auto_gross_salary, total_advances)
        
        context = {
            'teacher': teacher,
            'total_advances': total_advances,
            'years_range': years_range,
            'today': date.today(),
            'selected_year': selected_year,
            'selected_month': selected_month,
            'auto_gross_salary': auto_gross_salary,
            'max_advance_deduction': max_advance_deduction,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, pk):
        teacher = get_object_or_404(Teacher, pk=pk)
        
        # **1. تحقق من السنة والشهر بشكل آمن**
        try:
            year_str = request.POST.get('year', '').strip()
            month_str = request.POST.get('month', '').strip()
            
            # إذا كانت فارغة، استخدم القيم الحالية
            if not year_str or not year_str.isdigit():
                year = date.today().year
            else:
                year = int(year_str)
            
            if not month_str or not month_str.isdigit():
                month = date.today().month
            else:
                month = int(month_str)
                
            # تأكد من أن الشهر بين 1 و 12
            if month < 1 or month > 12:
                month = date.today().month
                
        except:
            # إذا فشل كل شيء، استخدم التاريخ الحالي
            today = date.today()
            year = today.year
            month = today.month
        
        # **2. الحصول على القيم المالية**
        gross_salary_str = request.POST.get('gross_salary', '').strip()
        advance_deduction_str = request.POST.get('advance_deduction', '0').strip()
        notes = request.POST.get('notes', '')
        
        # **3. التحقق من وجود راتب لنفس الشهر**
        existing = ManualTeacherSalary.objects.filter(
            teacher=teacher, year=year, month=month
        ).exists()
        
        if existing:
            messages.error(request, f'❌ تم إضافة راتب لهذا الشهر مسبقاً!')
            return self._redirect_with_period(teacher.pk, year, month)
        
        # **4. التحقق من الراتب الإجمالي**
        if not gross_salary_str:
            messages.error(request, '❌ يجب إدخال قيمة للراتب الإجمالي')
            return self._redirect_with_period(teacher.pk, year, month)
        gross_salary = None
        
        # **5. محاولة تحويل الراتب إلى رقم**
        try:
            # تنظيف النص
            advance_clean = advance_deduction_str.replace(',', '').replace(' ', '')
            
            # تحويل إلى Decimal
            if gross_salary is None:
                gross_clean = gross_salary_str.replace(',', '').replace(' ', '')
                gross_salary = Decimal(gross_clean)
            advance_deduction = Decimal(advance_clean) if advance_clean else Decimal('0')
            
        except:
            messages.error(request, '❌ قيمة الراتب غير صحيحة. استخدم أرقاماً فقط')
            return self._redirect_with_period(teacher.pk, year, month)
        
        # **6. التحقق من أن الراتب أكبر من الصفر**
        if gross_salary <= 0:
            messages.error(request, '❌ يجب أن يكون الراتب أكبر من صفر')
            return self._redirect_with_period(teacher.pk, year, month)
        
        # **7. حساب الصافي وإنشاء الراتب**
        if advance_deduction < 0:
            messages.error(request, 'â‌Œ لا يمكن أن يكون خصم السلف قيمة سالبة')
            return self._redirect_with_period(teacher.pk, year, month)

        total_advances = teacher.get_total_advances(year, month)

        if advance_deduction > gross_salary:
            messages.error(request, 'â‌Œ لا يمكن أن يتجاوز خصم السلف قيمة الراتب الإجمالي')
            return self._redirect_with_period(teacher.pk, year, month)

        if advance_deduction > total_advances:
            messages.error(
                request,
                f'â‌Œ لا يمكن أن يتجاوز خصم السلف السلف المستحقة لهذه الفترة ({total_advances})'
            )
            return self._redirect_with_period(teacher.pk, year, month)

        net_salary = gross_salary - advance_deduction
        
        try:
            salary = ManualTeacherSalary.objects.create(
                teacher=teacher,
                year=year,
                month=month,
                gross_salary=gross_salary,
                advance_deduction=advance_deduction,
                net_salary=net_salary,
                notes=notes,
                created_by=request.user
            )
            
            messages.success(request, f'✅ تم إضافة راتب شهر {month}/{year} للمدرس {teacher.full_name}')
            return redirect('employ:teacher_profile', pk=teacher.pk)
            
        except Exception as e:
            messages.error(request, f'❌ خطأ في الحفظ: {str(e)}')
            return self._redirect_with_period(teacher.pk, year, month)
        
class EditManualSalaryView(LoginRequiredMixin, View):
    """تعديل راتب يدوي"""
    
    template_name = 'employ/edit_manual_salary.html'
    
    def get(self, request, pk):
        salary = get_object_or_404(ManualTeacherSalary, pk=pk)
        
        # التحقق من صلاحية التعديل (غير مدفوع)
        if salary.is_paid:
            messages.error(request, 'لا يمكن تعديل راتب تم دفعه')
            return redirect('employ:teacher_profile', pk=salary.teacher.pk)
        
        # حساب السلف غير المسددة
        total_advances = salary.teacher.get_total_advances(salary.year, salary.month)
        
        context = {
            'salary': salary,
            'teacher': salary.teacher,
            'total_advances': total_advances,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, pk):
        salary = get_object_or_404(ManualTeacherSalary, pk=pk)
        
        # التحقق من صلاحية التعديل
        if salary.is_paid:
            messages.error(request, 'لا يمكن تعديل راتب تم دفعه')
            return redirect('employ:teacher_profile', pk=salary.teacher.pk)
        
        try:
            gross_salary = Decimal(request.POST.get('gross_salary', '0'))
            advance_deduction = Decimal(request.POST.get('advance_deduction', '0'))
            notes = request.POST.get('notes', '')
            
            # التحقق من عدم تجاوز خصم السلف
            if advance_deduction > gross_salary:
                messages.error(request, 'لا يمكن أن يتجاوز خصم السلف قيمة الراتب الإجمالي')
                return redirect('employ:edit_manual_salary', pk=salary.pk)
            
            # تحديث الراتب
            salary.gross_salary = gross_salary
            salary.advance_deduction = advance_deduction
            salary.notes = notes
            salary.save()
            
            messages.success(request, 'تم تعديل الراتب بنجاح')
            return redirect('employ:teacher_profile', pk=salary.teacher.pk)
            
        except Exception as e:
            messages.error(request, f'خطأ في تعديل الراتب: {e}')
            return redirect('employ:edit_manual_salary', pk=salary.pk)


class PayManualSalaryView(LoginRequiredMixin, View):
    """دفع راتب يدوي"""
    
    def post(self, request, pk):
        salary = get_object_or_404(ManualTeacherSalary, pk=pk)
        
        # التحقق من عدم دفعه مسبقاً
        if salary.is_paid:
            messages.warning(request, 'هذا الراتب مدفوع مسبقاً')
            return redirect('employ:teacher_profile', pk=salary.teacher.pk)
        
        try:
            # تسجيل الدفع وإنشاء القيد وتحديث السلف بآلية موحدة
            salary.mark_as_paid(request.user)
            
            messages.success(request, f'تم دفع راتب شهر {salary.get_month_display()} {salary.year} للمدرس {salary.teacher.full_name}')
            
        except Exception as e:
            messages.error(request, f'خطأ في عملية الدفع: {e}')
        
        return redirect('employ:teacher_profile', pk=salary.teacher.pk)


class ViewManualSalaryView(LoginRequiredMixin, DetailView):
    """عرض تفاصيل راتب يدوي"""
    
    model = ManualTeacherSalary
    template_name = 'employ/view_manual_salary.html'
    context_object_name = 'salary'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['teacher'] = self.object.teacher
        return context


class TeacherPartnerLedgerView(LoginRequiredMixin, DetailView):
    """كشف تفصيلي لحساب الشريك (دفتر الأستاذ)"""
    model = Teacher
    template_name = 'employ/teacher_partner_ledger.html'
    context_object_name = 'teacher'
    pk_url_kwarg = 'teacher_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.get_object()
        
        if not teacher.is_partner:
            from django.http import Http404
            raise Http404("هذا المدرس ليس شريكاً مساهماً")
            
        from accounts.models import Account, Transaction
        from django.shortcuts import get_object_or_404
        from decimal import Decimal
        
        account_id = self.kwargs.get('account_id')
        account = get_object_or_404(Account, id=account_id)
        
        current_year = getattr(self.request, 'current_academic_year', None)
        
        # جلب المعاملات (دفتر الأستاذ) للحساب
        transactions_qs = Transaction.objects.filter(account=account).select_related('journal_entry').order_by('journal_entry__date', 'id')
        if current_year:
            transactions_qs = transactions_qs.filter(journal_entry__academic_year=current_year)
            
        # حساب الرصيد المتراكم
        transactions = []
        running_balance = Decimal('0.00')
        total_debit = Decimal('0.00')
        total_credit = Decimal('0.00')
        
        for tx in transactions_qs:
            amount = tx.amount or Decimal('0.00')
            dollar_amount = tx.dollar_amount
            is_debit = tx.is_debit
            
            if is_debit:
                debit_val = amount
                credit_val = Decimal('0.00')
                total_debit += amount
            else:
                debit_val = Decimal('0.00')
                credit_val = amount
                total_credit += amount
                
            # حساب الرصيد المتراكم بناءً على نوع الحساب
            if account.account_type in ['ASSET', 'EXPENSE']:
                if is_debit:
                    running_balance += amount
                else:
                    running_balance -= amount
            else: # LIABILITY, EQUITY, REVENUE
                if is_debit:
                    running_balance -= amount
                else:
                    running_balance += amount
                    
            transactions.append({
                'id': tx.id,
                'date': tx.journal_entry.date,
                'entry_number': tx.journal_entry.entry_number or tx.journal_entry.id,
                'journal_entry_id': tx.journal_entry.id,
                'description': tx.journal_entry.description,
                'debit': debit_val,
                'credit': credit_val,
                'dollar_amount': dollar_amount,
                'running_balance': running_balance,
            })
            
        net_balance = account.get_rollup_balance(academic_year=current_year)
        
        context.update({
            'account': account,
            'transactions': transactions,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'net_balance': net_balance,
            'current_year': current_year,
        })
        return context
