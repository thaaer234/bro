# views.py
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from students.models import Student
from employ.models import Employee, Teacher, EmployeePermission
from accounts.models import Transaction, Course
from django.utils import timezone
from datetime import timedelta, datetime, time as time_value
from decimal import Decimal
from django.db.models import Sum, Q, Count, Max
from .models import ActivityLog  # استيراد النموذج الجديد
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import redirect, render
import json
from urllib.parse import urlencode
from api.models import MobileUser
from mobile.models import MobileDeviceToken
from .user_guide import build_user_guide_context
from .manual_center import build_manual_center_context
from manuals.guide_data import build_manuals_context, build_user_manual_context
from django.urls import reverse, NoReverseMatch


SITEMAP_PERMISSION_GROUPS = [
    ('students_', 'students', 'الطلاب النظاميون', 'fas fa-user-graduate'),
    ('quick_students_', 'quick', 'الطلاب السريعون', 'fas fa-bolt'),
    ('attendance_', 'attendance', 'الحضور', 'fas fa-calendar-check'),
    ('classroom_', 'classroom', 'الشعب الدراسية', 'fas fa-school'),
    ('courses_', 'courses', 'المواد الدراسية', 'fas fa-book-open'),
    ('exams_', 'exams', 'الاختبارات', 'fas fa-square-poll-vertical'),
    ('teachers_', 'employ', 'المدرسون', 'fas fa-chalkboard-user'),
    ('hr_', 'employ', 'الموارد البشرية', 'fas fa-users-gear'),
    ('accounting_', 'accounts', 'المحاسبة', 'fas fa-calculator'),
    ('course_accounting_', 'accounts', 'دورات المحاسبة', 'fas fa-file-invoice-dollar'),
    ('reports_', 'pages', 'التقارير والتحليلات', 'fas fa-chart-line'),
    ('admin_', 'pages', 'الإدارة العامة', 'fas fa-shield-halved'),
]

GUIDE_PARAM_KEYS = (
    'guide',
    'guide_target',
    'guide_title',
    'guide_message',
    'guide_duration',
    'guide_modal',
)


def _sitemap_button_icon(label):
    text = (label or '').strip()
    rules = [
        (('قيد', 'يومية'), 'fas fa-book-medical'),
        (('طالب سريع',), 'fas fa-bolt'),
        (('طالب',), 'fas fa-user-graduate'),
        (('مدرس', 'أستاذ'), 'fas fa-chalkboard-user'),
        (('موظف',), 'fas fa-id-badge'),
        (('بحث', 'فلتر'), 'fas fa-magnifying-glass'),
        (('حفظ', 'اعتماد'), 'fas fa-floppy-disk'),
        (('طباعة', 'pdf'), 'fas fa-print'),
        (('تقرير', 'كشف', 'ميزان'), 'fas fa-chart-column'),
        (('عرض الطلاب', 'عرض'), 'fas fa-users'),
        (('سلفة', 'دفعة', 'صرف'), 'fas fa-hand-holding-dollar'),
        (('حضور',), 'fas fa-calendar-check'),
        (('دورة',), 'fas fa-book-open'),
        (('ربط',), 'fas fa-link'),
        (('إعداد', 'صلاح'), 'fas fa-sliders'),
    ]
    for keywords, icon in rules:
        if any(keyword in text for keyword in keywords):
            return icon
    return 'fas fa-circle-nodes'


def _build_guide_url(path, *, target='@primary-action', title='', message='', duration=10000, modal=''):
    clean_path = (path or '').strip()
    if not clean_path:
        return ''
    separator = '&' if '?' in clean_path else '?'
    params = {
        'guide': '1',
        'guide_target': target or '@primary-action',
        'guide_title': title or 'خطوة موجهة',
        'guide_message': message or 'اتبع التمييز لإكمال هذه الخطوة.',
        'guide_duration': duration,
    }
    if modal:
        params['guide_modal'] = modal
    return f"{clean_path}{separator}{urlencode(params)}"


def _safe_reverse(name, *args, **kwargs):
    try:
        return reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return ''


