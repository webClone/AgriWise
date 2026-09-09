"""Refined deep check: real shadowing, async-blocking, circular imports."""
import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "services" / "agribrain"
NL = chr(10)

EXCLUDE_DIRS = {"tests", "scratch", "scripts", "legacy", "__pycache__",
                "agriwise_agribrain.egg-info", "artifacts", "data", "datasets"}

def is_production(f):
    parts = set(f.relative_to(TARGET).parts)
    return not (parts & EXCLUDE_DIRS) and not f.name.startswith("test_")

files = [f for f in sorted(TARGET.rglob("*.py")) if is_production(f)]

# 1) Module-level duplicate top-level defs (real shadowing)
print("=== MODULE-LEVEL DUPLICATE DEFS (later shadows earlier) ===")
for f in files:
    rel = str(f.relative_to(ROOT))
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    seen = defaultdict(list)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            seen[node.name].append(node.lineno)
    for name, linenos in seen.items():
        if len(linenos) > 1:
            print("  %s: %s at %s" % (rel, name, linenos))

# 2) Blocking calls INSIDE async def
print()
print("=== BLOCKING CALLS INSIDE async def ===")
found_async_block = False
for f in files:
    rel = str(f.relative_to(ROOT))
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    BLOCKING = {"time.sleep", "requests.get", "requests.post", "requests.put",
                "requests.delete", "requests.request"}
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            q = ""
            if isinstance(fn, ast.Attribute):
                base = fn.value.id if isinstance(fn.value, ast.Name) else ""
                q = base + "." + fn.attr if base else fn.attr
            elif isinstance(fn, ast.Name):
                q = fn.id
            if q in BLOCKING:
                p = parents.get(node)
                while p is not None:
                    if isinstance(p, ast.AsyncFunctionDef):
                        print("  %s:%d %s inside async %s" % (rel, node.lineno, q, p.name))
                        found_async_block = True
                        break
                    p = parents.get(p)
if not found_async_block:
    print("  none found")

# 3) Unused imports excluding __init__.py re-exports
print()
print("=== UNUSED IMPORTS (excluding __init__.py), top files ===")
per_file = defaultdict(int)
for f in files:
    if f.name == "__init__.py":
        continue
    rel = str(f.relative_to(ROOT))
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported[(a.asname or a.name.split(".")[0])] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    imported[(a.asname or a.name)] = node.lineno
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            n = node
            while isinstance(n, ast.Attribute):
                n = n.value
            if isinstance(n, ast.Name):
                used.add(n.id)
    for name in imported:
        if name not in used and name != "annotations":
            per_file[rel] += 1
total = sum(per_file.values())
for rel, n in sorted(per_file.items(), key=lambda kv: -kv[1])[:20]:
    print("  %4d  %s" % (n, rel))
print("  TOTAL:", total)

# 4) Circular imports among local packages (module-level imports only)
print()
print("=== CIRCULAR IMPORT CHECK (module-level local imports) ===")
graph = defaultdict(set)
mod_of = {}
for f in files:
    try:
        mod = str(f.relative_to(TARGET))[:-3].replace(chr(92), ".").replace("/", ".")
    except Exception:
        continue
    if mod.endswith(".__init__"):
        mod = mod[:-9]
    mod_of[f] = mod
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    for node in tree.body:  # module-level only
        targets = []
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("services.agribrain"):
            targets.append(node.module)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("services.agribrain"):
                    targets.append(a.name)
        for t in targets:
            base = t
            while base not in graph and "." in base:
                base = base.rsplit(".", 1)[0]
            graph[mod].add(base)

cycles = []
def dfs(start, current, path, visited):
    for nxt in graph.get(current, ()):
        if nxt == start:
            cycles.append(path + [nxt])
        elif nxt not in visited:
            dfs(start, nxt, path + [nxt], visited | {nxt})

for m in list(graph):
    dfs(m, m, [m], {m})
# dedupe cycles by frozenset
seen = set()
uniq = []
for c in cycles:
    key = frozenset(c)
    if key not in seen:
        seen.add(key)
        uniq.append(c)
if uniq:
    for c in uniq[:15]:
        print("  CYCLE:", " -> ".join(c))
else:
    print("  no module-level import cycles detected")