# Akaloris Plot — Round 2 / Pass 05: scientific interpretation, action authorization and provenance

**SHA:** `1ee2c20119af29dd1f0a0b46c85217d91206b744`. **Evidence:** source code, not a live successful publication. The user's current screenshot shows no published science; findings here concern code paths when zone/pixel records do become available.

### R2-14 — P1, hard-coded agronomic treatments presented as calculated protocols

[`ZoneDetailStrip.tsx#L15-L121`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ZoneDetailStrip.tsx#L15-L121) defines a fixed `STRIP_INTEL` catalogue. The examples contain “20-30 kg/ha urea,” “25mm irrigation in 2 split applications,” fungicide actions and prophylactic treatment suggestions. [`#L118-L168`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ZoneDetailStrip.tsx#L118-L168) chooses one by zone type or free-text driver; [`#L263-L342`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ZoneDetailStrip.tsx#L263-L342) displays the protocol as if derived from the selected zone. **No physical actuation is shown here, but field users could receive unsupported treatment guidance.** There is no per-recommendation authorization receipt/crop specificity/sensor proof in this lookup.

**Remediation:** remove hardcoded treatment quantities from shared zone UI. Move to typed backend-qualified `Observation`, `Hypothesis`, `Verification`, `RecommendationAuthorization` records. In observation-only pilot allow scouting/verification language only; diagnostics cannot authorize irrigation/fertilizer/chemical applications by text inference.

### R2-15 — P1, linked actions bypass restrictions

[`ZoneDetailStrip.tsx#L315-L340`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ZoneDetailStrip.tsx#L315-L340) and [`ZoneInspector.tsx#L206-L230`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ZoneInspector.tsx#L206-L230) directly render `zone.linked_actions` as “Linked Prescriptions”/“Recommended action.” [`sanitizeRecommendedAction()`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/plot-map-evidence-state.ts#L620-L669) suppresses only one string pattern involving “highlighted zone.” With `actionCap='prescription_blocked'` it still returns original action text (sets `actionLevel='act_blocked'` but `suppressed:false`). Thus merely displaying “blocked” does not stop unsafe free-text output in every consumer.

**Remediation:** a single `isActionVisible(action, publicationAuthority, zone, plot, mode)` gate used by **all** UI consumers; default deny if `authorizedActionReceipt` is absent, expired, revoked, wrong plot or non-actionable. Add repo-wide consumer search and adversarial UI test with `linked_actions=['APPLY_UREA_30_KG_HA']`; assert no treatment displayed anywhere.

### R2-16 — P2, fabricated trust and instrument defaults

[`ZoneInspector.tsx#L153-L210`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ZoneInspector.tsx#L153-L210) fills missing provenance with “Multi-spectral imaging,” “14 days,” “P02-P98 per-field stretch,” “Layer 0 Reliability Surface Tracker,” “Strong spatio-temporal coherence.” It labels a non-inferred zone “Observed (Sensor)” even when there is no signed in-situ sensor evidence in its props. These are claims of origin and support, not harmless placeholders.

**Remediation:** use `Not reported`; distinguish `observed_satellite`, `observed_in_situ_authenticated`, `model_inferred`, `provider_proxy`, `unknown`. “Sensor observed” requires registered instrument, admission metadata and content-bound first-availability proof.

### R2-17 — P2, React hook order and unsupported cause inference

`ZoneInspector` has `if (!zone) return null` before `useMemo`, with ESLint rules-of-hooks disabled ([`#L85-L112`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/ZoneInspector.tsx#L85-L112)). This violates hooks-order design and could fail when null/non-null props alternate within one mounted instance; a runtime test is needed to establish an actual crash. Both `ZoneInspector` and `ZoneDetailStrip` also generate biological causation from zone labels rather than verified diagnostic data. Move inference to a source-qualified presenter, never silently replace missing evidence.

### Positive safeguards worth retaining

`SidebarFarmerView` gates some heat physiology text on `physiological_claim_allowed` and calls out imputed humidity ([`#L207-L255`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/intelligence/SidebarFarmerView.tsx#L207-L255)). The scientific legend says basemap is not evidence. Those protections should become **consistent central policies**, not be erased by a broad redesign.

### Acceptance

- Model-only water-stress zone, no prescription authorization → never display irrigation dose.
- Diagnostic nutrient-risk zone, no crop/lab calibration → only sample/inspect recommendation.
- Rejected/foreign plot linked action → no text, no button, no chat recommendation prompt.
- Unknown source/date/units → “Not reported,” not default observational claim.
- Selected zone null→present→null across same mounted component → no React hook-order error.
- All farmer/expert/zone/sidebar/chat surfaces consume one action policy; no alternate unsafe path.

**Status:** source-level scientific presentation defects confirmed; crop efficacy/hardware not evaluated.