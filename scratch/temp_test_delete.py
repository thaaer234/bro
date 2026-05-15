import os
import django
import sys
import traceback

# Setup Django
sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import JournalEntry, Account
from django.db import transaction

def test_deletion():
    # Find entries related to "شوقل" or just any entry if none found
    # The user is searching for "شوقل"
    jes = JournalEntry.objects.filter(description__icontains='شوقل') | \
          JournalEntry.objects.filter(reference__icontains='شوقل')
    
    if not jes.exists():
        print("No entries found matching 'شوقل'. Testing with the first available entry.")
        jes = JournalEntry.objects.all()[:1]
    
    if not jes.exists():
        print("No JournalEntries in database.")
        return

    for je in jes:
        print(f"Testing deletion of JournalEntry: {je.reference} (ID: {je.id})")
        try:
            with transaction.atomic():
                # Simulate what happens in Admin
                accounts_to_update = set(t.account for t in je.transactions.all())
                print(f"Accounts to update: {[a.code for a in accounts_to_update]}")
                
                # Delete the entry
                print("Deleting entry...")
                je.delete()
                
                # Update balances
                print("Updating balances...")
                for account in accounts_to_update:
                    print(f"Updating account: {account.code}")
                    account.balance = account.get_net_balance()
                    account.save(update_fields=['balance'])
                
                print("Deletion successful (simulated).")
                # We raise an exception to rollback so we don't actually delete data
                raise Exception("ROLLBACK_SUCCESS")
        except Exception as e:
            if str(e) == "ROLLBACK_SUCCESS":
                print("Rollback performed successfully.")
            else:
                print("ERROR DURING DELETION:")
                traceback.print_exc()

if __name__ == "__main__":
    test_deletion()
