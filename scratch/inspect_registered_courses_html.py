def search_registered_courses():
    with open("templates/students/student_profile.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    import re
    # Find all occurrences of words like "الدورات" or "المسجلة"
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        if "الدورات المسجلة" in line or "البيانات الأكاديمية" in line or "academic" in line.lower() or "tab" in line.lower():
            if any(term in line for term in ["الدورات", "المسجلة", "الأكاديمية"]):
                print(f"Line {idx}: {line.strip()[:150]}")

if __name__ == "__main__":
    search_registered_courses()