def _decorate_sitemap_button(screen, button):
    label = (button.get('label') or '').strip()
    screen_slug = screen.get('slug', '')
    screen_path = screen.get('path', '') if str(screen.get('path', '')).startswith('/') else ''

    target_path = screen_path
    guide_target = '@primary-action'
    guide_title = f'تنقل مباشر: {label}'
    guide_message = f'انتقلت الآن إلى المكان الأنسب لتنفيذ إجراء "{label}". اتبع العنصر المضيء لإكمال الخطوة.'
    guide_modal = ''

    if 'قيد' in label and 'جديد' in label:
        target_path = _safe_reverse('accounts:journal_entry_create')
        guide_target = '@first-field'
    elif 'إضافة طالب سريع' in label:
        target_path = _safe_reverse('quick:student_create')
        guide_target = '@first-field'
    elif 'لوحة التحكم' in label:
        target_path = _safe_reverse('pages:index')
        guide_target = '@primary-action'
    elif 'دليل المستخدم' in label:
        target_path = _safe_reverse('manuals:home')
        guide_target = '@search'
    elif 'دليل التشغيل' in label:
        target_path = _safe_reverse('manuals:handbook')
        guide_target = '@search'
    elif 'مجموعة الطلاب' in label:
        target_path = _safe_reverse('students:student_list')
        guide_target = '[data-guide-key="students-create"]'
    elif 'المحاسبة' in label:
        target_path = _safe_reverse('accounts:dashboard')
        guide_target = '[data-guide-key="accounts-journal-create"]'
    elif 'إضافة طالب' in label or 'طالب جديد' in label:
        target_path = _safe_reverse('students:student_type_choice') or _safe_reverse('students:create_student')
        guide_target = '@primary-action'
    elif 'الأسماء المكررة' in label:
        target_path = _safe_reverse('quick:duplicate_students_report')
        guide_target = '@search'
    elif 'الطلاب المشتركون' in label:
        target_path = _safe_reverse('quick:student_intersections')
        guide_target = '@search'
    elif 'فرز شبه يدوي' in label:
        target_path = _safe_reverse('quick:manual_sorting')
        guide_target = '@primary-action'
    elif 'ربط تلقائي' in label:
        target_path = _safe_reverse('quick:student_list')
        guide_target = '[data-guide-key="quick-auto-assign-years"]'
        guide_message = 'هذه الأداة تنفذ الربط التلقائي. راجع البيانات ثم استخدم الزر المضيء لإتمام الربط.'
    elif 'دورة جديدة' in label:
        target_path = _safe_reverse('quick:course_create')
        guide_target = '@first-field'
    elif 'حضور الدورات السريعة' in label:
        target_path = _safe_reverse('quick:quick_course_attendance')
        guide_target = '@primary-action'
    elif 'تعارض الطلاب' in label:
        target_path = _safe_reverse('quick:quick_course_conflicts_report')
        guide_target = '@search'
    elif 'توليد برنامج لكل الدورات' in label:
        target_path = _safe_reverse('quick:course_list')
        guide_target = '@primary-action'
    elif 'برنامج الصفوف' in label:
        target_path = _safe_reverse('quick:quick_course_schedule_print')
        guide_target = '@search'
    elif 'حساب جديد' in label:
        target_path = _safe_reverse('accounts:account_create')
        guide_target = '@first-field'
    elif 'الإيصالات والمصاريف' in label:
        target_path = _safe_reverse('accounts:receipts_expenses')
        guide_target = '@primary-action'
    elif 'التقارير' in label:
        target_path = _safe_reverse('accounts:reports')
        guide_target = '@primary-action'
    elif 'المتأخرون عن السداد' in label:
        target_path = _safe_reverse('quick:late_payment_courses')
        guide_target = '@search'
    elif screen_slug == 'quick-outstanding-courses' and 'عرض الطلاب' in label:
        target_path = _safe_reverse('quick:outstanding_courses') + '?course_type=INTENSIVE'
        guide_target = '[data-guide-key="quick-outstanding-show-students"]'
        guide_message = 'اختر الدورة المطلوبة ثم استخدم زر "عرض الطلاب" المضيء للوصول إلى تفاصيل غير المسددين.'
    elif screen_slug == 'quick-outstanding-courses' and 'طباعة' in label:
        target_path = _safe_reverse('quick:outstanding_courses') + '?course_type=INTENSIVE'
        guide_target = '[data-guide-key="quick-outstanding-print-intensive"]'
        guide_message = 'الزر المضيء يفتح نسخة الطباعة الجاهزة لهذا التقرير.'
    elif screen_slug == 'accounts-outstanding-courses' and 'عرض حسب الشعب' in label:
        target_path = _safe_reverse('accounts:outstanding_students_by_classroom')
        guide_target = '@search'
    elif screen_slug == 'accounts-outstanding-courses' and 'الطلاب المنسحبين' in label:
        target_path = _safe_reverse('accounts:withdrawn_students')
        guide_target = '@search'
    elif screen_slug == 'accounts-outstanding-courses' and 'عرض الطلاب' in label:
        target_path = _safe_reverse('accounts:outstanding_courses')
        guide_target = '[data-guide-key="accounts-outstanding-show-students"]'
        guide_message = 'بعد فتح التقرير استخدم زر "عرض الطلاب" المضيء داخل صف الدورة للوصول إلى التفاصيل.'
    elif 'دفعات الأستاذ' in label or 'دفعة للأستاذ' in label:
        target_path = _safe_reverse('quick:outstanding_courses') + '?course_type=INTENSIVE'
        guide_target = '[data-guide-key="quick-teacher-payout"]'
        guide_message = 'أنت الآن في قسم المتبقي للدورات السريعة. استخدم زر "دفعات الأستاذ" المضيء داخل صف الدورة المطلوبة.'
    elif 'سلفة موظف' in label:
        target_path = _safe_reverse('employ:employee_advance_create')
        guide_target = '@first-field'
    elif 'سلفة مدرس' in label:
        target_path = _safe_reverse('employ:teachers')
        guide_target = '@table-action'
        guide_message = 'انتقلت إلى قسم المدرسين. افتح ملف المدرس المطلوب ثم أكمل إلى صفحة السلفة من الإجراءات المتاحة.'
    elif 'مدرس جديد' in label or ('مدرس' in label and 'جديد' in label):
        target_path = _safe_reverse('employ:create')
        guide_target = '@first-field'
    elif 'حفظ' in label:
        guide_target = 'button[type="submit"], .btn-success'
    elif 'بحث' in label:
        guide_target = '@search'

    action_url = _build_guide_url(
        target_path,
        target=guide_target,
        title=guide_title,
        message=guide_message,
        duration=10000,
        modal=guide_modal,
    ) if target_path else ''

    return {
        **button,
        'icon': _sitemap_button_icon(label),
        'action_url': action_url,
        'action_target': guide_target,
    }


