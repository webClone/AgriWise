"""
Runner for the P8 real-world edge case benchmarks.

Six synthetic-but-realistic scenarios stress-testing V3 pipeline
improvements: multi-scale tiepoints, edge-aware seams, hole clustering,
and resolution-mode awareness.

Usage:
    py -3.13 -m services.agribrain.drone_photogrammetry.benchmark.run_real_benchmark
"""

from __future__ import annotations
import time
import sys

from .cases_real import REAL_CASES, generate_real_case
from ..engine import PhotogrammetryEngine


def run_real_benchmark() -> bool:
    print("========================================================================")
    print("  DRONE PHOTOGRAMMETRY — V3 REAL-WORLD BENCHMARK SCORECARD")
    print("========================================================================\n")
    
    engine = PhotogrammetryEngine()
    
    passed_count = 0
    warned_count = 0
    failed_count = 0
    results = []
    
    for idx, case in enumerate(REAL_CASES, 1):
        inp = generate_real_case(case)
        
        start_ms = time.time() * 1000
        output = engine.process(inp)
        elapsed_ms = int(time.time() * 1000 - start_ms)
        
        # Evaluate pass/warn/fail
        # Hard gate: usability (unusable = fail if we expected usable)
        # Soft gate: exact status match (usable vs degraded)
        status_match = output.status.value == case.expect_status
        usability_match = output.usable == case.expect_usable
        
        if not usability_match:
            # Hard fail: pipeline disagrees on whether result is usable
            status_icon = "❌"
            failed_count += 1
        elif status_match:
            status_icon = "✅"
            passed_count += 1
        else:
            # Usability correct, but exact status differs (usable ↔ degraded)
            status_icon = "⚠️ "
            warned_count += 1
            
        holes = getattr(output, 'holes_fraction', 0.0)
        seam = getattr(output, 'seam_artifact_score', 0.0)
        
        print(f"  [{idx}/{len(REAL_CASES)}] {status_icon} {case.case_id}")
        print(f"       {case.description}")
        print(f"       Status: {output.status.value} (expected: {case.expect_status})")
        print(f"       Coverage: {output.coverage_completeness:.0%}  "
              f"Holes: {holes:.0%}  Seam: {seam:.2f}  "
              f"QA: {output.qa_score:.2f}")
        print(f"       Time: {elapsed_ms}ms\n")
        
        results.append({
            "case_id": case.case_id,
            "status": output.status.value,
            "expected": case.expect_status,
            "pass": status_match,
            "coverage": output.coverage_completeness,
            "holes": holes,
            "seam": seam,
            "qa": output.qa_score,
            "time_ms": elapsed_ms,
        })
        
    print("========================================================================")
    print("  SUMMARY")
    print("========================================================================")
    print(f"  ✅ Passed:  {passed_count}/{len(REAL_CASES)}")
    print(f"  ⚠️  Warned:  {warned_count}/{len(REAL_CASES)}")
    print(f"  ❌ Failed:  {failed_count}/{len(REAL_CASES)}\n")
    
    return failed_count == 0


if __name__ == "__main__":
    success = run_real_benchmark()
    sys.exit(0 if success else 1)
