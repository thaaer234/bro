import os
import sys

# Add project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
import django
django.setup()

from classroom.models import Classroom, ClassroomSubject

# Mapping old classrooms to new classrooms
mapping = {
    5: 25,   # الشعبة الأولى (علمي) -> الشعبة الاولى (علمي - دورة صيف)
    6: 26,   # الشعبة الثانية (علمي) -> الشعبة الثانية (علمي - دورة صيف)
    7: 27,   # الشعبة الثالثة (علمي) -> الشعبة الثالثة (علمي - دورة صيف)
    8: 28,   # الشعبة الرابعة (علمي) -> الشعبة الرابعة (علمي - دورة صيف)
    9: 29,   # الشعبة الخامسة (علمي) -> الشعبة الخامسة (علمي - دورة صيف)
    15: 30,  # الشعبة الأولى تاسع (تاسع) -> الشعبة الأولى (تاسع - دورة صيف)
}

print("=== DRY RUN: COPYING SUBJECTS TO NEW CLASSROOMS ===")
for old_id, new_id in mapping.items():
    try:
        old_classroom = Classroom.objects.get(id=old_id)
        new_classroom = Classroom.objects.get(id=new_id)
        
        old_subjects = ClassroomSubject.objects.filter(classroom=old_classroom).select_related('subject')
        print(f"\nFrom Classroom {old_classroom.name} (ID: {old_id}) to {new_classroom.name} (ID: {new_id}):")
        
        for cs in old_subjects:
            subject = cs.subject
            exists = ClassroomSubject.objects.filter(classroom=new_classroom, subject=subject).exists()
            status = "Already exists" if exists else "Will be added"
            print(f"  - Subject: {subject.name} (ID: {subject.id}) | Status: {status}")
            
    except Exception as e:
        print(f"Error processing mapping {old_id} -> {new_id}: {e}")
