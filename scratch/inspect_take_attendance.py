def inspect_template():
    with open("templates/attendance/take_students_attendance.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"Read {len(content)} characters.")
    
    # Search for subjects_note in the content
    lines = content.splitlines()
    matches = []
    for idx, line in enumerate(lines, 1):
        if "subjects_note" in line or "badge" in line or "student.id" in line:
            matches.append((idx, line))
            
    print(f"Found {len(matches)} matches.")
    for idx, line in matches[:40]:
        print(f"Line {idx}: {line.strip()[:140]}")

if __name__ == "__main__":
    inspect_template()
