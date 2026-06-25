import os
from PIL import Image

# Directory containing screenshots
brain_dir = r"C:\Users\THAAER\AppData\Local\Temp" if not os.path.exists("C:\\Users\\THAAER\\.gemini\\antigravity-ide\\brain\\3e35de3c-48b5-4014-9016-29bda27c79db") else "C:\\Users\\THAAER\\.gemini\\antigravity-ide\\brain\\3e35de3c-48b5-4014-9016-29bda27c79db"
artifacts_dir = r"C:\Users\THAAER\.gemini\antigravity-ide\brain\3e35de3c-48b5-4014-9016-29bda27c79db"

def inspect_image(name, filename):
    filepath = os.path.join(brain_dir, filename)
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
    
    img = Image.open(filepath)
    width, height = img.size
    print(f"Image {name}: {width}x{height}")
    
    # Save a cropped version to the artifacts directory to inspect
    # Let's save a smaller preview
    preview = img.resize((width // 2, height // 2))
    preview_path = os.path.join(artifacts_dir, f"preview_{name}.png")
    preview.save(preview_path)
    print(f"Saved preview to: {preview_path}")

# List files in brain directory containing report
files = [f for f in os.listdir(brain_dir) if f.startswith("report_") or f.startswith("page") or f.startswith("cover") or f.startswith("initial") or f.startswith("full")]
print("Available screenshots:", files)

# Inspect some key screenshots
inspect_image("initial", "initial_view_1782356767510.png")
inspect_image("page2", "page2_view_1782356803001.png")
inspect_image("page3", "page3_view_1782356825602.png")
inspect_image("full", "full_report_layout_1782356897047.png")
