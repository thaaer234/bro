# -*- coding: utf-8 -*-
import subprocess

def main():
    print("🔍 فحص حالة خدمة Gunicorn وسجلات التشغيل...")
    
    # 1. Check systemctl status
    print("\n📊 حالة الخدمة (systemctl status):")
    try:
        status_out = subprocess.check_output("sudo systemctl status bro-gunicorn", shell=True, text=True)
        print(status_out)
    except Exception as e:
        print(f"❌ فشل جلب حالة الخدمة: {e}")
        
    # 2. Check journalctl logs
    print("\n📋 سجلات تشغيل الخدمة الأخيرة (journalctl):")
    try:
        logs_out = subprocess.check_output("sudo journalctl -u bro-gunicorn -n 50 --no-pager", shell=True, text=True)
        print(logs_out)
    except Exception as e:
        print(f"❌ فشل جلب السجلات: {e}")

if __name__ == "__main__":
    main()
