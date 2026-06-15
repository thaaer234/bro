def show_lines():
    with open("students/views.py", "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    start_line = -1
    for idx, line in enumerate(lines):
        if "def update_student_discount" in line:
            start_line = idx
            break
            
    if start_line != -1:
        for idx in range(start_line, start_line + 65):
            if idx < len(lines):
                print(f"Line {idx+1}: {lines[idx]}", end="")
    else:
        print("Not found.")

if __name__ == "__main__":
    show_lines()
