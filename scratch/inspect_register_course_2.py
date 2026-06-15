def show_register_course2():
    with open("students/views.py", "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    start_line = 2100
    for idx in range(start_line, start_line + 100):
        if idx < len(lines):
            print(f"Line {idx+1}: {lines[idx]}", end="")

if __name__ == "__main__":
    show_register_course2()
