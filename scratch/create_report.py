import os
import sys
import django

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.contrib.auth.models import User
from technical_services.models import TechnicalReport
from datetime import datetime

# Get or create employee user
user = User.objects.filter(is_staff=True).first()
if not user:
    user = User.objects.first()
if not user:
    user = User.objects.create_user(username='admin_temp', password='temp_password123', is_staff=True)

# Create report
report, created = TechnicalReport.objects.get_or_create(
    report_number='REP-20260624-1',
    defaults={
        'employee': user,
        'job_title': 'محاسب',
        'department': 'المحاسبة',
        'incident_date': datetime.strptime('2026-06-25', '%Y-%m-%d').date(),
        'issue_description': '1- اية الله الحج حذوف حسابا\n2- وداد زيدان ماعم يرضى السسينت يسجلو شتوي\n3- محمد رضوان الحسني ماعم يقرأه بمزيان لمراجعة انو مجاني',
        'issue_impact': 'تأثير المشكلة على سير العمل والتقارير المالية والتحقق من حسابات الطلاب بشكل دقيق.',
        'code_solution': '/* SQL Solution for account retrieval */\nUPDATE students_student SET status = \'active\' WHERE id = 104;\n\n/* JS Registration fix */\nif (selectedYear === 2026) {\n    registerStudent(studentId, \'winter\');\n}',
        'employee_instructions': '1- عند الرغبة بإيقاف حساب طالب يجب استخدام خيار تعطيل الحساب من داخل النظام وعدم حذف السجل نهائياً إلا بعد مراجعة الإدارة التقنية.\n2- في حال تعذر تسجيل أي طالب في فصل دراسي جديد يجب التأكد أولاً من اختيار السنة الدراسية الصحيحة وعدم وجود تسجيل سابق لنفس الطالب ضمن نفس الدورة.\n3- عند وجود طالب معفى مالياً يجب التأكد من تسجيل نسبة الخصم أو الإعفاء بشكل صحيح ضمن بيانات الطالب قبل إجراء المراجعة المالية.\n4- في حال استمرار المشكلة يجب تزويد قسم الدعم التقني باسم الطالب.',
        'recommendations': 'توصيات وملاحظات لتحسين أداء وهيكلية النظام مستقبلاً وتدريب الموظفين على استخدام الخيارات الصحيحة.',
        'is_resolved': True
    }
)

print(f"Report created/found: {report.id}, Number: {report.report_number}")
