import re
import subprocess
import os

html_path = "templates/students/student_profile.html"
with open(html_path, "r", encoding="utf-8") as f:
    content = f.read()

# Extract script blocks
script_matches = re.findall(r"<script>(.*?)</script>", content, re.DOTALL)
if not script_matches:
    print("No script tags found!")
    exit(1)

for idx, script in enumerate(script_matches):
    print(f"Checking script block {idx+1}...")
    
    # Replace Django tags: {% ... %} and {{ ... }}
    clean_script = re.sub(r"\{%.*?%\}", '"django_tag"', script)
    clean_script = re.sub(r"\{\{.*?\}\}", '"django_var"', clean_script)
    
    # Save to a temporary file
    temp_file = f"scratch/temp_script_{idx}.js"
    with open(temp_file, "w", encoding="utf-8") as tf:
        tf.write(clean_script)
    
    # Run node syntax check: node --check filename
    res = subprocess.run(["node", "--check", temp_file], capture_output=True, text=True)
    if res.returncode == 0:
        print(f"Script block {idx+1} is SYNTAX OK!")
    else:
        print(f"Script block {idx+1} has SYNTAX ERRORS:")
        print(res.stderr)
        
    # Clean up
    if os.path.exists(temp_file):
        os.remove(temp_file)
