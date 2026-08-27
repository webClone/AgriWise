from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from services.agribrain.layer05_asmae import background_jobs as jobs


class WorkerLifecycleTests(unittest.TestCase):
    def _write_job(
        self,
        root: Path,
        *,
        job_id: str = 'a' * 24,
        status: str = 'queued',
        **changes,
    ) -> Path:
        job_path = root / f'{job_id}.job.json'
        manifest_path = root / f'{job_id}.manifest.json'
        payload = {
            'job_id': job_id,
            'plot_id': 'plot-worker-test',
            'run_id': 'run-worker-test',
            'status': status,
            'stage': 'test_fixture',
            'progress_pct': 5,
            'attempts': 0,
            'revision': 1,
            'manifest_ref': str(manifest_path),
            'manifest_hash': 'fixture-manifest-hash',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'lease_generation': 0,
            **changes,
        }
        jobs._atomic_json(job_path, payload)
        return job_path

    def test_expired_running_job_is_fail_closed_as_stalled(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expired = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
            job_path = self._write_job(
                root,
                status='running',
                lease_owner='pid:old',
                lease_token='old-token',
                lease_generation=7,
                lease_expires_at=expired,
            )
            with patch.object(jobs, 'JOBS_DIR', root):
                public = jobs.get_job_status('a' * 24)

            self.assertIsNotNone(public)
            self.assertEqual('stalled', public['status'])
            self.assertTrue(public['recoverable'])
            self.assertNotIn('lease_token', public)
            stored = json.loads(job_path.read_text(encoding='utf-8'))
            self.assertEqual(8, stored['lease_generation'])
            self.assertIsNone(stored['lease_token'])
            self.assertEqual('expired_worker_lease', stored['recovery_reason'])

    def test_stale_lease_cannot_update_recovered_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job_path = self._write_job(
                root,
                status='running',
                lease_owner='pid:old',
                lease_token='old-token',
                lease_generation=3,
                lease_expires_at=(
                    datetime.now(timezone.utc) - timedelta(seconds=1)
                ).isoformat(),
            )
            old_lease = jobs.WorkerLease('old-token', 3, 'pid:old')
            with patch.object(jobs, 'JOBS_DIR', root):
                jobs._mark_stalled_if_expired(job_path)
                with self.assertRaises(jobs.LeaseLostError):
                    jobs._fenced_update_job(
                        job_path,
                        old_lease,
                        status='completed',
                        progress_pct=100,
                    )
            stored = json.loads(job_path.read_text(encoding='utf-8'))
            self.assertEqual('stalled', stored['status'])

    def test_old_worker_cannot_remove_replacement_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job_path = self._write_job(
                root,
                status='running',
                lease_expires_at=(
                    datetime.now(timezone.utc) - timedelta(seconds=1)
                ).isoformat(),
            )
            old_claim = jobs._claim(job_path)
            self.assertIsNotNone(old_claim)
            old_time = time.time() - jobs.LEASE_SECONDS - 2
            os.utime(old_claim.path, (old_time, old_time))
            replacement = jobs._claim(job_path)
            self.assertIsNotNone(replacement)
            self.assertNotEqual(old_claim.token, replacement.token)

            jobs._release_claim(old_claim)
            self.assertTrue(replacement.path.exists())
            jobs._release_claim(replacement)
            self.assertFalse(replacement.path.exists())

    def test_recovery_marks_stalled_before_launching_replacement(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job_path = self._write_job(
                root,
                status='running',
                lease_token='expired-token',
                lease_generation=2,
                lease_expires_at=(
                    datetime.now(timezone.utc) - timedelta(seconds=1)
                ).isoformat(),
            )
            with patch.object(jobs, 'JOBS_DIR', root), patch.object(
                jobs, 'spawn_worker', return_value=True
            ) as spawn:
                resumed = jobs.recover_pending_jobs(plot_id='plot-worker-test')

            self.assertEqual(1, resumed)
            spawn.assert_called_once_with(job_path)
            stored = json.loads(job_path.read_text(encoding='utf-8'))
            self.assertEqual('stalled', stored['status'])
            self.assertTrue(stored['recoverable'])

    def test_delayed_launch_token_cannot_claim_replacement_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job_path = self._write_job(
                root,
                status='queued',
                launch_token='replacement-launch-token',
            )
            with patch.object(jobs, 'JOBS_DIR', root):
                jobs.run_job(job_path, launch_token='obsolete-launch-token')

            stored = json.loads(job_path.read_text(encoding='utf-8'))
            self.assertEqual('queued', stored['status'])
            self.assertEqual(0, stored['attempts'])
            self.assertFalse(job_path.with_suffix('.lock').exists())

    def test_expired_worker_stops_after_recovery_attempt_ceiling(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job_path = self._write_job(
                root,
                status='running',
                attempts=jobs.MAX_EXECUTION_ATTEMPTS,
                lease_token='last-token',
                lease_generation=9,
                lease_expires_at=(
                    datetime.now(timezone.utc) - timedelta(seconds=1)
                ).isoformat(),
            )
            with patch.object(jobs, 'JOBS_DIR', root), patch.object(
                jobs, 'spawn_worker', return_value=True
            ) as spawn:
                resumed = jobs.recover_pending_jobs(plot_id='plot-worker-test')

            self.assertEqual(0, resumed)
            spawn.assert_not_called()
            stored = json.loads(job_path.read_text(encoding='utf-8'))
            self.assertEqual('failed', stored['status'])
            self.assertEqual('worker_recovery_exhausted', stored['stage'])
            self.assertEqual('manual_review', stored['retry_classification'])
            self.assertFalse(stored['recoverable'])

    def test_recovery_launches_only_newest_plot_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old_created = (
                datetime.now(timezone.utc) - timedelta(hours=1)
            ).isoformat()
            old_path = self._write_job(
                root,
                job_id='a' * 24,
                run_id='run-old',
                created_at=old_created,
            )
            new_path = self._write_job(
                root,
                job_id='b' * 24,
                run_id='run-new',
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            with patch.object(jobs, 'JOBS_DIR', root), patch.object(
                jobs, 'spawn_worker', return_value=True
            ) as spawn:
                resumed = jobs.recover_pending_jobs(
                    plot_id='plot-worker-test'
                )
                latest = jobs.latest_job_for_plot('plot-worker-test')
                exact_old = jobs.latest_job_for_plot(
                    'plot-worker-test', run_id='run-old'
                )

            self.assertEqual(1, resumed)
            spawn.assert_called_once_with(new_path)
            old = json.loads(old_path.read_text(encoding='utf-8'))
            self.assertEqual('superseded', old['status'])
            self.assertEqual('b' * 24, old['superseded_by_job_id'])
            self.assertEqual('b' * 24, latest['job_id'])
            self.assertEqual('a' * 24, exact_old['job_id'])

    def test_real_subprocess_records_contract_failure_and_logs(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            root = Path(temporary)
            job_path = self._write_job(root)
            with patch.object(jobs, 'JOBS_DIR', root):
                self.assertTrue(jobs.spawn_worker(job_path))
                deadline = time.monotonic() + 15.0
                stored = {}
                while time.monotonic() < deadline:
                    stored = json.loads(job_path.read_text(encoding='utf-8'))
                    claim_path = job_path.with_suffix('.lock')
                    if stored.get('status') == 'failed' and not claim_path.exists():
                        break
                    time.sleep(0.05)
                # The detached child releases its claim immediately before
                # process teardown; allow Windows to close the inherited log
                # handle before TemporaryDirectory removes the fixture.
                time.sleep(0.25)

            self.assertEqual('failed', stored.get('status'))
            self.assertEqual('contract_validation_failed', stored.get('stage'))
            stdout_path, event_path = jobs._job_log_paths(job_path)
            self.assertTrue(stdout_path.exists())
            self.assertTrue(event_path.exists())
            events = [
                json.loads(line)
                for line in event_path.read_text(encoding='utf-8').splitlines()
                if line.strip()
            ]
            names = {event['event'] for event in events}
            self.assertIn('worker_process_started', names)
            self.assertIn('worker_lease_acquired', names)
            self.assertIn('worker_contract_rejected', names)


if __name__ == '__main__':
    unittest.main()
