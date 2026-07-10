# -*- coding: utf-8 -*-
import os

def main():
    log_paths = [
        "/var/www/bro/error.log",
        "/var/www/bro/debug.log",
        "/var/www/bro/gunicorn.log"
    ]
    
    found = False
    for path in log_paths:
        if os.path.exists(path):
            found = True
            print(f"\n📋 نهاية ملف السجل: {path}")
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    last_lines = lines[-50:]
                    for line in last_lines:
                        print(line, end='')
            except Exception as e:
                print(f"❌ فشل قراءة الملف: {e}")
                
    if not found:
        print("❌ لم يتم العثور على أي ملفات سجل أخطاء في المسارات الشائعة.")

if __name__ == "__main__":
    main()
