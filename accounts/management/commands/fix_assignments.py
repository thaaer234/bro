from django.core.management.base import BaseCommand
from employ.models import Teacher
from accounts.models import CostCenter, CourseTeacherAssignment, Course

class Command(BaseCommand):
    help = 'إصلاح وتعيين جميع المدرسين لمراكز التكلفة'
    
    def handle(self, *args, **options):
        self.stdout.write("🚀 بدء الإصلاح الشامل...")
        
        # 1. احذف كل التعيينات القديمة
        deleted_count, _ = CourseTeacherAssignment.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"🗑️ تم حذف {deleted_count} تعيين قديم"))
        
        # 2. احصل على جميع البيانات
        teachers = Teacher.objects.all()
        active_centers = CostCenter.objects.filter(is_active=True)
        
        total_assignments = 0
        total_teachers = teachers.count()
        
        self.stdout.write(f"👨‍🏫 عدد المدرسين: {total_teachers}")
        self.stdout.write(f"🏢 مراكز التكلفة النشطة: {active_centers.count()}")
        
        # 3. ربط كل مدرس بكل الدورات في كل المراكز
        for teacher in teachers:
            teacher_assignments = 0
            
            for cost_center in active_centers:
                for course in cost_center.courses.filter(is_active=True):
                    try:
                        CourseTeacherAssignment.objects.create(
                            teacher=teacher,
                            course=course,
                            start_date='2024-01-01',
                            is_active=True,
                            notes='ربط شامل'
                        )
                        teacher_assignments += 1
                        total_assignments += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"خطأ في تعيين {teacher.full_name}: {e}"))
            
            if teacher_assignments > 0:
                self.stdout.write(self.style.SUCCESS(f"✅ {teacher.full_name} - {teacher_assignments} تعيين"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠️ {teacher.full_name} - 0 تعيين"))
        
        # 4. التحقق النهائي
        final_count = CourseTeacherAssignment.objects.count()
        expected_count = total_teachers * sum(cc.courses.filter(is_active=True).count() for cc in active_centers)
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("🎉 تم الانتهاء من الإصلاح!"))
        self.stdout.write(f"📊 الإحصائيات النهائية:")
        self.stdout.write(f"   👨‍🏫 المدرسين: {total_teachers}")
        self.stdout.write(f"   🔗 التعيينات: {final_count}")
        self.stdout.write(f"   📈 المتوقع: {expected_count}")
        
        if final_count == expected_count:
            self.stdout.write(self.style.SUCCESS("🎊 كل شيء مثالي!"))
        else:
            self.stdout.write(self.style.WARNING("⚠️ هناك مشكلة في بعض التعيينات"))