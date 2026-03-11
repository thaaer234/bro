import requests
url = 'https://alyaman.pythonanywhere.com/api/auth/student-login/'
data = {'student_name':'أسامة شرشار','password':'0998275919'}
res = requests.post(url, json=data, timeout=30)
print('login status', res.status_code)
print(res.text)
res.raise_for_status()
token = res.json().get('token')
print('token', token)
profile = requests.get('https://alyaman.pythonanywhere.com/api/student/profile/full/', params={'token': token}, timeout=30)
print('profile status', profile.status_code)
print(profile.text)

