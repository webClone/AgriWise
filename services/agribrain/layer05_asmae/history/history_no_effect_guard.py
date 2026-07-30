"""
History No-Effect Guard.
Computes cryptographic checksums of operational files/directories before historical runs
and asserts they remain unmodified afterwards.
"""
import os
import hashlib
from typing import Dict, List

WATCH_DIRS = [
    "services/agribrain/artifacts/validation_ledger",
    "services/agribrain/artifacts/plot_memory",
    "services/agribrain/artifacts/v90_certifications",
    "services/agribrain/artifacts/surfaces_cache",
    "services/agribrain/artifacts/layer1_state_evidence",
    "services/agribrain/artifacts/current_asmae_state",
]

ALLOWED_HISTORY_OUTPUT_ROOTS = {
    "archive_cache",
    "archive_manifest",
    "archive_metrics",
    "historical_assimilation",
    "historical_surfaces_cache",
    "archive_pilot_reports",
}


class HistoryNoEffectGuard:
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    def _get_absolute_path(self, rel_path: str) -> str:
        return os.path.abspath(os.path.join(self.workspace_root, rel_path.replace("/", os.sep)))

    def _compute_file_hash(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return "not_found"
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except OSError:
            return "error"

    def record_pre_run_checksums(self) -> Dict[str, str]:
        """Records hashes of all subfiles in critical operational directories recursively."""
        checksums = {}
        for rel_dir in WATCH_DIRS:
            abs_dir = self._get_absolute_path(rel_dir)
            if os.path.exists(abs_dir) and os.path.isdir(abs_dir):
                for root, _, files in os.walk(abs_dir):
                    for file in files:
                        if file.endswith(".tmp") or file.endswith(".temp") or ".tmp" in file or ".temp" in file:
                            continue
                        full_path = os.path.join(root, file)
                        rel_file = os.path.relpath(full_path, self.workspace_root).replace(os.sep, "/")
                        checksums[rel_file] = self._compute_file_hash(full_path)
            else:
                checksums[rel_dir] = "dir_not_found"
        return checksums

    def assert_post_run_unchanged(self, pre_checksums: Dict[str, str]) -> None:
        """Asserts that watch paths and subfiles have not been modified or added."""
        violations = []
        
        # 1. Check if watched files changed or were deleted
        for rel_file, pre_hash in pre_checksums.items():
            if pre_hash == "dir_not_found":
                abs_dir = self._get_absolute_path(rel_file)
                if os.path.exists(abs_dir) and os.path.isdir(abs_dir) and os.listdir(abs_dir):
                    violations.append(f"Violation: Directory '{rel_file}' did not exist but was created and populated post-run!")
                continue
                
            abs_path = self._get_absolute_path(rel_file)
            post_hash = self._compute_file_hash(abs_path)
            if pre_hash != post_hash:
                violations.append(
                    f"Violation: File '{rel_file}' was modified or deleted! "
                    f"Pre-run hash: {pre_hash}, Post-run hash: {post_hash}"
                )

        # 2. Check if new files were created in watched directories
        for rel_dir in WATCH_DIRS:
            abs_dir = self._get_absolute_path(rel_dir)
            if os.path.exists(abs_dir) and os.path.isdir(abs_dir):
                for root, _, files in os.walk(abs_dir):
                    for file in files:
                        if file.endswith(".tmp") or file.endswith(".temp") or ".tmp" in file or ".temp" in file:
                            continue
                        full_path = os.path.join(root, file)
                        rel_file = os.path.relpath(full_path, self.workspace_root).replace(os.sep, "/")
                        if rel_file not in pre_checksums:
                            is_new = True
                            for k, v in pre_checksums.items():
                                if v == "dir_not_found" and rel_file.startswith(k):
                                    is_new = False
                                    break
                            if is_new:
                                violations.append(f"Violation: New file '{rel_file}' was created post-run!")

        if violations:
            raise AssertionError(
                "History No-Effect Guard Failed!\n" + "\n".join(violations)
            )
