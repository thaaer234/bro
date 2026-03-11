# alyaman/admin_unified.py
"""
ملف Admin موحد لتجنب التضاربات
"""

from django.contrib import admin
from django.apps import apps

# استيراد جميع ModelAdmin من التطبيقات
from accounts.admin import (
    AccountAdmin, JournalEntryAdmin, TransactionAdmin, 
    StudentReceiptAdmin, ExpenseEntryAdmin, CostCenterAdmin
)
from accounts.models import (
    Account, JournalEntry, Transaction, StudentReceipt,
    ExpenseEntry, CostCenter, Student, Course, Studentenrollment,
    EmployeeAdvance, AccountingPeriod, Budget, StudentAccountLink
)

# تسجيل النماذج الرئيسية مرة واحدة فقط
admin.site.register(Account, AccountAdmin)
admin.site.register(JournalEntry, JournalEntryAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(StudentReceipt, StudentReceiptAdmin)
admin.site.register(ExpenseEntry, ExpenseEntryAdmin)
admin.site.register(CostCenter, CostCenterAdmin)

# تسجيل النماذج البسيطة
admin.site.register(Student)
admin.site.register(Course)
admin.site.register(Studentenrollment)
admin.site.register(EmployeeAdvance)
admin.site.register(AccountingPeriod)
admin.site.register(Budget)
admin.site.register(StudentAccountLink)

print("✅ تم تحميل الـ Admin الموحد بنجاح!")