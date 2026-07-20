import os

file_path = r'c:\Users\DELL\RISE\RISE-Frontend\templates\dashboard.html'
layout_path = r'c:\Users\DELL\RISE\RISE-Frontend\templates\new_layout.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

with open(layout_path, 'r', encoding='utf-8') as f:
    new_layout = f.read()

# Find the start of the block to replace
start_marker = "<!--  STATS ROW -->"
end_marker = "<!-- Announcements Style Overrides -->"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx != -1 and end_idx != -1:
    # We want to replace from the start marker to right before the end marker
    new_content = content[:start_idx] + new_layout + "\n\n" + content[end_idx:]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Replaced successfully!")
else:
    print(f"Start index: {start_idx}, End index: {end_idx}")
