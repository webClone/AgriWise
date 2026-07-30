"""
In-memory or persisted registry of archive run states.
"""
from typing import Dict
from .archive_job import ArchiveJob

class ArchiveRunStateRegistry:
    def __init__(self):
        self._jobs: Dict[str, ArchiveJob] = {}

    def register_job(self, job_id: str, job: ArchiveJob) -> None:
        self._jobs[job_id] = job

    def get_job(self, job_id: str) -> ArchiveJob:
        return self._jobs.get(job_id)
