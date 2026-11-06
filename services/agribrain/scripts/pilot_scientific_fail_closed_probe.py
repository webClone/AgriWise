#!/usr/bin/env python3
"""Read-only Plot A scientific prescription fail-closed baseline.

Does not execute /v2/run, mutate a plot, create a publication, or ingest data.
Can fetch an existing exact snapshot from the owner-authenticated Next.js GET
route; uses an ALREADY CAPTURED /api/agribrain/run response to inspect the
actual L8 prescription authorization decision.

Usage (from repository root, Python 3.10+):
  python services/agribrain/scripts/pilot_scientific_fail_closed_probe.py --self-test
  python services/agribrain/scripts/pilot_scientific_fail_closed_probe.py \
      --snapshot-json path/to/snapshot.json --run-json path/to/existing-run.json \
      --output path/to/pilot-baseline-receipt.json

To fetch the snapshot live from localhost, set environment variable
PILOT_SESSION_COOKIE to a session Cookie header for the logged-in plot owner,
then add --live-snapshot. Never paste your cookie into output or source control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PLOT_ID = "6ab14f59ad442f274c3f2a62"
SNAPSHOT_ID = "ASMAE-SNAPSHOT-06d689425502dc902afcc88215c7a123"
BASE_SHA = "6edd3721c0defa7eed94b44cf96601ba59a49696"
VALIDATION_FLAGS = (
    "nodeValid", "publicationValid", "receiptValid", "inventoryValid",
    "temporalBindingValid", "bindingValid", "lineageValid", "schemaValid",
    "contractValid", "publicationStatusValid",
)
HEX_HASH = re.compile(r"^(?:[a-fA-F0-9]{64}|sha256:[a-fA-F0-9]{64})$")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def inspect_observation_only_runtime():
    """Local-process safety preflight; not a claim about other deployments."""
    setting = os.getenv("AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION", "").strip().lower()
    disabled = setting in ("", "false", "0", "off", "no")
    return {
        "status": "PASS" if disabled else "FAIL",
        "reason": "signed_irrigation_disabled" if disabled else "signed_irrigation_not_disabled",
        "local_process_flag_checked": True,
        "other_processes_verified": False,
    }


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def unwrap_response(source):
    if isinstance(source, dict) and isinstance(source.get("data"), dict):
        return source["data"]
    return source


def fetch_live_snapshot(base: str, plot_id: str, snapshot_id: str, cookie: str):
    """GET only, from an explicitly restricted loopback origin. Never submit a run."""
    if base not in ("http://localhost:3000", "http://127.0.0.1:3000"):
        raise ValueError("Live snapshot fetch only allows localhost:3000")
    if not cookie or "\r" in cookie or "\n" in cookie:
        raise ValueError("Set PILOT_SESSION_COOKIE to the owner's valid session Cookie header")
    target = base + "/api/agribrain/surfaces/latest?" + urlencode({
        "plotId": plot_id, "snapshotId": snapshot_id,
    })
    request = Request(target, method="GET", headers={
        "Cookie": cookie,
        "Accept": "application/json",
        "Cache-Control": "no-cache",
    })
    try:
        with urlopen(request, timeout=25) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            payload = {"reason": "non_json_error_response"}
        return exc.code, payload
    except URLError as exc:
        return 0, {"reason": "localhost_unreachable", "error_type": type(exc.reason).__name__}


def valid_clock(value):
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        normalized = value.strip().replace("Z", "+00:00")
        stamp = datetime.fromisoformat(normalized)
        return stamp.tzinfo is not None and stamp.utcoffset() is not None
    except (ValueError, TypeError, OverflowError):
        return False


def inspect_snapshot(payload, plot_id, snapshot_id, http_status=None):
    raw = unwrap_response(payload)
    if not isinstance(raw, dict):
        return {"status": "INVALID", "reason": "snapshot_response_not_object"}
    validation = raw.get("validation") or {}
    receipt_hash = (
        raw.get("canonical_publication_receipt_hash")
        or raw.get("publication_receipt_hash")
        or raw.get("receiptHash")
    )
    cutoff = raw.get("evidence_cutoff_at") or raw.get("evidenceCutoffAt")
    actual_id = (
        raw.get("snapshot_id") or raw.get("snapshotId")
        or raw.get("intelligence_snapshot_id")
    )
    actual_plot = raw.get("plot_id") or raw.get("plotId")
    all_flags = all(validation.get(name) is True for name in VALIDATION_FLAGS)
    checks = {
        "http_200_if_live": http_status is None or http_status == 200,
        "exact_snapshot_id": actual_id == snapshot_id,
        "correct_plot_id": actual_plot == plot_id,
        "published_available": raw.get("available") is not False,
        "validation_10_of_10": all_flags,
        "receipt_hash_format": isinstance(receipt_hash, str) and bool(HEX_HASH.fullmatch(receipt_hash)),
        "evidence_cutoff_recorded": valid_clock(cutoff),
    }
    # NOTE: checking validation flags is NOT independent cryptographic
    # recomputation; the trusted server route performed that verification.
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "http_status": http_status,
        "snapshot_id": actual_id,
        "plot_id": actual_plot,
        "publication_receipt_hash": receipt_hash,
        "evidence_cutoff_at": cutoff,
        "validation": {name: validation.get(name) is True for name in VALIDATION_FLAGS},
        "server_verified_hashes_not_recomputed_locally": True,
    }


def inspect_run(payload, plot_id):
    """Classify the *real recorded* run boundary, not a fabricated RunArtifact."""
    raw = unwrap_response(payload)
    if not isinstance(raw, dict):
        return {"status": "INVALID", "reason": "run_response_not_object"}
    auth = ((raw.get("audit") or {}).get("prescription_authorization") or {})
    public_auth = raw.get("prescription_authorization") or {}
    auth_status = auth.get("status") or public_auth.get("status")
    recommendations = raw.get("recommendations")
    if isinstance(recommendations, list):
        count = len(recommendations)
    else:
        count = None
    actual_plot = raw.get("plot_id") or raw.get("plotId")
    run_id = raw.get("run_id") or raw.get("runId")
    decision = {
        "plot_matches": actual_plot == plot_id,
        "authorization_status": auth_status,
        "authorization_reason": auth.get("reason") or public_auth.get("reason"),
        "recommendation_count": count,
        "envelope_hash_present": bool(auth.get("envelope_hash") or public_auth.get("envelope_hash")),
        "run_id": run_id,
        "prescription_gate_status": (
            ((raw.get("diagnostic_integration") or {}).get("prescription_gate") or {}).get("status")
        ),
    }
    if actual_plot != plot_id or not run_id:
        decision["status"] = "INVALID"
        decision["reason"] = "wrong_plot_or_missing_run_identity"
    elif auth_status == "BLOCKED" and count == 0 and not decision["envelope_hash_present"]:
        decision["status"] = "PASS_FAIL_CLOSED"
    elif auth_status == "AUTHORIZED":
        decision["status"] = "NOT_FAIL_CLOSED"
        decision["reason"] = "authorization_present_requires_separate_positive_pilot_audit"
    else:
        decision["status"] = "INCONCLUSIVE"
        decision["reason"] = "authorization_or_recommendations_missing_or_inconsistent"
    return decision


def inspect_source_boundary():
    """Native Python oracle on the existing L8 public serializer; no real run."""
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "services" / "agribrain"))
    from types import SimpleNamespace
    from services.agribrain.orchestrator_v2.schema import LayerStatus
    from services.agribrain.orchestrator_v2.run_schema import (
        _validated_authorization, _extract_recommendations,
    )
    artifact = SimpleNamespace(
        layer_8=SimpleNamespace(
            status=LayerStatus.OK,
            output=SimpleNamespace(run_id="probe-unpublished", authorization_envelope=None),
        ),
    )
    authorization, reason = _validated_authorization(artifact)
    recommendations = _extract_recommendations(artifact, authorization)
    passed = (
        authorization is None
        and "authorization envelope is missing" in str(reason).lower()
        and recommendations == []
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "source_level_only": True,
        "reason": reason,
        "recommendations": recommendations,
    }


def run_probe(args):
    report = {
        "schema_version": "akaloris_scientific_pilot_fail_closed_baseline_v1",
        "measured_at": utc_now(),
        "expected_base": BASE_SHA,
        "plot_id": args.plot_id,
        "expected_snapshot_id": args.snapshot_id,
        "non_invasive": True,
        "executed_new_orchestrator_run": False,
        "observation_only_runtime": inspect_observation_only_runtime(),
        "snapshot": {"status": "NOT_RUN"},
        "source_boundary": {"status": "NOT_RUN"},
        "run_boundary": {"status": "NOT_RUN"},
        "qualifications": {
            "published_snapshot_read_only": False,
            "recorded_plot_run_fail_closed": False,
            "new_live_orchestrator_run_executed": False,
            "published_snapshot_linked_to_run": False,
            "positive_prescription_pilot": False,
        },
    }
    if report["observation_only_runtime"]["status"] != "PASS":
        # Do not even fetch a live snapshot with signed irrigation enabled
        # in this process. The operator must disable L3 first.
        report["gate_status"] = "FAIL_SIGNED_IRRIGATION_NOT_DISABLED"
        return report
    if args.self_test:
        try:
            report["source_boundary"] = inspect_source_boundary()
        except Exception as exc:
            report["source_boundary"] = {
                "status": "ERROR", "error_type": type(exc).__name__, "details": str(exc)[:220],
            }
    if args.snapshot_json:
        report["snapshot"] = inspect_snapshot(
            read_json(args.snapshot_json), args.plot_id, args.snapshot_id,
        )
    if args.live_snapshot:
        http_status, body = fetch_live_snapshot(
            args.origin, args.plot_id, args.snapshot_id,
            os.getenv("PILOT_SESSION_COOKIE", ""),
        )
        report["snapshot"] = inspect_snapshot(
            body, args.plot_id, args.snapshot_id, http_status=http_status,
        )
        report["snapshot"]["read_source"] = "authenticated_loopback_exact_snapshot_GET"
    if args.run_json:
        report["run_boundary"] = inspect_run(read_json(args.run_json), args.plot_id)
        report["run_boundary"]["read_source"] = "previously_captured_real_run_response"
    report["qualifications"]["published_snapshot_read_only"] = (
        report["snapshot"]["status"] == "PASS"
    )
    report["qualifications"]["recorded_plot_run_fail_closed"] = (
        report["run_boundary"]["status"] == "PASS_FAIL_CLOSED"
        and report["snapshot"]["status"] == "PASS"
    )
    report["gate_status"] = (
        "PASS_READ_ONLY_EXISTING_RUN"
        if report["qualifications"]["recorded_plot_run_fail_closed"]
        else "FAIL"
        if any(x.get("status") in ("FAIL", "INVALID", "ERROR")
               for x in (report["snapshot"], report["run_boundary"], report["source_boundary"]))
        else "INCONCLUSIVE_NEEDS_EXISTING_RUN_RESPONSE"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plot-id", default=PLOT_ID)
    parser.add_argument("--snapshot-id", default=SNAPSHOT_ID)
    parser.add_argument("--snapshot-json", type=str, help="Previously captured read-only snapshot JSON")
    parser.add_argument("--live-snapshot", action="store_true",
                        help="Authenticated local GET only, using PILOT_SESSION_COOKIE")
    parser.add_argument("--run-json", type=str,
                        help="ALREADY CAPTURED /api/agribrain/run response; never executes run")
    parser.add_argument("--origin", default="http://localhost:3000")
    parser.add_argument("--self-test", action="store_true",
                        help="Call actual Python serializer authorization gate with in-memory no-envelope fixture")
    parser.add_argument("--output", type=str,
                        help="Local JSON receipt file; never commit plot/account secrets")
    args = parser.parse_args()
    if args.snapshot_json and args.live_snapshot:
        parser.error("Choose --snapshot-json OR --live-snapshot, not both")
    report = run_probe(args)
    output = json.dumps(report, indent=2, sort_keys=True)
    print(output)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    return 0 if report["gate_status"] in ("PASS_READ_ONLY_EXISTING_RUN",) else 2


if __name__ == "__main__":
    raise SystemExit(main())
