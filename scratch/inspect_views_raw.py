with open("students/views.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
print("Line 1755 (1-based):", repr(lines[1754]))
print("Line 1756 (1-based):", repr(lines[1755]))
