import os
import sys
import django

sys.path.append(r'c:\Users\THAAER\Desktop\project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from django.contrib.admin.models import LogEntry

print("=== SEARCHING ADMIN LOGS ===")
logs = LogEntry.objects.filter(object_repr__icontains="منجد") | LogEntry.objects.filter(object_repr__icontains="عجاج") | LogEntry.objects.filter(change_message__icontains="منجد") | LogEntry.objects.filter(change_message__icontains="عجاج")

print(f"Found {logs.count()} log entries:")
for log in logs.order_by('-action_time')[:50]:
    print(f"Time: {log.action_time} | User: {log.user} | Model: {log.content_type} | Action: {log.get_action_flag_display()} | Object: {log.object_repr} | Message: {log.change_message}")

print("\n=== SEARCHING ADMIN LOGS FOR 'عبد الكريم' ===")
logs_ak = LogEntry.objects.filter(object_repr__icontains="عبد الكريم") | LogEntry.objects.filter(change_message__icontains="عبد الكريم")
print(f"Found {logs_ak.count()} log entries:")
for log in logs_ak.order_by('-action_time')[:50]:
    print(f"Time: {log.action_time} | User: {log.user} | Model: {log.content_type} | Action: {log.get_action_flag_display()} | Object: {log.object_repr} | Message: {log.change_message}")
