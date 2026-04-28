"""
Strip 'services.agribrain.' from all Python imports under services/agribrain/.

This normalizes the codebase so that the archive root is services/agribrain/
and all imports resolve relative to that root (e.g., layer0.perception...,
drone_mission.planner..., ip_camera_runtime...).
"""
import os
import re

ROOT = r"c:\Users\E-C\Desktop\agriwise\services\agribrain"

IMPORT_PATTERNS = [
    # from services.agribrain.X import Y  ->  from X import Y
    (r'from\s+services\.agribrain\.', 'from '),
    # import services.agribrain.X  ->  import X
    (r'import\s+services\.agribrain\.', 'import '),
    # "services.agribrain.X" in strings (e.g., -m module paths)
    (r'"services\.agribrain\.', '"'),
    (r"'services\.agribrain\.", "'"),
]

changed_files = []
total_replacements = 0

for dirpath, dirnames, filenames in os.walk(ROOT):
    # Skip __pycache__, .git, node_modules, etc.
    dirnames[:] = [d for d in dirnames if not d.startswith(('.', '__'))]
    
    for fname in filenames:
        if not fname.endswith('.py'):
            continue
        
        fpath = os.path.join(dirpath, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        
        new_content = content
        file_replacements = 0
        
        for pattern, replacement in IMPORT_PATTERNS:
            new_content, count = re.subn(pattern, replacement, new_content)
            file_replacements += count
        
        if file_replacements > 0:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            rel = os.path.relpath(fpath, ROOT)
            changed_files.append((rel, file_replacements))
            total_replacements += file_replacements

print(f"Total files modified: {len(changed_files)}")
print(f"Total replacements: {total_replacements}")
print()
for rel, count in sorted(changed_files):
    print(f"  {count:3d} replacements in {rel}")
