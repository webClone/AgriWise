"""Deep check: scan all .py files under services/agribrain for unresolvable imports."""
import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "services" / "agribrain"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TARGET))

STDLIB = set(sys.stdlib_module_names)

def resolves(top: str) -> bool:
    if top in STDLIB:
        return True
    if importlib.util.find_spec(top) is not None:
        return True
    # local package/dir check
    for base in (ROOT, TARGET):
        cand = base / top
        if cand.is_dir() or Path(str(cand) + ".py").exists():
            return True
    return False

issues = []
files = sorted(TARGET.rglob("*.py"))
for f in files:
    rel = f.relative_to(ROOT)
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"), filename=str(f))
    except SyntaxError as e:
        issues.append((rel, f"SYNTAX ERROR: {e}"))
        continue
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods = [node.module.split(".")[0]]
        for m in mods:
            if not resolves(m):
                issues.append((rel, f"unresolved import '{m}' (line {node.lineno})"))

print(f"Scanned {len(files)} files")
if issues:
    print(f"{len(issues)} issue(s):")
    for rel, msg in issues:
        print(f"  {rel}: {msg}")
else:
    print("No unresolved imports found.")