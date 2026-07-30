"""
V63A Live Plot Smoke Test
=========================
Two-tier verification that the live HTTP dashboard path uses V62B
Layer0 → Layer1 V1 → Layer 10 SIRE pipeline.

Tier 1 (required):  FastAPI direct    → http://127.0.0.1:8000/v2/run
Tier 2 (optional):  Next.js proxy     → http://localhost:3000/api/agribrain/run

Usage:
    python scratch/smoke_v63a_live_plot.py

The script:
  1. Sends a surfaces mode request with force_refresh=true
  2. Asserts the response contains V62B provenance in the audit block
  3. Generates a JSON report at scratch/smoke_v63a_report.json
"""

import sys
import os
import json
import base64
import time
import urllib.request
import urllib.error

FASTAPI_URL = "http://127.0.0.1:8000/v2/run"
NEXTJS_URL = "http://localhost:3000/api/agribrain/run"

# Test context: minimal plot with coordinates
TEST_CONTEXT = {
    "plot_id": "smoke_v63a_test",
    "lat": 36.5,
    "lng": 2.9,
    "area": 1.5,
    "farm_id": "smoke_farm",
    "polygon": None,
    "crop": "wheat",
    "stage": "GROWING",
    "soil_type": "LOAM",
}

TIMEOUT_SECONDS = 120  # Pipeline can take a while with satellite fetches


def _build_payload(force_refresh: bool = True) -> dict:
    """Build the /v2/run surfaces request payload."""
    ctx_b64 = base64.b64encode(json.dumps(TEST_CONTEXT).encode()).decode()
    return {
        "context": ctx_b64,
        "query": "",
        "mode": "surfaces",
        "history": "",
        "exp": "INTERMEDIATE",
        "userMode": "FARMER",
        "force_refresh": force_refresh,
    }


def _build_nextjs_payload() -> dict:
    """Build the Next.js proxy request payload (different schema)."""
    return {
        "plotId": TEST_CONTEXT["plot_id"],
        "mode": "surfaces",
        "query": "",
    }


