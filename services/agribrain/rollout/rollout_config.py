"""
Rollout Configuration.
Defines parameters and paths for the V85 rollout monitor and registry.
"""

from __future__ import annotations
from pathlib import Path

ROLLOUT_DIR = Path(__file__).parent.resolve()
REGISTRY_FILE_PATH = ROLLOUT_DIR / "asmae_rollout_registry.json"
AUDIT_LOG_FILE_PATH = ROLLOUT_DIR.parent / "artifacts" / "rollout_audit.log"
VALIDATION_LEDGER_PATH = ROLLOUT_DIR.parent / "artifacts" / "validation_ledger" / "asmae_validation_ledger.jsonl"
ROLLOUT_REPORT_PATH = ROLLOUT_DIR.parent / "artifacts" / "v85_rollout_report.json"
PLOT_STATUS_SUMMARY_PATH = ROLLOUT_DIR.parent / "artifacts" / "v85_plot_status_summary.json"
