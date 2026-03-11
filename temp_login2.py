import requests
url = "https://alyaman.pythonanywhere.com/api/auth/student-login/"
data = {"student_name":"أسامة شرشار","password":"0998275919"}
res = requests.post(url, json=data, timeout=30)
print(res.status_code)
print(res.text)
res.raise_for_status()
token = res.json().get("token")
print("token", token)
profile_res = requests.get("https://alyaman.pythonanywhere.com/api/student/profile/full/", params={"token": token}, timeout=30)
print("profile", profile_res.status_code)
print(profile_res.text)

