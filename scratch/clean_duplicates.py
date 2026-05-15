
import os

admin_path = r'c:\Users\THAAER\Desktop\project\accounts\admin.py'

with open(admin_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_until = None

for i, line in enumerate(lines):
    # Check if we are at the start of the duplicate section
    if "def get_course_name(self, obj):" in line and i > 780:
        # This is likely the start of the old methods that weren't replaced properly
        skip_until = "@admin.register(EmployeeAdvance)"
    
    if skip_until and skip_until in line:
        skip_until = None
    
    if not skip_until:
        new_lines.append(line)

with open(admin_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Duplicates cleaned successfully!")
