from django.core.management.base import BaseCommand
from django.utils import timezone
from students.models import Student
from quick.models import AcademicYear
from django.db.models import Q
from datetime import datetime

class Command(BaseCommand):
    help = 'ربط الطلاب النظاميين تلقائياً بالفصول الدراسية حسب تاريخ التسجيل'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='إعادة ربط جميع الطلاب حتى لو كانوا مرتبطين مسبقاً',
        )
        parser.add_argument(
            '--create-year',
            action='store_true',
            help='إنشاء فصل دراسي تلقائياً إذا لم يوجد',
        )

    def handle(self, *args, **options):
        force = options['force']
        create_year = options['create_year']
        
        # جلب الطلاب
        if force:
            students = Student.objects.all()
        else:
            students = Student.objects.filter(academic_year__isnull=True)
        
        assigned_count = 0
        total_students = students.count()
        
        self.stdout.write(f'جاري معالجة {total_students} طالب...')
        
        # إذا لم توجد فصول دراسية وإنشاء فصل مفعل
        if create_year and not AcademicYear.objects.filter(is_active=True).exists():
            self.create_default_academic_year()
        
        for student in students:
            if student.registration_date:
                # البحث عن الفصل الدراسي الذي ينتمي له الطالب حسب تاريخ التسجيل
                academic_year = self.find_academic_year(student.registration_date)
                
                if academic_year:
                    student.academic_year = academic_year
                    student.save()
                    assigned_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ تم ربط الطالب {student.full_name} بالفصل {academic_year.name}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️  لم يتم العثور على فصل دراسي للطالب {student.full_name} (تاريخ التسجيل: {student.registration_date})'
                        )
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  الطالب {student.full_name} ليس لديه تاريخ تسجيل'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'🎉 تم ربط {assigned_count} طالب تلقائياً بالفصول الدراسية')
        )
        
        # إحصائيات
        if total_students > 0:
            percentage = (assigned_count / total_students) * 100
            self.stdout.write(f'📊 النسبة: {percentage:.1f}% من الطلاب تم ربطهم')

    def find_academic_year(self, registration_date):
        """البحث عن الفصل الدراسي المناسب مع مرونة أكثر"""
        # البحث الدقيق أولاً
        academic_year = AcademicYear.objects.filter(
            start_date__lte=registration_date,
            end_date__gte=registration_date,
            is_active=True
        ).first()
        
        if academic_year:
            return academic_year
        
        # إذا لم يوجد تطابق دقيق، ابحث عن أقرب فصل
        academic_year = AcademicYear.objects.filter(
            start_date__lte=registration_date,
            is_active=True
        ).order_by('-start_date').first()
        
        return academic_year

    def create_default_academic_year(self):
        """إنشاء فصل دراسي افتراضي"""
        from datetime import datetime
        
        # إنشاء فصل دراسي يغطي سنة كاملة
        default_year = AcademicYear.objects.create(
            name="الفصل الافتراضي 2024-2025",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2025, 12, 31),
            is_active=True
        )
        self.stdout.write(
            self.style.SUCCESS(f'✅ تم إنشاء الفصل الدراسي الافتراضي: {default_year.name}')
        )
        return default_year