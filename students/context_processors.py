import os
import json
from django.conf import settings

CONFIG_FILE = os.path.join(settings.BASE_DIR, 'sidebar_config.json')

DEFAULT_CONFIG = {
    # القوائم الرئيسية للنظام الأول
    'dashboard': True,
    'system_report': True,
    'announcements': True,
    'security': True,
    'technical_services': True,
    'handbook': True,
    'daily_report': True,
    'academic_years': True,
    'students_management': True,
    'hr': True,
    'education': True,
    'subjects': True,
    'passwords': True,
    
    # التهيئة المالية
    'acc_chart_of_accounts': True,
    'acc_periods': True,
    'acc_budgets': True,
    'acc_cost_centers': True,
    
    # العمليات اليومية
    'acc_journal_entries': True,
    'acc_new_journal_entry': True,
    'acc_receipts_expenses': True,
    'acc_advances': True,
    
    # التقارير والتحليل
    'acc_reports_center': True,
    'acc_trial_balance': True,
    'acc_account_statement': True,
    'acc_balance_sheet': True,
    'acc_income_statement': True,
    
    # مستقلة
    'acc_courses': True,
    'acc_outstanding': True,
    
    # النظام السريع للطلاب
    'acc_quick_student_list': True,
    'acc_quick_student_create': True,
    'acc_quick_course_list': True,
    'acc_quick_outstanding': True,
    'acc_quick_late_payments': True,
    'acc_quick_intersections': True,
    'acc_quick_manual_sorting': True
}

def sidebar_settings(request):
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                config.update(saved)
        except Exception:
            pass

    return {
        'sidebar_config': config,
        'is_thaaer': request.user.is_authenticated and (request.user.is_superuser or request.user.username == 'thaaer')
    }