def _decorate_sitemap_screens(screens):
    decorated_screens = []
    for screen in screens:
        buttons = [_decorate_sitemap_button(screen, button) for button in screen.get('buttons', [])]
        decorated_screens.append({
            **screen,
            'buttons': buttons,
        })
    return decorated_screens


def _build_sitemap_permission_summary(user):
    granted_codes = set()
    if getattr(user, 'is_authenticated', False):
        if getattr(user, 'is_superuser', False):
            granted_codes = {code for code, _label in EmployeePermission.PERMISSION_CHOICES}
        else:
            employee = getattr(user, 'employee_profile', None)
            if employee:
                granted_codes = set(
                    employee.permissions.filter(is_granted=True).values_list('permission', flat=True)
                )

    summaries = []
    for prefix, group_key, title, icon in SITEMAP_PERMISSION_GROUPS:
        items = [
            {'code': code, 'label': label}
            for code, label in EmployeePermission.PERMISSION_CHOICES
            if code.startswith(prefix)
        ]
        if not items:
            continue
        granted_count = sum(1 for item in items if item['code'] in granted_codes)
        summaries.append({
            'key': group_key,
            'title': title,
            'icon': icon,
            'total_count': len(items),
            'granted_count': granted_count,
            'items': items,
        })

    return summaries, len(granted_codes)


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = 'pages/index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # إحصائيات الطلاب والمدرسين
        context['students_count'] = Student.objects.count()
        context['teachers_count'] = Teacher.objects.count()
        
        # حساب الدخل والمصروفات الشهرية
        start_date = timezone.now().replace(day=1)
        end_date = start_date + timedelta(days=31)
        
        # context['monthly_income'] = Transaction.objects.filter(
        #     type='income',
        #     date__gte=start_date,
        #     date__lte=end_date
        # ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # context['monthly_expenses'] = Transaction.objects.filter(
        #     type='expense',
        #     date__gte=start_date,
        #     date__lte=end_date
        # ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # جلب جميع المستخدمين للفلترة باستثناء admin
        context['users'] = User.objects.exclude(username='admin')
        
        # جلب معاملات الفلترة من الطلب
        user_filter = self.request.GET.get('user', '')
        start_date_filter = self.request.GET.get('start_date', '')
        end_date_filter = self.request.GET.get('end_date', '')
        
        # حفظ قيم الفلترة للعرض في القوائم
        context['selected_user'] = user_filter
        context['start_date'] = start_date_filter
        context['end_date'] = end_date_filter
        
        # بناء الاستعلام مع الفلترة - استبعاد نشاطات admin
        activity_query = ActivityLog.objects.filter(
            Q(user__is_superuser=False) | Q(user__isnull=True)
        ).exclude(content_type='LogEntry')
        
        # استبعاد نشاطات المستخدم admin إذا كان اسم المستخدم admin
        activity_query = activity_query.exclude(user__username='admin')
        
        # تطبيق فلترة المستخدم
        if user_filter:
            activity_query = activity_query.filter(user_id=user_filter)
        
        # تطبيق فلترة التاريخ
        if start_date_filter:
            try:
                start_date = datetime.strptime(start_date_filter, '%Y-%m-%d')
                activity_query = activity_query.filter(timestamp__gte=start_date)
            except ValueError:
                pass  # تجاهل في حالة تاريخ غير صحيح
        
        if end_date_filter:
            try:
                end_date = datetime.strptime(end_date_filter, '%Y-%m-%d')
                # إضافة يوم كامل للتأكد من تضمين اليوم المحدد
                end_date = end_date + timedelta(days=1)
                activity_query = activity_query.filter(timestamp__lt=end_date)
            except ValueError:
                pass  # تجاهل في حالة تاريخ غير صحيح
        
        # ترتيب النتائج وتحديد العدد
        context['recent_activities'] = activity_query.order_by('-timestamp')[:2000]  # تحديد 50 نشاط فقط
        
        return context
    
    
class welcome(TemplateView):
    template_name =   'pages/welcome.html'      


class UserGuideView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        return redirect('manuals:home')


class UserGuideHandbookView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        return redirect('manuals:handbook')


class ManualCenterView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        return redirect('manuals:home')


class ManualCenterHandbookView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        return redirect('manuals:handbook')


from django.http import HttpResponse, JsonResponse
import csv
from django.contrib.admin.models import LogEntry
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

def export_activities(request):
    # جلب البيانات المصفاة
    user_id = request.GET.get('user')
    action = request.GET.get('action')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    activities = LogEntry.objects.all().select_related('user', 'content_type')
    
    # تطبيق الفلاتر
    if user_id:
        activities = activities.filter(user_id=user_id)
    if action:
        # تحويل action من نص إلى رقم
        action_map = {'add': 1, 'change': 2, 'delete': 3}
        activities = activities.filter(action_flag=action_map.get(action, 0))
    if start_date:
        activities = activities.filter(action_time__gte=start_date)
    if end_date:
        activities = activities.filter(action_time__lte=end_date)
    
    # إنشاء response مع ملف CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="activities_export.csv"'
    
    # كتابة BOM للتعرف على UTF-8 في Excel
    response.write('\ufeff')
    
    writer = csv.writer(response)
    # كتابة العناوين
    writer.writerow(['النشاط', 'المستخدم', 'الكائن', 'التفاصيل', 'التاريخ', 'الوقت'])
    
    # كتابة البيانات
    for activity in activities:
        writer.writerow([
            activity.get_action_flag_display(),
            str(activity.user.get_full_name()) if activity.user and activity.user.get_full_name() else str(activity.user) if activity.user else 'نظام',
            f"{activity.content_type} - {activity.object_repr}",
            activity.change_message or '',
            activity.action_time.strftime('%Y-%m-%d'),
            activity.action_time.strftime('%H:%M'),
        ])
    
    return response


