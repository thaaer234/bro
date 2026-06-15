def search_modal_js_css():
    with open("templates/students/student_profile.html", "r", encoding="utf-8") as f:
        content = f.read()
        
    import re
    # Search for modal functions
    modal_funcs = re.findall(r'function\s+\w*modal\w*.*?\n\}', content, re.DOTALL)
    print("Modal functions found:")
    for fn in modal_funcs:
        print(fn)
        
    # Search for modal CSS
    modal_styles = re.findall(r'\.modal\b.*?\}', content, re.DOTALL)
    print("\nModal styles found:")
    for style in modal_styles:
        print(style)

if __name__ == "__main__":
    search_modal_js_css()
