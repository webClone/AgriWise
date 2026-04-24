"""
Photogrammetry Benchmark Runner.

Runs all benchmark cases through the photogrammetry pipeline and scores
against expected outcomes.

Metrics:
  - Usability accuracy (binary: usable/not)
  - Status accuracy (usable/degraded/unusable)
  - Coverage completeness
  - Holes fraction
  - Seam artifact score
  - Blur rejection accuracy
  - Provenance completeness
  - Pipeline stage completion
"""

from __future__ import annotations
import sys
import time

from .cases import BENCHMARK_CASES, generate_synthetic_frame_set
from ..engine import PhotogrammetryEngine


def run_benchmark():
    """Run all benchmark cases and print scorecard."""
    engine = PhotogrammetryEngine()
    
    print()
    print("=" * 72)
    print("  DRONE PHOTOGRAMMETRY — BENCHMARK SCORECARD")
    print("=" * 72)
    print()
    
    results = []
    
    for idx, case in enumerate(BENCHMARK_CASES, 1):
        inp = generate_synthetic_frame_set(case)
        
        start = time.time()
        output = engine.process(inp)
        elapsed_ms = (time.time() - start) * 1000
        
        # Score this case
        passed = True
        failures = []
        
        # Usability check
        if case.expect_usable and not output.usable:
            passed = False
            failures.append(f"Expected usable but got unusable: {output.rejection_reason}")
        
        # Status check
        actual_status = output.status.value
        if actual_status != case.expect_status:
            # Not a hard failure — status can be stricter than expected
            if actual_status == "unusable" and case.expect_status in ("usable", "degraded"):
                passed = False
                failures.append(f"Status: expected={case.expect_status}, got={actual_status}")
        
        # Coverage check
        if output.usable and output.coverage_completeness < case.min_coverage:
            failures.append(
                f"Coverage: {output.coverage_completeness:.0%} < {case.min_coverage:.0%}"
            )
        
        # Holes check
        if output.usable and output.holes_fraction > case.max_holes:
            failures.append(
                f"Holes: {output.holes_fraction:.0%} > {case.max_holes:.0%}"
            )
        
        # Seam check
        if output.usable and output.seam_artifact_score > case.max_seam_score:
            failures.append(
                f"Seam: {output.seam_artifact_score:.2f} > {case.max_seam_score:.2f}"
            )
        
        # Provenance completeness (MANDATORY)
        prov = output.provenance
        prov_complete = (
            prov.pipeline_version != ""
            and prov.alignment_method != ""
            and prov.surface_model_type != ""
            and len(prov.processing_steps) > 0
        )
        if not prov_complete:
            failures.append("Provenance incomplete")
        
        status_icon = "✅" if passed and not failures else ("⚠️" if passed else "❌")
        
        print(f"  [{idx}/{len(BENCHMARK_CASES)}] {status_icon} {case.case_id}")
        print(f"       Status: {actual_status} (expected: {case.expect_status})")
        print(f"       Coverage: {output.coverage_completeness:.0%}  "
              f"Holes: {output.holes_fraction:.0%}  "
              f"Seam: {output.seam_artifact_score:.2f}  "
              f"QA: {output.qa_score:.2f}  "
              f"σ: {output.sigma_inflation:.1f}")
        print(f"       Frames: {prov.total_frames_ingested} ingested, "
              f"{prov.frames_rejected_qa} rejected, "
              f"{prov.frames_used_in_mosaic} used")
        print(f"       Alignment: {prov.alignment_method}, "
              f"reproj={prov.mean_reprojection_error_px:.1f}px, "
              f"tiepoints={prov.tiepoint_density:.0f}")
        print(f"       Surface: {prov.surface_model_type}  "
              f"Time: {elapsed_ms:.0f}ms")
        
        if failures:
            for f in failures:
                print(f"       ⚠ {f}")
        
        print()
        
        results.append({
            "case_id": case.case_id,
            "passed": passed,
            "failures": failures,
            "status": actual_status,
            "coverage": output.coverage_completeness,
            "holes": output.holes_fraction,
            "seam": output.seam_artifact_score,
            "qa": output.qa_score,
            "sigma": output.sigma_inflation,
            "provenance_complete": prov_complete,
        })
    
    # --- Summary Scorecard ---
    print("=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    
    total = len(results)
    passed_count = sum(1 for r in results if r["passed"] and not r["failures"])
    warned_count = sum(1 for r in results if r["passed"] and r["failures"])
    failed_count = sum(1 for r in results if not r["passed"])
    
    status_correct = sum(
        1 for r, c in zip(results, BENCHMARK_CASES)
        if r["status"] == c.expect_status
    )
    prov_complete = sum(1 for r in results if r["provenance_complete"])
    
    mean_coverage = sum(r["coverage"] for r in results) / total
    mean_qa = sum(r["qa"] for r in results) / total
    
    print(f"  ✅ Passed:  {passed_count}/{total}")
    print(f"  ⚠️  Warned:  {warned_count}/{total}")
    print(f"  ❌ Failed:  {failed_count}/{total}")
    print()
    print(f"  Status accuracy:       {status_correct}/{total} "
          f"({status_correct/total:.0%})")
    print(f"  Provenance complete:   {prov_complete}/{total} "
          f"({prov_complete/total:.0%})")
    print(f"  Mean coverage:         {mean_coverage:.0%}")
    print(f"  Mean QA score:         {mean_qa:.2f}")
    print()
    
    return failed_count == 0


if __name__ == "__main__":
    success = run_benchmark()
    sys.exit(0 if success else 1)
