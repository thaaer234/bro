
import os

admin_path = r'c:\Users\THAAER\Desktop\project\accounts\admin.py'

with open(admin_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix net_price_display
content = content.replace(
    "return format_html('<b>{:,.0f}</b>', obj.net_amount)",
    "return format_html('<b>{}</b>', f'{obj.net_amount:,.0f}')"
)

# Fix paid_display
content = content.replace(
    "return format_html('<span style=\"color: green;\">{:,.0f}</span>', paid)",
    "return format_html('<span style=\"color: green;\">{}</span>', f'{paid:,.0f}')"
)

# Fix balance_display
content = content.replace(
    "return format_html('<span style=\"color: {}; font-weight: bold;\">{:,.0f}</span>', color, balance)",
    "return format_html('<span style=\"color: {}; font-weight: bold;\">{}</span>', color, f'{balance:,.0f}')"
)

with open(admin_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Formatting fix applied successfully!")
