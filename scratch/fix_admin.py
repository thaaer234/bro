
import os

admin_path = r'c:\Users\THAAER\Desktop\project\accounts\admin.py'
backup_path = r'c:\Users\THAAER\Desktop\project\bro\accounts\admin.py'

# Read backup
with open(backup_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports
old_imports = """from .models import (
    Account, JournalEntry, Transaction, StudentReceipt, ExpenseEntry,
    Course, Student, Studentenrollment, EmployeeAdvance, CostCenter,
    AccountingPeriod, Budget, StudentAccountLink,
)"""

new_imports = """from .models import (
    Account, JournalEntry, Transaction, StudentReceipt, ExpenseEntry,
    Course, Student, Studentenrollment, EmployeeAdvance, CostCenter,
    AccountingPeriod, Budget, StudentAccountLink, DiscountRule
)"""

content = content.replace(old_imports, new_imports)

# 2. Update StudentReceiptAdmin
old_receipt_admin = """@admin.register(StudentReceipt)
class StudentReceiptAdmin(AcademicYearScopedAdminMixin, ImportExportModelAdmin, admin.ModelAdmin):
    academic_year_foreignkey_scopes = {
        'student_profile': 'academic_year',
        'course': 'academic_year',
        'enrollment': 'academic_year',
        'journal_entry': 'academic_year',
    }
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
    payment_method_badge.short_description = '💳 طريقة الدفع'"""

new_receipt_admin = """@admin.register(StudentReceipt)
class StudentReceiptAdmin(AcademicYearScopedAdminMixin, ImportExportModelAdmin, admin.ModelAdmin):
    academic_year_foreignkey_scopes = {
        'student': 'academic_year',
        'course': 'academic_year',
        'enrollment': 'academic_year',
        'journal_entry': 'academic_year',
    }
    resource_class = StudentReceiptResource
    list_display = [
        'receipt_number', 'date', 'get_display_student', 'get_display_course', 
        'paid_amount_display', 'payment_method_badge', 'created_by'
    ]
    list_filter = [
        'payment_method',
        ('date', DateRangeFilter),
        'academic_year',
    ]
    search_fields = [
        'receipt_number', 'student_name', 'course_name',
        'student__full_name', 'student__phone', 'course__name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 30
    date_hierarchy = 'date'
    
    def get_display_student(self, obj):
        if obj.student:
            return obj.student.full_name
        return obj.student_name
    get_display_student.short_description = 'الطالب / Student'

    def get_display_course(self, obj):
        if obj.course:
            return obj.course.name
        return obj.course_name
    get_display_course.short_description = 'الدورة / Course'

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
            'BANK': 'info',
            'CARD': 'primary',
            'TRANSFER': 'warning',
        }
        color = method_colors.get(obj.payment_method, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_payment_method_display()
        )
    payment_method_badge.short_description = '💳 طريقة الدفع'"""

content = content.replace(old_receipt_admin, new_receipt_admin)

# 3. Add StudentReceiptInline and update StudentenrollmentAdmin
receipt_inline_code = """class StudentReceiptInline(admin.TabularInline):
    model = StudentReceipt
    extra = 0
    fields = ['date', 'receipt_number', 'paid_amount', 'payment_method']
    readonly_fields = ['date', 'receipt_number', 'paid_amount', 'payment_method']
    can_delete = False
    verbose_name = "دفعة مالية"
    verbose_name_plural = "المدفوعات المالية لهذا التسجيل"

"""

old_enrollment_admin = """@admin.register(Studentenrollment)
class StudentenrollmentAdmin(AcademicYearScopedAdminMixin, admin.ModelAdmin):
    academic_year_foreignkey_scopes = {
        'student': 'academic_year',
        'course': 'academic_year',
        'enrollment_journal_entry': 'academic_year',
        'completion_journal_entry': 'academic_year',
    }
    list_display = ['get_student_name', 'get_course_name', 'enrollment_date', 'is_active_badge']
    list_filter = [('enrollment_date', DateRangeFilter)]
    
    def get_search_fields(self, request):
        \"\"\"إرجاع حقول البحث المتاحة فقط\"\"\"
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
        \"\"\"تحسين الاستعلام لتجنب الأخطاء\"\"\"
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
    get_student_name.short_description = 'الطالب'"""

new_enrollment_admin = receipt_inline_code + """@admin.register(Studentenrollment)
class StudentenrollmentAdmin(AcademicYearScopedAdminMixin, admin.ModelAdmin):
    academic_year_foreignkey_scopes = {
        'student': 'academic_year',
        'course': 'academic_year',
        'enrollment_journal_entry': 'academic_year',
        'completion_journal_entry': 'academic_year',
    }
    list_display = [
        'get_student_name', 'get_course_name', 'enrollment_date', 
        'total_price_display', 'discount_display', 'net_price_display', 
        'paid_display', 'balance_display', 'is_active_badge'
    ]
    list_filter = [
        'is_completed',
        ('enrollment_date', DateRangeFilter),
        'academic_year',
        'course',
    ]
    inlines = [StudentReceiptInline]
    
    def get_search_fields(self, request):
        return ['student__full_name', 'student__phone', 'course__name', 'notes']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student', 'course')

    def get_student_name(self, obj):
        if obj.student:
            return obj.student.full_name
        return "—"
    get_student_name.short_description = 'الطالب'

    def get_course_name(self, obj):
        if obj.course:
            return obj.course.name
        return "—"
    get_course_name.short_description = 'الدورة'

    def total_price_display(self, obj):
        return f"{obj.total_amount:,.0f}"
    total_price_display.short_description = 'السعر'

    def discount_display(self, obj):
        if obj.discount_percent > 0:
            return f"{obj.discount_percent}%"
        if obj.discount_amount > 0:
            return f"{obj.discount_amount:,.0f}"
        return "0"
    discount_display.short_description = 'الخصم'

    def net_price_display(self, obj):
        return format_html('<b>{:,.0f}</b>', obj.net_amount)
    net_price_display.short_description = 'الصافي'

    def paid_display(self, obj):
        paid = obj.amount_paid
        return format_html('<span style="color: green;">{:,.0f}</span>', paid)
    paid_display.short_description = 'المدفوع'

    def balance_display(self, obj):
        balance = obj.balance_due
        color = "red" if balance > 0 else "gray"
        return format_html('<span style="color: {}; font-weight: bold;">{:,.0f}</span>', color, balance)
    balance_display.short_description = 'المتبقي'

    def is_active_badge(self, obj):
        if obj.is_completed:
            return format_html('<span class="badge badge-secondary">مكتمل</span>')
        return format_html('<span class="badge badge-success">نشط</span>')
    is_active_badge.short_description = 'الحالة'"""

content = content.replace(old_enrollment_admin, new_enrollment_admin)

# Write back
with open(admin_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fix applied successfully!")
