"""
Satellite RGB V1 Benchmark Runner — satrgb_benchmark_v1

Runs all benchmark cases through the Satellite RGB engine and produces:
  1. Overall scorecard (7 metrics)
  2. Per-slice scorecard (7 slices)
  3. Confusion matrices (density class, phenology, QA usable)
  4. Detailed per-case results

Metrics:
  - Vegetation fraction MAE        (target <= 0.08)
  - Soil fraction MAE              (target <= 0.08)
  - Density class accuracy         (target >= 85%)
  - Phenology stage MAE            (target <= 1.0)
  - QA gating accuracy             (target >= 95%)
  - Anomaly false positive rate    (target <= 10%)
  - Boundary contamination accuracy (target >= 90%)
"""

import sys
import json
import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from layer0.perception.satellite_rgb.benchmark.cases import (
    BENCHMARK_CASES,
    BENCHMARK_VERSION,
    SatRGBBenchmarkCase,
    _generate_pixel_grid,
)
from layer0.perception.satellite_rgb.engine import SatelliteRGBEngine
from layer0.perception.satellite_rgb.schemas import SatelliteRGBEngineInput
from layer0.perception.common.base_types import SatelliteProvider
from layer0.perception.common.benchmark_contract import (
    BenchmarkGateResult, finalize, result_to_dict,
    exit_code_from_result, summarize_failures, validate_case_metadata,
)


# ============================================================================
# Result container
# ============================================================================

class CaseResult:
    """Result for a single benchmark case."""
    def __init__(self, case: SatRGBBenchmarkCase):
        self.case = case
        self.pred_vegetation_fraction: float = 0.0
        self.pred_soil_fraction: float = 0.0
        self.pred_density_class: str = "bare"
        self.pred_phenology_stage: float = 0.0
        self.pred_anomaly_fraction: float = 0.0
        self.pred_boundary_score: float = 0.0
        self.pred_qa_score: float = 0.0
        self.pred_qa_usable: bool = True
        self.pred_reliability_weight: float = 1.0
        self.pred_sigma_inflation: float = 1.0
        self.n_packets: int = 0
        self.error: Optional[str] = None
        self.elapsed_ms: float = 0.0

    @property
    def veg_error(self) -> float:
        return abs(self.pred_vegetation_fraction - self.case.gt_vegetation_fraction)

    @property
    def soil_error(self) -> float:
        return abs(self.pred_soil_fraction - self.case.gt_soil_fraction)

    @property
    def density_correct(self) -> bool:
        return self.pred_density_class == self.case.gt_density_class

    @property
    def phenology_error(self) -> float:
        return abs(self.pred_phenology_stage - self.case.gt_phenology_stage)

    @property
    def qa_correct(self) -> bool:
        """QA gating accuracy: usable/unusable decision matches ground truth."""
        return self.pred_qa_usable == self.case.gt_qa_usable

    @property
    def anomaly_fp(self) -> bool:
        """Anomaly FP: anomaly detected on a case where none expected."""
        return not self.case.gt_anomaly_expected and self.pred_anomaly_fraction > 0.10

    @property
    def boundary_correct(self) -> bool:
        """Boundary detection: contamination proportional to plot size.
        
        Small plots (< 20px) have high boundary fraction by geometry.
        Large plots (> 40px) have low boundary fraction.
        Expected: contaminated cases should have boundary_score > 0.30,
        clean cases should have boundary_score <= 0.30.
        """
        if self.case.gt_boundary_contamination:
            return self.pred_boundary_score > 0.30
        else:
            return self.pred_boundary_score <= 0.30


# ============================================================================
# Runner
# ============================================================================

