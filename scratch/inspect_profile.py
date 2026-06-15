import re

def search_profile():
    with open("templates/students/student_profile.html", "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    print(f"Read {len(content)} characters from student_profile.html")
    
    # Search for updateDiscountModal or update_student_discount or discount
    matches = []
    for i, line in enumerate(content.splitlines(), 1):
        if "discount" in line.lower() or "subjects" in line.lower() or "update_student" in line.lower():
            matches.append((i, line))
            
    print(f"Found {len(matches)} matching lines.")
    for i, line in matches[:50]:
        print(f"Line {i}: {line.strip()[:150]}")

if __name__ == "__main__":
    search_profile()
