# -*- coding: utf-8 -*-
"""
سكريبت لإصلاح قاعدة البيانات التالفة (Database disk image is malformed)
يقوم باستخدام أمر .recover أو .dump الخاص بـ SQLite لإعادة بناء قاعدة البيانات بشكل نظيف.
"""
import os
import subprocess
import sys

def main():
    db_path = "/var/www/bro/db.sqlite3"
    dump_path = "/var/www/bro/db_dump.sql"
    fixed_db_path = "/var/www/bro/db_fixed.sqlite3"
    backup_db_path = "/var/www/bro/db.sqlite3.corrupted"

    print("=" * 60)
    print("🛠️ البدء في إصلاح قاعدة البيانات التالفة...")
    print("=" * 60)

    if not os.path.exists(db_path):
        print(f"❌ لم يتم العثور على قاعدة البيانات في المسار: {db_path}")
        return

    # 1. إيقاف خدمة Gunicorn مؤقتاً لضمان عدم وجود اتصالات نشطة
    print("⏳ إيقاف خدمة Gunicorn لمنع الكتابة أثناء الإصلاح...")
    subprocess.run(["sudo", "systemctl", "stop", "bro-gunicorn"])

    try:
        # 2. محاولة عمل recover لقاعدة البيانات
        print("🔍 جاري محاولة استرداد البيانات (SQLite Recover)...")
        # سنحاول أولاً استخدام .recover وهو الأمر الأحدث والأفضل للإصلاح
        proc = subprocess.run(
            f'sqlite3 {db_path} ".recover" > {dump_path}',
            shell=True,
            capture_output=True,
            text=True
        )
        
        # إذا لم يدعم النظام .recover، نستخدم .dump كخيار بديل
        if proc.returncode != 0:
            print("⚠️ أمر .recover غير مدعوم أو فشل. جاري المحاولة باستخدام .dump...")
            subprocess.run(
                f'sqlite3 {db_path} ".dump" > {dump_path}',
                shell=True
            )

        print("📋 تم استخراج ملف البيانات بنجاح.")

        # 3. إزالة الملف القديم إذا كان موجوداً
        if os.path.exists(fixed_db_path):
            os.remove(fixed_db_path)

        # 4. بناء قاعدة البيانات الجديدة من ملف dump
        print("🏗️ جاري إنشاء قاعدة البيانات الجديدة وإعادة بناء الفهارس...")
        subprocess.run(
            f'sqlite3 {fixed_db_path} < {dump_path}',
            shell=True
        )

        # 5. التحقق من سلامة قاعدة البيانات الجديدة
        print("🧐 التحقق من سلامة قاعدة البيانات الجديدة...")
        check_proc = subprocess.run(
            f'sqlite3 {fixed_db_path} "PRAGMA integrity_check;"',
            shell=True,
            capture_output=True,
            text=True
        )
        
        result = check_proc.stdout.strip()
        print(f"   نتيجة الفحص: {result}")

        if "ok" in result.lower():
            print("✅ تم الإصلاح بنجاح وقاعدة البيانات الجديدة سليمة 100%!")
            
            # 6. نقل الملفات وتفعيل الجديدة
            if os.path.exists(backup_db_path):
                import time
                backup_db_path = f"{backup_db_path}_{int(time.time())}"
            
            os.rename(db_path, backup_db_path)
            os.rename(fixed_db_path, db_path)
            
            # ضبط الأذونات لتكون تابعة للمستخدم root أو www-data حسب التكوين
            subprocess.run(["chmod", "666", db_path])
            
            print(f"💾 تم نسخ قاعدة البيانات القديمة التالفة إلى: {backup_db_path}")
            print(f"🚀 تم تفعيل قاعدة البيانات الجديدة المصلحة.")
        else:
            print("❌ فشل الإصلاح! قاعدة البيانات الناتجة لا تزال تحتوي على أخطاء.")
            if os.path.exists(fixed_db_path):
                os.remove(fixed_db_path)

    except Exception as e:
        print(f"❌ حدث خطأ غير متوقع أثناء عملية الإصلاح: {str(e)}")
    finally:
        # 7. إعادة تشغيل Gunicorn
        print("🚀 إعادة تشغيل خدمة Gunicorn...")
        subprocess.run(["sudo", "systemctl", "start", "bro-gunicorn"])
        
        # تنظيف ملف الـ dump المؤقت لعدم استهلاك مساحة القرص
        if os.path.exists(dump_path):
            os.remove(dump_path)
            
    print("=" * 60)
    print("🏁 انتهت العملية.")
    print("=" * 60)

if __name__ == "__main__":
    main()