def sitemap_view(request):
    """عرض خريطة الموقع الشاملة"""
    context = build_user_guide_context()
    manuals_context = build_manuals_context()
    user_manual_context = build_user_manual_context(request.user)
    permission_groups, granted_permissions_count = _build_sitemap_permission_summary(request.user)

    context.update(manuals_context)
    manual_user_screens = _decorate_sitemap_screens(user_manual_context.get('manual_screens', []))

    context.update({
        'manual_user_allowed_group_keys': user_manual_context.get('manual_user_allowed_group_keys', []),
        'manual_user_departments': user_manual_context.get('manual_user_departments', []),
        'manual_user_screen_total': len(manual_user_screens),
        'manual_user_screens': manual_user_screens,
        'sitemap_permission_groups': permission_groups,
        'sitemap_total_permissions': len(EmployeePermission.PERMISSION_CHOICES),
        'sitemap_granted_permissions_count': granted_permissions_count,
    })
    return render(request, 'pages/sitemap.html', context)


def app_users_report(request):
    today = timezone.localdate()

    device_stats = MobileDeviceToken.objects.values(
        "user_type", "user_id"
    ).annotate(
        devices=Count("id"),
        last_seen=Max("last_seen_at"),
        today_active=Count("id", filter=Q(last_seen_at__date=today)),
    )
    device_map = {
        (row["user_type"], row["user_id"]): row for row in device_stats
    }

    total_users = MobileUser.objects.count()
    students_total = MobileUser.objects.filter(user_type="student").count()
    parents_total = MobileUser.objects.filter(user_type="parent").count()
    teachers_total = MobileUser.objects.filter(user_type="teacher").count()

    devices_total = MobileDeviceToken.objects.count()
    daily_logins = MobileDeviceToken.objects.filter(last_seen_at__date=today).values("token").distinct().count()
    active_devices = MobileDeviceToken.objects.filter(last_seen_at__date=today).count()

    last_login_user = MobileUser.objects.aggregate(last=Max("last_login")).get("last")
    last_seen_device = MobileDeviceToken.objects.aggregate(last=Max("last_seen_at")).get("last")
    last_activity = max(
        [dt for dt in [last_login_user, last_seen_device] if dt is not None],
        default=None,
    )

    role_counts = {
        row["login_role"] or "غير محدد": row["count"]
        for row in MobileDeviceToken.objects.values("login_role").annotate(count=Count("id"))
    }

    users_list = []
    for user in MobileUser.objects.select_related("student", "teacher").order_by("-last_login"):
        if user.user_type == "teacher":
            profile_name = user.teacher.full_name if user.teacher_id else user.username
            profile_id = user.teacher_id
        else:
            profile_name = user.student.full_name if user.student_id else user.username
            profile_id = user.student_id
        key = (user.user_type, profile_id)
        stats = device_map.get(key, {})
        users_list.append({
            "name": profile_name,
            "username": user.username,
            "user_type": user.user_type,
            "last_login": user.last_login,
            "devices": stats.get("devices", 0),
            "last_seen": stats.get("last_seen"),
            "today_active": stats.get("today_active", 0),
        })

    most_active_user = None
    most_active_count = 0
    if users_list:
        most_active_user = max(users_list, key=lambda u: u.get("today_active", 0))
        most_active_count = most_active_user.get("today_active", 0)

    context = {
        "total_users": total_users,
        "students_total": students_total,
        "parents_total": parents_total,
        "teachers_total": teachers_total,
        "daily_logins": daily_logins,
        "active_devices": active_devices,
        "devices_total": devices_total,
        "last_activity": last_activity,
        "role_counts": role_counts,
        "users_list": users_list,
        "most_active_user": most_active_user,
        "most_active_count": most_active_count,
    }
    return render(request, "pages/app_users_report.html", context)


@login_required
@require_POST
def track_click_event(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'ok': False}, status=400)

    is_trusted = bool(payload.get('is_trusted', False))
    if not is_trusted:
        return JsonResponse({'ok': False})

    session_key = request.session.session_key
    if not session_key:
        request.session.save()
        session_key = request.session.session_key or ''

    def _clean(value, max_len):
        if value is None:
            return ''
        value = str(value).strip()
        if len(value) > max_len:
            return value[:max_len]
        return value

    try:
        UserClickEvent.objects.create(
            user=request.user,
            path=_clean(payload.get('path'), 255),
            page_title=_clean(payload.get('page_title'), 255),
            element_tag=_clean(payload.get('element_tag'), 40),
            element_id=_clean(payload.get('element_id'), 120),
            element_class=_clean(payload.get('element_class'), 255),
            element_text=_clean(payload.get('element_text'), 255),
            is_trusted=is_trusted,
            session_key=_clean(session_key, 120),
            client_x=payload.get('x'),
            client_y=payload.get('y'),
        )
    except Exception:
        return JsonResponse({'ok': False}, status=500)

    return JsonResponse({'ok': True})

from .models import DailyEmailReportSchedule, ReportSchedule, SystemReport, SystemReportRequest, UserClickEvent
from .reporting import create_system_report
from .email_reports import send_daily_operations_report


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_requester_type(user):
    if not user:
        return 'system'
    if user.is_superuser or user.is_staff:
        return 'admin'
    return 'student'


