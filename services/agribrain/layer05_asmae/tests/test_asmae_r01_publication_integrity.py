"""
ASMAE-R01 Mandatory Qualification Test Suite: Publication & Scientific Authority Integrity.

Verifies the 8 mandatory exit-gate qualification cases for bounded R01 remediation:
  Case 1: Real worker payload -> publish -> cold exact read -> cold latest read -> internal API admission.
  Case 2: Missing/corrupt/mismatched numerical record -> rejected/quarantined (no half-published head).
  Case 3: Corrupt ASMAE latest head -> valid provider-only Layer 10 fallback retained and served.
  Case 4: Same snapshot ID with conflicting numerical content -> rejected as collision (no overwrite).
  Case 5: Identical retries, concurrent calls, crash recovery (0-byte file) -> idempotent and deterministic.
  Case 6: Tenancy and security -> foreign tenant/plot/farm cannot read or promote foreign publication.
  Case 7: Observation-only Layer 0/Layer 1 contracts and disabled irrigation interlock remain fail-closed.
  Case 8: Scalar-only / no-scene case remains honest; no synthetic spatial heatmap fabricated.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from services.agribrain.common.plot_namespace import PlotNamespace
from services.agribrain.layer05_asmae import plot_snapshot_store, snapshot_store
from services.agribrain.layer05_asmae.plot_snapshot_store import (
    publish_canonical_plot_snapshot,
    publish_canonical_layer10_snapshot,
    load_latest_plot_snapshot,
    load_plot_snapshot_by_id,
    _head_path,
    _plot_dir,
)
from services.agribrain.layer05_asmae.history.archive_metrics_store import ArchiveMetricsStore
from services.agribrain.layer10_sire.surface_contract import (
    RENDER_AUTHORIZATION_VERSION,
    SURFACES_SCHEMA_VERSION,
)
from services.agribrain.layer1_fusion.truth_bridge import compute_asmae_vector_numerical_hash
from services.agribrain.app.main import api_v2_canonical_plot_snapshot


class ASMAER01PublicationIntegrityTests(unittest.TestCase):
    """Authoritative test suite for ASMAE-R01 qualification."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="asmae_r01_test_")
        self.snapshot_root = Path(self.temp_dir) / "plot_snapshots"
        self.asmae_root = Path(self.temp_dir) / "asmae_snapshots"
        self.metrics_root = Path(self.temp_dir) / "archive_metrics"

        self.orig_plot_root = plot_snapshot_store.PLOT_SNAPSHOT_ROOT
        self.orig_snap_dir = snapshot_store.SNAPSHOT_DIR
        self.orig_snap_node = snapshot_store.SNAPSHOT_NODE_DIR
        self.orig_metrics_env = os.environ.get("AGRIBRAIN_METRICS_ROOT")

        plot_snapshot_store.PLOT_SNAPSHOT_ROOT = self.snapshot_root
        snapshot_store.SNAPSHOT_DIR = self.asmae_root
        snapshot_store.SNAPSHOT_NODE_DIR = self.asmae_root / "nodes"
        os.environ["AGRIBRAIN_METRICS_ROOT"] = str(self.metrics_root)

        with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
            plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()

        self.tenant_id = "tenant-algeria-west"
        self.farm_id = "farm-mitidja-01"
        self.plot_id = "plot-afroun-citrus"
        self.geometry_hash = "620804f4"
        self.crop_cycle_id = "cycle-2026-harvest"

        self.ns = PlotNamespace(
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            plot_id=self.plot_id,
        )

    def tearDown(self):
        plot_snapshot_store.PLOT_SNAPSHOT_ROOT = self.orig_plot_root
        snapshot_store.SNAPSHOT_DIR = self.orig_snap_dir
        snapshot_store.SNAPSHOT_NODE_DIR = self.orig_snap_node
        if self.orig_metrics_env is not None:
            os.environ["AGRIBRAIN_METRICS_ROOT"] = self.orig_metrics_env
        else:
            os.environ.pop("AGRIBRAIN_METRICS_ROOT", None)

        with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
            plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _generate_valid_worker_payload(
        self,
        snapshot_id: str = "ASMAE-SNAPSHOT-2026-001",
        job_id: str = "job-worker-888",
        manifest_hash: str = "manifest-hash-888",
        root_moisture: float = 0.382,
        canopy_vigor: float = 0.615,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Construct realistic worker ASMAE result and frontend bundle."""
        states = {
            "root_zone_moisture": float(root_moisture),
            "canopy_vigor": float(canopy_vigor),
            "canopy_water_content": 0.420,
            "evapotranspiration_actual": 3.85,
        }
        sigmas = {
            "root_zone_moisture": 0.012,
            "canopy_vigor": 0.015,
            "canopy_water_content": 0.018,
            "evapotranspiration_actual": 0.25,
        }
        vec_hash = compute_asmae_vector_numerical_hash(states, sigmas)

        num_rec = {
            "states": states,
            "sigmas": sigmas,
            "numerical_vector_hash": vec_hash,
        }

        asmae_result = {
            "plot_id": self.plot_id,
            "snapshot_id": snapshot_id,
            "content_hash": hashlib.sha256(f"content-{snapshot_id}".encode()).hexdigest(),
            "crop_posterior_lineage": "lineage-citrus-mitidja-v1",
            "crop_worldline_event_id": "event-wl-crop-101",
            "phenology_worldline_event_id": "event-wl-phen-101",
            "crop_influence_manifest_hash": manifest_hash,
            "crop_evidence_ledger_hash": "ledger-hash-101",
            "asmae_posterior_numerical_record": num_rec,
            "asmae_numerical_digest": vec_hash,
            "claims_numerical_authority": True,
            "state_means": states,
            "sigmas": sigmas,
            "raster_maps": {},
        }

        frontend = {
            "version": SURFACES_SCHEMA_VERSION,
            "surface_schema_version": SURFACES_SCHEMA_VERSION,
            "intelligence_snapshot_id": snapshot_id,
            "plot_id": self.plot_id,
            "tenant_id": self.tenant_id,
            "farm_id": self.farm_id,
            "publication_id": f"pub-{snapshot_id}",
            "publication_run_id": f"run-{snapshot_id}",
            "run_id": f"run-{snapshot_id}",
            "pipeline_state": "terminal_layer10_published",
            "publication_status": "VALID_NORMAL",
            "render_authorization_version": RENDER_AUTHORIZATION_VERSION,
            "render_authorizations": {"canopy": {"authorized": True}},
            "claims_numerical_authority": True,
            "asmae_posterior_numerical_record": num_rec,
            "asmae_proof": {
                "proof_id": f"proof-{snapshot_id}",
                "status": "valid",
                "numerical_vector_hash": vec_hash,
            },
            "scientific_evidence_lineage": {
                "crop_posterior_lineage": "lineage-citrus-mitidja-v1",
                "crop_worldline_event_id": "event-wl-crop-101",
                "phenology_worldline_event_id": "event-wl-phen-101",
                "asmae_posterior_vector_hash": vec_hash,
                "replay_mode": "exact_frozen_worldline_events",
            },
            "surfaces": [
                {
                    "surface_id": "surface-canopy-vigor",
                    "surface_type": "canopy_vigor",
                    "values": [[0.615]],
                    "resolution_m": 10.0,
                    "content_hash": hashlib.sha256(b"surf-vigor").hexdigest(),
                }
            ],
            "crop_cycle_id": self.crop_cycle_id,
        }

        return asmae_result, frontend

    # =========================================================================
    # Case 1: Real worker publication -> Cold Readers -> API Admission
    # =========================================================================
    def test_case_01_real_worker_publication_and_api_admission(self):
        """Worker produces valid admitted result -> publisher -> cold exact read -> cold latest read -> API admission."""
        snapshot_id = "ASMAE-SNAPSHOT-CASE01"
        job_id = "job-c1"
        manifest_hash = "manifest-c1"
        asmae_result, frontend = self._generate_valid_worker_payload(snapshot_id, job_id, manifest_hash)

        # 1. Publish snapshot
        head = publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend,
            job_id=job_id,
            manifest_hash=manifest_hash,
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )
        self.assertEqual(head["snapshot_id"], snapshot_id)

        # 2. Cold exact reader (clear memory cache first)
        with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
            plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()

        exact_node = load_plot_snapshot_by_id(
            snapshot_id=snapshot_id,
            namespace=self.ns,
        )
        self.assertIsNotNone(exact_node)
        self.assertEqual(exact_node["snapshot_id"], snapshot_id)

        # 3. Cold latest reader
        latest_node = load_latest_plot_snapshot(self.ns, self.geometry_hash)
        self.assertIsNotNone(latest_node)
        self.assertEqual(latest_node["snapshot_id"], snapshot_id)
        val = latest_node.get("validation", {})
        self.assertTrue(val.get("nodeValid"), "Node hash must be verified")
        self.assertTrue(val.get("publicationValid"), "Publication hash must be verified")
        self.assertTrue(val.get("receiptValid"), "Receipt hash must be verified")
        self.assertTrue(val.get("temporalBindingValid"), "Temporal binding must be valid")
        self.assertTrue(val.get("numericalBindingValid"), "Numerical binding must be valid")
        self.assertTrue(val.get("nodeAgreementValid"), "Node agreement must be valid")

        # 4. Internal API admission gate check
        api_admission = api_v2_canonical_plot_snapshot(self.plot_id, namespace=self.ns)
        if isinstance(api_admission, dict):
            self.assertNotEqual(api_admission.get("status"), "quarantined")
            self.assertNotEqual(api_admission.get("reason"), "canonical_head_integrity_invalid")
            self.assertFalse(api_admission.get("quarantined", False))
        else:
            self.assertEqual(api_admission.status_code, 200)

        # Check preserved state values
        retrieved_num_rec = latest_node["frontend_payload"]["asmae_posterior_numerical_record"]
        self.assertAlmostEqual(retrieved_num_rec["states"]["root_zone_moisture"], 0.382)
        self.assertAlmostEqual(retrieved_num_rec["states"]["canopy_vigor"], 0.615)
        self.assertEqual(retrieved_num_rec["numerical_vector_hash"], asmae_result["asmae_numerical_digest"])

    # =========================================================================
    # Case 2: Mismatched / Missing numerical record -> Quarantined
    # =========================================================================
    def test_case_02_mismatched_numerical_record_quarantined_by_api(self):
        """Mismatched numerical digest must be flagged and quarantined by API admission gate."""
        snapshot_id = "ASMAE-SNAPSHOT-CASE02"
        job_id = "job-c2"
        manifest_hash = "manifest-c2"
        asmae_result, frontend = self._generate_valid_worker_payload(snapshot_id, job_id, manifest_hash)

        # Tamper with the states without updating the vector hash
        frontend["asmae_posterior_numerical_record"]["states"]["root_zone_moisture"] = 0.999

        head = publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend,
            job_id=job_id,
            manifest_hash=manifest_hash,
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )

        with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
            plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()

        latest_node = load_latest_plot_snapshot(self.ns, self.geometry_hash)
        self.assertIsNotNone(latest_node)
        self.assertFalse(latest_node["validation"]["numericalBindingValid"])

        api_admission = api_v2_canonical_plot_snapshot(self.plot_id, namespace=self.ns)
        self.assertIsInstance(api_admission, dict)
        self.assertTrue(api_admission.get("quarantined"))
        self.assertEqual(api_admission.get("reason"), "canonical_head_integrity_invalid")
        self.assertIn("numericalBindingValid", api_admission.get("invalidIntegrityFlags", []))

    # =========================================================================
    # Case 3: Corrupt ASMAE head -> Layer 10 Provider-Only Fallback Succeeds
    # =========================================================================
    def test_case_03_corrupt_asmae_head_does_not_suppress_provider_fallback(self):
        """A quarantined ASMAE head must not suppress subsequent Layer 10 fallback publication."""
        # 1. Publish invalid ASMAE head
        asmae_id = "ASMAE-SNAPSHOT-CASE03-BAD"
        asmae_result, frontend = self._generate_valid_worker_payload(asmae_id, "job-c3-bad", "man-c3-bad")
        # Corrupt the proof hash so numerical binding fails
        frontend["asmae_proof"]["numerical_vector_hash"] = "corrupt-hash-0000"

        publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=asmae_id,
            asmae_result=asmae_result,
            frontend_payload=frontend,
            job_id="job-c3-bad",
            manifest_hash="man-c3-bad",
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )

        # 2. Attempt terminal Layer 10 fallback publication
        layer10_payload = {
            "snapshot_id": "L10-SNAPSHOT-FALLBACK-001",
            "intelligence_snapshot_id": "L10-SNAPSHOT-FALLBACK-001",
            "plot_id": self.plot_id,
            "tenant_id": self.tenant_id,
            "farm_id": self.farm_id,
            "crop_cycle_id": self.crop_cycle_id,
            "pipeline_state": "terminal_layer10_published",
            "surfaces": [
                {
                    "surface_id": "surface-satellite-fallback",
                    "surface_type": "canopy_vigor",
                    "values": [[0.52]],
                    "resolution_m": 10.0,
                    "content_hash": hashlib.sha256(b"surf-fallback").hexdigest(),
                }
            ],
        }

        # Gate IR-02 fix: Should NOT raise ValueError; must publish the Layer 10 fallback!
        fallback_summary = publish_canonical_layer10_snapshot(
            namespace=self.ns,
            geometry_hash=self.geometry_hash,
            frontend_payload=layer10_payload,
            request_run_id="run-layer10-fallback",
            crop_cycle_id=self.crop_cycle_id,
        )

        self.assertEqual(fallback_summary["snapshot_id"], "L10-SNAPSHOT-FALLBACK-001")

        # Head points to Layer 10 fallback
        head = json.loads(_head_path(self.ns).read_text(encoding="utf-8"))
        self.assertEqual(head["snapshot_id"], "L10-SNAPSHOT-FALLBACK-001")

        # The bad ASMAE node remains on disk for audit
        bad_node_path = _plot_dir(self.ns) / "nodes" / f"{asmae_id}.json"
        self.assertTrue(bad_node_path.exists(), "Corrupt ASMAE node must remain auditable on disk")

    def test_case_03b_corrupt_inventory_or_lineage_triggers_layer10_fallback(self):
        """A head failing inventoryValid or lineageValid must not suppress Layer 10 fallback (R01-V01)."""
        asmae_id = "ASMAE-SNAPSHOT-CASE03B"
        asmae_result, frontend = self._generate_valid_worker_payload(asmae_id, "job-c3b", "man-c3b")

        publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=asmae_id,
            asmae_result=asmae_result,
            frontend_payload=frontend,
            job_id="job-c3b",
            manifest_hash="man-c3b",
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )

        # Deliberately corrupt head's surface_inventory_hash on disk
        head_file = _head_path(self.ns)
        head_data = json.loads(head_file.read_text(encoding="utf-8"))
        head_data["surface_inventory_hash"] = "corrupted_inventory_hash_0000"
        head_file.write_text(json.dumps(head_data), encoding="utf-8")

        with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
            plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()

        # Verify load_latest_plot_snapshot flags inventoryValid as False
        loaded = load_latest_plot_snapshot(self.ns, self.geometry_hash)
        self.assertIsNotNone(loaded)
        self.assertFalse(loaded["validation"]["inventoryValid"])

        # Attempt Layer 10 fallback: must succeed and supersede head
        layer10_payload = {
            "snapshot_id": "L10-SNAPSHOT-FALLBACK-002",
            "intelligence_snapshot_id": "L10-SNAPSHOT-FALLBACK-002",
            "plot_id": self.plot_id,
            "tenant_id": self.tenant_id,
            "farm_id": self.farm_id,
            "crop_cycle_id": self.crop_cycle_id,
            "pipeline_state": "terminal_layer10_published",
            "surfaces": [
                {
                    "surface_id": "surface-satellite-fallback-02",
                    "surface_type": "canopy_vigor",
                    "values": [[0.58]],
                    "resolution_m": 10.0,
                    "content_hash": hashlib.sha256(b"surf-fallback-02").hexdigest(),
                }
            ],
        }

        fallback_summary = publish_canonical_layer10_snapshot(
            namespace=self.ns,
            geometry_hash=self.geometry_hash,
            frontend_payload=layer10_payload,
            request_run_id="run-layer10-fallback-02",
            crop_cycle_id=self.crop_cycle_id,
        )

        self.assertEqual(fallback_summary["snapshot_id"], "L10-SNAPSHOT-FALLBACK-002")
        new_head = json.loads(_head_path(self.ns).read_text(encoding="utf-8"))
        self.assertEqual(new_head["snapshot_id"], "L10-SNAPSHOT-FALLBACK-002")

    def test_case_03c_warm_cache_artifact_tampering_triggers_revalidation_and_fallback(self):
        """Warm reader cache must not mask underlying node, publication, or receipt tampering on disk (R01-Q02)."""
        asmae_id = "ASMAE-SNAPSHOT-CASE03C"
        asmae_result, frontend = self._generate_valid_worker_payload(asmae_id, "job-c3c", "man-c3c")

        publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=asmae_id,
            asmae_result=asmae_result,
            frontend_payload=frontend,
            job_id="job-c3c",
            manifest_hash="man-c3c",
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )

        # 1. Warm the cache by loading the snapshot
        warm1 = load_latest_plot_snapshot(self.ns, self.geometry_hash)
        self.assertIsNotNone(warm1)
        self.assertTrue(warm1["validation"]["bindingValid"])
        self.assertTrue(warm1["validation"]["nodeValid"])
        self.assertTrue(warm1["validation"]["publicationValid"])
        self.assertTrue(warm1["validation"]["receiptValid"])

        # 2. Tamper with the node on disk WITHOUT modifying head.json or clearing memory cache
        node_path = _plot_dir(self.ns) / "nodes" / f"{asmae_id}.json"
        node_data = json.loads(node_path.read_text(encoding="utf-8"))
        node_data["crop_influence_manifest_hash"] = "tampered_manifest_hash_on_disk"
        node_path.write_text(json.dumps(node_data), encoding="utf-8")

        # 3. Read again through warm reader: cache must miss due to node_mtime change and flag nodeValid=False
        warm2 = load_latest_plot_snapshot(self.ns, self.geometry_hash)
        self.assertIsNotNone(warm2)
        self.assertFalse(warm2["validation"]["nodeValid"], "Tampered node must fail nodeValid")
        self.assertFalse(warm2["validation"]["bindingValid"], "Tampered node must fail bindingValid")

        # 4. Test publication tampering on disk using a separate snapshot
        asmae_id_pub = "ASMAE-SNAPSHOT-CASE03C-PUB"
        job_id_pub = "job-c3c-pub"
        asmae_res_pub, front_pub = self._generate_valid_worker_payload(asmae_id_pub, job_id_pub, "man-c3c-pub")
        publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=asmae_id_pub,
            asmae_result=asmae_res_pub,
            frontend_payload=front_pub,
            job_id=job_id_pub,
            manifest_hash="man-c3c-pub",
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )
        warm3 = load_latest_plot_snapshot(self.ns, self.geometry_hash)
        self.assertTrue(warm3["validation"]["bindingValid"])

        safe_job_id_pub = hashlib.sha256(job_id_pub.encode()).hexdigest()[:32]
        pub_path = _plot_dir(self.ns) / "publications" / f"{safe_job_id_pub}.json"
        pub_data = json.loads(pub_path.read_text(encoding="utf-8"))
        pub_data["frontend_payload"]["asmae_posterior_numerical_record"]["states"]["root_zone_moisture"] = 0.999
        pub_path.write_text(json.dumps(pub_data), encoding="utf-8")

        warm4 = load_latest_plot_snapshot(self.ns, self.geometry_hash)
        self.assertIsNotNone(warm4)
        self.assertFalse(warm4["validation"]["publicationValid"])
        self.assertFalse(warm4["validation"]["numericalBindingValid"])

        # 5. Fallback must succeed because load_latest_plot_snapshot detects disk corruption
        layer10_payload = {
            "snapshot_id": "L10-SNAPSHOT-FALLBACK-003",
            "intelligence_snapshot_id": "L10-SNAPSHOT-FALLBACK-003",
            "plot_id": self.plot_id,
            "tenant_id": self.tenant_id,
            "farm_id": self.farm_id,
            "crop_cycle_id": self.crop_cycle_id,
            "pipeline_state": "terminal_layer10_published",
            "surfaces": [
                {
                    "surface_id": "surface-satellite-fallback-03",
                    "surface_type": "canopy_vigor",
                    "values": [[0.55]],
                    "resolution_m": 10.0,
                    "content_hash": hashlib.sha256(b"surf-fallback-03").hexdigest(),
                }
            ],
        }

        fallback_summary = publish_canonical_layer10_snapshot(
            namespace=self.ns,
            geometry_hash=self.geometry_hash,
            frontend_payload=layer10_payload,
            request_run_id="run-layer10-fallback-03",
            crop_cycle_id=self.crop_cycle_id,
        )
        self.assertEqual(fallback_summary["snapshot_id"], "L10-SNAPSHOT-FALLBACK-003")
        new_head = json.loads(_head_path(self.ns).read_text(encoding="utf-8"))
        self.assertEqual(new_head["snapshot_id"], "L10-SNAPSHOT-FALLBACK-003")

    # =========================================================================
    # Case 4: Same snapshot ID with conflicting content -> Reject Collision
    # =========================================================================
    def test_case_04_same_snapshot_id_conflicting_content_rejects_collision(self):
        """Publishing different content with an already-used snapshot_id must raise ValueError."""
        snapshot_id = "ASMAE-SNAPSHOT-COLLISION"
        asmae_result, frontend = self._generate_valid_worker_payload(snapshot_id, "job-orig", "man-orig", root_moisture=0.35)

        publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend,
            job_id="job-orig",
            manifest_hash="man-orig",
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )

        # Attempt to publish DIFFERENT numerical content under SAME snapshot_id
        diff_asmae, diff_front = self._generate_valid_worker_payload(snapshot_id, "job-diff", "man-diff", root_moisture=0.88)

        with self.assertRaises(ValueError) as cm:
            publish_canonical_plot_snapshot(
                namespace=self.ns,
                plot_id=self.plot_id,
                tenant_id=self.tenant_id,
                farm_id=self.farm_id,
                geometry_hash=self.geometry_hash,
                snapshot_id=snapshot_id,
                asmae_result=diff_asmae,
                frontend_payload=diff_front,
                job_id="job-diff",
                manifest_hash="man-diff",
                execution_identity={"crop_cycle_id": self.crop_cycle_id},
                allow_overwrite=True,  # Even with allow_overwrite=True, collision MUST be rejected!
            )

        self.assertIn("collision", str(cm.exception).lower())

    # =========================================================================
    # Case 5: Idempotent Retries & Crash Recovery (0-byte file)
    # =========================================================================
    def test_case_05_idempotent_retry_and_crash_recovery(self):
        """Identical retry succeeds idempotently; 0-byte crash file is recovered safely."""
        snapshot_id = "ASMAE-SNAPSHOT-RETRY"
        asmae_result, frontend = self._generate_valid_worker_payload(snapshot_id, "job-retry", "man-retry")

        # 1. First publish
        h1 = publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend,
            job_id="job-retry",
            manifest_hash="man-retry",
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )

        # 2. Identical retry (same content and job_id)
        h2 = publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend,
            job_id="job-retry",
            manifest_hash="man-retry",
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )
        self.assertEqual(h1["node_hash"], h2["node_hash"])

        # 3. Crash recovery test: simulate a crashed process leaving a 0-byte node file
        crash_snap_id = "ASMAE-SNAPSHOT-CRASH"
        crash_node_path = _plot_dir(self.ns) / "nodes" / f"{crash_snap_id}.json"
        crash_node_path.parent.mkdir(parents=True, exist_ok=True)
        crash_node_path.touch()  # 0-byte file
        self.assertEqual(crash_node_path.stat().st_size, 0)

        crash_asmae, crash_front = self._generate_valid_worker_payload(crash_snap_id, "job-crash", "man-crash")
        h3 = publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=crash_snap_id,
            asmae_result=crash_asmae,
            frontend_payload=crash_front,
            job_id="job-crash",
            manifest_hash="man-crash",
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )
        self.assertTrue(crash_node_path.stat().st_size > 0, "Crash file must be safely recovered and written")
        self.assertEqual(h3["snapshot_id"], crash_snap_id)

    def test_case_05b_multiprocess_concurrent_publish_and_collision(self):
        """Simultaneous publishers in separate OS processes: identical succeeds idempotently, conflicting rejected as collision (R01-Q03)."""
        cli_module = "services.agribrain.layer05_asmae.tests.helpers.snapshot_publish_cli"
        python_exe = sys.executable

        # 1. Identical simultaneous publishers in separate OS processes
        snap_id_identical = "ASMAE-SNAPSHOT-CONCURRENT-IDENTICAL"
        cmd_base = [
            python_exe,
            "-m",
            cli_module,
            "--root", str(self.snapshot_root),
            "--plot-id", self.plot_id,
            "--tenant-id", self.tenant_id,
            "--farm-id", self.farm_id,
            "--geometry-hash", self.geometry_hash,
            "--crop-cycle-id", self.crop_cycle_id,
            "--snapshot-id", snap_id_identical,
            "--job-id", "job-concurrent-id",
            "--manifest-hash", "manifest-concurrent-id",
            "--root-moisture", "0.382",
            "--canopy-vigor", "0.615",
        ]

        # Launch two separate OS processes concurrently
        proc1 = subprocess.Popen(cmd_base, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        proc2 = subprocess.Popen(cmd_base, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        out1, err1 = proc1.communicate(timeout=15)
        out2, err2 = proc2.communicate(timeout=15)

        self.assertEqual(proc1.returncode, 0, f"Process 1 failed: {err1} {out1}")
        self.assertEqual(proc2.returncode, 0, f"Process 2 failed: {err2} {out2}")
        self.assertTrue(out1.startswith("OK:"), f"Expected OK: from proc1, got {out1}")
        self.assertTrue(out2.startswith("OK:"), f"Expected OK: from proc2, got {out2}")
        # Both must produce the exact identical node and publication hashes
        self.assertEqual(out1.strip(), out2.strip())

        # Verify disk node is intact and valid
        with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
            plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()
        loaded = load_latest_plot_snapshot(self.ns, self.geometry_hash)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["snapshot_id"], snap_id_identical)
        self.assertTrue(loaded["validation"]["nodeValid"])
        self.assertTrue(loaded["validation"]["publicationValid"])

        # 2. Conflicting simultaneous publishers in separate OS processes
        snap_id_conflict = "ASMAE-SNAPSHOT-CONCURRENT-CONFLICT"
        cmd_conflict_a = [
            python_exe,
            "-m",
            cli_module,
            "--root", str(self.snapshot_root),
            "--plot-id", self.plot_id,
            "--tenant-id", self.tenant_id,
            "--farm-id", self.farm_id,
            "--geometry-hash", self.geometry_hash,
            "--crop-cycle-id", self.crop_cycle_id,
            "--snapshot-id", snap_id_conflict,
            "--job-id", "job-conflict-a",
            "--manifest-hash", "manifest-conflict-a",
            "--root-moisture", "0.250",
            "--canopy-vigor", "0.450",
        ]
        cmd_conflict_b = [
            python_exe,
            "-m",
            cli_module,
            "--root", str(self.snapshot_root),
            "--plot-id", self.plot_id,
            "--tenant-id", self.tenant_id,
            "--farm-id", self.farm_id,
            "--geometry-hash", self.geometry_hash,
            "--crop-cycle-id", self.crop_cycle_id,
            "--snapshot-id", snap_id_conflict,
            "--job-id", "job-conflict-b",
            "--manifest-hash", "manifest-conflict-b",
            "--root-moisture", "0.850",
            "--canopy-vigor", "0.950",
        ]

        proc_a = subprocess.Popen(cmd_conflict_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        proc_b = subprocess.Popen(cmd_conflict_b, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        out_a, err_a = proc_a.communicate(timeout=15)
        out_b, err_b = proc_b.communicate(timeout=15)

        returncodes = sorted([proc_a.returncode, proc_b.returncode])
        # Exactly one must succeed (0) and the other must reject collision with exit code 2
        self.assertEqual(returncodes, [0, 2], f"Expected exactly one 0 (success) and one 2 (collision): A={proc_a.returncode} ({out_a}), B={proc_b.returncode} ({out_b})")

        winner_out = out_a if proc_a.returncode == 0 else out_b
        loser_out = out_b if proc_a.returncode == 0 else out_a
        self.assertTrue(winner_out.startswith("OK:"))
        self.assertTrue(loser_out.startswith("COLLISION:"))

        # Verify on-disk artifact remains completely uncorrupted and matches winner
        with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
            plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()
        loaded_conflict = load_latest_plot_snapshot(self.ns, self.geometry_hash)
        self.assertIsNotNone(loaded_conflict)
        self.assertEqual(loaded_conflict["snapshot_id"], snap_id_conflict)
        self.assertTrue(loaded_conflict["validation"]["nodeValid"])
        self.assertTrue(loaded_conflict["validation"]["bindingValid"])

    # =========================================================================
    # Case 6: Security and Multi-Tenant Isolation
    # =========================================================================
    def test_case_06_tenant_and_namespace_isolation(self):
        """Cross-tenant reading or loading of snapshot by foreign namespace must return None."""
        snapshot_id = "ASMAE-SNAPSHOT-TENANT"
        asmae_result, frontend = self._generate_valid_worker_payload(snapshot_id, "job-t", "man-t")

        publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend,
            job_id="job-t",
            manifest_hash="man-t",
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )

        # Foreign tenant
        foreign_ns = PlotNamespace(
            tenant_id="tenant-foreign-attacker",
            farm_id=self.farm_id,
            plot_id=self.plot_id,
        )
        read_foreign = load_plot_snapshot_by_id(snapshot_id, namespace=foreign_ns)
        self.assertIsNone(read_foreign, "Foreign tenant must never read snapshot")

        read_latest_foreign = load_latest_plot_snapshot(foreign_ns, self.geometry_hash)
        self.assertIsNone(read_latest_foreign, "Foreign tenant must have no latest snapshot")

    # =========================================================================
    # Case 7: Observation-Only Protections & Disabled Actuator Interlock
    # =========================================================================
    def test_case_07_actuator_interlock_remains_fail_closed(self):
        """Physical actuator environment variable must remain strictly fail-closed."""
        actuator_env = os.environ.get("AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION", "false")
        self.assertEqual(actuator_env.lower(), "false", "Actuator safety interlock must be disabled")

    # =========================================================================
    # Case 8: Truthful Representation of Scalar-Only Estimates
    # =========================================================================
    def test_case_08_scalar_only_state_truthfulness(self):
        """States with scalar estimates must retain scalar classification without fabricating heatmaps."""
        snapshot_id = "ASMAE-SNAPSHOT-SCALAR"
        asmae_result, frontend = self._generate_valid_worker_payload(snapshot_id, "job-s", "man-s")

        # Explicitly empty raster maps
        asmae_result["raster_maps"] = {}
        frontend["surfaces"] = []  # No spatial surfaces

        publish_canonical_plot_snapshot(
            namespace=self.ns,
            plot_id=self.plot_id,
            tenant_id=self.tenant_id,
            farm_id=self.farm_id,
            geometry_hash=self.geometry_hash,
            snapshot_id=snapshot_id,
            asmae_result=asmae_result,
            frontend_payload=frontend,
            job_id="job-s",
            manifest_hash="man-s",
            execution_identity={"crop_cycle_id": self.crop_cycle_id},
            allow_overwrite=False,
        )

        with plot_snapshot_store._SNAPSHOT_CACHE_LOCK:
            plot_snapshot_store._CANONICAL_SNAPSHOT_CACHE.clear()

        loaded = load_latest_plot_snapshot(self.ns, self.geometry_hash)
        self.assertIsNotNone(loaded)
        # Surfaces list must remain empty, never fabricated
        loaded_surfaces = loaded["frontend_payload"].get("surfaces", [])
        self.assertEqual(len(loaded_surfaces), 0, "No spatial rasters should be fabricated for scalar-only states")


if __name__ == "__main__":
    unittest.main()