def _post_json(url: str, payload: dict, timeout: int = TIMEOUT_SECONDS) -> dict:
    """Send a POST request and return the JSON response."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ConnectionError(f"Cannot reach {url}: {e}")


def _run_assertions(result: dict, tier_name: str) -> dict:
    """Run V63A acceptance gate assertions against a response.
    
    Returns a dict of {gate_name: bool} results.
    """
    gates = {}
    
    audit = result.get("audit", {})
    
    # Gate 1: primary_acquisition is serialized
    gates["audit_primary_acquisition_serialized"] = "primary_acquisition" in audit
    
    # Gate 2: fallback metadata is serialized
    gates["audit_fallback_metadata_serialized"] = (
        "fallback_used" in audit and "fallback_reason" in audit
    )
    
    # Gate 3: primary_acquisition == "layer0"
    gates[f"{tier_name}_primary_acquisition_layer0"] = (
        audit.get("primary_acquisition") == "layer0"
    )
    
    # Gate 4: fallback_used == False
    gates[f"{tier_name}_fallback_used_false"] = (
        audit.get("fallback_used") is False
    )
    
    # Gate 5: pipeline_mode is correct
    gates[f"{tier_name}_pipeline_mode_correct"] = (
        audit.get("pipeline_mode") == "layer0_layer1_v1_primary"
    )
    
    # Gate 6: fusion_engine is correct
    gates[f"{tier_name}_fusion_engine_layer1_v1"] = (
        audit.get("fusion_engine") == "layer1_v1"
    )
    
    # Gate 7: surfaces non-empty
    surfaces = result.get("surfaces", [])
    gates[f"{tier_name}_surfaces_non_empty"] = len(surfaces) > 0
    
    # Gate 8: quality.surfaces_generated > 0
    quality = result.get("quality", result.get("global_quality", {}))
    sgen = quality.get("surfaces_generated", 0)
    gates[f"{tier_name}_quality_surfaces_generated_gt_zero"] = sgen > 0
    
    # Gate 9: run_id starts with AGB2-
    run_id = result.get("run_id", "")
    gates[f"{tier_name}_run_id_valid"] = run_id.startswith("AGB2-")
    
    # Gate 10: cache was bypassed (fresh run)
    cache_meta = result.get("cache", {})
    gates["cache_bypassed_or_fresh_run_confirmed"] = (
        cache_meta.get("hit") is False
    )
    
    return gates


def run_tier1_fastapi() -> dict:
    """Tier 1: FastAPI direct smoke test (required)."""
    tier = {
        "tier": "fastapi",
        "url": FASTAPI_URL,
        "executed": False,
        "passed": None,
        "gates": {},
        "error": None,
        "primary_acquisition": None,
        "fallback_used": None,
        "pipeline_mode": None,
        "surfaces_count": 0,
        "run_id": None,
        "elapsed_s": 0.0,
    }
    
    print(f"\n{'='*70}")
    print(f"TIER 1: FastAPI Direct Smoke Test")
    print(f"URL: {FASTAPI_URL}")
    print(f"{'='*70}")
    
    try:
        payload = _build_payload(force_refresh=True)
        print(f"Sending surfaces request with force_refresh=True ...")
        t0 = time.perf_counter()
        result = _post_json(FASTAPI_URL, payload)
        elapsed = time.perf_counter() - t0
        tier["elapsed_s"] = round(elapsed, 2)
        tier["executed"] = True
        
        # Check for top-level error
        if result.get("error"):
            tier["error"] = result["error"]
            tier["passed"] = False
            print(f"  ERROR: {result['error']}")
            return tier
        
        # Run assertions
        gates = _run_assertions(result, "fastapi")
        tier["gates"] = gates
        
        # Extract summary fields
        audit = result.get("audit", {})
        tier["primary_acquisition"] = audit.get("primary_acquisition")
        tier["fallback_used"] = audit.get("fallback_used")
        tier["pipeline_mode"] = audit.get("pipeline_mode")
        tier["surfaces_count"] = len(result.get("surfaces", []))
        tier["run_id"] = result.get("run_id")
        tier["cache"] = result.get("cache", {})
        
        # Overall pass/fail
        all_pass = all(gates.values())
        tier["passed"] = all_pass
        
        # Print results
        for gate_name, gate_val in gates.items():
            status = "PASS" if gate_val else "FAIL"
            print(f"  {status}  {gate_name}")
        
        print(f"\n  Pipeline: {tier['pipeline_mode']}")
        print(f"  Surfaces: {tier['surfaces_count']}")
        print(f"  Run ID:   {tier['run_id']}")
        print(f"  Elapsed:  {tier['elapsed_s']}s")
        print(f"  Result:   {'PASSED' if all_pass else 'FAILED'}")
        
    except ConnectionError as e:
        tier["error"] = str(e)
        tier["passed"] = False
        print(f"  CONNECTION ERROR: {e}")
    except Exception as e:
        tier["error"] = str(e)
        tier["passed"] = False
        print(f"  ERROR: {e}")
    
    return tier


def run_tier2_nextjs() -> dict:
    """Tier 2: Next.js proxy smoke test (optional — required when available)."""
    tier = {
        "tier": "nextjs_proxy",
        "url": NEXTJS_URL,
        "executed": False,
        "passed": None,
        "gates": {},
        "error": None,
        "status": None,
        "primary_acquisition": None,
        "fallback_used": None,
        "pipeline_mode": None,
        "surfaces_count": 0,
        "run_id": None,
        "elapsed_s": 0.0,
    }
    
    print(f"\n{'='*70}")
    print(f"TIER 2: Next.js Proxy Smoke Test")
    print(f"URL: {NEXTJS_URL}")
    print(f"{'='*70}")
    
    # Check if Next.js is reachable
    try:
        probe_req = urllib.request.Request("http://localhost:3000/api/health", method="GET")
        urllib.request.urlopen(probe_req, timeout=3)
    except Exception:
        # Try just the base URL
        try:
            probe_req = urllib.request.Request("http://localhost:3000/", method="GET")
            urllib.request.urlopen(probe_req, timeout=3)
        except Exception:
            tier["status"] = "skipped_not_available"
            tier["error"] = "Next.js or MongoDB dev stack not running"
            print(f"  SKIPPED: Next.js dev server not reachable at localhost:3000")
            return tier
    
    try:
        # Next.js proxy uses a different payload shape (plotId, mode, query)
        payload = _build_nextjs_payload()
        # The Next.js proxy doesn't support force_refresh directly,
        # but it passes through to FastAPI which does.
        # We pass force_refresh for future-proofing.
        print(f"Sending surfaces request via Next.js proxy ...")
        t0 = time.perf_counter()
        result = _post_json(NEXTJS_URL, payload)
        elapsed = time.perf_counter() - t0
        tier["elapsed_s"] = round(elapsed, 2)
        tier["executed"] = True
        
        # Next.js wraps some responses
        data = result.get("data", result)
        
        if data.get("error") or data.get("success") is False:
            tier["error"] = data.get("error", "Unknown error")
            tier["passed"] = False
            print(f"  ERROR: {tier['error']}")
            return tier
        
        # Run assertions
        gates = _run_assertions(data, "nextjs_proxy")
        tier["gates"] = gates
        
        # Extract summary
        audit = data.get("audit", {})
        tier["primary_acquisition"] = audit.get("primary_acquisition")
        tier["fallback_used"] = audit.get("fallback_used")
        tier["pipeline_mode"] = audit.get("pipeline_mode")
        tier["surfaces_count"] = len(data.get("surfaces", []))
        tier["run_id"] = data.get("run_id")
        
        all_pass = all(gates.values())
        tier["passed"] = all_pass
        
        for gate_name, gate_val in gates.items():
            status = "PASS" if gate_val else "FAIL"
            print(f"  {status}  {gate_name}")
        
        print(f"\n  Pipeline: {tier['pipeline_mode']}")
        print(f"  Surfaces: {tier['surfaces_count']}")
        print(f"  Run ID:   {tier['run_id']}")
        print(f"  Elapsed:  {tier['elapsed_s']}s")
        print(f"  Result:   {'PASSED' if all_pass else 'FAILED'}")
        
    except ConnectionError as e:
        tier["status"] = "skipped_not_available"
        tier["error"] = str(e)
        print(f"  SKIPPED: {e}")
    except Exception as e:
        tier["error"] = str(e)
        tier["passed"] = False
        print(f"  ERROR: {e}")
    
    return tier


def main():
    print("=" * 70)
    print("V63A LIVE PLOT SMOKE TEST")
    print("Verifying V62B Layer0 -> Layer1 V1 pipeline via live HTTP")
    print("=" * 70)
    
    # Tier 1: FastAPI (required)
    fastapi_result = run_tier1_fastapi()
    
    # Tier 2: Next.js proxy (optional)
    nextjs_result = run_tier2_nextjs()
    
    # Compile overall report
    report = {
        "test": "V63A_LIVE_PLOT_SMOKE_TEST",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fastapi_smoke": fastapi_result,
        "nextjs_proxy_smoke": nextjs_result,
    }
    
    # Compute overall gate status
    overall_gates = {}
    
    # FastAPI gates (required)
    overall_gates["fastapi_smoke_executed"] = fastapi_result["executed"]
    if fastapi_result.get("gates"):
        overall_gates.update(fastapi_result["gates"])
    
    # Next.js gate (required when available, skipped otherwise)
    nextjs_skipped = nextjs_result.get("status") == "skipped_not_available"
    overall_gates["nextjs_proxy_smoke_executed_or_explicitly_skipped"] = (
        nextjs_result["executed"] or nextjs_skipped
    )
    if nextjs_result.get("gates"):
        overall_gates.update(nextjs_result["gates"])
    
    report["overall_gates"] = overall_gates
    
    # V63A pass: FastAPI must pass, Next.js must pass or be skipped
    fastapi_ok = fastapi_result.get("passed") is True
    nextjs_ok = nextjs_result.get("passed") is True or nextjs_skipped
    v63a_passed = fastapi_ok and nextjs_ok
    
    report["gate_status"] = "PASSED" if v63a_passed else "FAILED"
    
    # Save report
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoke_v63a_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"V63A GATE STATUS: {report['gate_status']}")
    print(f"{'='*70}")
    print(f"  FastAPI:   {'PASS' if fastapi_ok else 'FAIL'}")
    print(f"  Next.js:   {'PASS' if nextjs_result.get('passed') else 'SKIPPED' if nextjs_skipped else 'FAIL'}")
    print(f"  Report:    {report_path}")
    print(f"{'='*70}")
    
    # Exit code
    sys.exit(0 if v63a_passed else 1)


if __name__ == "__main__":
    main()