def _build_report_diff(current_summary, previous_summary):
    if not current_summary or not previous_summary:
        return {}

    def _get(path, default=0):
        node = current_summary
        for key in path:
            node = node.get(key, {})
        return node or default

    def _get_prev(path, default=0):
        node = previous_summary
        for key in path:
            node = node.get(key, {})
        return node or default

    def _to_decimal(value):
        if value in (None, ""):
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value).replace(",", "").strip())
        except Exception:
            return Decimal("0")

    fields = {
        "users_total": ("counts", "users_total"),
        "students_total": ("counts", "students_total"),
        "courses_total": ("counts", "courses_total"),
        "transactions_count": ("transactions", "count"),
        "debit_total": ("transactions", "debit_total"),
        "credit_total": ("transactions", "credit_total"),
        "attendance_students": ("attendance", "students_records"),
        "attendance_teachers": ("attendance", "teachers_records"),
    }
    diff = {}
    for key, path in fields.items():
        current_value = _to_decimal(_get(path, 0))
        previous_value = _to_decimal(_get_prev(path, 0))
        delta = current_value - previous_value
        direction = "neutral"
        if delta > 0:
            direction = "up"
        elif delta < 0:
            direction = "down"
        delta_pct = None
        if previous_value != 0:
            try:
                delta_pct = (delta / previous_value) * Decimal("100")
            except Exception:
                delta_pct = None
        diff[key] = {
            "current": current_value,
            "previous": previous_value,
            "delta": delta,
            "delta_pct": delta_pct,
            "direction": direction,
        }
    return diff


def _normalize_report_number(value):
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "").strip())
    except Exception:
        return Decimal("0")


def _build_quick_courses_summary(summary):
    details = (summary or {}).get("details", {})
    quick_courses = details.get("quick_courses") or []
    totals = {
        "course_count": Decimal(len(quick_courses)),
        "enrollments_total": Decimal("0"),
        "receipts_total": Decimal("0"),
        "remaining_total": Decimal("0"),
        "balance_total": Decimal("0"),
    }
    for course in quick_courses:
        totals["enrollments_total"] += _normalize_report_number(course.get("enrollments_count"))
        totals["receipts_total"] += _normalize_report_number(course.get("receipts_amount"))
        totals["remaining_total"] += _normalize_report_number(course.get("remaining_amount"))
        totals["balance_total"] += _normalize_report_number(course.get("account_balance"))
    return totals


def _build_quick_courses_comparison(current_totals, previous_totals):
    if not current_totals or not previous_totals:
        return None

    def make_item(label, key, improve_when):
        current_value = current_totals.get(key, Decimal("0"))
        previous_value = previous_totals.get(key, Decimal("0"))
        delta = current_value - previous_value
        if delta > 0:
            trend = "زيادة"
        elif delta < 0:
            trend = "نقصان"
        else:
            trend = "ثبات"

        if improve_when == "up":
            improved = delta > 0
        elif improve_when == "down":
            improved = delta < 0
        else:
            improved = None

        return {
            "label": label,
            "current": current_value,
            "previous": previous_value,
            "delta": delta,
            "trend": trend,
            "improved": improved,
        }

    items = [
        make_item("إجمالي الدورات", "course_count", None),
        make_item("إجمالي الطلاب", "enrollments_total", "up"),
        make_item("إجمالي الإيرادات", "receipts_total", "up"),
        make_item("إجمالي المتبقي", "remaining_total", "down"),
        make_item("إجمالي الرصيد", "balance_total", None),
    ]

    improvement_count = sum(1 for item in items if item["improved"] is True)
    decline_count = sum(1 for item in items if item["improved"] is False)

    return {
        "items": items,
        "improvement_count": improvement_count,
        "decline_count": decline_count,
        "total_tracked": improvement_count + decline_count,
    }


def _build_courses_summary(summary):
    details = (summary or {}).get("details", {})
    courses = details.get("courses") or []
    totals = {
        "course_count": Decimal(len(courses)),
        "enrollments_total": Decimal("0"),
        "receipts_total": Decimal("0"),
        "remaining_total": Decimal("0"),
        "balance_total": Decimal("0"),
    }
    for course in courses:
        totals["enrollments_total"] += _normalize_report_number(course.get("enrollments_count"))
        totals["receipts_total"] += _normalize_report_number(course.get("receipts_amount"))
        totals["remaining_total"] += _normalize_report_number(course.get("remaining_amount"))
        totals["balance_total"] += _normalize_report_number(course.get("account_balance"))
    return totals


def _build_discounts_totals(summary):
    details = (summary or {}).get("details", {})
    discounts = details.get("discounts_summary") or {}
    total_count = (
        _normalize_report_number(discounts.get("student_receipts_count"))
        + _normalize_report_number(discounts.get("quick_receipts_count"))
        + _normalize_report_number(discounts.get("enrollments_count"))
        + _normalize_report_number(discounts.get("quick_enrollments_count"))
    )
    total_percent_count = (
        _normalize_report_number(discounts.get("student_receipts_discount_percent_count"))
        + _normalize_report_number(discounts.get("quick_receipts_discount_percent_count"))
        + _normalize_report_number(discounts.get("enrollments_discount_percent_count"))
        + _normalize_report_number(discounts.get("quick_enrollments_discount_percent_count"))
    )
    total_amount = (
        _normalize_report_number(discounts.get("student_receipts_discount_amount"))
        + _normalize_report_number(discounts.get("quick_receipts_discount_amount"))
        + _normalize_report_number(discounts.get("enrollments_discount_amount"))
        + _normalize_report_number(discounts.get("quick_enrollments_discount_amount"))
    )
    return {
        "total_count": total_count,
        "total_percent_count": total_percent_count,
        "total_amount": total_amount,
    }


