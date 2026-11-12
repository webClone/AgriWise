# P10 — MESIA Observatory receiver network coverage scientific experiments and RF map
**Status:** NOT STARTED · **Prerequisites:** P04,P05,P06 · **Primary agents:** A4+A5+A6 · **Independent verification:** A7 + A6 / A4  
**Proposed code branch:** `feat/plot-workspace-p10-mesia-observatory` (not created).
## Product scope and safety boundary
Expose the complete MESIA tool ecosystem—from radio discovery, coverage graphs and dielectric interpretation to ASMAE supervisor and controlled experiments—through the same map, including explicit hardware availability. RF observability isn't automatically agricultural measurement or geographic coverage.
## Source targets
- `services/agribrain/mesia/CONTRACT.md`
- `services/agribrain/mesia/contracts/receiver.py`
- `services/agribrain/mesia/contracts/coverage.py`
- `services/agribrain/mesia/control_plane/coverage_engine.py`
- `services/agribrain/mesia/experiments/experiment_runner.py`
- `services/agribrain/mesia/experiments/field_plot_experiment.py`
- `services/agribrain/mesia/experiments/bench_experiment.py`
- `src/app/api/agribrain/mesia/route.ts`
- `src/components/farm/intelligence/MesiaObservatoryWorkspace.tsx`
- `src/components/farm/intelligence/mesia/tabs/SignalsTab.tsx`
- `src/components/farm/intelligence/mesia/tabs/AsmaeSupervisorTab.tsx`
## Ordered execution packages
### P10.01 — MESIA subtool inventory and user modes
Map current Signals, Dielectric, In-Situ, ASMAE Supervisor, Wave Studio; catalog receiver coverage/unknown observability, GNSS-R, Wi-Fi CSI, cellular, LoRa/LPWAN, backscatter, radar/UWB and controlled trials as real/code/hardware/future statuses.

### P10.02 — RF receiver geospatial identity
Map receiver node where manifest has actual position, antenna orientation/geometry epoch, hardware health and calibration; unknown position -> list only. Frequency tuning span is not an RF footprint.

### P10.03 — Qualified coverage visualization
Convert actual `CoverageTuple` spatial support, time, frequency, polarization and outcome to map overlay only when geometry is credible. Render UNKNOWN/UNAVAILABLE as no coverage fill and clear observability gap labels.

### P10.04 — Interactive observatory panels
Selecting a receiver focuses RF traces and verified supported bandwidth, antenna chain, shielding/pose drift, health and source epoch. Frequency/time/receiver selection updates map where spatially supported; panel controls cannot fabricate local soil estimates.

### P10.05 — MESIA-ASMAE cross-science bridge
Show radio observation or hypothesis, authorized observation operator, nuisance/covariance and admission decision; only post-L1/ASMAE receipt may show state contribution. Keep receiver noise and biology separate.

### P10.06 — Physical experiments workbench
Bench, soil column, controlled field and closure experiments get configuration, protocol, sample/device registration, run ledger, results/compare screens. Actual harnesses with `NotImplementedError` show `Hardware/data integration required`, not completed trial.

### P10.07 — Remove hard-coded scientific fallback as measured
Audit `AsmaeSupervisorTab` example invariant rows/values and `SignalsTab` illustration labels; any example numbers become explicit DEMO data or disappear from 'live' view. Never show weather, SNR or mast displacement as measured without receipts.

### P10.08 — Simulation overlays and provenance
FDTD/dielectric/noise scenario output visually marks modeled vs controlled experiment, spatial support and input assumptions; cannot replace genuine RF/ground sensors or field study.

### P10.09 — Operational controls and permissions
Actual receiver scan, antenna movement or transmit commands require independent equipment permission, documented physical exposure limits and audited control-plane contracts; read-only pilot defaults.

### P10.10 — Empty-state and adversarial testing
Unknown receiver coordinate, missing antenna config, blind frequency band, stale geometry epoch, no physical instruments and unavailable experiment DB cannot yield a supposed coverage map or field confirmation.
## Pass-specific adversarial acceptance
- **P10-G01** Every MESIA family appears in Library; unavailable physical lab has configuration/protocol UI.
- **P10-G02** Unknown spatial RF coverage never painted as confirmed geographic coverage.
- **P10-G03** Receiver/antenna/time/coverage geometry epochs consistent across map/panel.
- **P10-G04** Hardcoded numerical fallback never presented as measured status.
- **P10-G05** Simulated dielectric/wave output cannot become ASMAE observation without ingestion.
- **P10-G06** No real radio transmitting/antenna actuation from read-only pilot.
- **P10-G07** Foreign plot receiver/experiment not visible.
- **P10-G08** Historical radio measurement cannot be admitted after its knowledge cutoff.
## Deliverable/receipt list
- MESIA tool capability matrix and receiver/capability/coverage feature adapters.
- Map-linked Signals/Dielectric/In-situ/ASMAE/Wave workbench screenshots.
- Experiment protocol/receipt records and explicit physical harness HOLD.
- Independent A4+A6 scientific/radio safety review with negative fixtures.
**HOLD condition:** radio coverage or biophysical measurement invented or real experiment falsely certified.
## Multi-agent orchestration for this pass
R0 owner pins source SHA and current code; R1 owner & independent specialist separately prepare tests/approach; R2 scientific A4 and safety A6 challenge data authority and actual/simulated boundaries; R3 A7 executes negative gates; R4 A2/A3/A8 verify map interactions in real browser; R5 A0 records GO/HOLD with exact receipt links. These are **planned review duties**, not claims of review already performed.
