# test_api_final.py
import requests
import json

def test_all_endpoints():
    base_url = 'http://localhost:8000/api/v1/'
    
    # 1. اختبار الاتصال
    print("1. Testing connection...")
    response = requests.get(base_url + 'test/')
    print(f"   Status: {response.status_code}, Response: {response.json()}")
    
    # 2. اختبار تسجيل الدخول
    print("\n2. Testing student login...")
    login_data = {
        'student_name': 'أسامة شرشار',
        'password': '0998275919'
    }
    response = requests.post(base_url + 'auth/student-login/', json=login_data)
    
    if response.status_code == 200:
        try:
            result = response.json()
            print(f"   Status: {response.status_code}")
            print(f"   Success: {result.get('success')}")
            print(f"   Message: {result.get('message')}")
            
            if result.get('token'):
                token = result['token']
                print(f"   Token: {token[:20]}...")
                
                # 3. اختبار ملف الطالب
                print("\n3. Testing student profile...")
                headers = {'Authorization': f'Bearer {token}'}
                response2 = requests.get(base_url + 'student/profile/', headers=headers)
                print(f"   Status: {response2.status_code}")
                if response2.status_code == 200:
                    print(f"   Profile data keys: {response2.json().keys()}")
        except:
            print(f"   Response text: {response.text[:200]}")
    else:
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
    
    # 4. اختبار تسجيل دخول المدرس
    print("\n4. Testing teacher login...")
    teacher_data = {
        'teacher_name': 'اسم المدرس',
        'password': 'رقم الهاتف'
    }
    response = requests.post(base_url + 'auth/teacher-login/', json=teacher_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        try:
            print(f"   Response: {response.json()}")
        except:
            print(f"   Text: {response.text[:200]}")

if __name__ == '__main__':
    print("=== API Testing ===")
    test_all_endpoints()