def _build_accounts_totals(summary):
    details = (summary or {}).get("details", {})
    balances = details.get("account_balances") or []
    total_balance = Decimal("0")
    for row in balances:
        total_balance += _normalize_report_number(row.get("balance"))
    return {
        "accounts_count": Decimal(len(balances)),
        "total_balance": total_balance,
    }


def _build_expenses_totals(summary):
    details = (summary or {}).get("details", {})
    expense_summary = details.get("expenses_summary") or {}
    return {
        "total_count": _normalize_report_number(expense_summary.get("total_count")),
        "total_amount": _normalize_report_number(expense_summary.get("total_amount")),
    }


def _build_addresses_totals(summary):
    details = (summary or {}).get("details", {})
    addresses = details.get("top_addresses") or []
    total_students = Decimal("0")
    for row in addresses:
        total_students += _normalize_report_number(row.get("count"))
    return {
        "addresses_count": Decimal(len(addresses)),
        "students_total": total_students,
    }


def _build_users_totals(summary):
    details = (summary or {}).get("details", {})
    users = details.get("users") or []
    total_active_hours = Decimal("0")
    total_logins = Decimal("0")
    total_clicks = Decimal("0")
    for user in users:
        total_active_hours += _normalize_report_number(user.get("active_hours"))
        total_logins += _normalize_report_number(user.get("logins"))
        total_clicks += _normalize_report_number(user.get("clicks_count"))
    return {
        "active_hours_total": total_active_hours,
        "logins_total": total_logins,
        "clicks_total": total_clicks,
    }


