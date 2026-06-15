def check_register_course():
    with open("templates/students/register_course.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    import re
    # Find subjects inputs or fields
    lines = content.splitlines()
    found = False
    for idx, line in enumerate(lines, 1):
        if "subjects" in line.lower() or "المواد" in line:
            print(f"Line {idx}: {line.strip()[:150]}")
            found = True
    if not found:
        print("No subject elements found in register_course.html.")

if __name__ == "__main__":
    check_register_course()
