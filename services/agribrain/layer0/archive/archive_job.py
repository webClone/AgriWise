"""
Historical Sentinel Ingestion Job Orchestrator.
Enforces that historical_full mode requires explicit admin-backfill, scientific-refresh,
or certification-support flags, and validates state transitions.
"""
from typing import List, Optional, Set

class ArchiveJobState:
    CREATED = "created"
    MANIFEST_PLANNED = "manifest_planned"
    MANIFEST_BUILT = "manifest_built"
    DOWNLOAD_PLANNED = "download_planned"
    DOWNLOADED = "downloaded"
    HARMONIZED = "harmonized"
    QUALITY_GATED = "quality_gated"
    ASMAE_READY = "asmae_ready"
    FAILED = "failed"
    CANCELLED = "cancelled"

VALID_TRANSITIONS = {
    ArchiveJobState.CREATED: {ArchiveJobState.MANIFEST_PLANNED, ArchiveJobState.FAILED, ArchiveJobState.CANCELLED},
    ArchiveJobState.MANIFEST_PLANNED: {ArchiveJobState.MANIFEST_BUILT, ArchiveJobState.FAILED, ArchiveJobState.CANCELLED},
    ArchiveJobState.MANIFEST_BUILT: {ArchiveJobState.DOWNLOAD_PLANNED, ArchiveJobState.FAILED, ArchiveJobState.CANCELLED},
    ArchiveJobState.DOWNLOAD_PLANNED: {ArchiveJobState.DOWNLOADED, ArchiveJobState.FAILED, ArchiveJobState.CANCELLED},
    ArchiveJobState.DOWNLOADED: {ArchiveJobState.HARMONIZED, ArchiveJobState.FAILED, ArchiveJobState.CANCELLED},
    ArchiveJobState.HARMONIZED: {ArchiveJobState.QUALITY_GATED, ArchiveJobState.FAILED, ArchiveJobState.CANCELLED},
    ArchiveJobState.QUALITY_GATED: {ArchiveJobState.ASMAE_READY, ArchiveJobState.FAILED, ArchiveJobState.CANCELLED},
    ArchiveJobState.ASMAE_READY: set(),
    ArchiveJobState.FAILED: set(),
    ArchiveJobState.CANCELLED: set()
}

class ArchiveJob:
    def __init__(
        self,
        plot_id: str,
        mode: str,
        trigger_context: Optional[str] = None
    ):
        self.plot_id = plot_id
        self.mode = mode
        self.trigger_context = trigger_context
        self.state = ArchiveJobState.CREATED
        self.error_message: Optional[str] = None
        
        # Guard rule: historical_full is only allowed under specific contexts
        if self.mode == "historical_full":
            allowed_contexts = {"scientific_refresh", "certification_support", "admin_backfill"}
            if not self.trigger_context or self.trigger_context not in allowed_contexts:
                raise ValueError(
                    f"historical_full mode is forbidden under trigger context '{self.trigger_context}'. "
                    "Must be run from 'scientific_refresh', 'certification_support', or 'admin_backfill'."
                )

    def transition_to(self, new_state: str) -> None:
        if new_state not in VALID_TRANSITIONS[self.state]:
            raise ValueError(f"Invalid state transition from {self.state} to {new_state}")
        self.state = new_state
