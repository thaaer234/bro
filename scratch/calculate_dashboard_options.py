import os
import sys
import django

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

from accounts.models import Account
from academic_years.services.session import get_current_academic_year

# Let's mock a request to get the current academic year in active session
# or just query all academic years to see what years exist
from quick.models import AcademicYear
years = AcademicYear.objects.all()
print("Academic Years:")
for y in years:
    print(f"ID: {y.id} | Name: {y.name} | Is Open: {y.is_open_ended}")

cash_accounts = Account.objects.filter(
    code__in=['121', '1115'], is_active=True
)

for y in [None] + list(years):
    print(f"\n--- FOR ACADEMIC YEAR: {y.name if y else 'None (All Years)'} ---")
    
    # 1. Current Dashboard code:
    current_val = sum(acc.get_net_balance(academic_year=y) for acc in cash_accounts)
    print(f"1. Current Dashboard method (get_net_balance): {current_val:,.2f}")
    
    # 2. Get rollup balance (scoped to year):
    rollup_scoped = sum(acc.get_rollup_balance(academic_year=y) for acc in cash_accounts)
    print(f"2. Rollup scoped to year (get_rollup_balance): {rollup_scoped:,.2f}")
    
    # 3. Get rollup balance (all years):
    # Since physical cashboxes span all years, maybe fund_balance should also span all years!
    # Let's calculate rollup using all-years:
    rollup_all = sum(acc.get_rollup_balance(academic_year=None) for acc in cash_accounts)
    print(f"3. Rollup all years (get_rollup_balance(None)): {rollup_all:,.2f}")
