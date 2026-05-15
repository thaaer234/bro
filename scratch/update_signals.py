
import os

models_path = r'c:\Users\THAAER\Desktop\project\accounts\models.py'

with open(models_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the Studentenrollment pre_delete signal
old_signal = """@receiver(pre_delete, sender=Studentenrollment)
def delete_student_entry_when_enrollment_deleted(sender, instance, **kwargs):
    if getattr(instance, '_skip_linked_cleanup', False):
        return

    for entry in [instance.enrollment_journal_entry, instance.completion_journal_entry]:
        if not entry:
            continue
        entry._skip_linked_cleanup = True
        entry.delete()"""

new_signal = """@receiver(pre_delete, sender=Studentenrollment)
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

if old_signal in content:
    content = content.replace(old_signal, new_signal)
else:
    # Try with slightly different whitespace if needed, but the previous view showed this exact code
    print("Could not find exact signal string, trying fuzzy match...")
    import re
    content = re.sub(r'@receiver\(pre_delete,\s*sender=Studentenrollment\).*?entry\.delete\(\)', new_signal, content, flags=re.DOTALL)

with open(models_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Enrollment cascade deletion signal updated successfully!")