def run_benchmark(verbose: bool = True) -> List[CaseResult]:
    """Run all benchmark cases and return results."""
    engine = SatelliteRGBEngine()
    results = []

    total_start = time.time()

    if verbose:
        print(f"\n{'=' * 72}")
        print(f"  Satellite RGB V1 Benchmark — {BENCHMARK_VERSION}")
        print(f"  Running {len(BENCHMARK_CASES)} cases...")
        print(f"{'=' * 72}\n")

    # Validate case metadata: reject critical + soft_fail combination
    for case in BENCHMARK_CASES:
        validate_case_metadata(case.case_id, case.critical_case, case.allowed_soft_fail)

    for i, case in enumerate(BENCHMARK_CASES):
        t0 = time.time()
        result = CaseResult(case)

        try:
            pixels = _generate_pixel_grid(case)
            engine_input = SatelliteRGBEngineInput(
                plot_id=f"bench_{case.case_id}",
                timestamp=datetime(2026, 4, 15),
                bbox=(-1.5, 34.0, -1.49, 34.01),
                rgb_image_ref=f"test://bench_{case.case_id}",
                plot_polygon="POLYGON((-1.5 34.0, -1.49 34.0, -1.49 34.01, -1.5 34.01, -1.5 34.0))",
                crs_or_georef="EPSG:4326",
                ground_resolution_m=case.ground_resolution_m,
                image_width=case.image_width,
                image_height=case.image_height,
                provider=SatelliteProvider.SENTINEL2,
                cloud_estimate=case.cloud_estimate,
                haze_score=case.haze_score,
                recentness_days=case.recentness_days,
                plot_area_ha=case.plot_area_ha,
                sun_angle=case.sun_angle,
                image_content_hash=f"bench_{case.case_id}_hash",
                synthetic_pixels=pixels,
            )

            output = engine.process_full(engine_input)
            if output is None:
                result.pred_qa_usable = False
                result.error = "process_full returned None"
            else:
                eng_out, packets = output
                result.pred_vegetation_fraction = eng_out.vegetation_fraction
                result.pred_soil_fraction = eng_out.bare_soil_fraction
                result.pred_anomaly_fraction = eng_out.anomaly_fraction
                result.pred_phenology_stage = eng_out.coarse_phenology_stage
                result.pred_boundary_score = eng_out.boundary_contamination_score
                result.pred_qa_score = eng_out.qa_score
                result.pred_reliability_weight = eng_out.reliability_weight
                result.pred_sigma_inflation = eng_out.sigma_inflation
                result.n_packets = len(packets)

                # Use the engine's actual density classification
                result.pred_density_class = eng_out.canopy_density_class

                # QA usable: if engine returned packets (or output with reasonable qa)
                result.pred_qa_usable = eng_out.qa_score >= 0.30 and len(packets) > 0

        except Exception as e:
            result.error = str(e)

        result.elapsed_ms = (time.time() - t0) * 1000
        results.append(result)

        if verbose:
            ok = "PASS" if not result.error else f"FAIL ({result.error})"
            print(f"  [{i+1:2d}/{len(BENCHMARK_CASES)}] {ok} {case.case_id}")

    total_elapsed = (time.time() - total_start) * 1000

    if verbose:
        _print_scorecard(results, total_elapsed)

    # --- Compute gate result (same population/thresholds as scorecard) ---
    gate_result = _compute_gate_result(results)

    # Save results with gate contract
    _save_results(results, gate_result)

    return results, gate_result


# ============================================================================
# Gate result computation (single source of truth for thresholds)
# ============================================================================

# These thresholds are used for BOTH the printed scorecard and the gate logic.
# If the scorecard prints [FAIL], the gate MUST also fail.
THRESHOLDS = {
    "veg_mae": 0.08,
    "soil_mae": 0.08,
    "density_acc": 85.0,
    "pheno_mae": 1.0,
    "qa_acc": 95.0,
    "anomaly_fp_rate": 10.0,
    "boundary_acc": 90.0,
}


