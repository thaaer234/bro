# api/tests/test_api.py
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from students.models import Student
from api.models import MobileUser

class APITestCase(TestCase):
    def setUp(self):
        # إنشاء طالب تجريبي
        self.student = Student.objects.create(
            full_name="محمد أحمد",
            phone="0998275919",
            student_number="TEST001",
            is_active=True
        )
        
        # إنشاء مستخدم موبايل
        self.mobile_user = MobileUser.objects.create(
            username="test_parent",
            phone_number="0998275919",
            user_type="parent",
            student=self.student,
            is_active=True
        )
        self.mobile_user.set_password("123456")
        self.mobile_user.save()
        
        self.client = APIClient()
    
    def test_connection(self):
        """اختبار نقطة الاتصال الأساسية"""
        response = self.client.get(reverse('api:api_test'))
        print(f"✅ Status Code: {response.status_code}")
        print(f"✅ Response: {response.json()}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'success')
    
    def test_simple_login(self):
        """اختبار تسجيل الدخول المبسط"""
        response = self.client.post(
            reverse('api:simple_login'),
            format='json'
        )
        
        print(f"✅ Simple Login Status: {response.status_code}")
        print(f"✅ Simple Login Response: {response.json()}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()['success'])
    
    def test_student_list(self):
        """اختبار عرض الطلاب"""
        students = Student.objects.all()
        print(f"\n📊 عدد الطلاب في قاعدة البيانات: {students.count()}")
        
        for s in students:
            print(f"👤 الطالب: {s.id} - {s.full_name} - {s.phone}")