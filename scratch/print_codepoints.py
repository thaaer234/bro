with open("students/views.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
line = lines[1754]
print("Line 1755:", line)
print("Codepoints:", [ord(c) for c in line])
print("Hex codepoints:", [hex(ord(c)) for c in line])
