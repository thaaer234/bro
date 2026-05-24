import os
import sys
import django

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alyaman.settings")
django.setup()

from accounts.models import Account
from academic_years.services.session import get_current_academic_year

print("--- TESTING BALANCES ---")
academic_year = None # we can also test with the active year if any

accounts_121 = Account.objects.filter(code__startswith='121')
print(f"Found {accounts_121.count()} accounts starting with 121:")
for acc in accounts_121:
    print(f"Code: {acc.code} | Name: {acc.name_ar or acc.name}")
    print(f"  get_net_balance(): {acc.get_net_balance()}")
    print(f"  get_net_balance_all_years(): {acc.get_net_balance_all_years()}")
    print(f"  get_rollup_balance(): {acc.get_rollup_balance()}")
    print(f"  get_rollup_balance(all): {acc.get_rollup_balance(academic_year=None)}")

print("\n--- FUND BALANCE CALCULATION IN DASHBOARD ---")
cash_accounts = Account.objects.filter(
    code__in=['121', '1115'], is_active=True
)
for acc in cash_accounts:
    print(f"Code: {acc.code} | Name: {acc.name_ar or acc.name}")
    print(f"  get_net_balance(ay=None): {acc.get_net_balance(academic_year=None)}")
    print(f"  get_rollup_balance(ay=None): {acc.get_rollup_balance(academic_year=None)}")
