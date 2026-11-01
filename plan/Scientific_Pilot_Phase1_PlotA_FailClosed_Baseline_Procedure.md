# Scientific Pilot Phase 1 — Plot A Read-Only Fail-Closed Baseline Procedure

**Baseline:** `main@6edd3721c0defa7eed94b44cf96601ba59a49696`  
**Qualification branch:** `feat/akaloris-scientific-pilot-qualification`  
**Exact plot:** `6ab14f59ad442f274c3f2a62`  
**Expected snapshot:** `ASMAE-SNAPSHOT-06d689425502dc902afcc88215c7a123`

This protocol tests **existing** runtime evidence. It **never POSTs to `/v2/run`**, executes new assimilation, or changes canonical scientific publication state.

## Execution

From the local checked-out branch:

1. Run deterministic receipt parser regression fixtures:

   ```powershell
   python -m unittest discover -s services/agribrain/tests -p "test_scientific_pilot_baseline_probe.py"
   ```

2. Check the actual Python public-action authorization boundary with an in-memory no-envelope fixture:

   ```powershell
   python services/agribrain/scripts/pilot_scientific_fail_closed_probe.py --self-test
   ```

   The self-test reports **source-level** verification and intentionally exits nonzero with `INCONCLUSIVE_NEEDS_EXISTING_RUN_RESPONSE`. This is NOT a live Plot A confirmation.

3. Obtain an **existing** exact-snapshot response by signing into the plot owner's running Next.js application and, from that same authenticated browser tab, executing:

   ```javascript
   const url = "/api/agribrain/surfaces/latest?plotId=6ab14f59ad442f274c3f2a62&snapshotId=ASMAE-SNAPSHOT-06d689425502dc902afcc88215c7a123";
   const res = await fetch(url, { credentials: "same-origin", cache: "no-store" });
   console.log("snapshot HTTP", res.status);
   const payload = await res.json();
   console.log({
     available: payload.available,
     snapshotId: payload.snapshot_id,
     receiptHash: payload.canonical_publication_receipt_hash,
     evidenceCutoff: payload.evidence_cutoff_at,
     validation: payload.validation
   });
   ```

   Save the **entire JSON response body** to a local untracked file such as `pilot-snapshot.json`. Alternatively, the Python probe can fetch this GET itself with `--live-snapshot` if `PILOT_SESSION_COOKIE` is set in your local environment; **never share or commit a cookie**.

4. Locate a **previously recorded real run response** from the actual plot owner (e.g., an existing `POST /api/agribrain/run` response visible in the browser Network tab). Save it to `pilot-existing-run.json`. The probe does not issue a new `POST /api/agribrain/run` or `POST /v2/run` because those execute work.

   Confirm that this response includes `run_id`, `plot_id`, `audit.prescription_authorization` and `recommendations`. If no recorded response exists, **do not invent one**. The live fail-closed execution gate remains **INCONCLUSIVE**.

5. Analyze the two already recorded responses, leaving evidence local:

   ```powershell
   python services/agribrain/scripts/pilot_scientific_fail_closed_probe.py --snapshot-json pilot-snapshot.json --run-json pilot-existing-run.json --self-test --output pilot-baseline-receipt.json
   ```

   To use an authenticated local GET instead of a saved snapshot, replace `--snapshot-json pilot-snapshot.json` with `--live-snapshot`.

## Exact acceptance

The baseline is **negative/blocked** only when all are true:

- Authenticated canonical exact-snapshot retrieval succeeds with matching plot and snapshot, a valid receipt-hash shape and all ten server-provided validation flags true.
- The *previously executed, actual Plot A* run response contains a nonempty `run_id` and exact `plot_id`.
- `audit.prescription_authorization.status === "BLOCKED"`.
- `recommendations` is a real empty array, and there is no authorized envelope hash.
- Any missing run response, authorization audit, mismatched plot, or inconsistent fields is **INCONCLUSIVE/INVALID**, never a pass.
- If an actual authorized response is found, that is **not** a passed negative gate: investigate it under the positive pilot with strict publication binding.

**Terminology clarification:** `SHADOW_ONLY_PENDING_AUTHORIZATION_ENVELOPE` is a `publication_status` inside the L8 *prescription promotion lineage* policy check. It is **not** the `PrescriptiveDegradation` enum or a required value of `degradation_mode`. The read-only public-run boundary is assessed through `audit.prescription_authorization` and `recommendations`.

## Evidence limitations

- Ten server verification flags are trusted from the authenticated publication API. The probe does not cryptographically recompute all hashes from raw artifacts.
- Reading an existing run response does not independently prove it came from the specified published snapshot. That stronger binding is the explicit subject of `PILOT-AUTH-01` and the future V2 envelope design.
- The **only** way to generate an actual new end-to-end full-run response when none exists would be a separately planned, explicitly authorized orchestrator execution. That is **outside this non-invasive Step 1**.
- Do not commit cookies, session tokens, private crop/plot records or the raw local receipt to the GitHub branch. Summarize the gate statuses and nonsecret identity hashes in the review record.

## Gate interpretation

| Response | Status | Interpretation |
|---|---|---|
| Exact publication available, prior actual Plot A run BLOCKED, recommendations empty | `PASS_READ_ONLY_EXISTING_RUN` | Negative fail-closed behavior confirmed from a previously recorded run |
| Valid publication but no existing run response | `INCONCLUSIVE_NEEDS_EXISTING_RUN_RESPONSE` | Published surface alone says nothing about the prescription boundary |
| Missing/corrupt/superseded publication | `FAIL` | No valid exact publication for this gate |
| Run reports AUTHORIZED | `NOT_FAIL_CLOSED` / `FAIL` | Requires positive authorization scrutiny, not proof of the negative gate |

Do not merge scientific-pilot work based solely on these read-only receipts; the V2 binding and actual positive parcel qualification remain separate work.
