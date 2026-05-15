
import os

models_path = r'c:\Users\THAAER\Desktop\project\accounts\models.py'

with open(models_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Improved signal with balance updates
improved_signal = """@receiver(pre_delete, sender=Studentenrollment)
def delete_student_entry_when_enrollment_deleted(sender, instance, **kwargs):
    if getattr(instance, '_skip_linked_cleanup', False):
        return

    affected_accounts = set()

    # 1. Collect accounts from enrollment journal entries
    for entry in [instance.enrollment_journal_entry, instance.completion_journal_entry]:
        if entry:
            for t in entry.transactions.all():
                affected_accounts.add(t.account)

    # 2. Delete all linked receipts and collect their accounts
    for receipt in instance.payments.all():
        for entry in receipt.get_linked_journal_entries():
            for t in entry.transactions.all():
                affected_accounts.add(t.account)
        receipt.delete()

    # 3. Delete enrollment journal entries
    for entry in [instance.enrollment_journal_entry, instance.completion_journal_entry]:
        if entry:
            try:
                entry._skip_linked_cleanup = True
                entry.delete()
            except:
                pass
    
    # 4. Surgically update balances for affected accounts
    for account in affected_accounts:
        try:
            account.balance = account.get_net_balance()
            account.save(update_fields=['balance'])
        except:
            pass"""

# Find the old one (which I just wrote)
old_signal_to_replace = """@receiver(pre_delete, sender=Studentenrollment)
def delete_student_entry_when_enrollment_deleted(sender, instance, **kwargs):
    if getattr(instance, '_skip_linked_cleanup', False):
        return

    # 1. Delete all linked receipts (this will trigger their own signals to delete JEs)
    for receipt in instance.payments.all():
        receipt.delete()

    # 2. Delete enrollment journal entries
    for entry in [instance.enrollment_journal_entry, instance.completion_journal_entry]:
        if entry:
            try:
                # Use _skip_linked_cleanup to avoid circular signals
                entry._skip_linked_cleanup = True
                entry.delete()
            except:
                pass"""

if old_signal_to_replace in content:
    content = content.replace(old_signal_to_replace, improved_signal)
else:
    import re
    content = re.sub(r'@receiver\(pre_delete,\s*sender=Studentenrollment\).*?pass', improved_signal, content, flags=re.DOTALL)

with open(models_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Enrollment cascade deletion with balance updates updated successfully!")
