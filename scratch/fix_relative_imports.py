"""
Convert relative imports to absolute imports in all layer0/ Python files.
"""
import os
import re
from pathlib import Path

ROOT = Path(r"c:\Users\E-C\Desktop\agriwise\services\agribrain")

# Pattern matches: from ...X.Y import Z  or  from ..X import Z
RELATIVE_IMPORT = re.compile(r'^(\s*)from\s+(\.+)(\S*)\s+import\s+(.+)$', re.MULTILINE)

def resolve_relative(file_path: Path, dots: str, module_tail: str) -> str:
    """Resolve a relative import to an absolute import path."""
    levels = len(dots)
    # Start from the file's directory
    current = file_path.parent
    for _ in range(levels - 1):
        current = current.parent
    
    # Build the absolute module path relative to archive root
    rel = current.relative_to(ROOT)
    parts = list(rel.parts)
    if module_tail:
        parts.extend(module_tail.split('.'))
    return '.'.join(parts)

changed = 0
for dirpath, dirnames, filenames in os.walk(ROOT / "layer0"):
    dirnames[:] = [d for d in dirnames if not d.startswith(('.', '__'))]
    for fname in filenames:
        if not fname.endswith('.py'):
            continue
        fpath = Path(dirpath) / fname
        content = fpath.read_text(encoding='utf-8')
        
        def replacer(match):
            indent = match.group(1)
            dots = match.group(2)
            module_tail = match.group(3)
            imports = match.group(4)
            absolute = resolve_relative(fpath, dots, module_tail)
            return f"{indent}from {absolute} import {imports}"
        
        new_content = RELATIVE_IMPORT.sub(replacer, content)
        if new_content != content:
            fpath.write_text(new_content, encoding='utf-8')
            rel = fpath.relative_to(ROOT)
            print(f"  Fixed: {rel}")
            changed += 1

print(f"\nTotal files fixed: {changed}")
