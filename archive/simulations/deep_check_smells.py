"""Deep check: code smells scan for services/agribrain."""
import ast
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "services" / "agribrain"

todo_re = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)
secret_re = re.compile(
    r"(api[_-]?key\s*=\s*['\"][A-Za-z0-9_\-]{16,}|secret\s*=\s*['\"][A-Za-z0-9_\-]{16,}"
    r"|password\s*=\s*['\"][^'\"]{6,}|Bearer\s+[A-Za-z0-9_\-\.]{20,})", re.IGNORECASE)

todos = Counter()
bare_excepts = []
prints = Counter()
secrets = []

files = sorted(TARGET.rglob("*.py"))
for f in files:
    rel = str(f.relative_to(ROOT))
    text = f.read_text(encoding="utf-8", errors="replace")
    for m in todo_re.finditer(text):
        todos[m.group(1).upper()] += 1
    if secret_re.search(text):
        secrets.append(rel)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue
    n_print = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            bare_excepts.append((rel, node.lineno))
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "print":
                n_print += 1
    if n_print:
        prints[rel] = n_print

print(f"Files scanned: {len(files)}")
print(f"\nTODO/FIXME/HACK markers: {sum(todos.values())} total {dict(todos)}")
print(f"\nBare 'except:' clauses: {len(bare_excepts)}")
for rel, ln in bare_excepts[:30]:
    print(f"  {rel}:{ln}")
if len(bare_excepts) > 30:
    print(f"  ... and {len(bare_excepts) - 30} more")
print(f"\nFiles containing potential hardcoded secrets: {len(secrets)}")
for s in secrets[:20]:
    print(f"  {s}")
print(f"\nFiles with print() calls: {len(prints)} ({sum(prints.values())} calls)")
for rel, n in prints.most_common(15):
    print(f"  {n:4d}  {rel}")