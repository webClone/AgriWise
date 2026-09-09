"""Deep check: dependency hygiene — actual third-party imports vs declared requirements."""
import ast
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "services" / "agribrain"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(TARGET))
STDLIB = set(sys.stdlib_module_names)

# top-level pip name mapping for common cases
ALIAS = {"sklearn": "scikit-learn", "cv2": "opencv-python", "PIL": "pillow",
         "yaml": "pyyaml", "dotenv": "python-dotenv", "dateutil": "python-dateutil"}

def local_top(name: str) -> bool:
    for base in (ROOT, TARGET):
        cand = base / name
        if cand.is_dir() or Path(str(cand) + ".py").exists():
            return True
    return False

used = Counter()
for f in TARGET.rglob("*.py"):
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods = [node.module.split(".")[0]]
        for m in mods:
            if m in STDLIB or local_top(m) or m == "services":
                continue
            used[ALIAS.get(m, m)] += 1

declared = set()
req = TARGET / "requirements.txt"
for line in req.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    name = re.split(r"[<>=!\[]", line)[0].strip().lower()
    declared.add(name)

undeclared = {m: c for m, c in used.items() if m.lower() not in declared}
unused = sorted(d for d in declared if d not in {m.lower() for m in used})

print("Third-party imports actually used (top 30):")
for m, c in used.most_common(30):
    mark = "" if m.lower() in declared else "  <-- NOT IN requirements.txt"
    print(f"  {c:4d}  {m}{mark}")

print()
print("Declared but never imported directly:", unused)
