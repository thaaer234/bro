import re

def search_views():
    with open("students/views.py", "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    print(f"Read {len(content)} characters from students/views.py")
    
    # Let's find def update_student_discount
    pattern = re.compile(r"def\s+update_student_discount\b")
    match = pattern.search(content)
    if match:
        start_idx = match.start()
        print(f"Found function update_student_discount at index {start_idx}")
        # Print next 1000 characters
        print(content[start_idx:start_idx+2000])
    else:
        print("Function def update_student_discount NOT found.")
        # Let's find any occurrences of update_student_discount
        occurrences = [m.start() for m in re.finditer(r"update_student_discount", content)]
        print(f"Occurrences found at indices: {occurrences}")

if __name__ == "__main__":
    search_views()
