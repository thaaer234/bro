import os
import sys
import django

sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from accounts.models import Account

codes = [
    '1251-018',
    '21001-018',
    '21001-020',
    '21001-021',
    '21001-022',
    '21001-023',
    '21001-024',
    '1252-001',
    '1252-002',
    '1252-003',
]

print("--- Inspecting Accounts ---")
for code in codes:
    try:
        acc = Account.objects.get(code=code)
        print(f"Code: {acc.code} | Name: {acc.display_name} | Academic Year: {acc.academic_year} (ID: {acc.academic_year_id}) | Parent: {acc.parent} | is_course: {acc.is_course_account} | is_student: {acc.is_student_account}")
    except Account.DoesNotExist:
        print(f"Code: {code} | DOES NOT EXIST")