def _build_section_comparisons(current_summary, previous_summary):
    if not current_summary or not previous_summary:
        return []

    def make_item(label, current_value, previous_value, improve_when=None):
        current_value = _normalize_report_number(current_value)
        previous_value = _normalize_report_number(previous_value)
        delta = current_value - previous_value
        if delta > 0:
            trend = "زيادة"
        elif delta < 0:
            trend = "نقصان"
        else:
            trend = "ثبات"

        if improve_when == "up":
            improved = delta > 0
        elif improve_when == "down":
            improved = delta < 0
        else:
            improved = None

        return {
            "label": label,
            "current": current_value,
            "previous": previous_value,
            "delta": delta,
            "trend": trend,
            "improved": improved,
        }

    def make_section(title, items):
        improvement_count = sum(1 for item in items if item["improved"] is True)
        decline_count = sum(1 for item in items if item["improved"] is False)
        return {
            "title": title,
            "items": items,
            "improvement_count": improvement_count,
            "decline_count": decline_count,
            "total_tracked": improvement_count + decline_count,
        }

    current_counts = (current_summary or {}).get("counts", {})
    previous_counts = (previous_summary or {}).get("counts", {})
    current_transactions = (current_summary or {}).get("transactions", {})
    previous_transactions = (previous_summary or {}).get("transactions", {})
    current_attendance = (current_summary or {}).get("attendance", {})
    previous_attendance = (previous_summary or {}).get("attendance", {})
    current_activity = (current_summary or {}).get("activity", {})
    previous_activity = (previous_summary or {}).get("activity", {})

    current_students = (current_summary or {}).get("details", {}).get("student_comparison", {})
    previous_students = (previous_summary or {}).get("details", {}).get("student_comparison", {})
    current_outstanding = (current_summary or {}).get("details", {}).get("regular_outstanding_totals", {})
    previous_outstanding = (previous_summary or {}).get("details", {}).get("regular_outstanding_totals", {})

    current_courses = _build_courses_summary(current_summary)
    previous_courses = _build_courses_summary(previous_summary)
    current_quick = _build_quick_courses_summary(current_summary)
    previous_quick = _build_quick_courses_summary(previous_summary)
    current_discounts = _build_discounts_totals(current_summary)
    previous_discounts = _build_discounts_totals(previous_summary)
    current_accounts = _build_accounts_totals(current_summary)
    previous_accounts = _build_accounts_totals(previous_summary)
    current_expenses = _build_expenses_totals(current_summary)
    previous_expenses = _build_expenses_totals(previous_summary)
    current_addresses = _build_addresses_totals(current_summary)
    previous_addresses = _build_addresses_totals(previous_summary)
    current_users = _build_users_totals(current_summary)
    previous_users = _build_users_totals(previous_summary)

    sections = [
        make_section("نظرة عامة", [
            make_item("إجمالي المستخدمين", current_counts.get("users_total"), previous_counts.get("users_total")),
            make_item("إجمالي الطلاب", current_counts.get("students_total"), previous_counts.get("students_total")),
            make_item("إجمالي الدورات", current_counts.get("courses_total"), previous_counts.get("courses_total")),
            make_item("إجمالي المقبوضات", current_transactions.get("credit_total"), previous_transactions.get("credit_total"), "up"),
            make_item("إجمالي المصروفات", current_transactions.get("debit_total"), previous_transactions.get("debit_total"), "down"),
        ]),
        make_section("ساعات عمل المستخدمين", [
            make_item("إجمالي ساعات العمل", current_users.get("active_hours_total"), previous_users.get("active_hours_total"), "up"),
            make_item("إجمالي تسجيلات الدخول", current_users.get("logins_total"), previous_users.get("logins_total"), "up"),
            make_item("إجمالي النقرات", current_users.get("clicks_total"), previous_users.get("clicks_total"), "up"),
        ]),
        make_section("الطلاب", [
            make_item("الطلاب النظاميون", current_students.get("regular_students_total"), previous_students.get("regular_students_total")),
            make_item("الطلاب السريعون", current_students.get("quick_students_total"), previous_students.get("quick_students_total")),
            make_item("الطلاب الخارجيون", current_students.get("external_total_count"), previous_students.get("external_total_count")),
        ]),
        make_section("الدورات النظامية", [
            make_item("عدد الدورات", current_courses.get("course_count"), previous_courses.get("course_count")),
            make_item("إجمالي الطلاب", current_courses.get("enrollments_total"), previous_courses.get("enrollments_total"), "up"),
            make_item("إجمالي الإيرادات", current_courses.get("receipts_total"), previous_courses.get("receipts_total"), "up"),
            make_item("إجمالي المتبقي", current_courses.get("remaining_total"), previous_courses.get("remaining_total"), "down"),
            make_item("إجمالي الرصيد", current_courses.get("balance_total"), previous_courses.get("balance_total")),
        ]),
        make_section("المتبقي على الطلاب", [
            make_item(
                "المتبقي على الطلاب (نظامي)",
                current_outstanding.get("total_outstanding"),
                previous_outstanding.get("total_outstanding"),
                "down",
            ),
        ]),
        make_section("الدورات السريعة", [
            make_item("عدد الدورات", current_quick.get("course_count"), previous_quick.get("course_count")),
            make_item("إجمالي الطلاب", current_quick.get("enrollments_total"), previous_quick.get("enrollments_total"), "up"),
            make_item("إجمالي الإيرادات", current_quick.get("receipts_total"), previous_quick.get("receipts_total"), "up"),
            make_item("إجمالي المتبقي", current_quick.get("remaining_total"), previous_quick.get("remaining_total"), "down"),
            make_item("إجمالي الرصيد", current_quick.get("balance_total"), previous_quick.get("balance_total")),
        ]),
        make_section("الخصومات", [
            make_item("عدد الخصومات", current_discounts.get("total_count"), previous_discounts.get("total_count")),
            make_item("عدد خصومات النسبة", current_discounts.get("total_percent_count"), previous_discounts.get("total_percent_count")),
            make_item("إجمالي قيمة الخصومات", current_discounts.get("total_amount"), previous_discounts.get("total_amount"), "down"),
        ]),
        make_section("الحسابات والأرصدة", [
            make_item("عدد الحسابات", current_accounts.get("accounts_count"), previous_accounts.get("accounts_count")),
            make_item("إجمالي الرصيد", current_accounts.get("total_balance"), previous_accounts.get("total_balance")),
        ]),
        make_section("المصاريف", [
            make_item("عدد المصروفات", current_expenses.get("total_count"), previous_expenses.get("total_count"), "down"),
            make_item("إجمالي المصروفات", current_expenses.get("total_amount"), previous_expenses.get("total_amount"), "down"),
        ]),
        make_section("العناوين الأكثر تكرارًا", [
            make_item("عدد العناوين", current_addresses.get("addresses_count"), previous_addresses.get("addresses_count")),
            make_item("إجمالي الطلاب ضمن العناوين الأعلى", current_addresses.get("students_total"), previous_addresses.get("students_total")),
        ]),
        make_section("الحضور", [
            make_item("حضور الطلاب", current_attendance.get("students_records"), previous_attendance.get("students_records")),
            make_item("حضور المدرسين", current_attendance.get("teachers_records"), previous_attendance.get("teachers_records")),
        ]),
        make_section("النشاطات", [
            make_item("إجمالي النشاطات", current_activity.get("total"), previous_activity.get("total")),
        ]),
    ]

    return sections


