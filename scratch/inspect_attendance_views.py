def show_get_students():
    with open("attendance/views.py", "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    start_line = -1
    for idx, line in enumerate(lines):
        if "def get_students(" in line:
            start_line = idx
            break
            
    if start_line != -1:
        for idx in range(start_line, start_line + 80):
            if idx < len(lines):
                print(f"Line {idx+1}: {lines[idx]}", end="")
    else:
        print("Not found.")

if __name__ == "__main__":
    show_get_students()