def _compute_gate_result(results: List[CaseResult]) -> BenchmarkGateResult:
    """Compute aggregate metrics and gate result.

    Uses ALL gt_qa_usable cases for structural metrics (same population
    as the printed scorecard). If the scorecard says [FAIL], gate says FAIL.
    """
    structural = [r for r in results if r.case.gt_qa_usable]
    all_cases = results

    veg_mae = sum(r.veg_error for r in structural) / max(len(structural), 1)
    soil_mae = sum(r.soil_error for r in structural) / max(len(structural), 1)
    density_acc = sum(1 for r in structural if r.density_correct) / max(len(structural), 1) * 100
    pheno_mae = sum(r.phenology_error for r in structural) / max(len(structural), 1)
    qa_acc = sum(1 for r in all_cases if r.qa_correct) / max(len(all_cases), 1) * 100

    non_anomaly = [r for r in structural if not r.case.gt_anomaly_expected]
    anomaly_fps = sum(1 for r in non_anomaly if r.anomaly_fp)
    anomaly_fp_rate = anomaly_fps / max(len(non_anomaly), 1) * 100

    boundary_acc = sum(1 for r in all_cases if r.boundary_correct) / max(len(all_cases), 1) * 100

    # Evaluate each metric against its threshold
    gate = BenchmarkGateResult(engine="satellite_rgb")
    scorecard_metrics = {}

    for name, value, threshold, higher_better in [
        ("veg_mae", veg_mae, THRESHOLDS["veg_mae"], False),
        ("soil_mae", soil_mae, THRESHOLDS["soil_mae"], False),
        ("density_acc", density_acc, THRESHOLDS["density_acc"], True),
        ("pheno_mae", pheno_mae, THRESHOLDS["pheno_mae"], False),
        ("qa_acc", qa_acc, THRESHOLDS["qa_acc"], True),
        ("anomaly_fp_rate", anomaly_fp_rate, THRESHOLDS["anomaly_fp_rate"], False),
        ("boundary_acc", boundary_acc, THRESHOLDS["boundary_acc"], True),
    ]:
        passed = (value >= threshold) if higher_better else (value <= threshold)
        scorecard_metrics[name] = {"value": round(value, 4), "threshold": threshold, "passed": passed}
        if not passed:
            gate.aggregate_failures += 1
            gate.failing_metrics.append(name)

    gate.scorecard = scorecard_metrics

    # Evaluate each case
    for r in results:
        c = r.case
        veg_ok = r.veg_error <= 0.12
        soil_ok = r.soil_error <= 0.12
        den_ok = r.density_correct
        phen_ok = r.phenology_error <= 1.5
        qa_ok = r.qa_correct
        bnd_ok = r.boundary_correct
        anom_ok = not r.anomaly_fp
        all_ok = veg_ok and soil_ok and den_ok and phen_ok and qa_ok and bnd_ok and anom_ok

        case_entry = {
            "case_id": c.case_id,
            "passed": all_ok,
            "critical": c.critical_case,
            "soft_fail": c.allowed_soft_fail,
        }
        gate.case_results.append(case_entry)

        if not all_ok:
            if c.allowed_soft_fail:
                gate.soft_failures += 1
            elif c.critical_case:
                gate.critical_failures += 1
                gate.failing_cases.append(c.case_id)

    return finalize(gate)


# ============================================================================
# Scorecard printing
# ============================================================================

