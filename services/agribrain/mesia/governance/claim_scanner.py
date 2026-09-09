"""Automated Scientific Claim Scanner for MESIA Governance (R6 / P-01..P-10).

Recursively scans code, UI templates, test fixtures, and documentation to enforce
zero unreviewed or deceptive claims of physical measurement, zero synthetic,
dual closure verified, or ground truth.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Tuple

# Workspace root
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]

FORBIDDEN_PATTERNS: List[Tuple[str, Pattern[str]]] = [
    ("100%_REAL", re.compile(r"\b100%\s*(?:real|authentic)\b", re.IGNORECASE)),
    ("ZERO_SYNTHETIC", re.compile(r"\bzero\s+synthetic\b", re.IGNORECASE)),
    ("DUAL_CLOSURE_VERIFIED", re.compile(r"\bdual\s+closure\s+verified\b", re.IGNORECASE)),
    ("GROUND_TRUTH", re.compile(r"\bground\s+truth\b", re.IGNORECASE)),
    ("FULL_ASMAE_ASSIMILATION", re.compile(r"\bfull\s+asmae\s+assimilation\b", re.IGNORECASE)),
    ("ACTIVE_SENSING_VERIFIED", re.compile(r"\bactive\s+sensing\s+verified\b", re.IGNORECASE)),
    ("100%_OBSERVATION_DATA", re.compile(r"\b100%\s*(?:real\s+)?observation\s+data\b", re.IGNORECASE)),
]

SCAN_EXTENSIONS = {".py", ".ts", ".tsx", ".md", ".json", ".html"}
IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".gemini",
    "venv",
    ".venv",
    "dist",
    "build",
    "archive",
}


def load_exemptions(exemptions_file: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Loads reviewed exemptions from manifest."""
    if exemptions_file is None:
        exemptions_file = Path(__file__).parent / "claim_exemptions.json"

    if not exemptions_file.is_file():
        return []

    try:
        data = json.loads(exemptions_file.read_text(encoding="utf-8"))
        return data.get("exemptions", [])
    except Exception:
        return []


def is_file_exempt(rel_path_str: str, exemptions: List[Dict[str, Any]]) -> bool:
    """Checks if a file path is listed in exemptions."""
    norm_path = rel_path_str.replace("\\", "/")
    if norm_path.endswith("claim_exemptions.json") or norm_path.endswith("claim_scanner.py"):
        return True
    for ex in exemptions:
        pat = ex.get("file_pattern", "").replace("\\", "/")
        if pat and pat in norm_path:
            return True
    return False


def scan_repository_for_forbidden_claims(
    target_dirs: Optional[List[Path]] = None,
    exemptions_file: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Scans specified directories or defaults for forbidden scientific claim patterns.
    Returns list of violation dictionaries.
    """
    if target_dirs is None:
        target_dirs = [
            WORKSPACE_ROOT / "services" / "agribrain" / "mesia",
            WORKSPACE_ROOT / "src" / "components" / "farm" / "intelligence",
            WORKSPACE_ROOT / "src" / "app" / "api" / "agribrain" / "mesia",
        ]

    exemptions = load_exemptions(exemptions_file)
    violations: List[Dict[str, Any]] = []

    for base_dir in target_dirs:
        if not base_dir.exists():
            continue

        for p in base_dir.rglob("*"):
            if p.is_dir() or p.suffix not in SCAN_EXTENSIONS:
                continue

            # Skip ignored directories
            if any(part in IGNORE_DIRS for part in p.parts):
                continue

            rel_str = str(p.relative_to(WORKSPACE_ROOT)).replace("\\", "/")

            if is_file_exempt(rel_str, exemptions):
                continue

            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for line_idx, line in enumerate(content.splitlines(), start=1):
                for rule_name, pat in FORBIDDEN_PATTERNS:
                    match = pat.search(line)
                    if match:
                        violations.append({
                            "rule": rule_name,
                            "file": rel_str,
                            "line_number": line_idx,
                            "matched_text": match.group(0),
                            "line_snippet": line.strip()[:120],
                        })

    return violations


def main() -> int:
    """CLI entrypoint for claim scanner."""
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 70)
    print("MESIA Scientific Claim Scanner — Principle P-08 Scientific Truth")
    print("=" * 70)

    violations = scan_repository_for_forbidden_claims()

    if not violations:
        print("\n[PASSED] Zero forbidden scientific claims detected. Codebase is clean.\n")
        return 0

    print(f"\n[FAILED] {len(violations)} forbidden scientific claim violations detected:\n")
    for v in violations:
        safe_snippet = v["line_snippet"].encode("ascii", errors="replace").decode("ascii")
        print(f"  [{v['rule']}] {v['file']}:{v['line_number']}")
        print(f"    Match: '{v['matched_text']}'")
        print(f"    Code:  {safe_snippet}\n")

    return 1


if __name__ == "__main__":
    sys.exit(main())

