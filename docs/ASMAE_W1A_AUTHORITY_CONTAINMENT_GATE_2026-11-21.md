# ASMAE W1-A — Full shadow and quick-visual authority containment
**Date:** 2026-11-21
**Baseline:** draft PR #32 `64a9f69945d8e3eda2bf33de9ff24e98186c9a17`
**Status:** Source remediation candidate, targeted tests authored only. Not independently executed or merged.

## Changes (all three user-requested paths)
- `orchestrator_v2/runner.py`: quick-visual submission explicitly declines production and training permissions, instead of unconditionally setting them true.
- `layer05_asmae/runner.py`: registry permissions form the immutable ceiling; request-context flags can **only narrow** selected rights, never widen registry identity, rollout phase, or authority. Shadow/quick-visual always deny production and training.
- `layer05_asmae/engine.py`: final plot-state assembly intersects production science with non-shadow mode and verified registry permission *before* final `state_update_allowed`, `layer1_export_allowed` and weak-label rights.
- Additional cache containment: a previously qualified cache record loses weak labels and numerical/production/export rights on a permission downgrade; diagnostic visualization remains available when separately allowed.

## Source and dynamic qualification gates
Run at the exact branch SHA:
```powershell
python -m pytest services/agribrain/layer05_asmae/tests/test_asmae_w1a_authority_containment.py -q
python -m pytest services/agribrain/layer05_asmae/tests/ -q
python -m pytest services/agribrain/tests/ -q
node scripts/run-frontend-tests.mjs
npx tsc --noEmit
```
Also execute an actual orchestrator `quick_visual` request for (a) unregistered (b) registered rollout plots and a cold cached `standard` response after revocation. Prove no state write, Layer1 export, training label or prescription authority under shadow. Full call-path tests, rollout demotion and multi-process revocation remain acceptance gates.

**Protected invariants:** PR #32 draft unchanged; certified 1m and numerical publication held; verified irrigation disabled; 238 findings retained (zero newly independently closed).
