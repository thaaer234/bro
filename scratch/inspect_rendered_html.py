import urllib.request
import re

url = "http://127.0.0.1:8000/technical-services/1/"
try:
    response = urllib.request.urlopen(url)
    html = response.read().decode('utf-8')
    
    # Let's count specific elements and check their nesting/ordering
    a4_indices = [m.start() for m in re.finditer(r'<div class="a4-container">', html)]
    print(f"Total a4-containers: {len(a4_indices)}")
    
    for i, idx in enumerate(a4_indices):
        end_idx = a4_indices[i+1] if i+1 < len(a4_indices) else len(html)
        chunk = html[idx:end_idx]
        print(f"\nContainer {i+1} (length {len(chunk)}):")
        
        # Find headers
        headers = re.findall(r'<div class="[^"]*header[^"]*">', chunk)
        print(f"  Headers: {headers}")
        
        # Find content containers
        content_containers = re.findall(r'<div class="[^"]*content-page-container[^"]*">', chunk)
        print(f"  Content Containers: {content_containers}")
        
        # Find section cards
        section_cards = re.findall(r'<div class="[^"]*section-card[^"]*">', chunk)
        print(f"  Section Cards found: {len(section_cards)}")
        for card in section_cards:
            print(f"    - {card}")
            
        # Find footer slant
        footer_slant = re.findall(r'<div class="[^"]*page-footer-slant-row[^"]*">', chunk)
        print(f"  Footers found: {len(footer_slant)}")
        
except Exception as e:
    print(f"Error: {e}")
