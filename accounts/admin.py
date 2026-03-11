from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
import json
from datetime import datetime, timedelta
import calendar
from django.db.models.functions import TruncMonth, TruncYear
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext_lazy as _

# ==============================
# LIBRARIES & IMPORTS
# ==============================
from rangefilter.filter import DateRangeFilter
from import_export.admin import ImportExportModelAdmin, ExportActionMixin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, DecimalWidget

from .models import (
    Account, JournalEntry, Transaction, StudentReceipt, ExpenseEntry,
    Course, Student, Studentenrollment, EmployeeAdvance, CostCenter,
    AccountingPeriod, Budget, StudentAccountLink,
)

# ==============================
# CUSTOM ADMIN SITE CONFIGURATION
# ==============================
admin.site.site_header = "🏦 نظام المحاسبة - مركز الموهوبين 🎓"
admin.site.site_title = "نظام المحاسبة المتكامل"
admin.site.index_title = "📊 لوحة التحكم الرئيسية"

# ==============================
# IMPORT/EXPORT RESOURCES
# ==============================
class AccountResource(resources.ModelResource):
    class Meta:
        model = Account
        fields = ('code', 'name', 'name_ar', 'account_type', 'balance', 'is_active')
        export_order = fields

class JournalEntryResource(resources.ModelResource):
    class Meta:
        model = JournalEntry
        fields = ('reference', 'date', 'description', 'total_amount', 'is_posted', 'entry_type')
        export_order = fields

class StudentReceiptResource(resources.ModelResource):
    class Meta:
        model = StudentReceipt
        fields = ('receipt_number', 'date', 'student_name', 'course_name', 'paid_amount', 'payment_method')
        export_order = fields

