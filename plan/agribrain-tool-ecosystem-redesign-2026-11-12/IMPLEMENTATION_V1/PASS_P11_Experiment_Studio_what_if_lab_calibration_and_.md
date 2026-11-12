# P11 — Experiment Studio what if lab calibration and sandboxed scientific comparisons
**Status:** NOT STARTED · **Prerequisites:** P03,P04,P07 (map P06 available) · **Primary agents:** A4+A2+A7 · **Independent verification:** A7 + A6 / A4  
**Proposed code branch:** `feat/plot-workspace-p11-experiment-studio` (not created).
## Product scope and safety boundary
Create a unified interactive experimentation environment on top of AgriBrain: weather/water/nutrient hypotheses, sensitivity, calibration, multi-source evaluation and controlled field protocol design. Scenarios remain isolated from immutable published scientific state and real physical operations.
## Source targets
- `services/agribrain/layer9_interface/engines/what_if_sandbox.py`
- `services/agribrain/mesia/experiments/experiment_runner.py`
- `services/agribrain/world_model/contracts.py`
- `src/app/api/agribrain/sandbox/route.ts`
- `src/components/farm/intelligence/EnginePipelinePanel.tsx`
- `src/components/farm/intelligence/MesiaObservatoryWorkspace.tsx`
- `src/hooks/useLayer10.ts`
- `src/components/farm/workspace/ExperimentStudio.tsx (proposed)`
## Ordered execution packages
### P11.01 — Define experimental run identity
Every scenario references base publication, plot, geometry/crop cycle, time cutoff, assumptions, input-data versions, engine/model version, random seed if applicable and epistemic mode. Store run separate from SIRE publication; ensure branch comparison source identity.

### P11.02 — Build experiment composer
Select goal (water scenario, nutrient sensitivity, heat/rain change, detection test, MESIA bench, calibration); select eligible plot/zone/sensor/ASMAE state; configure ranges/constraints and control group with units; show preview/testability even if engine absent.

### P11.03 — Build isolated execution adapter
Call sandbox/experiment engine through scoped API, explicitly `SIMULATION`. No direct writes to canonical Layer10 head, device registry or intervention ledger. Prevent client override of verified source timestamps or tenant.

### P11.04 — What-if scientific assumptions
Check hardcoded/fallback baselines in `what_if_sandbox.py`; show which assumptions came from real evidence vs defaults. No labeling of default simulated soil moisture/disease response as measured or validated causal forecast.

### P11.05 — Map comparison and no-data response
If simulation has actual georeferenced output, show patterned hypothetical overlay and scale, separate from observed raster; if only plot/zone scalar, use numeric cards and charts, not a fabricated heatmap.

### P11.06 — Side-by-side outputs
Baseline mean/sigma, simulated trajectory, deltas, uncertainty and hypothesis metadata; link selected state/zone and historical event. Results share context with SIRE but cannot overwrite `publicationId`.

### P11.07 — MESIA physical protocol templates
Provide setup steps and registry of receiver, calibration, controls, instrument logs, expected raw-file schema, signed receipts. Hardware-dependent physical trial stays BLOCKED until device/logger/DB evidence, irrespective of simulator result.

### P11.08 — Comparison and reproducibility ledger
Save scenario versions, reproducible input hash, run ID, assumptions, results and warnings; model revision must mark past simulations stale/incompatible. Export report with disclaimer of validation status.

### P11.09 — Adversarial scenario tests
Try forged snapshot, foreign plot, assumption unit mismatch, negative rainfall, future leakage, simulation disguised as observation, large raster, concurrent experiment during plot change, attempt to invoke physical action.

### P11.10 — Interactive research UX
Parameter slider changes produce debounced preview and explicit recompute event, never silently rewrite published science. A user can compare A/B scenarios and annotate with evidence uncertainty.
## Pass-specific adversarial acceptance
- **P11-G01** Simulation never mutates snapshot store or published head identity.
- **P11-G02** A scenario overlay always says simulated/hypothetical and carries scenario run ID.
- **P11-G03** No raster produced for scalar-only scenario.
- **P11-G04** Invalid units, missing baseline, cross-tenant and future evidence rejected.
- **P11-G05** MESIA physical harness remains explicitly not executed when no hardware/DB.
- **P11-G06** Historical replay of scenario retains input model version and original assumptions.
- **P11-G07** Cancel/plot switch drops old pending scenario result.
- **P11-G08** No physical irrigation/chemical command originates from sandbox controls.
## Deliverable/receipt list
- Versioned experiment/run contract, parameter validation, immutability tests.
- Experiment Studio linked to map+ASMAE+time with separate hypothetical legend.
- Scenario comparison report and evidence/provenance export.
- Independent A4/A6/A7 science/sandbox gate receipts.
**HOLD condition:** canonical scientific state altered by scenario or live/physical result falsely claimed.
## Multi-agent orchestration for this pass
R0 owner pins source SHA and current code; R1 owner & independent specialist separately prepare tests/approach; R2 scientific A4 and safety A6 challenge data authority and actual/simulated boundaries; R3 A7 executes negative gates; R4 A2/A3/A8 verify map interactions in real browser; R5 A0 records GO/HOLD with exact receipt links. These are **planned review duties**, not claims of review already performed.
