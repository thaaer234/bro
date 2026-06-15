import os
import sys
import traceback

# Redirect stdout and stderr to a file immediately
log_file = open("test_results.txt", "w", encoding="utf-8")
sys.stdout = log_file
sys.stderr = log_file

print("Initializing test script...")
log_file.flush()

try:
    import django
    from decimal import Decimal
    
    # Set up Django
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
    django.setup()
    print("Django setup completed successfully.")
    log_file.flush()
    
    from django.test import RequestFactory
    from django.contrib.auth.models import User
    from accounts.models import Course, Studentenrollment
    from students.models import Student
    from classroom.models import Classroom, Classroomenrollment
    from students.views import register_course, update_student_discount
    from attendance.views import get_students
    from django.utils import timezone
    
    print("Imports completed successfully.")
    log_file.flush()
    
    def run_test():
        print("--- Starting End-to-End Flow Test ---")
        log_file.flush()
        
        import random
        rand_suffix = random.randint(1000, 9999)
        
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.create_superuser('admin_test', 'admin@test.com', 'admin_pass')
            print("Created superuser admin_test")
        else:
            print(f"Using superuser: {user.username}")
            
        course = Course.objects.create(
            name=f"Test Course {rand_suffix}",
            price=Decimal('50000.00'),
            is_active=True
        )
        print(f"Created Course: {course.name}")
        
        student = Student.objects.create(
            full_name=f"Test Student {rand_suffix}",
            student_number=f"TS-{rand_suffix}",
            academic_year=course.academic_year,
            gender="M"
        )
        print(f"Created Student: {student.full_name}")
        
        classroom = Classroom.objects.create(
            name=f"Classroom for Course {rand_suffix}",
            course=course
        )
        print(f"Created Classroom: {classroom.name}")
        log_file.flush()

        factory = RequestFactory()
        
        post_data = {
            'course_id': str(course.id),
            'apply_discount': 'true',
            'discount_percent': '10',
            'discount_amount': '5000',
            'discount_reason': 'Test Reason',
            'subjects_choice': 'custom',
            'subjects_custom_text': 'رياضيات، فيزياء'
        }
        
        request = factory.post(f'/students/{student.id}/register-course/', post_data)
        request.user = user
        
        from django.contrib.sessions.middleware import SessionMiddleware
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, '_messages', FallbackStorage(request))
        
        print("Simulating course registration POST...")
        log_file.flush()
        register_course(request, student.id)
        
        enrollment = Studentenrollment.objects.filter(student=student, course=course).first()
        assert enrollment is not None, "Enrollment was not created!"
        print("SUCCESS: Enrollment created successfully!")
        print(f"Enrollment subjects_note: '{enrollment.subjects_note}'")
        assert enrollment.subjects_note == 'رياضيات، فيزياء', f"Expected 'رياضيات، فيزياء', got '{enrollment.subjects_note}'"
        log_file.flush()
        
        update_post_data = {
            'enrollment_id': str(enrollment.id),
            'discount_percent': '15',
            'discount_amount': '7500',
            'discount_reason': 'Updated Test Reason',
            'subjects_note': 'كامل المواد'
        }
        
        request_update = factory.post(f'/students/student/{student.id}/update_discount/', update_post_data)
        request_update.user = user
        
        print("Simulating enrollment update POST...")
        log_file.flush()
        import json
        response_update = update_student_discount(request_update, student.id)
        resp_content = json.loads(response_update.content)
        print("Update response:", resp_content)
        assert resp_content['success'] is True, "Update failed!"
        
        enrollment.refresh_from_db()
        print(f"Updated subjects_note: '{enrollment.subjects_note}'")
        assert enrollment.subjects_note == 'كامل المواد', f"Expected 'كامل المواد', got '{enrollment.subjects_note}'"
        log_file.flush()
        
        Classroomenrollment.objects.create(
            student=student,
            classroom=classroom
        )
        print("Enrolled student in classroom.")
        
        request_api = factory.get(f'/attendance/api/students/?classroom={classroom.id}')
        response_api = get_students(request_api)
        api_data = json.loads(response_api.content)
        print("API Data returned:", api_data)
        
        student_record = None
        for rec in api_data:
            if rec['id'] == student.id:
                student_record = rec
                break
                
        assert student_record is not None, "Student not found in attendance API data!"
        print(f"API student subjects_note: '{student_record['subjects_note']}'")
        assert student_record['subjects_note'] == 'كامل المواد', f"Expected 'كامل المواد', got '{student_record['subjects_note']}'"
        log_file.flush()
        
        update_post_data_2 = {
            'enrollment_id': str(enrollment.id),
            'discount_percent': '15',
            'discount_amount': '7500',
            'discount_reason': 'Updated Test Reason',
            'subjects_note': 'كيمياء، علوم'
        }
        
        request_update_2 = factory.post(f'/students/student/{student.id}/update_discount/', update_post_data_2)
        request_update_2.user = user
        update_student_discount(request_update_2, student.id)
        
        response_api_2 = get_students(request_api)
        api_data_2 = json.loads(response_api_2.content)
        for rec in api_data_2:
            if rec['id'] == student.id:
                student_record = rec
                break
        print(f"API student updated subjects_note: '{student_record['subjects_note']}'")
        assert student_record['subjects_note'] == 'كيمياء، علوم', f"Expected 'كيمياء، علوم', got '{student_record['subjects_note']}'"
        log_file.flush()
        
        enrollment.delete()
        classroom.delete()
        student.delete()
        course.delete()
        print("SUCCESS: Cleaned up test data.")
        print("--- All tests passed successfully! ---")
        log_file.flush()
        
    run_test()
    os._exit(0)
    
except Exception as e:
    traceback.print_exc(file=log_file)
    log_file.flush()
    os._exit(1)
