import os
import sys
import django

sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from accounts.models import Course, Account

ids = [18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
print("--- Course Database State ---")
for cid in ids:
    try:
        c = Course.objects.get(id=cid)
        print(f"Course ID: {c.id} | Name: {c.name} | AY: {c.academic_year} (ID: {c.academic_year_id})")
        # Check corresponding accounts
        ar_code = f"1251-{c.id:03d}"
        def_code = f"21001-{c.id:03d}"
        
        ar_acc = Account.objects.filter(code=ar_code).first()
        def_acc = Account.objects.filter(code=def_code).first()
        
        print(f"  AR Account: {ar_code} | AY: {ar_acc.academic_year if ar_acc else 'NONE'} (ID: {ar_acc.academic_year_id if ar_acc else 'NONE'})")
        print(f"  Deferred Account: {def_code} | AY: {def_acc.academic_year if def_acc else 'NONE'} (ID: {def_acc.academic_year_id if def_acc else 'NONE'})")
    except Course.DoesNotExist:
        print(f"Course ID: {cid} | DOES NOT EXIST")
