"""
Archive Scheduler handling the execution orchestration of sentinel archive ingestion jobs.
"""
from typing import Optional
from .archive_job import ArchiveJob, ArchiveJobState
from .archive_run_state import ArchiveRunStateRegistry

class ArchiveScheduler:
    def __init__(self, registry: Optional[ArchiveRunStateRegistry] = None):
        self.registry = registry or ArchiveRunStateRegistry()

    def submit_job(self, job_id: str, job: ArchiveJob) -> None:
        self.registry.register_job(job_id, job)
        
    def execute_next_stage(self, job_id: str, next_state: str) -> None:
        job = self.registry.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in scheduler registry.")
        job.transition_to(next_state)
