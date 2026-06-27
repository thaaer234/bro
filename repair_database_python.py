# -*- coding: utf-8 -*-
"""
إصلاح قاعدة البيانات التالفة باستخدام مكتبة sqlite3 المدمجة في بايثون بالكامل
(لا يحتاج إلى تثبيت أداة sqlite3 على النظام)
"""
import os
import sqlite3
import subprocess
import sys
import traceback

def main():
    db_path = "/var/www/bro/db.sqlite3"
    fixed_db_path = "/var/www/bro/db_fixed.sqlite3"
    backup_db_path = "/var/www/bro/db.sqlite3.corrupted"

    print("=" * 60)
    print("🛠️ البدء في إصلاح قاعدة البيانات باستخدام Python SQLite...")
    print("=" * 60)

    if not os.path.exists(db_path):
        print(f"❌ لم يتم العثور على قاعدة البيانات في: {db_path}")
        return

    # 1. إيقاف Gunicorn
    print("⏳ إيقاف خدمة Gunicorn لمنع الكتابة...")
    subprocess.run(["sudo", "systemctl", "stop", "bro-gunicorn"])

    try:
        # 2. إنشاء اتصال بقاعدة البيانات التالفة والجديدة
        print("🔍 جاري قراءة البيانات وإعادة إنشائها...")
        
        # إذا كانت قاعدة البيانات الجديدة مؤقتة موجودة، نحذفها
        if os.path.exists(fixed_db_path):
            os.remove(fixed_db_path)

        src_conn = sqlite3.connect(db_path)
        dst_conn = sqlite3.connect(fixed_db_path)
        
        # تفعيل دعم ترميز UTF-8
        src_conn.text_factory = lambda x: str(x, 'utf-8', 'ignore')
        dst_conn.text_factory = str

        # 3. استخدام iterdump المدمج لاستخراج الهيكل والبيانات
        print("✍️ جاري استخراج البيانات وكتابتها لقاعدة بيانات جديدة...")
        
        cursor_dst = dst_conn.cursor()
        
        # سنقوم بتنفيذ العبارات المستخرجة واحدة تلو الأخرى مع تجاهل الأخطاء البسيطة الناتجة عن التلف
        success_count = 0
        fail_count = 0
        
        # نوقف التحقق من القيود الأجنبية مؤقتاً لتسريع الاسترداد
        cursor_dst.execute("PRAGMA foreign_keys = OFF;")
        
        for sql_statement in src_conn.iterdump():
            try:
                # تجنب كتابة المعاملات يدوياً لأن iterdump يحتوي على COMMIT/BEGIN الخاصة به
                cursor_dst.execute(sql_statement)
                success_count += 1
            except Exception as e:
                # إذا كانت العبارة تالفة، نتجاهلها ونكمل البقية لاستعادة 99% من البيانات
                fail_count += 1
                if fail_count < 10:
                    print(f"⚠️ تجاهل عبارة تالفة: {str(e)}")
                    
        dst_conn.commit()
        
        src_conn.close()
        dst_conn.close()

        print(f"📊 تم استرداد {success_count} عبارة محاسبية بنجاح (تجاهل {fail_count} تالفة).")

        # 4. فحص سلامة قاعدة البيانات الجديدة
        print("🧐 فحص سلامة قاعدة البيانات الجديدة...")
        test_conn = sqlite3.connect(fixed_db_path)
        check_cursor = test_conn.cursor()
        check_cursor.execute("PRAGMA integrity_check;")
        result = check_cursor.fetchone()[0]
        test_conn.close()
        
        print(f"   نتيجة الفحص: {result}")

        if result.lower() == "ok":
            print("✅ تم استرداد وإصلاح قاعدة البيانات بنجاح وقاعدة البيانات الجديدة سليمة 100%!")
            
            # نسخ الاحتياطي والتفعيل
            import time
            current_backup = f"{backup_db_path}_{int(time.time())}"
            os.rename(db_path, current_backup)
            os.rename(fixed_db_path, db_path)
            
            # ضبط الصلاحيات
            subprocess.run(["chmod", "666", db_path])
            
            print(f"💾 تم حفظ النسخة التالفة في: {current_backup}")
            print(f"🚀 تم تفعيل قاعدة البيانات الجديدة المصلحة.")
        else:
            print("❌ قاعدة البيانات الناتجة لا تزال غير سليمة.")
            if os.path.exists(fixed_db_path):
                os.remove(fixed_db_path)

    except Exception as e:
        print("❌ حدث خطأ غير متوقع أثناء الاسترداد:")
        traceback.print_exc()
    finally:
        # 5. تشغيل Gunicorn
        print("🚀 إعادة تشغيل خدمة Gunicorn...")
        subprocess.run(["sudo", "systemctl", "start", "bro-gunicorn"])

    print("=" * 60)
    print("🏁 انتهت العملية.")
    print("=" * 60)

if __name__ == "__main__":
    main()