def system_report_dashboard(request):
    schedule = ReportSchedule.get_solo()
    daily_schedule = DailyEmailReportSchedule.get_solo()
    selected_report = None

    if request.method == 'POST':
        action = request.POST.get('action')
        course_id = _parse_int(request.POST.get('course_id'))
        user_id = _parse_int(request.POST.get('user_id'))
        report_scope = request.POST.get('report_scope') or None
        sections = request.POST.getlist('sections') or None

        if action == 'manual':
            start_date = _parse_date(request.POST.get('start_date'))
            end_date = _parse_date(request.POST.get('end_date'))
            today = timezone.localdate()
            if not end_date:
                end_date = today
            if not start_date:
                start_date = end_date - timedelta(days=6)
            if start_date > end_date:
                start_date, end_date = end_date, start_date

            selected_report = create_system_report(
                period_start=start_date,
                period_end=end_date,
                report_type='manual',
                created_by=request.user,
                course_id=course_id,
                user_id=user_id,
                report_scope=report_scope,
                sections=sections,
            )
            SystemReportRequest.objects.create(
                report=selected_report,
                requested_by=request.user,
                requester_type=_resolve_requester_type(request.user),
            )
            messages.success(request, 'تم إنشاء التقرير بنجاح.')
            return redirect(f"{request.path}?report_id={selected_report.pk}")

        if action == 'send_daily_email':
            report_date = _parse_date(request.POST.get('report_date')) or timezone.localdate()
            result = send_daily_operations_report(
                day=report_date,
                requested_by=request.user,
                recipients=daily_schedule.get_recipient_list() or None,
                report_type='manual',
            )
            if result.get('sent'):
                messages.success(request, 'تم إرسال التقرير اليومي بالبريد بنجاح.')
            elif result.get('error'):
                messages.error(request, f"تعذر إرسال التقرير بالبريد: {result['error']}")
            else:
                messages.warning(request, 'لم يتم إرسال التقرير لأنه لا يوجد بريد مستلم مضبوط.')
            return redirect(request.path)

        if action == 'save_daily_email_schedule':
            daily_schedule.is_enabled = bool(request.POST.get('daily_is_enabled'))
            time_raw = request.POST.get('daily_time_of_day')
            if time_raw:
                try:
                    daily_schedule.time_of_day = datetime.strptime(time_raw, '%H:%M').time()
                except ValueError:
                    daily_schedule.time_of_day = time_value(19, 0)
            daily_schedule.recipient_emails = (request.POST.get('recipient_emails') or '').strip()
            daily_schedule.next_run = daily_schedule.compute_next_run()
            daily_schedule.save()
            messages.success(request, 'تم حفظ جدولة البريد اليومي.')
            return redirect(request.path)

        if action == 'schedule':
            schedule.is_enabled = bool(request.POST.get('is_enabled'))
            schedule.weekday = int(request.POST.get('weekday', schedule.weekday))
            time_raw = request.POST.get('time_of_day')
            if time_raw:
                try:
                    schedule.time_of_day = datetime.strptime(time_raw, '%H:%M').time()
                except ValueError:
                    schedule.time_of_day = time_value(9, 0)
            schedule.next_run = schedule.compute_next_run()
            schedule.save()
            messages.success(request, 'تم حفظ إعدادات الجدولة.')
            return redirect(request.path)

        if action == 'run_scheduled':
            today = timezone.localdate()
            selected_report = create_system_report(
                period_start=today - timedelta(days=6),
                period_end=today,
                report_type='scheduled',
                created_by=request.user,
            )
            SystemReportRequest.objects.create(
                report=selected_report,
                requested_by=request.user,
                requester_type=_resolve_requester_type(request.user),
            )
            schedule.last_run = timezone.now()
            schedule.next_run = schedule.compute_next_run()
            schedule.save()
            messages.success(request, 'تم إنشاء التقرير المجدول الآن.')
            return redirect(f"{request.path}?report_id={selected_report.pk}")

    report_id = request.GET.get('report_id')
    if report_id:
        selected_report = SystemReport.objects.filter(pk=report_id).first()
    if not selected_report:
        selected_report = SystemReport.objects.first()

    previous_report = None
    comparison = {}
    quick_courses_comparison = None
    quick_courses_totals = None
    section_comparisons = []
    if selected_report:
        previous_report = SystemReport.objects.filter(
            created_at__lt=selected_report.created_at
        ).order_by('-created_at').first()
        if previous_report:
            comparison = _build_report_diff(selected_report.summary or {}, previous_report.summary or {})
        current_quick_totals = _build_quick_courses_summary(selected_report.summary or {})
        quick_courses_totals = current_quick_totals
        previous_quick_totals = (
            _build_quick_courses_summary(previous_report.summary or {})
            if previous_report
            else None
        )
        quick_courses_comparison = _build_quick_courses_comparison(
            current_quick_totals, previous_quick_totals
        )
        if previous_report:
            section_comparisons = _build_section_comparisons(
                selected_report.summary or {},
                previous_report.summary or {}
            )

    recent_reports = SystemReport.objects.all()[:15]
    weekdays = [
        (0, 'الاثنين'),
        (1, 'الثلاثاء'),
        (2, 'الأربعاء'),
        (3, 'الخميس'),
        (4, 'الجمعة'),
        (5, 'السبت'),
        (6, 'الأحد'),
    ]

    return render(request, 'pages/system_report.html', {
        'schedule': schedule,
        'daily_schedule': daily_schedule,
        'selected_report': selected_report,
        'previous_report': previous_report,
        'comparison': comparison,
        'quick_courses_comparison': quick_courses_comparison,
        'quick_courses_totals': quick_courses_totals,
        'section_comparisons': section_comparisons,
        'recent_reports': recent_reports,
        'weekdays': weekdays,
        'courses': Course.objects.all().order_by('name'),
        'users': User.objects.all().order_by('username'),
    })



def system_report_print(request, report_id):
    report = SystemReport.objects.filter(pk=report_id).first()
    if not report:
        report = SystemReport.objects.first()
    previous_report = None
    quick_courses_comparison = None
    quick_courses_totals = None
    section_comparisons = []
    if report:
        previous_report = SystemReport.objects.filter(
            created_at__lt=report.created_at
        ).order_by('-created_at').first()
        current_quick_totals = _build_quick_courses_summary(report.summary or {})
        quick_courses_totals = current_quick_totals
        previous_quick_totals = (
            _build_quick_courses_summary(previous_report.summary or {})
            if previous_report
            else None
        )
        quick_courses_comparison = _build_quick_courses_comparison(
            current_quick_totals, previous_quick_totals
        )
        if previous_report:
            section_comparisons = _build_section_comparisons(
                report.summary or {},
                previous_report.summary or {}
            )
    return render(request, 'pages/system_report_print.html', {
        'report': report,
        'previous_report': previous_report,
        'quick_courses_comparison': quick_courses_comparison,
        'quick_courses_totals': quick_courses_totals,
        'section_comparisons': section_comparisons,
    })
