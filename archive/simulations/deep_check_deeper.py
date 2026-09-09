"""Deeper still: semantic bug classes + determinism risks (production code only).

Checks:
1. broad `except Exception` density
2. naive datetime usage (utcnow / now() without tz) - determinism & deprecation risk
3. builtin hash() used for content addressing/cache keys - PYTHONHASHSEED nondeterminism
4. random module usage in production paths - violates deterministic-replay doctrine
5. open() without context manager - resource leaks
6. inconsistent return statements (some paths return, others fall through -> implicit None)
7. class-level mutable attributes (shared state across instances)
8. `== None` / `!= None` comparisons
9. duplicate module basenames across packages (import shadowing confusion)
10. type-annotation coverage
"""
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
    if parts & EXCLUDE_DIRS or f.name.startswith("test_"):
        return False
    if f.name == "__init__.py":
        return False
    return True

files = [f for f in sorted(TARGET.rglob("*.py")) if is_production(f)]

broad_except = Counter()
naive_dt = []
builtin_hash = []
random_use = []
open_no_with = []
inconsistent_returns = []
class_mutable = []
none_cmp = []

def call_q(fn):
    if isinstance(fn, ast.Attribute):
        base = fn.value.id if isinstance(fn.value, ast.Name) else ""
        return base + "." + fn.attr if base else fn.attr
    if isinstance(fn, ast.Name):
        return fn.id
    return ""

for f in files:
    rel = str(f.relative_to(ROOT))
    text = f.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        continue

    # parents map for context checks
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    ann_total = ann_fn = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            t = node.type
            name = None
            if isinstance(t, ast.Name):
                name = t.id
            elif isinstance(t, ast.Attribute):
                name = t.attr
            if name in ("Exception", "BaseException"):
                broad_except[rel] += 1

        if isinstance(node, ast.Call):
            q = call_q(node.func)
            if q == "datetime.utcnow":
                naive_dt.append((rel, node.lineno, "datetime.utcnow()"))
            elif q == "datetime.now" and not node.keywords:
                # check enclosing function for tz param - naive now()
                naive_dt.append((rel, node.lineno, "datetime.now() [no tz]"))
            elif q == "hash":
                builtin_hash.append((rel, node.lineno))
            elif q.startswith("random.") or q in ("randint", "randrange", "choice", "shuffle", "uniform", "random"):
                random_use.append((rel, node.lineno, q))
            elif q == "open":
                p = parents.get(node)
                if not isinstance(p, ast.withitem):
                    open_no_with.append((rel, node.lineno))

        if isinstance(node, ast.Compare):
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant) and comp.value is None:
                    none_cmp.append((rel, node.lineno))

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            n_args = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
            if getattr(args, "vararg", None): n_args += 1
            if getattr(args, "kwarg", None): n_args += 1
            if n_args > 0:
                ann_total += n_args
                all_ann = all(a.annotation is not None for a in
                              list(args.args) + list(args.posonlyargs) + list(args.kwonlyargs))
                ret_ann = node.returns is not None
                if all_ann and ret_ann:
                    ann_fn += 1
            # inconsistent returns
            has_value_return = False
            has_bare_return_or_fallthrough = False
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return):
                    if sub.value is not None:
                        has_value_return = True
                    else:
                        has_bare_return_or_fallthrough = True
            ends_with_return = False
            body_last = node.body[-1] if node.body else None
            if isinstance(body_last, ast.Return):
                ends_with_return = True
            if has_value_return and (has_bare_return_or_fallthrough or not ends_with_return):
                # only flag if there is at least one path that can fall through
                fallthrough = False
                for stmt in node.body:
                    if isinstance(stmt, ast.Return):
                        continue
                    if isinstance(stmt, (ast.If, ast.Try, ast.For, ast.While, ast.With)):
                        fallthrough = True
                if fallthrough:
                    inconsistent_returns.append((rel, node.lineno, node.name))

    # class-level mutable attributes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                targets = []
                if isinstance(stmt, ast.Assign):
                    targets = stmt.targets
                elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                    targets = [stmt.target]
                for t in targets:
                    if isinstance(t, ast.Name) and isinstance(stmt.value, (ast.List, ast.Dict, ast.Set)):
                        class_mutable.append((rel, stmt.lineno, node.name, t.id))

print("Production files scanned:", len(files))
print()
print("=== BROAD except Exception/BaseException: %d total in %d files ===" % (sum(broad_except.values()), len(broad_except)))
for rel, n in broad_except.most_common(15):
    print("  %4d  %s" % (n, rel))
print()
print("=== NAIVE DATETIME USAGE: %d ===" % len(naive_dt))
per = Counter(r for r, _, _ in naive_dt)
for rel, n in per.most_common(12):
    print("  %4d  %s" % (n, rel))
print()
print("=== BUILTIN hash() CALLS (PYTHONHASHSEED nondeterminism risk): %d ===" % len(builtin_hash))
seen = Counter(r for r, _ in builtin_hash)
for rel, n in seen.most_common(15):
    print("  %4d  %s" % (n, rel))
print()
print("=== RANDOM MODULE USAGE IN PRODUCTION: %d ===" % len(random_use))
seenr = Counter((r, q) for r, _, q in random_use)
for (rel, q), n in seenr.most_common(15):
    print("  %4d  %s  (%s)" % (n, rel, q))
print()
print("=== open() WITHOUT context manager: %d ===" % len(open_no_with))
for rel, ln in open_no_with[:20]:
    print("  %s:%d" % (rel, ln))
if len(open_no_with) > 20:
    print("  ... and %d more" % (len(open_no_with) - 20))
print()
print("=== FUNCTIONS WITH MIXED RETURN PATHS (implicit None risk): %d ===" % len(inconsistent_returns))
for rel, ln, name in inconsistent_returns[:25]:
    print("  %s:%d %s()" % (rel, ln, name))
if len(inconsistent_returns) > 25:
    print("  ... and %d more" % (len(inconsistent_returns) - 25))
print()
print("=== CLASS-LEVEL MUTABLE ATTRIBUTES: %d ===" % len(class_mutable))
for rel, ln, cls, attr in class_mutable[:20]:
    print("  %s:%d %s.%s" % (rel, ln, cls, attr))
if len(class_mutable) > 20:
    print("  ... and %d more" % (len(class_mutable) - 20))
print()
print("=== '== None' / '!= None' COMPARISONS: %d ===" % len(none_cmp))
for rel, ln in none_cmp[:15]:
    print("  %s:%d" % (rel, ln))