def _print_scorecard(results: List[CaseResult], total_elapsed_ms: float) -> None:
    """Print the full benchmark scorecard.

    Uses the exact same population and thresholds as _compute_gate_result.
    """
    sep = "-" * 72
    structural = [r for r in results if r.case.gt_qa_usable]
    all_cases = results

    # Compute metrics (same formulas as _compute_gate_result)
    veg_mae = sum(r.veg_error for r in structural) / max(len(structural), 1)
    soil_mae = sum(r.soil_error for r in structural) / max(len(structural), 1)
    density_correct = sum(1 for r in structural if r.density_correct)
    density_acc = density_correct / max(len(structural), 1) * 100
    pheno_mae = sum(r.phenology_error for r in structural) / max(len(structural), 1)
    qa_correct = sum(1 for r in all_cases if r.qa_correct)
    qa_acc = qa_correct / max(len(all_cases), 1) * 100
    non_anomaly = [r for r in structural if not r.case.gt_anomaly_expected]
    anomaly_fps = sum(1 for r in non_anomaly if r.anomaly_fp)
    anomaly_fp_rate = anomaly_fps / max(len(non_anomaly), 1) * 100
    boundary_correct_n = sum(1 for r in all_cases if r.boundary_correct)
    boundary_acc = boundary_correct_n / max(len(all_cases), 1) * 100

    T = THRESHOLDS
    print(f"\n{'=' * 72}")
    print(f"  OVERALL SCORECARD -- {BENCHMARK_VERSION}")
    print(f"{'=' * 72}")
    print(f"  Total cases:             {len(all_cases)}")
    print(f"  Structural cases:        {len(structural)} (gt_qa_usable=True)")
    print(f"")
    print(f"  Veg fraction MAE:        {veg_mae:.3f}  {'[PASS]' if veg_mae <= T['veg_mae'] else '[FAIL]'} (target <= {T['veg_mae']})")
    print(f"  Soil fraction MAE:       {soil_mae:.3f}  {'[PASS]' if soil_mae <= T['soil_mae'] else '[FAIL]'} (target <= {T['soil_mae']})")
    print(f"  Density class accuracy:  {density_acc:.1f}%  {'[PASS]' if density_acc >= T['density_acc'] else '[FAIL]'} (target >= {T['density_acc']}%)")
    print(f"  Phenology stage MAE:     {pheno_mae:.2f}  {'[PASS]' if pheno_mae <= T['pheno_mae'] else '[FAIL]'} (target <= {T['pheno_mae']})")
    print(f"  QA gating accuracy:      {qa_acc:.1f}%  {'[PASS]' if qa_acc >= T['qa_acc'] else '[FAIL]'} (target >= {T['qa_acc']}%)")
    print(f"  Anomaly FP rate:         {anomaly_fp_rate:.1f}%  {'[PASS]' if anomaly_fp_rate <= T['anomaly_fp_rate'] else '[FAIL]'} (target <= {T['anomaly_fp_rate']}%)")
    print(f"  Boundary accuracy:       {boundary_acc:.1f}%  {'[PASS]' if boundary_acc >= T['boundary_acc'] else '[FAIL]'} (target >= {T['boundary_acc']}%)")

    # --- Per-slice scorecard ---
    print(f"\n{sep}")
    print(f"  PER-SLICE SCORECARD")
    print(f"{sep}")

    slices = defaultdict(list)
    for r in results:
        slices[r.case.slice_name].append(r)

    for slice_name, slice_results in sorted(slices.items()):
        s_structural = [r for r in slice_results if r.case.gt_qa_usable]
        n = len(slice_results)
        if s_structural:
            s_veg = sum(r.veg_error for r in s_structural) / len(s_structural)
            s_soil = sum(r.soil_error for r in s_structural) / len(s_structural)
            s_dens = sum(1 for r in s_structural if r.density_correct)
            s_pheno = sum(r.phenology_error for r in s_structural) / len(s_structural)
            print(f"    {slice_name:25s} n={n:2d}  veg_mae={s_veg:.3f}  "
                  f"soil_mae={s_soil:.3f}  density={s_dens}/{len(s_structural)}  "
                  f"pheno_mae={s_pheno:.2f}")
        else:
            s_qa = sum(1 for r in slice_results if r.qa_correct)
            print(f"    {slice_name:25s} n={n:2d}  qa={s_qa}/{n}")

    # --- Detailed results ---
    print(f"\n{sep}")
    print(f"  DETAILED RESULTS")
    print(f"  {'Case ID':30s} {'Slice':18s} {'Veg':>6s} {'Soil':>6s} "
          f"{'Den':>6s} {'Phen':>5s} {'QA':>4s} {'Anom':>5s} {'Bnd':>4s} OK?")
    print(f"  {'-' * 30} {'-' * 18} {'-' * 6} {'-' * 6} "
          f"{'-' * 6} {'-' * 5} {'-' * 4} {'-' * 5} {'-' * 4} ---")

    for r in results:
        c = r.case
        veg_ok = r.veg_error <= 0.12
        soil_ok = r.soil_error <= 0.12
        den_ok = r.density_correct
        phen_ok = r.phenology_error <= 1.5
        qa_ok = r.qa_correct
        bnd_ok = r.boundary_correct
        anom_ok = not r.anomaly_fp

        all_ok = veg_ok and soil_ok and den_ok and phen_ok and qa_ok and bnd_ok and anom_ok
        ok_sym = "[PASS]" if all_ok else "[FAIL]"

        veg_str = f"{r.pred_vegetation_fraction:.2f}" if c.gt_qa_usable else "-"
        soil_str = f"{r.pred_soil_fraction:.2f}" if c.gt_qa_usable else "-"
        den_str = r.pred_density_class[:4] if c.gt_qa_usable else "-"
        phen_str = f"{r.pred_phenology_stage:.1f}" if c.gt_qa_usable else "-"
        qa_str = "U" if r.pred_qa_usable else "X"
        anom_str = f"{r.pred_anomaly_fraction:.2f}" if c.gt_qa_usable else "-"
        bnd_str = f"{r.pred_boundary_score:.2f}" if True else "-"

        print(f"  {c.case_id:30s} {c.slice_name:18s} {veg_str:>6s} {soil_str:>6s} "
              f"{den_str:>6s} {phen_str:>5s} {qa_str:>4s} {anom_str:>5s} {bnd_str:>4s} {ok_sym}")

    # --- Density confusion table ---
    print(f"\n{sep}")
    print(f"  DENSITY CLASS CONFUSION (rows=GT, cols=Pred)")
    density_classes = ["bare", "sparse", "moderate", "dense"]
    density_matrix = defaultdict(lambda: defaultdict(int))
    for r in structural:
        density_matrix[r.case.gt_density_class][r.pred_density_class] += 1

    print(f"  {'':18s} {'bare':>8s} {'sparse':>8s} {'moderate':>10s} {'dense':>8s}")
    for gt in density_classes:
        row = "  " + f"{gt:18s}"
        for pred in density_classes:
            row += f" {density_matrix[gt][pred]:>8d}"
        print(row)

    # --- Phenology confusion (binned) ---
    print(f"\n{sep}")
    print(f"  PHENOLOGY STAGE (GT vs Pred, structural cases)")
    pheno_bins = ["dormant(0)", "early(0.5)", "veg(1.5)", "flower(2)", "ripen(3)", "senes(3.5+)"]
    def _bin_pheno(val):
        if val < 0.25: return 0
        elif val < 1.0: return 1
        elif val < 1.75: return 2
        elif val < 2.5: return 3
        elif val < 3.25: return 4
        else: return 5

    pheno_matrix = defaultdict(lambda: defaultdict(int))
    for r in structural:
        gt_bin = _bin_pheno(r.case.gt_phenology_stage)
        pred_bin = _bin_pheno(r.pred_phenology_stage)
        pheno_matrix[gt_bin][pred_bin] += 1

    header = "  " + f"{'':14s}"
    for j, name in enumerate(pheno_bins):
        header += f" {name:>10s}"
    print(header)
    for i, name in enumerate(pheno_bins):
        row = "  " + f"{name:14s}"
        for j in range(len(pheno_bins)):
            row += f" {pheno_matrix[i][j]:>10d}"
        print(row)

    # --- QA confusion ---
    print(f"\n{sep}")
    print(f"  QA USABLE CONFUSION (rows=GT, cols=Pred)")
    qa_matrix = defaultdict(lambda: defaultdict(int))
    for r in all_cases:
        gt_label = "usable" if r.case.gt_qa_usable else "unusable"
        pred_label = "usable" if r.pred_qa_usable else "unusable"
        qa_matrix[gt_label][pred_label] += 1

    print(f"  {'':12s} {'usable':>8s} {'unusable':>10s}")
    for gt in ["usable", "unusable"]:
        print(f"  {gt:12s} {qa_matrix[gt]['usable']:>8d} {qa_matrix[gt]['unusable']:>10d}")

    # --- Timing ---
    print(f"\n{'=' * 72}")
    avg = total_elapsed_ms / max(len(results), 1)
    print(f"  Total time: {total_elapsed_ms:.0f}ms  Avg per case: {avg:.1f}ms")
    print(f"{'=' * 72}")


