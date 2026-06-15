with open("students/views.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()

replacement_chars = content.count('\ufffd')
print(f"Number of \\ufffd characters in students/views.py: {replacement_chars}")

# Find context around first 5 occurrences
if replacement_chars > 0:
    print("\nOccurrences details:")
    lines = content.splitlines()
    found = 0
    for idx, line in enumerate(lines, 1):
        if '\ufffd' in line:
            print(f"Line {idx}: {repr(line)}")
            found += 1
            if found >= 15:
                break
