def check_profile_tabs():
    with open("templates/students/student_profile.html", "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    # Search for tabs container
    for idx, line in enumerate(lines, 1):
        if "tab" in line.lower() or "nav" in line.lower() or "data-tab" in line.lower():
            if "class=" in line:
                print(f"Line {idx}: {line.strip()[:150]}")

if __name__ == "__main__":
    check_profile_tabs()
