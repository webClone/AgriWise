"""Extreme deep check: production code only (no tests/scratch/scripts/legacy/audit files)."""
import ast
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "services" / "agribrain"
NL = chr(10)

EXCLUDE_DIRS = {"tests", "scratch", "scripts", "legacy", "__pycache__",
                "agriwise_agribrain.egg-info", "artifacts", "data", "datasets"}

def is_production(f):
    parts = set(f.relative_to(TARGET).parts)
    if parts & EXCLUDE_DIRS:
        return False
    name = f.name
    if name.startswith("test_") or name.endswith("_test.py"):
        return False
    if "audit" in name.lower() or "conftest" in name:
        return False
    return True

files = [f for f in sorted(TARGET.rglob("*.py")) if is_production(f)]

mutable_defaults = []
dyn_exec = []
shell_true = []
silent_except = []
asserts = Counter()
blocking_calls = []
unused_imports = Counter()
dup_defs = []
hardcoded_paths = []
globals_used = Counter()
long_files = []
long_funcs = []

BLOCKING = {"time.sleep", "requests.get", "requests.post", "requests.put",
            "requests.delete", "requests.request", "input"}
WIN_PREFIXES = ("C:" + chr(92), "c:" + chr(92))

for f in files:
    rel = str(f.relative_to(ROOT))
    text = f.read_text(encoding="utf-8", errors="replace")
    lines = text.count(NL) + 1
    if lines > 1500:
        long_files.append((lines, rel))
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue

    imported_names = {}
    top_defs = defaultdict(list)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_len = (node.end_lineno or node.lineno) - node.lineno
            if fn_len > 200:
                long_funcs.append((fn_len, "%s:%d %s" % (rel, node.lineno, node.name)))
            for d in node.args.defaults + [d for d in node.args.kw_defaults if d]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)) or (
                        isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                        and d.func.id in ("list", "dict", "set")):
                    mutable_defaults.append((rel, node.lineno, node.name))
            top_defs[node.name].append(node.lineno)
        elif isinstance(node, ast.ClassDef):
            top_defs[node.name].append(node.lineno)

        if isinstance(node, ast.Call):
            fn = node.func
            q = ""
            if isinstance(fn, ast.Attribute):
                base = fn.value.id if isinstance(fn.value, ast.Name) else ""
                q = base + "." + fn.attr if base else fn.attr
            elif isinstance(fn, ast.Name):
                q = fn.id
            if q in ("eval", "exec", "compile"):
                dyn_exec.append((rel, node.lineno, q))
            if q == "pickle.loads":
                dyn_exec.append((rel, node.lineno, "pickle.loads"))
            if q in ("subprocess.run", "subprocess.Popen", "subprocess.call"):
                for kw in node.keywords:
                    if kw.arg == "shell":
                        v = kw.value
                        if isinstance(v, ast.Constant) and v.value is True:
                            shell_true.append((rel, node.lineno))
            if q in BLOCKING:
                blocking_calls.append((rel, node.lineno, q))

        if isinstance(node, ast.ExceptHandler):
            body = node.body
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                silent_except.append((rel, node.lineno))

        if isinstance(node, ast.Assert):
            asserts[rel] += 1

        if isinstance(node, ast.Import):
            for a in node.names:
                imported_names[(a.asname or a.name.split(".")[0])] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    imported_names[(a.asname or a.name)] = node.lineno

        if isinstance(node, ast.Global):
            globals_used[rel] += 1

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if (v.startswith(WIN_PREFIXES) or v.startswith("/home/")
                    or v.startswith("/Users/")) and len(v) > 8:
                hardcoded_paths.append((rel, node.lineno, v[:60]))

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
    for name, lineno in imported_names.items():
        if name not in used and name != "annotations":
            unused_imports["%s:%d -> %s" % (rel, lineno, name)] += 1

    for defname, linenos in top_defs.items():
        if len(linenos) > 1:
            dup_defs.append((rel, defname, linenos))

def report(title, items, limit=25, fmt=None):
    print()
    print("=== %s: %d ===" % (title, len(items)))
    for it in items[:limit]:
        print(" ", fmt(it) if fmt else it)
    if len(items) > limit:
        print("  ... and %d more" % (len(items) - limit))

print("Production files scanned:", len(files))
report("MUTABLE DEFAULT ARGUMENTS (real bug risk)", mutable_defaults,
       fmt=lambda t: "%s:%d in %s()" % t)
report("DYNAMIC CODE EXECUTION (eval/exec/pickle.loads)", dyn_exec,
       fmt=lambda t: "%s:%d %s" % t)
report("subprocess shell=True", shell_true, fmt=lambda t: "%s:%d" % t)
report("SILENT except: pass", silent_except, fmt=lambda t: "%s:%d" % t)
print()
print("=== assert statements in production code: %d in %d files ===" % (sum(asserts.values()), len(asserts)))
for rel, n in asserts.most_common(10):
    print("  %3d  %s" % (n, rel))
report("BLOCKING CALLS (time.sleep/requests/input)", blocking_calls,
       fmt=lambda t: "%s:%d %s" % t)
print()
print("=== UNUSED IMPORTS: %d ===" % len(unused_imports))
for k in list(unused_imports)[:25]:
    print(" ", k)
report("DUPLICATE def/class names in same file", dup_defs,
       fmt=lambda t: "%s: %s at lines %s" % t)
print()
print("=== HARDCODED ABSOLUTE PATHS: %d ===" % len(hardcoded_paths))
for rel, ln, v in hardcoded_paths[:15]:
    print("  %s:%d %s" % (rel, ln, v))
print()
print("=== global statements: %d in %d files ===" % (sum(globals_used.values()), len(globals_used)))
for rel, n in globals_used.most_common(10):
    print("  %3d  %s" % (n, rel))
print()
print("=== FILES > 1500 lines: %d ===" % len(long_files))
for n, rel in sorted(long_files, reverse=True)[:15]:
    print("  %5d  %s" % (n, rel))
print()
print("=== FUNCTIONS > 200 lines: %d ===" % len(long_funcs))
for n, rel in sorted(long_funcs, reverse=True)[:15]:
    print("  %5d  %s" % (n, rel))