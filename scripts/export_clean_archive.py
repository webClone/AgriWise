"""
V79A Phase 12 / V922.2A: Clean export archive script.

Creates a distribution archive that enforces .exportignore rules.
Fails if excluded files are detected in the output.

V922.2A additions:
  --verify-only: Scan an existing archive or directory without creating a new one
  --max-size-mb: Abort if archive would exceed size limit (default 50MB)
  Summary statistics: file count by extension, total size, largest files

Usage:
    python scripts/export_clean_archive.py [output_path]
    python scripts/export_clean_archive.py --verify-only path/to/archive.zip
    python scripts/export_clean_archive.py --verify-only path/to/directory/
    python scripts/export_clean_archive.py --max-size-mb 30
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
import zipfile
from collections import Counter
from pathlib import Path


# V922.2A: Hard-forbidden paths that MUST NEVER appear in any export
_HARD_FORBIDDEN_PATHS = [
    "services/agribrain/services/agribrain/",
]


def load_exportignore(root: Path) -> list:
    """Load exclusion patterns from .exportignore."""
    ignorefile = root / ".exportignore"
    if not ignorefile.exists():
        return []

    patterns = []
    for line in ignorefile.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def should_exclude(rel_path: str, patterns: list) -> bool:
    """Check if a relative path matches any exclusion pattern."""
    parts = rel_path.replace("\\", "/").split("/")
    basename = parts[-1]
    normalized = rel_path.replace("\\", "/")

    # Hardcoded security exclusions for real env files
    if basename == ".env.example":
        return False
    if basename == ".env" or basename.startswith(".env.") or basename.endswith(".env"):
        return True

    # V922.2A: Hard-forbidden paths
    for forbidden in _HARD_FORBIDDEN_PATHS:
        if normalized.startswith(forbidden) or f"/{forbidden}" in f"/{normalized}":
            return True

    for pattern in patterns:
        # Direct filename match
        if fnmatch.fnmatch(basename, pattern):
            return True

        # Directory match (pattern ends with /)
        if pattern.endswith("/"):
            dir_pattern = pattern.rstrip("/")
            if any(fnmatch.fnmatch(part, dir_pattern) for part in parts[:-1]):
                return True
            if fnmatch.fnmatch(basename, dir_pattern):
                return True

        # Full path match
        if fnmatch.fnmatch(normalized, pattern):
            return True

        # ** glob support for nested directory matching
        if pattern.startswith("**/"):
            sub_pattern = pattern[3:]
            if fnmatch.fnmatch(basename, sub_pattern):
                return True
            for part in parts[:-1]:
                if fnmatch.fnmatch(part + "/", sub_pattern):
                    return True

    return False


def create_clean_archive(root: Path, output_path: Path, max_size_mb: float = 50.0) -> dict:
    """Create a clean zip archive excluding .exportignore patterns.

    Returns summary dict with counts.
    """
    patterns = load_exportignore(root)
    if not patterns:
        print("WARNING: No .exportignore found, using defaults")
        patterns = [".env", ".env.*", "*.pem", "*.key",
                     "__pycache__/", "*.pyc", ".pytest_cache/",
                     "*.egg-info/", "node_modules/", ".next/", "*.zip",
                     "artifacts/", ".git/"]

    included = []
    excluded = []
    total_size = 0
    ext_counts: Counter = Counter()

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip excluded directories
            dirnames[:] = [
                d for d in dirnames
                if not should_exclude(d + "/", patterns)
                and not should_exclude(
                    os.path.relpath(os.path.join(dirpath, d), root) + "/",
                    patterns,
                )
            ]

            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root)

                if should_exclude(rel_path, patterns):
                    excluded.append(rel_path)
                    continue

                file_size = os.path.getsize(full_path)
                total_size += file_size

                # V922.2A: Check size limit before adding
                total_mb = total_size / (1024 * 1024)
                if total_mb > max_size_mb:
                    print(f"\n[ABORT] Archive would exceed {max_size_mb}MB limit "
                          f"({total_mb:.1f}MB after {len(included)} files)")
                    # Remove partial archive
                    output_path.unlink(missing_ok=True)
                    sys.exit(1)

                zf.write(full_path, rel_path)
                included.append(rel_path)

                # Track extension stats
                ext = Path(filename).suffix.lower() or "(no extension)"
                ext_counts[ext] += 1

    return {
        "archive": str(output_path),
        "included_count": len(included),
        "excluded_count": len(excluded),
        "excluded_files": excluded,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "extension_counts": dict(ext_counts.most_common(20)),
    }


def verify_archive(archive_path: Path, patterns: list) -> list:
    """Verify that no excluded files leaked into the archive.

    Returns list of violations. Empty = clean.
    """
    violations = []
    with zipfile.ZipFile(archive_path, "r") as zf:
        for name in zf.namelist():
            if should_exclude(name, patterns):
                violations.append(name)
    return violations


def verify_directory(dir_path: Path, patterns: list) -> list:
    """Verify that a directory tree has no files that should be excluded.

    Returns list of violations. Empty = clean.
    """
    violations = []
    for dirpath, dirnames, filenames in os.walk(dir_path):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, dir_path)
            if should_exclude(rel_path, patterns):
                violations.append(rel_path)
    return violations


def _print_summary(result: dict):
    """Print summary statistics."""
    print(f"\nIncluded: {result['included_count']} files")
    print(f"Excluded: {result['excluded_count']} files")
    print(f"Total size: {result['total_size_mb']} MB")

    if result.get("extension_counts"):
        print("\nFile types (top 10):")
        for ext, count in list(result["extension_counts"].items())[:10]:
            print(f"  {ext}: {count}")

    if result["excluded_files"]:
        print(f"\nExcluded files (first 20 of {result['excluded_count']}):")
        for f in result["excluded_files"][:20]:
            print(f"  [EXCLUDE] {f}")
        if len(result["excluded_files"]) > 20:
            print(f"  ... and {len(result['excluded_files']) - 20} more")


def main():
    parser = argparse.ArgumentParser(description="Create/verify clean export archive")
    parser.add_argument("output", nargs="?", default=None,
                        help="Output archive path or path to verify")
    parser.add_argument("--verify-only", action="store_true",
                        help="Verify an existing archive or directory only")
    parser.add_argument("--max-size-mb", type=float, default=50.0,
                        help="Maximum archive size in MB (default 50)")

    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent

    if args.verify_only:
        target = Path(args.output) if args.output else root
        patterns = load_exportignore(root)

        if target.is_file() and target.suffix == ".zip":
            print(f"Verifying archive: {target}")
            violations = verify_archive(target, patterns)
        elif target.is_dir():
            print(f"Verifying directory: {target}")
            violations = verify_directory(target, patterns)
        else:
            print(f"[ERROR] {target} is not a valid zip file or directory")
            sys.exit(1)

        if violations:
            print(f"\n[FAIL] {len(violations)} excluded files found!")
            # Group by type
            type_counts: Counter = Counter()
            for v in violations:
                parts = v.replace("\\", "/").split("/")
                basename = parts[-1]
                if basename == ".env":
                    type_counts[".env"] += 1
                elif basename.endswith(".pyc"):
                    type_counts[".pyc"] += 1
                elif "__pycache__" in v:
                    type_counts["__pycache__"] += 1
                elif basename.endswith(".zip"):
                    type_counts["nested .zip"] += 1
                elif "artifacts/" in v.replace("\\", "/"):
                    type_counts["artifacts/"] += 1
                elif "services/agribrain/services/" in v.replace("\\", "/"):
                    type_counts["nested services/"] += 1
                else:
                    type_counts["other"] += 1

            for type_name, count in type_counts.most_common():
                print(f"  {type_name}: {count}")

            # Show first 10 individual violations
            for v in violations[:10]:
                print(f"  [VIOLATION] {v}")
            if len(violations) > 10:
                print(f"  ... and {len(violations) - 10} more")

            sys.exit(1)
        else:
            print("\n[SUCCESS] No excluded files detected.")
            sys.exit(0)
    else:
        output = Path(args.output) if args.output else root / "export.zip"

        print(f"Creating clean archive from: {root}")
        print(f"Output: {output}")
        print(f"Max size: {args.max_size_mb} MB")

        result = create_clean_archive(root, output, max_size_mb=args.max_size_mb)
        _print_summary(result)

        # Post-verification
        patterns = load_exportignore(root)
        violations = verify_archive(output, patterns)

        if violations:
            print(f"\n[FAIL] {len(violations)} excluded files found in archive!")
            for v in violations[:10]:
                print(f"  [VIOLATION] {v}")
            sys.exit(1)
        else:
            print(f"\n[SUCCESS] Archive is clean — no excluded files detected.")
            print(f"  Archive: {output}")
            print(f"  Size: {result['total_size_mb']} MB")


if __name__ == "__main__":
    main()
