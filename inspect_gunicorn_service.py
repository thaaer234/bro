# -*- coding: utf-8 -*-
import subprocess
import os

def main():
    print("🔍 فحص إعدادات خدمة Gunicorn والبيئة...")
    
    # 1. Read systemd service file
    service_path = "/etc/systemd/system/bro-gunicorn.service"
    if os.path.exists(service_path):
        print(f"\n📄 محتوى ملف الخدمة ({service_path}):")
        try:
            with open(service_path, 'r', encoding='utf-8') as f:
                print(f.read())
        except Exception as e:
            print(f"❌ فشل قراءة الملف: {e}")
    else:
        print(f"⚠️ لم يتم العثور على ملف الخدمة في {service_path}")
        
    # 2. Check running gunicorn processes and their environment
    print("\n🖥️ العمليات النشطة لـ Gunicorn:")
    try:
        output = subprocess.check_output("ps aux | grep gunicorn", shell=True, text=True)
        print(output)
    except Exception as e:
        print(f"❌ فشل جلب العمليات: {e}")
        
    # 3. Search for db.sqlite3 files globally on the server (outside /var/www too)
    print("\n📂 البحث عن أي ملفات sqlite3 أخرى في النظام:")
    try:
        # Search in /var/www, /home, /opt, /root
        search_dirs = ["/var/www", "/home", "/opt", "/root", "/var/lib"]
        for sdir in search_dirs:
            if os.path.exists(sdir):
                cmd = f"find {sdir} -name 'db.sqlite3' -maxdepth 4 2>/dev/null"
                files = subprocess.check_output(cmd, shell=True, text=True).strip().split('\n')
                for f in files:
                    if f:
                        size_mb = os.path.getsize(f) / (1024 * 1024)
                        print(f" - {f} ({size_mb:.2f} MB)")
    except Exception as e:
        print(f"❌ فشل البحث عن الملفات: {e}")

if __name__ == "__main__":
    main()