def _save_results(results: List[CaseResult], gate_result: BenchmarkGateResult) -> None:
    """Save benchmark results and gate contract to JSON."""
    out_dir = os.path.dirname(os.path.abspath(__file__))

    # Save detailed results with embedded gate contract
    out_path = os.path.join(out_dir, "benchmark_results.json")
    gate_dict = result_to_dict(gate_result)

    data = {
        "version": BENCHMARK_VERSION,
        "timestamp": datetime.now().isoformat(),
        "n_cases": len(results),
        "gate_result": gate_dict,
        "cases": [],
    }

    for r in results:
        data["cases"].append({
            "case_id": r.case.case_id,
            "slice": r.case.slice_name,
            "gt_veg": r.case.gt_vegetation_fraction,
            "pred_veg": round(r.pred_vegetation_fraction, 4),
            "gt_soil": r.case.gt_soil_fraction,
            "pred_soil": round(r.pred_soil_fraction, 4),
            "gt_density": r.case.gt_density_class,
            "pred_density": r.pred_density_class,
            "gt_pheno": r.case.gt_phenology_stage,
            "pred_pheno": round(r.pred_phenology_stage, 2),
            "gt_qa_usable": r.case.gt_qa_usable,
            "pred_qa_usable": r.pred_qa_usable,
            "qa_score": round(r.pred_qa_score, 3),
            "anomaly_fraction": round(r.pred_anomaly_fraction, 4),
            "boundary_score": round(r.pred_boundary_score, 4),
            "n_packets": r.n_packets,
            "elapsed_ms": round(r.elapsed_ms, 1),
            "error": r.error,
        })

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  Results saved to: {out_path}")

    # Save standalone gate artifact
    gate_path = os.path.join(out_dir, "benchmark_gate_result.json")
    with open(gate_path, "w") as f:
        json.dump(gate_dict, f, indent=2)
    print(f"  Gate artifact saved to: {gate_path}")


# ============================================================================
# CLI entry point
# ============================================================================

if __name__ == "__main__":
    results, gate_result = run_benchmark(verbose=True)
    print(f"\n{summarize_failures(gate_result)}")
    sys.exit(exit_code_from_result(gate_result))