# ==============================
# CUSTOM FILTERS & MIXINS
# ==============================
class DateRangeQuickFilter(admin.SimpleListFilter):
    title = 'الفترة الزمنية'
    parameter_name = 'date_range'
    
    def lookups(self, request, model_admin):
        return (
            ('today', 'اليوم'),
            ('yesterday', 'أمس'),
            ('this_week', 'هذا الأسبوع'),
            ('this_month', 'هذا الشهر'),
            ('this_year', 'هذه السنة'),
            ('last_month', 'الشهر الماضي'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'today':
            return queryset.filter(date=timezone.now().date())
        elif self.value() == 'yesterday':
            return queryset.filter(date=timezone.now().date() - timedelta(days=1))
        elif self.value() == 'this_week':
            start_date = timezone.now().date() - timedelta(days=timezone.now().weekday())
            return queryset.filter(date__gte=start_date)
        elif self.value() == 'this_month':
            return queryset.filter(date__month=timezone.now().month, date__year=timezone.now().year)
        elif self.value() == 'this_year':
            return queryset.filter(date__year=timezone.now().year)
        elif self.value() == 'last_month':
            last_month = timezone.now().month - 1 if timezone.now().month > 1 else 12
            year = timezone.now().year if timezone.now().month > 1 else timezone.now().year - 1
            return queryset.filter(date__month=last_month, date__year=year)
        return queryset

class FinancialMetricsMixin:
    """Mixin لإضافة مقاييس مالية للـ ModelAdmin"""
    
    def get_financial_metrics(self, request):
        """إرجاع مقاييس مالية سريعة"""
        today = timezone.now().date()
        
        # حساب المقاييس
        total_accounts = Account.objects.filter(is_active=True).count()
        total_balance = Account.objects.filter(is_active=True).aggregate(Sum('balance'))['balance__sum'] or 0
        today_receipts = StudentReceipt.objects.filter(date=today).aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
        today_expenses = ExpenseEntry.objects.filter(date=today).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return {
            'total_accounts': total_accounts,
            'total_balance': total_balance,
            'today_receipts': today_receipts,
            'today_expenses': today_expenses,
            'net_today': today_receipts - today_expenses,
        }

# ==============================
# CUSTOM INLINES
# ==============================
class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 1
    classes = ('collapse',)
    fields = ('account', 'amount', 'is_debit', 'cost_center', 'description')
    readonly_fields = ('debit_amount_display', 'credit_amount_display')
    
    def debit_amount_display(self, obj):
        if obj.is_debit:
            amount_str = f"{obj.amount:,.2f}"
            return format_html('<span style="color: green; font-weight: bold;">🔺 {}</span>', amount_str)
        return "—"
    debit_amount_display.short_description = 'مدين'
    
    def credit_amount_display(self, obj):
        if not obj.is_debit:
            amount_str = f"{obj.amount:,.2f}"
            return format_html('<span style="color: red; font-weight: bold;">🔻 {}</span>', amount_str)
        return "—"
    credit_amount_display.short_description = 'دائن'

# ==============================
# MODEL ADMIN CLASSES
# ==============================
@admin.register(Account)
class AccountAdmin(ImportExportModelAdmin, FinancialMetricsMixin, admin.ModelAdmin):
    resource_class = AccountResource
    list_display = [
        'code', 'name_display', 'account_type_badge',
        'balance_display', 'transaction_count', 'is_active_badge', 'created_at'
    ]
    list_filter = [
        'account_type',
        'is_active',
        ('created_at', DateRangeFilter),
    ]
    search_fields = ['code', 'name', 'name_ar', 'description']
    ordering = ['code']
    readonly_fields = ['balance', 'created_at', 'updated_at', 'transaction_count', 'financial_metrics']
    list_per_page = 50
    actions = ['activate_accounts', 'deactivate_accounts']
    
    fieldsets = (
        ('📋 المعلومات الأساسية', {
            'fields': ('code', 'name', 'name_ar', 'account_type', 'parent'),
            'classes': ('collapse', 'wide')
        }),
        ('⚙️ الإعدادات المتقدمة', {
            'fields': ('is_course_account', 'course_name', 'is_student_account', 'student_name'),
            'classes': ('collapse',)
        }),
        ('📝 معلومات إضافية', {
            'fields': ('description', 'is_active')
        }),
        ('💰 المعلومات المالية', {
            'fields': ('balance', 'transaction_count', 'financial_metrics')
        }),
        ('📅 التواريخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def name_display(self, obj):
        return format_html('<strong>{}</strong>', obj.name_ar if obj.name_ar else obj.name)
    name_display.short_description = '👤 اسم الحساب'

    def account_type_badge(self, obj):
        type_colors = {
            'ASSET': 'primary',
            'LIABILITY': 'warning',
            'EQUITY': 'success',
            'REVENUE': 'info',
            'EXPENSE': 'danger'
        }
        color = type_colors.get(obj.account_type, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_account_type_display()
        )
    account_type_badge.short_description = '📊 النوع'

    def balance_display(self, obj):
        balance = obj.balance
        if balance is None:
            balance = 0
        
        if balance > 0:
            amount_str = f"{abs(balance):,.2f}"
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">💰 +{}</span>',
                amount_str
            )
        elif balance < 0:
            amount_str = f"{balance:,.2f}"
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">💸 {}</span>',
                amount_str
            )
        else:
            return format_html('<span style="color: #6c757d;">⚪ 0.00</span>')
    balance_display.short_description = '💳 الرصيد'

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span class="badge badge-success">✅ نشط</span>')
        return format_html('<span class="badge badge-danger">❌ غير نشط</span>')
    is_active_badge.short_description = 'الحالة'

    def opening_balance_display(self, obj):
        start_of_month = timezone.now().date().replace(day=1)
        opening_balance = obj.get_opening_balance(start_of_month)
        amount_str = f"{opening_balance:,.2f}"
        return format_html('<strong>{}</strong>', amount_str)
    opening_balance_display.short_description = 'Opening Balance'

    def opening_balance_display(self, obj):
        start_of_month = timezone.now().date().replace(day=1)
        opening_balance = obj.get_opening_balance(start_of_month)
        amount_str = f"{opening_balance:,.2f}"
        return format_html('<strong>{}</strong>', amount_str)
    opening_balance_display.short_description = 'Opening Balance'

    def opening_balance_display(self, obj):
        start_of_month = timezone.now().date().replace(day=1)
        opening_balance = obj.get_opening_balance(start_of_month)
        amount_str = f"{opening_balance:,.2f}"
        return format_html('<strong>{}</strong>', amount_str)
    opening_balance_display.short_description = 'Opening Balance'

    def transaction_count(self, obj):
        count = obj.transactions.count()
        url = reverse('admin:accounts_transaction_changelist') + f'?account__id__exact={obj.id}'
        return format_html('<a href="{}" class="badge badge-info">🔗 {} معاملة</a>', url, count)
    transaction_count.short_description = '🔄 المعاملات'

    def financial_metrics(self, obj):
        """عرض مقاييس مالية للحساب"""
        debit_total = obj.transactions.filter(is_debit=True).aggregate(Sum('amount'))['amount__sum'] or 0
        credit_total = obj.transactions.filter(is_debit=False).aggregate(Sum('amount'))['amount__sum'] or 0
        net_balance = debit_total - credit_total
        
        debit_str = f"{debit_total:,.2f}"
        credit_str = f"{credit_total:,.2f}"
        net_str = f"{net_balance:,.2f}"
        
        return format_html("""
            <div style="background: #f8f9fa; padding: 10px; border-radius: 5px;">
                <strong>📈 المقاييس المالية:</strong><br>
                • إجمالي المدين: <span style="color: green;">{}</span><br>
                • إجمالي الدائن: <span style="color: red;">{}</span><br>
                • الرصيد الصافي: <span style="color: blue;">{}</span>
            </div>
        """, debit_str, credit_str, net_str)
    financial_metrics.short_description = '📊 المقاييس المالية'

    def activate_accounts(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'✅ تم تفعيل {updated} حساب', messages.SUCCESS)
    activate_accounts.short_description = "تفعيل الحسابات المحددة"

    def deactivate_accounts(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'❌ تم إلغاء تفعيل {updated} حساب', messages.WARNING)
    deactivate_accounts.short_description = "إلغاء تفعيل الحسابات المحددة"

@admin.register(JournalEntry)
class JournalEntryAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = JournalEntryResource
    list_display = [
        'reference', 'date', 'description_short', 'total_amount_display',
        'posting_status', 'entry_type_badge', 'transaction_count', 'created_by', 'created_at'
    ]
    list_filter = [
        'entry_type',
        'is_posted',
        ('date', DateRangeFilter),
        ('created_at', DateRangeFilter),
    ]
    search_fields = ['reference', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at', 'posted_at', 'posted_by', 'balance_status']
    inlines = [TransactionInline]
    list_per_page = 30
    date_hierarchy = 'date'
    actions = ['post_selected_entries', 'export_as_json']
    
    fieldsets = (
        ('📋 المعلومات الأساسية', {
            'fields': ('reference', 'date', 'entry_type', 'description')
        }),
        ('💰 المعلومات المالية', {
            'fields': ('total_amount', 'balance_status', 'is_posted')
        }),
        ('🔄 معلومات الترحيل', {
            'fields': ('posted_at', 'posted_by'),
            'classes': ('collapse',)
        }),
        ('👤 المعلومات الإضافية', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def description_short(self, obj):
        if len(obj.description) > 60:
            return obj.description[:60] + '...'
        return obj.description
    description_short.short_description = '📝 الوصف'

    def total_amount_display(self, obj):
        amount_str = f"{obj.total_amount:,.2f}"
        return format_html(
            '<span style="font-weight: bold; font-size: 1.1em;">💎 {}</span>',
            amount_str
        )
    total_amount_display.short_description = '💰 المبلغ الإجمالي'

    def posting_status(self, obj):
        if obj.is_posted:
            return format_html(
                '<span class="badge badge-success">✅ مرحل</span>'
            )
        else:
            return format_html(
                '<span class="badge badge-warning">⏳ غير مرحل</span>'
            )
    posting_status.short_description = '🔄 حالة الترحيل'

    def entry_type_badge(self, obj):
        type_icons = {
            'MANUAL': '📝',
            'enrollment': '🎓',
            'PAYMENT': '💳',
            'COMPLETION': '✅',
            'EXPENSE': '💸',
            'SALARY': '💰',
            'ADVANCE': '🏦',
            'ADJUSTMENT': '⚙️',
        }
        icon = type_icons.get(obj.entry_type, '📄')
        return format_html('{} {}', icon, obj.get_entry_type_display())
    entry_type_badge.short_description = '📊 نوع القيد'

    def transaction_count(self, obj):
        count = obj.transactions.count()
        return format_html('<span class="badge badge-info">🔢 {} معاملة</span>', count)
    transaction_count.short_description = '🔄 عدد المعاملات'

    def balance_status(self, obj):
        debit_total = obj.transactions.filter(is_debit=True).aggregate(Sum('amount'))['amount__sum'] or 0
        credit_total = obj.transactions.filter(is_debit=False).aggregate(Sum('amount'))['amount__sum'] or 0
        
        if debit_total == credit_total:
            return format_html('<span class="badge badge-success">⚖️ متوازن</span>')
        else:
            return format_html('<span class="badge badge-danger">⚖️ غير متوازن</span>')
    balance_status.short_description = '⚖️ التوازن'

    def post_selected_entries(self, request, queryset):
        success_count = 0
        for entry in queryset:
            if not entry.is_posted:
                try:
                    entry.is_posted = True
                    entry.posted_at = timezone.now()
                    entry.posted_by = request.user
                    entry.save()
                    success_count += 1
                except Exception as e:
                    self.message_user(request, f'❌ خطأ في ترحيل {entry.reference}: {str(e)}', messages.ERROR)
        
        if success_count > 0:
            self.message_user(request, f'✅ تم ترحيل {success_count} قيد بنجاح', messages.SUCCESS)
    post_selected_entries.short_description = "🔄 ترحيل القيود المحددة"

    def export_as_json(self, request, queryset):
        """تصدير البيانات كـ JSON"""
        data = []
        for entry in queryset:
            entry_data = {
                'reference': entry.reference,
                'date': entry.date.isoformat(),
                'description': entry.description,
                'total_amount': str(entry.total_amount),
                'is_posted': entry.is_posted,
                'entry_type': entry.entry_type,
            }
            data.append(entry_data)
        
        response = JsonResponse(data, safe=False, encoder=DjangoJSONEncoder)
        response['Content-Disposition'] = 'attachment; filename="journal_entries.json"'
        return response
    export_as_json.short_description = "📤 تصدير كـ JSON"

@admin.register(Transaction)
class TransactionAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = [
        'id', 'journal_entry_link', 'account_link', 'amount_display', 
        'debit_credit_badge', 'cost_center', 'transaction_date', 'description_short'
    ]
    list_filter = [
        'is_debit',
        'account',
        'cost_center',
        ('journal_entry__date', DateRangeFilter),
    ]
    search_fields = ['description', 'account__name', 'journal_entry__reference']
    readonly_fields = ['created_at']
    list_per_page = 50
    
    def journal_entry_link(self, obj):
        url = reverse('admin:accounts_journalentry_change', args=[obj.journal_entry.id])
        return format_html('<a href="{}">{}</a>', url, obj.journal_entry.reference)
    journal_entry_link.short_description = '📒 القيد'

    def account_link(self, obj):
        url = reverse('admin:accounts_account_change', args=[obj.account.id])
        return format_html('<a href="{}">{}</a>', url, obj.account.name)
    account_link.short_description = '👤 الحساب'

    def amount_display(self, obj):
        amount_str = f"{obj.amount:,.2f}"
        return format_html('<strong>{}</strong>', amount_str)
    amount_display.short_description = '💰 المبلغ'

    def debit_credit_badge(self, obj):
        if obj.is_debit:
            return format_html('<span class="badge badge-success">🔺 مدين</span>')
        else:
            return format_html('<span class="badge badge-danger">🔻 دائن</span>')
    debit_credit_badge.short_description = 'النوع'

    def transaction_date(self, obj):
        return obj.journal_entry.date
    transaction_date.short_description = '📅 التاريخ'

    def description_short(self, obj):
        if obj.description and len(obj.description) > 40:
            return obj.description[:40] + '...'
        return obj.description or "—"
    description_short.short_description = '📝 الوصف'

@admin.register(StudentReceipt)
class StudentReceiptAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_class = StudentReceiptResource
    list_display = [
        'receipt_number', 'date', 'student_name', 'course_name', 
        'paid_amount_display', 'payment_method_badge', 'created_by', 'created_at'
    ]
    list_filter = [
        'payment_method',
        ('date', DateRangeFilter),
        ('created_at', DateRangeFilter),
    ]
    search_fields = ['receipt_number', 'student_name', 'course_name']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 30
    date_hierarchy = 'date'
    
    def paid_amount_display(self, obj):
        amount_str = f"{obj.paid_amount:,.2f}"
        return format_html(
            '<span style="color: #28a745; font-weight: bold;">💰 {}</span>',
            amount_str
        )
    paid_amount_display.short_description = '💵 المبلغ المدفوع'

    def payment_method_badge(self, obj):
        method_colors = {
            'CASH': 'success',
            'BANK_TRANSFER': 'info',
            'CHECK': 'warning',
            'CREDIT_CARD': 'primary',
        }
        color = method_colors.get(obj.payment_method, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_payment_method_display()
        )
    payment_method_badge.short_description = '💳 طريقة الدفع'

@admin.register(ExpenseEntry)
class ExpenseEntryAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ['reference', 'date', 'description', 'amount_display', 'cost_center', 'created_by']
    list_filter = [('date', DateRangeFilter), 'cost_center']
    search_fields = ['reference', 'description']

    def amount_display(self, obj):
        amount_str = f"{obj.amount:,.2f}"
        return format_html('<span style="color: #dc3545; font-weight: bold;">💸 {}</span>', amount_str)
    amount_display.short_description = '💸 المبلغ'

@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'description_short', 'is_active_badge','opening_balance_display']
    list_filter = ['is_active']
    search_fields = ['code', 'name', 'description']

    def description_short(self, obj):
        return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else obj.description
    description_short.short_description = 'الوصف'

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span class="badge badge-success">✅ نشط</span>')
        return format_html('<span class="badge badge-danger">❌ غير نشط</span>')
    is_active_badge.short_description = 'الحالة'

    def opening_balance_display(self, obj):
        start_of_month = timezone.now().date().replace(day=1)
        opening_balance = obj.get_opening_balance(start_of_month)
        amount_str = f"{opening_balance:,.2f}"
        return format_html('<strong>{}</strong>', amount_str)
    opening_balance_display.short_description = 'Opening Balance'

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'is_active_badge', 'created_at']
    search_fields = ['name', 'phone', 'email']
    list_filter = ['is_active']

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span class="badge badge-success">✅ نشط</span>')
        return format_html('<span class="badge badge-danger">❌ غير نشط</span>')
    is_active_badge.short_description = 'الحالة'

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_display', 'course_info', 'is_active_badge']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    
    def price_display(self, obj):
        # التحقق من وجود حقل السعر
        if hasattr(obj, 'price'):
            amount_str = f"{obj.price:,.2f}"
            return format_html('<span style="font-weight: bold;">{} 💵</span>', amount_str)
        elif hasattr(obj, 'cost'):
            amount_str = f"{obj.cost:,.2f}"
            return format_html('<span style="font-weight: bold;">{} 💵</span>', amount_str)
        elif hasattr(obj, 'amount'):
            amount_str = f"{obj.amount:,.2f}"
            return format_html('<span style="font-weight: bold;">{} 💵</span>', amount_str)
        else:
            return "—"
    price_display.short_description = '💰 السعر'

    def course_info(self, obj):
        # عرض معلومات إضافية عن الدورة
        info_parts = []
        
        # التحقق من وجود المدة
        if hasattr(obj, 'duration'):
            info_parts.append(f"{obj.duration} أشهر")
        elif hasattr(obj, 'period'):
            info_parts.append(f"{obj.period} أشهر")
        
        # التحقق من وجود المستوى
        if hasattr(obj, 'level'):
            info_parts.append(f"مستوى {obj.level}")
        
        # التحقق من وجود عدد الساعات
        if hasattr(obj, 'hours'):
            info_parts.append(f"{obj.hours} ساعة")
        
        return " | ".join(info_parts) if info_parts else "—"
    course_info.short_description = '⏳ معلومات الدورة'

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span class="badge badge-success">✅ نشط</span>')
        return format_html('<span class="badge badge-danger">❌ غير نشط</span>')
    is_active_badge.short_description = 'الحالة'

# ==============================
# ADMIN CLASSES للنماذج البسيطة
# ==============================

@admin.register(Studentenrollment)
class StudentenrollmentAdmin(admin.ModelAdmin):
    list_display = ['get_student_name', 'get_course_name', 'enrollment_date', 'is_active_badge']
    list_filter = [('enrollment_date', DateRangeFilter)]
    
    def get_search_fields(self, request):
        """إرجاع حقول البحث المتاحة فقط"""
        # نستخدم حقولاً آمنة فقط
        search_fields = []
        
        # نتحقق من وجود الحقول في النماذج المرتبطة
        try:
            # التحقق من نموذج Student
            student_model = Studentenrollment._meta.get_field('student').related_model
            if hasattr(student_model, 'name'):
                search_fields.append('student__name')
            if hasattr(student_model, 'phone'):
                search_fields.append('student__phone')
            if hasattr(student_model, 'email'):
                search_fields.append('student__email')
        except:
            pass
        
        try:
            # التحقق من نموذج Course
            course_model = Studentenrollment._meta.get_field('course').related_model
            if hasattr(course_model, 'name'):
                search_fields.append('course__name')
        except:
            pass
        
        # إذا لم نجد حقولاً مناسبة، نستخدم حقولاً أساسية فقط
        if not search_fields:
            search_fields = ['id']  # البحث باستخدام الـ ID فقط
        
        return search_fields

    def get_queryset(self, request):
        """تحسين الاستعلام لتجنب الأخطاء"""
        qs = super().get_queryset(request)
        return qs.select_related('student', 'course')

    def get_student_name(self, obj):
        try:
            if hasattr(obj.student, 'name') and obj.student.name:
                return obj.student.name
            else:
                return f"طالب {obj.student.id}"
        except:
            return "—"
    get_student_name.short_description = 'الطالب'

    def get_course_name(self, obj):
        try:
            if hasattr(obj.course, 'name') and obj.course.name:
                return obj.course.name
            else:
                return f"دورة {obj.course.id}"
        except:
            return "—"
    get_course_name.short_description = 'الدورة'

    def is_active_badge(self, obj):
        if hasattr(obj, 'is_active') and obj.is_active:
            return format_html('<span class="badge badge-success">✅ نشط</span>')
        return format_html('<span class="badge badge-danger">❌ غير نشط</span>')
    is_active_badge.short_description = 'الحالة'

@admin.register(EmployeeAdvance)
class EmployeeAdvanceAdmin(admin.ModelAdmin):
    list_display = ['get_employee_name', 'amount_display', 'date', 'settlement_status']
    list_filter = [('date', DateRangeFilter)]
    
    def get_search_fields(self, request):
        """إرجاع حقول البحث الآمنة فقط"""
        search_fields = []
        
        try:
            employee_model = EmployeeAdvance._meta.get_field('employee').related_model
            if hasattr(employee_model, 'name'):
                search_fields.append('employee__name')
            if hasattr(employee_model, 'phone'):
                search_fields.append('employee__phone')
        except:
            pass
        
        if not search_fields:
            search_fields = ['id']
            
        return search_fields

    def get_employee_name(self, obj):
        try:
            if hasattr(obj.employee, 'name') and obj.employee.name:
                return obj.employee.name
            else:
                return f"موظف {obj.employee.id}"
        except:
            return "—"
    get_employee_name.short_description = 'الموظف'

    def amount_display(self, obj):
        if hasattr(obj, 'amount'):
            amount_str = f"{obj.amount:,.2f}"
            return format_html('<strong>{}</strong>', amount_str)
        return "—"
    amount_display.short_description = '💰 المبلغ'

    def settlement_status(self, obj):
        if hasattr(obj, 'is_settled') and obj.is_settled:
            return format_html('<span class="badge badge-success">✅ مسدد</span>')
        return format_html('<span class="badge badge-warning">⏳ غير مسدد</span>')
    settlement_status.short_description = 'حالة التسديد'

@admin.register(AccountingPeriod)
class AccountingPeriodAdmin(admin.ModelAdmin):
    list_display = ['get_name', 'get_start_date', 'get_end_date', 'closed_status']
    search_fields = ['name']
    
    def get_name(self, obj):
        return obj.name if hasattr(obj, 'name') else f"الفترة {obj.id}"
    get_name.short_description = 'الاسم'
    
    def get_start_date(self, obj):
        return obj.start_date if hasattr(obj, 'start_date') else "—"
    get_start_date.short_description = 'تاريخ البداية'
    
    def get_end_date(self, obj):
        return obj.end_date if hasattr(obj, 'end_date') else "—"
    get_end_date.short_description = 'تاريخ النهاية'
    
    def closed_status(self, obj):
        if hasattr(obj, 'is_closed') and obj.is_closed:
            return format_html('<span class="badge badge-secondary">🔒 مغلق</span>')
        return format_html('<span class="badge badge-success">🔓 مفتوح</span>')
    closed_status.short_description = 'الحالة'

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['get_name', 'amount_display', 'get_start_date', 'get_end_date', 'active_status']
    search_fields = ['name']
    
    def get_name(self, obj):
        # التحقق من وجود الحقل name
        if hasattr(obj, 'name'):
            return obj.name
        elif hasattr(obj, 'title'):
            return obj.title
        elif hasattr(obj, 'description'):
            return obj.description[:30] + '...' if len(obj.description) > 30 else obj.description
        else:
            return f"الميزانية {obj.id}"
    get_name.short_description = 'الاسم'
    
    def amount_display(self, obj):
        if hasattr(obj, 'amount'):
            amount_str = f"{obj.amount:,.2f}"
            return format_html('<strong>{}</strong>', amount_str)
        return "—"
    amount_display.short_description = '💰 المبلغ'
    
    def get_start_date(self, obj):
        # التحقق من وجود الحقل start_date
        if hasattr(obj, 'start_date'):
            return obj.start_date
        elif hasattr(obj, 'start_period'):
            return obj.start_period
        elif hasattr(obj, 'period_start'):
            return obj.period_start
        else:
            return "—"
    get_start_date.short_description = 'تاريخ البداية'
    
    def get_end_date(self, obj):
        # التحقق من وجود الحقل end_date
        if hasattr(obj, 'end_date'):
            return obj.end_date
        elif hasattr(obj, 'end_period'):
            return obj.end_period
        elif hasattr(obj, 'period_end'):
            return obj.period_end
        else:
            return "—"
    get_end_date.short_description = 'تاريخ النهاية'
    
    def active_status(self, obj):
        if hasattr(obj, 'is_active') and obj.is_active:
            return format_html('<span class="badge badge-success">✅ نشط</span>')
        return format_html('<span class="badge badge-danger">❌ غير نشط</span>')
    active_status.short_description = 'الحالة'

@admin.register(StudentAccountLink)
class StudentAccountLinkAdmin(admin.ModelAdmin):
    list_display = ['get_student_name', 'get_account_name', 'active_status']
    
    def get_search_fields(self, request):
        """إرجاع حقول البحث الآمنة فقط"""
        search_fields = []
        
        try:
            student_model = StudentAccountLink._meta.get_field('student').related_model
            if hasattr(student_model, 'name'):
                search_fields.append('student__name')
            if hasattr(student_model, 'phone'):
                search_fields.append('student__phone')
        except:
            pass
        
        try:
            account_model = StudentAccountLink._meta.get_field('account').related_model
            if hasattr(account_model, 'name'):
                search_fields.append('account__name')
            if hasattr(account_model, 'code'):
                search_fields.append('account__code')
        except:
            pass
        
        if not search_fields:
            search_fields = ['id']
            
        return search_fields
    
    def get_student_name(self, obj):
        try:
            if hasattr(obj.student, 'name') and obj.student.name:
                return obj.student.name
            else:
                return f"طالب {obj.student.id}"
        except:
            return "—"
    get_student_name.short_description = 'الطالب'
    
    def get_account_name(self, obj):
        try:
            if hasattr(obj.account, 'name') and obj.account.name:
                return obj.account.name
            else:
                return f"حساب {obj.account.code}"
        except:
            return "—"
    get_account_name.short_description = 'الحساب'
    
    def active_status(self, obj):
        if hasattr(obj, 'is_active') and obj.is_active:
            return format_html('<span class="badge badge-success">✅ نشط</span>')
        return format_html('<span class="badge badge-danger">❌ غير نشط</span>')
    active_status.short_description = 'الحالة'

