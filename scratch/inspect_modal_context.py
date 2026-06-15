def show_modal_context():
    with open("templates/students/student_profile.html", "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for idx in range(1040, 1185):
        if idx < len(lines):
            print(f"Line {idx+1}: {lines[idx]}", end="")

if __name__ == "__main__":
    show_modal_context()
