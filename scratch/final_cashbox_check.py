import os
import sys
import django

# Setup django environment
sys.path.append(r"c:\Users\THAAER\Desktop\project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
os.environ["DISABLE_BIOMETRIC_SCHEDULER"] = "true"
django.setup()

from accounts.models import Account, Transaction
from quick.models import AcademicYear
from django.db.models import Sum


years = list(AcademicYear.objects.all().order_by('id'))

cashboxes = Account.objects.filter(code__startswith='121-0').order_by('code')

for year in years:
    print(f"\n{'='*70}")
    print(f"السنة الدراسية: {year.name} (AY{year.id})")
    print(f"{'='*70}")
    total = 0
    for a in cashboxes:
        d = Transaction.objects.filter(account=a, journal_entry__academic_year_id=year.id, is_debit=True).aggregate(s=Sum('amount'))['s'] or 0
        c = Transaction.objects.filter(account=a, journal_entry__academic_year_id=year.id, is_debit=False).aggregate(s=Sum('amount'))['s'] or 0
        net = d - c
        total += net
        print(f"  {a.code}: debit={d:>15,.0f}  credit={c:>15,.0f}  net={net:>15,.0f}")
    print(f"  {'TOTAL':60} {total:>15,.0f}")

print(f"\n\n{'='*70}")
print("NULL entries remaining:")
null_count = Transaction.objects.filter(journal_entry__academic_year__isnull=True, account__code__startswith='121-').count()
print(f"  Cashbox transactions with NULL AY: {null_count}")
