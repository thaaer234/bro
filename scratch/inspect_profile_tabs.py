def check_tabs():
    with open("templates/students/student_profile.html", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Let's find tab headers or buttons
    import re
    matches = re.findall(r'<a[^>]*class="[^"]*nav-link[^"]*"[^>]*>.*?</a>', content)
    print("Found navigation links/tabs:")
    for m in matches:
        print(m.strip())
        
    # Let's also look for buttons with modals
    btn_matches = re.findall(r'<button[^>]*data-bs-toggle="modal"[^>]*>.*?</button>', content)
    print("\nFound buttons triggering modals:")
    for b in btn_matches[:20]:
        print(b.strip())

if __name__ == "__main__":
    check_tabs()
