# run_setup.py
import subprocess
import sys
import os

def run_django_command(command):
    """تشغيل أمر Django"""
    try:
        result = subprocess.run(
            [sys.executable, 'manage.py', 'shell', '-c', command],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def main():
    print("🔧 تشغيل سكربت الإعداد التلقائي...")
    
    # 1. تشغيل السكربت الرئيسي
    print("\n📁 تحميل وإعداد السكربت الرئيسي...")
    try:
        from setup_auto_linking import setup_auto_linking_system
        setup_auto_linking_system()
    except Exception as e:
        print(f"❌ خطأ في تشغيل السكربت: {e}")
        return
    
    # 2. تطبيق التعديلات على قاعدة البيانات
    print("\n🗃️ تطبيق التعديلات على قاعدة البيانات...")
    returncode, stdout, stderr = run_django_command("""
from django.core.management import execute_from_command_line
execute_from_command_line(['manage.py', 'migrate'])
    """)
    
    if returncode == 0:
        print("✓ تم تطبيق التعديلات بنجاح")
    else:
        print(f"✗ خطأ في تطبيق التعديلات: {stderr}")
    
    print("\n🎊 اكتمل الإعداد بنجاح! النظام جاهز للعمل التلقائي.")

if __name__ == "__main__":
    main()