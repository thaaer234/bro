import os
import sys
import django

sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

sys.stdout.reconfigure(encoding="utf-8")

from accounts.models import Course, Account, Studentenrollment, StudentReceipt, Transaction

ids = [25, 26, 27, 28, 29, 30]
print("--- Inspecting courses 25-30 for data in Year 2 ---")
for cid in ids:
    try:
        c = Course.objects.get(id=cid)
        enrollment_count = Studentenrollment.objects.filter(course=c).count()
        receipt_count = StudentReceipt.objects.filter(enrollment__course=c).count()
        
        # Check transactions for corresponding accounts
        ar_code = f"1251-{c.id:03d}"
        def_code = f"21001-{c.id:03d}"
        ar_acc = Account.objects.filter(code=ar_code).first()
        def_acc = Account.objects.filter(code=def_code).first()
        
        ar_tx_count = 0
        def_tx_count = 0
        if ar_acc:
            ar_tx_count = Transaction.objects.filter(account=ar_acc).count()
        if def_acc:
            def_tx_count = Transaction.objects.filter(account=def_acc).count()
            
        print(f"Course ID: {c.id} | Name: {c.name} | Year ID: {c.academic_year_id} | Enrollments: {enrollment_count} | Receipts: {receipt_count} | AR Tx: {ar_tx_count} | Def Tx: {def_tx_count}")
    except Course.DoesNotExist:
        print(f"Course ID: {cid} | DOES NOT EXIST")
