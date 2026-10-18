# AgriWise / AgriBrain — detailed work-in-progress audit

**Audit:** began 17 October; finalized 18 October 2026, Africa/Algiers. **Pinned main:** `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`. **Repair-plan baseline:** `26d5c3f475cabdbb6edb0fa6fd8ccea5879f2bb4`.

## 1. Overall assessment

**The project has substantial working foundations and useful corrective implementation, but its physical, scientific and operational contracts are not yet consistently connected.** Recent repairs improved numeric admission, hydraulic persistence, quota accounting, uncertainty retention, archive publication, fault latching and several weather/action limits. The broader audit finds important work still open outside those narrow reproductions: water conservation under valid layered profiles, L3-to-L4 state transfer, immutable learning evidence, causal attribution, concrete controller completion, truthful EO representation, application persistence and advice identity.

The next implementation effort should close these boundaries before treating downstream learning or autonomous operation as qualified. This is not a recommendation to restart the project. Preserve the implemented components and repaired controls, replace the incompatible adapters and unsupported defaults, and demonstrate each corrected contract through the actual producer/consumer path.

World Model and Omega are **partially implemented capabilities**, rather than entirely absent features. Daily mechanistic forecasting and held-out evaluation exist. Surprise detection, experiment proposals and diagnostic evidence primitives exist. Learned conservative residual dynamics, independent multi-horizon calibration and a complete falsifiable investigation/replication loop are still target work. Their scientific purpose should remain central; permission labels alone do not supply those capabilities.

The report contains all **52 package assessments**, mapped to the R3 monograph and the existing execution addendum. No package is marked complete merely because a function exists or a suite passes. Equally, an unchecked acceptance box is not treated as proof that the package is unimplemented.

## 2. Scope and evidence

Six specialist agents reviewed disjoint package sets: trajectory (11 cards), decision/economics (8), spatial/MESIA (9), runtime (6), learning/Omega (7) and platform (11). The coordinator checked repository identity, programme change footprint, coverage reconciliation and the current resource-admission counterexample. The six assignments cover F01–F40 and T01–T12 exactly once.

GitHub main still names the previously reviewed commit; there is no newer pushed implementation in this audit. Its nontruncated tree has 4,068 entries. The production index includes1,674 selected code/configuration paths in AgriBrain, AgriWise and runtime configuration. Tests, historical audits, generated artifacts, scratch/probe directories and utility scripts were excluded from this source index. A subset was retrieved and independently Git-blob verified; lane manifests distinguish source available for imports from files actually inspected or executed. Indexing or copying a file does not mean every line was audited.

There were three new bounded offline probe groups in each lane, plus the coordinator's two current resource schedules. These exercise actual production functions, classes or exact AST-selected bodies with explicitly inert collaborators. Positive and negative controls are retained. Some probes use real OS processes or file stores; TypeScript route probes use Node type erasure with mocked authentication/DB/provider boundaries. They are not deployed-service, browser or physical-equipment executions. Runtime dependencies, loader adaptations and current source hashes are recorded alongside results.

Repository tests and historical verification reports were not adopted as correctness evidence. The reported 701 passing tests were not rerun. No production source, Git branch, database, provider account, controller, actuator, radio instrument or drone was changed or operated. Private source copies, offline fixtures and authored audit deliverables are the only writes.

Normative inputs are the R3 monograph and three original plan documents. The supplied R3 PDF SHA-256 is `3cef4ce8ce2d49acf0fed7fc63c1daedda86651260017b56fd6330c8e230292f`. The master package register maps153 unique R3 requirements. Mapping all 153is traceability, not independent acceptance of all 153 scientific requirements.

| Normative document | Exact Git blob |
|---|---|
| Deep Repair Plan | `08d378a65992de859369950599df198e64244f01` |
| Execution Sequencing Addendum | `40751038dc8760e91bc3ab115e30c5e28395953a` |
| Work Packages Task List | `8a564647af7e588802537817159117b349ff606b` |

All three remain unchanged. The task list has 52 unique full-acceptance rows, all open and zero checked. This audit changes no register status. Each specialist appendix separates direct execution, static caller/callee proof, conditional exposure, empirical research criteria and unestablished activation.

## 3. What has actually changed since the plan baseline

Tree-to-tree comparison identifies **39 changed or added paths among the1,674 currently indexed production/configuration paths**. This is a change footprint, not a percentage of implementation. Much useful code already existed at the baseline, and one edited file can contain either a small repair or a major subsystem.

The footprint is concentrated in irrigation runtime, canonical hydraulics, ASMAE, prescriptive gates, source/numeric contracts and archive persistence. Only one indexed frontend/API path differs from that baseline: dashboard statistics. This agrees with the broader findings that operational records, calendars, advice consistency and several scientific bridges still need work. Unchanged source does not itself prove those features absent; their package assessments below use current behavior instead.

The open draftPR#1 remains at `bcb9eda6b8ef1aa6425f5828669f753a191227bc`. Of its nine changed indexed production paths, four now match main byte-for-byte: observation_packet, wrappers, finite numeric helpers and dashboard statistics. Five differ. Thus “PR remains unmerged” must not be used to claim that all its corrections are missing from main. The programme delta and per-file comparisons are in `progress-delta.json`; no merge, checkout or rebase was performed.

The original FC01–FC06 reproduction fixes retain credit at this same SHA. This pass does not repeat every previous matrix or relabel those cases as failing. It expands the assessment to producer/consumer integration and the full 52-card target. The general resource-ownership contract still fails under the separately established claim→query→ACK schedule, freshly reproduced again here.

## 4. Highest-priority scientific and operational findings

The priorities below are review priorities for the stated boundary. They do not replace the master plan's package priority, and a component-level counterexample is not automatically a deployed incident.

| ID | Priority / packages | Finding and evidence level | Consequence established here |
|---|---|---|---|
| W01 | P1 — F03/F04 | Valid heterogeneous conductivity profile loses69.90 mm in a zero-extraction transition and69.38 mm in the complete water pipeline. | Physical closure fails; receipts correctly flag it. No field loss or actuator action is claimed. |
| W02 | P1 — F10/T01 | Full L4 execution replaces137.57 mm canonical supported storage with 83.30 mm and generic retention parameters. | The active water→nutrient bridge changes the scientific input while reporting OK/nondegraded. |
| W03 | P1 — F16–F18 | Fresh two-process resource handoff sends twoSTARTs; concrete Modbus/LoRaWAN STOP paths can clear ownership on transport acceptance. | Runtime ownership and positive physical completion are not a uniform contract. |
| W04 | P1 — F21/F22/F39/T02 | Issued training-window payload mutates1→99 with unchanged hash; raw telemetry is mutable and lost on module reload; known future forecast/plan inputs are quarantined by universal chronology. | Evidence continuity and objective input/target semantics are incomplete. |
| W05 | P1 scientific — F12/T05/T07 | Constant NDVI over equal13-day windows changes the yield proxy solely from extra sampling; verified exposure promotes PRE_POST to CAUSAL_ATTRIBUTED. | Sampling and delivery proof can be mistaken for effect evidence in the actual outcome function. |
| W06 | P1 contract — F20 | Foreign,30-day-old duplicate readings confirm a target 20 mm event with actual 0L and enter a calibration proposal. | Validator API is defective; an active external caller was not established. |
| W07 | P1 product consistency — F31 | Authenticated alternative advice path returns fixed fertilizer doses as successful content when its model key is absent. | Current advice can bypass canonical plot-response contracts; no automatic actuation is inferred. |
| W08 | P2 — F25/F26/F36 | EO fallback retains a learned-backend label; different support collides in hashes; per-state weak-label qualification is incomplete. | Representation lineage/eligibility cannot be inferred from shared flags or hashes alone. |
| W09 | P2 — F14/F13/T05 | Actual crop option loses crop/distribution; mixture and mean/median consumers retain numerical contract gaps. | Scenario/economic comparison is not yet a shared coherent distribution pipeline. |
| W10 | P2 — F30/F32/F33/T08/T09 | Context coalescing, persistence-success reporting and retry/accounting paths have concrete or statically active defects. | Wrong context, false success and duplicate expense are demonstrated at scoped boundaries. |
| W11 | P2 — F38/F40/T11 | Degraded branches have undefined locals; publication status can refer to another snapshot; selected annotation consumers fail. | Error handling/publication identity and supported runtime consumers remain incomplete. |

### W01 — physical closure fails on a valid impedance profile

The layered transition accepts a three-layer conductivity profile `[100,0.01,0.01]`cm/day with 100 mm rain. In the zero-extraction fixture, storage changes180→210 mm, infiltration is100 mm, deep drainage0.10 mm and runoff0. The ledger therefore cannot account for69.90 mm. Dry and permeable controls close exactly. The full engine fixture reports69.38mmclosure error after its realized ET.

The mechanism is visible in the actual solver: percolation is limited by each receiving layer's conductivity, but final theta is clipped to saturation without routing the clipped excess into conserved perched storage, return flow or runoff. The original repair that publishes integrated fluxes and separates analysis increments is useful and remains present. Its receipts honestly report `mass_conserved=false` and mass-quality 0. The full result nevertheless carries a canonical state, data_health 1 and an active diagnosticHOLD. HOLD here is not a demonstrated irrigation command.

**Required correction:** conserve overflow through the declared storage/flux system; distinguish numerical failure from an ordinary supported scientific transition; propagate closure failure to downstream state consumers. Validate dry-down, saturation, heterogeneous impedance, bounded extraction, capillary rise and quantization. Do not merely widen the closure tolerance.

Sources: [layer3_water/soil/layered_water_balance.py#L153-L170](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer3_water/soil/layered_water_balance.py#L153-L170), [layer3_water/soil/layered_water_balance.py#L194-L200](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer3_water/soil/layered_water_balance.py#L194-L200), [layer3_water/runner.py#L264-L285](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer3_water/runner.py#L264-L285), [layer3_water/contracts/state_factory.py#L392-L424](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer3_water/contracts/state_factory.py#L392-L424). R3 focus includes AB-AGR-004/005/008. The exact fixture and controls are in the trajectory appendix/results.

### W02 — the canonical L3 result is not preserved at L4

The actual orchestrator passes canonical water output into the nutrient runner. L4 asks for scalar fields that SoilWaterState does not provide and substitutes0.30/0.15/0.45for FC/WP/saturation and0.7×TAWfor current water. In the full production L3→L4 fixture, roots and soil both support exactly0–60 cm, so unsupported depth is not the explanation: actual 137.57 mm becomes83.30 mm. The output saysOK, nondegraded and uncertainty_multiplier1.

**Required correction:** consume typed profile/root-support quantities, supported storage and retention rather than nonexistent compatibility getters. Carry interval flux identity, closure quality, uncertainty and missingness. Clarify daily versus accumulated drainage and its transport support. A scalar loam surrogate may remain a declared fallback only when explicitly qualified, never a silently exact transfer.

Sources: [layer4_nutrients/runner.py#L189-L247](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer4_nutrients/runner.py#L189-L247), [layer4_nutrients/runner.py#L488-L500](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer4_nutrients/runner.py#L488-L500), [orchestrator_v2/runner.py#L2649-L2654](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/orchestrator_v2/runner.py#L2649-L2654). This must precede scientific acceptance of conservative nutrient feedback and T01 coupled trajectories.

### W03 — resource admission and concrete completion need one lifecycle

The retained current resource case uses two spawned processes. A commits STARTING and pauses before applying START; B truthfully samples idle after that claim; A sends/ACKs and becomes EXECUTING; B's delayed claim is accepted because its query timestamp is newer than A's claim. Both send START. A separate failed-query case also admits a secondSTART while A runs. The older FC01 schedules, with both queries before the claim, were repaired; this does not invalidate that credit.

A new concrete-driver probe shows a separate completion seam. Modbus accepts a coil write and the base STOP path clears its active command/sets ONLINE; the next independent status read still reportsEXECUTING. LoRaWAN clears ownership after network-server queue acceptance without device acknowledgement. These are inert transport fixtures, not hardware failure observations. MQTT's repaired fault/ACK controls are not generalized to other adapters.

**Required correction:** preserve resource ownership for acknowledged, pending or unresolved operations; qualify the query outcome and observed generation; consume a winning owner generation on mutation and before any physical send. Each driver must report accepted, confirmed or unknown, retaining STOP_REQUESTED and monitoring until current stopped evidence exists. TTL expiry or queue/coil acceptance alone is insufficient. Provide an owned periodic watchdog and startup-recovery caller: the current bounded source inventory finds passive evaluator APIs but no such callsite in its searched corpus. An external deployment integrator may exist; that was not established here.

Sources: [irrigation_runtime/safety.py#L1590-L1675](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/safety.py#L1590-L1675), [irrigation_runtime/dispatcher.py#L518-L609](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/dispatcher.py#L518-L609), [irrigation_runtime/drivers/modbus_driver.py#L334-L379](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/drivers/modbus_driver.py#L334-L379), [irrigation_runtime/drivers/modbus_driver.py#L466-L488](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/drivers/modbus_driver.py#L466-L488), [irrigation_runtime/drivers/lorawan_driver.py#L294-L304](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/drivers/lorawan_driver.py#L294-L304), [irrigation_runtime/actuator.py#L345-L359](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/actuator.py#L345-L359). Scope: AB-EXE-002/003/004 and AB-ARC-008.

### W04 — evidence must survive issuance, mutation and restart

The historical extractor's frozen dataclass contains mutable nested event dictionaries. A fresh real canonical-writer→extractor fixture changes an issued value1→99without changing its window hash; reloading canonical disk still returns 1. Current canonical event IDs do include payload and partition identity, so nonempty cross-tenant canonical events do not collide in that control. Empty partition windows still share a hash. The window digest omits a complete sealed payload/partition/policy/ancestry manifest.

The same extractor rejects an earlier-issued weather forecast or planned action as a chronology violation because knowledge precedes valid time. Future measurements and late-known historical observations are correctly excluded. Predictive inputs, later independent targets and retrospective reconstructions require different role-aware eligibility rules; none should turn a planned action into applied exposure.

Raw sensor storage is independently process-local and reference-mutable: changing caller payload20→99changes stored evidence, and reloading the module loses it. Atomic durable nonce admission is now a working slice. Its continuity is not enough if the accepted raw observation can disappear while its nonce survives. The latter ingestion-crash consequence is a static cross-module inference, not an additional executed crash experiment.

**Required correction:** immutable content-addressed raw/normalized evidence; durable admission/recovery continuity; complete issued manifests; role-aware availability and input/target separation; verify manifest hashes at dataset/model consumers. Preserve canonical event IDs, valid zeros and the repaired nonce/rollback controls.

Sources: [world_model/historical_extractor.py#L71-L130](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/historical_extractor.py#L71-L130), [world_model/historical_extractor.py#L179-L254](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/world_model/historical_extractor.py#L179-L254), [sensor_runtime/storage.py#L5-L20](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/sensor_runtime/storage.py#L5-L20), [sensor_runtime/ingestion.py#L79-L85](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/sensor_runtime/ingestion.py#L79-L85), [sensor_runtime/ingestion.py#L184-L201](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/sensor_runtime/ingestion.py#L184-L201). These are core prerequisites for T02 rather than optional archive polish.

### W05/W06 — delivery, response and causal effect are different quantities

For F12, constant NDVI0.5over equal13-day supports produces proxy delta0with two samples per support, but+0.5after adding a third identical post sample. The physical time integral remains6.5 NDVI-days on each side. Sample-index trapezoids cause the difference. Verified exposure also changes the label to CAUSAL_ATTRIBUTEDalthough the method remains PRE_POSTand there is no identification design. The actual L6 runner calls this outcome function and feeds calibration proposal construction; a complete L6 run was not executed.

For F20, the validator API accepts five repeats from a foreign sensor dated30 days before the window. A deliberately contradictory completed-event fixture has target 20 mm but actual 0L; the validator still reports CONFIRMED/confidence 0.95, reports the configured sensor as contributor and proposes 1.5×calibration. Correct qualified-response and no-reading controls behave sensibly. An active external caller to this validator was not established, so no actual field recalibration is claimed.

**Required correction:** timestamp-supported outcome integration; explicit observation identity/time/depth/zone/calibration/dedup admission; actual delivered exposure with uncertainty; association distinct from delivery proof and causal effect. PRE_POST remains association until a qualified estimand/design/assumptions/sensitivity record supports otherwise. These criteria are central to F12/F20, T05 economic value and Omega experiments.

Sources: [layer6_exec/outcomes/metrics.py#L43-L74](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer6_exec/outcomes/metrics.py#L43-L74), [layer6_exec/outcomes/metrics.py#L95-L167](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer6_exec/outcomes/metrics.py#L95-L167), [layer6_exec/runner.py#L325-L342](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer6_exec/runner.py#L325-L342), [irrigation_runtime/validation.py#L125-L215](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/validation.py#L125-L215), [irrigation_runtime/validation.py#L296-L399](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/validation.py#L296-L399).

## 5. Representation, uncertainty and economic correctness

### EO and MESIA foundations need truthful contracts

A failing ONNX-session collaborator returns exactly the deterministic fallback embedding while model_id remains `onnx_foundation` and mode remains `onnx`; the attempted tensor shape is [1,48]. Equal flattened values under different raster shapes or band identities collide in the support hash; changing cloud masks changes embeddings without changing that hash. Missing-band and true-zero features collapse; misaligned band lengths are accepted in the local probe.

The fusion path initially labels EO diagnostic. A shared truth bridge subsequently promotes provider/production flags while retaining false state-update/prescription flags. That contradictory metadata is a traced contract concern, not proof that a prescription was issued. Fix actual backend reporting, model-specific tensor adapters and full support identity before claiming a learned representation or qualified scientific input.

MESIA contains real lattice geometry, inversion, missingness and abstention structures. A rank-deficient observability fixture correctly refuses while an orthogonal control passes. That algebraic result is not independent biological identification. RF axis/topology/complex-loss concerns remain source-level because Torch was unavailable; they were not misrepresented as executed deep-learning failures.

The weak-label exporter correctly zeros unusable/blocked controls and labels outputs weak. With synthetic common pass flags and omitted per-coordinate sigmas, it nevertheless assigns all 13 states weight 0.3using default sigma 0.1. This demonstrates incomplete per-state qualification at the API boundary, not that those flags arise from real sensors or that a trained model was promoted. Objective-specific weak supervision may be legitimate; it must not become independent ground truth or calibrated per-state observability by naming convention.

Sources: [layer1_fusion/eo_foundation_model.py#L265-L325](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer1_fusion/eo_foundation_model.py#L265-L325), [layer1_fusion/eo_foundation_model.py#L336-L405](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer1_fusion/eo_foundation_model.py#L336-L405), [layer1_fusion/eo_foundation_model.py#L611-L627](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer1_fusion/eo_foundation_model.py#L611-L627), [layer1_fusion/truth_bridge.py#L423-L439](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer1_fusion/truth_bridge.py#L423-L439), [layer05_asmae/training/exporter.py#L77-L193](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer05_asmae/training/exporter.py#L77-L193). See the spatial appendix for F25–F29/F36/T03/T06/T12 and empirical limits.

### A common distribution must survive its consumers

The scalar Gaussian coefficient1.28155 is repaired. A posterior Gaussian moment match is not generally the same as mixture-CDF quantiles: the fresh declared 50/50wheat/cotton fixture produces current P10/P90=6.35/9.65 with mixture CDF levels≈0.089/0.882, rather than the declared 0.10/0.90. This is a model-contract calculation, not measured field calibration.

The actual L7 potato option contains crop, yield distribution and economics, but the invoked L8 adapter reads incompatible attribute names and returns empty crop plus relative yield 1.0. The orchestrator calls the adapter; a checked L8 consumer of candidate_scenarios was not traced. This establishes a real transfer defect, not an observed bad operational choice.

EOE uses P50where an expected margin should use the mean or joint samples. Under an accepted mean 42/median 40/price 400/fixed cost 3000fixture, expected profit is13000instead of13800. Current nominal YVEsetsmean=P50, so it hides this difference in that existing chain. L8summary cost`sum(rate×2)`, yield-percent`impact×15`and ROIbased on percentage/nominal cost are explicit heuristics, not dimensionally established economics. Preserve useful calculator baselines but label their assumptions.

**Required correction:** one distribution contract with variable, harvested quantity/unit/support, mean/median/quantiles or samples, contextual price/cost/currency/date and dependence assumptions. Preserve those fields through L7→L8and compute expected value from expectations/joint samples. Add contextual calibration and policy comparisons independently; a correct scalar normal formula does not establish them.

Sources: [layer6_yield/yield_forecast.py#L218-L244](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer6_yield/yield_forecast.py#L218-L244), [layer7_planning/schema.py#L99-L133](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer7_planning/schema.py#L99-L133), [layer8_prescriptive/scenario_contract.py#L54-L72](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer8_prescriptive/scenario_contract.py#L54-L72), [orchestrator_v2/runner.py#L2905-L2912](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/orchestrator_v2/runner.py#L2905-L2912), [layer7_planning/engines/eoe_economics.py#L23-L28](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer7_planning/engines/eoe_economics.py#L23-L28), [layer8_prescriptive/runner.py#L477-L493](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer8_prescriptive/runner.py#L477-L493).

## 6. AgriWise product and runtime integration

The production signed-session middleware protects the independentAIroute. The problem is an **authenticated alternative advice path**, not demonstrated anonymous access. `/advisor→/api/ai/chat→Gemini/static fallback` does not carry the canonical plot-response artifact contract. A missing key returns successful fixed Arabic advice containing100 kg/ha urea and10 t/ha organic; a provider quota failure can becomeHTTP 200 successful content. Farm context is accepted but not consumed by the provider function. Route generic educational content explicitly or route plot-specific advice through authorized canonical evidence and constraints; provider unavailability should remain a typed failure.

Conversation identity is incomplete in active paths. Browser and server memory use plot-only identities. The active run singleflight key omits history although the backend request includes it, so same plot/query/mode with different narratives can coalesce. This is a source-proven context contract issue, not a demonstrated cross-tenant authorization bypass. The semantic-cache number/scope counterexample is separate and its production activation remains unproved.

The photo route checks plot ownership/image constraints but only checks zone format. An inert authenticated-route fixture supplies a foreign well-formed zone and rawDBreply`{ok:1,n:0,writeErrors:[...]}`; the route reportsHTTP 200 success. Input creation followed by a failed total update returns 500 after the row exists; a retry creates a second 100 DZD row and the sum becomes 200. No real database was changed. These are transaction/admission boundary defects and should be fixed before records become scientific or financial evidence.

Useful controls are present: dashboard outage returns 503 with stats:null; ownership/finite/category checks exist on inputs and tasks. Remaining product paths include a hardcoded five-task calendar, farm outage presented as empty, and optimistic task completion without checkingHTTPstatus or rollback. The active yield widget synthesizesσ=15%of mean, labels peak-normalized values Probability%, and has a conditional zero-step loop when mean 0. Backend emission of the relevant tool was not established; this is static conditional UI exposure, not an observed browser hang.

Degraded paths also need attention: exact no-data assignment reads undefined ts, failed-ASMAEreceipt reads undefined geometry_hash, and progress can publish the relation to another head. Selected deferred annotation consumers fail while cold imports and most checked dataclasses pass. Do not call these all import failures or claim broad supported-runtime startup from a few positive imports.

Sources and exact evidence level for each are in the platform appendix, especially `src/app/api/agribrain/run/route.ts:179–204,459–472,851–869`, `src/app/api/evidence/add/route.ts`, `src/app/api/inputs/route.ts`, `src/components/farm/AgriBrainChat.tsx:464–488,548–588`, `src/components/farm/CycleDashboard.tsx:80–93`and the line-specific F38/F40 records. T08/T09/T10/T11 remain genuine capability/integration work, not cosmetic frontend polish.

## 7. World Model and Omega readiness

### Implemented foundations

- A canonical writer/extractor and scoped hydraulic checkpoint/recovery system.
- ASMAE candidate/validation/revocation ledgers, weak-target exclusions, plot-disjoint splits and artifact-byte checking.
- An actual crop-classifier training/reload API, trusted input receipts, partial hierarchy labels, fold-local validation imputation and a separate external release gate. It is not merely a placeholder trainer.
- Daily mechanistic forecast propagation, held-out observation operators, persistence-relative evaluation and separate prospective versus reconstruction fields.
- Omega scalar surprise detection and experiment proposals, diagnostic assertions with evidence/confounders and run-scoped contradiction/overlap ledgers.

### Criteria still required

T01 needs a coupled transition that actually consumes water/nutrient feedback in later vegetation dynamics. Shared IDs, optional schema fields and sequential L2→L3→L4calls do not establish operator coupling. Fix W01/W02and support/missingness first.

T02 needs immutable objective-specific input/target ancestry, role-aware times, finite qualified labels, split manifests and reproducible regeneration. A new ledger→dataset fixture preserves zero and rejects a weak flag, but admits NaN target and drops label times. A local model-registry fixture accepts nonempty placeholder evaluation dictionaries for approved_shadow_expert; this is a presence check, not deployed model skill or machine authorization. Preserve artifact-byte validation while strengthening scientific artifact identity.

T04 has real mechanism-based dynamics, but a learned bounded residual, memory sufficiency, uncertainty decomposition, multi-horizon prospective improvement and paired-intervention validation remain target criteria. Establish the mechanistic baseline on sealed issuance data before fitting a residual; assess independent outcomes rather than only self-consistency.

T07 has an actual surprise→proposal primitive: a 0.3 VWC disagreement producesz≈6.708andKL≈64.921 bits. Its explanations are three fixed strings; expected gain is0.8/0.6/0.4×KLrather than a measured or model-based discrimination calculation. This is useful scaffolding, not a completed scientific investigation. Build one sealed case with competing explanations, a discriminating prediction, feasible cost/power/interference/stopping design, observed outcome, negative/inconclusive/falsification handling, independent replication and domain-bound versioned knowledge. Include model-space inadequacy, instrument/management confounding and physical equation checks where relevant.

T03/T06/T12 need qualified multimodal acquisition/metrology, instrument/site/season holdouts and an independent reference programme. A file loader, rank test or synthetic fixture cannot establish those empirical criteria. This audit does not claim an external reference programme is absent outside the inspected evidence.

Exploratory research may proceed on explicit, bounded objectives while foundations are repaired. Qualification for training promotion, causal decisions, territorial conclusions or machine operation must follow the relevant evidence gates. Authority controls support this work; they are not Omega's scientific purpose.

## 8. Corrective implementation order

Keep the existing17-stage addendum and its dependencies. The following workstreams are bounded priority slices; they do not close full packages early or make every activity a universal blocker.

| Workstream | First concrete deliverable | Completion evidence | Dependencies / parallelism |
|---|---|---|---|
| A — physical state and execution | Conserved layered overflow; typed L3→L4root state; definitive accepted/confirmed/unknown driver outcomes; owned watchdog/recovery. | Valid impedance closes; canonical storage unchanged at L4; one STARTunder handoff; unconfirmed STOP retains ownership. | F03/F04/F10 and F16–F19 can be repaired in parallel within their declared prerequisites. |
| B — evidence continuity | Durable immutable raw telemetry plus replay recovery; frozen window manifests; role-aware input/target timing and finite labels. | Mutation cannot change issued evidence; restart retains raw record; valid issued forecast/plan inputs survive;NaN labels reject; canonical IDs preserved. | F01/F02/F09/F21/F22/F39 andT02 foundation. |
| C — biological/causal/economic semantics | Actual exposure in response qualification; timestamp-weighted outcomes; coherent yield distributions and L7→L8scenario transfer; conservative N-state definitions. | Foreign/stale duplicates add no confidence; resampling constant NDVIchanges no effect; PRE_POSTdoes not become causal from delivery alone; potato/distribution/mean survive consumers. | F10/F11/F12/F13/F14/F20/F34 before T05 scientific acceptance. |
| D — representation and per-state qualification | Truthful EO backend, complete support identity, masks/axis/complex contracts and per-variable observability/validation ledger. | Failure reports actual backend; shape/band/mask changes alter identity; missing differs from observed zero; Torch marker/phase controls in supported image; independent reference qualification. | F25–F29/F36 withT03/T06/T12; acquisition research can run on its own explicit eligibility. |
| E — operational product contracts | Canonical advice path and conversation identity; atomic/idempotent photo/input/task admissions; honest empty/error states; exact publication identity and supported package consumers. | No dose on model outage; distinct histories do not coalesce; rejected writes not successful; retry does not duplicate cost; progress refers to exact committed snapshot; selected introspection resolves. | F30–F33/F37/F38/F40 andT08/T09/T11. |
| F — validated extensions | One coupled trajectory, frozen objective corpus, prospective mechanistic baseline, bounded learned hybrid, shared decision distributions and one falsifiable scientific case. | Independent outcome and holdout receipts meet the relevant R3objective; negative/inconclusive findings retained; reference programme/domain limits explicit. | T01/T02 then eligible T03–T07/T10 extensions; no blanket ban on bounded exploratory experiments. |

Do not reuse an aggregate test count as closure for these criteria. For each completed slice, preserve the positive controls and update only the actual subtask evidence; full FA closure requires its remaining integration/empirical/operational gates. The original 2,564–4,540 hour programme estimate is not a current remaining-work estimate. This audit does not invent a completion percentage, engineer-day forecast or empirical readiness score.

## 9. All 52package register

The following table is a navigation register. Each specialist appendix contains the package's current behavior, verified slices, remaining criteria, exact source/R3references and acceptance scope. The accompanying machine-readable register preserves those assessments without reducing them to a misleading percentage.

| Package | Stage | Current assessed state | Next implementation slice |
|---|---:|---|---|
| F01 — Qualify provenance and numeric evidence at every admission boundary | 1 | partial; admission repairs present, field-role qualification incomplete | Use one component admission result carrying role, support, finite value, uncertainty and rejection reason; consume it before solver/authority selection. Preserve explicit zero reliability. |
| F02 — Enforce observation time and availability at issuance | 1 | partial; prospective initialization repaired, downstream issuance remains open | Resolve forcing by valid interval plus issuance cutoff and immutable record version; keep forecast scenario time separate from measurement event time; archive queries must resolve an authorized scoped knowledge view. |
| F03 — Publish the fluxes actually integrated and separate analysis increments | 2 | partial; original flux reporting repaired, physical closure defect remains | Repair perched-water/overflow accounting and declare a failed/partial scientific result when physical closure exceeds tolerance; prevent downstream consumers treating it as an ordinary supported state. |
| F04 — Validate soil geometry and hydraulic parameter vectors | 2 | partial; geometry/domain gates improved, parameter round-trip limits remain | Use finite_real plus explicit boolean rejection; serialize sufficient precision or define a minimum accepted representable domain. Record effective parameters if physical regularization is applied. |
| F05 — Use depth-aware soil observations and carry covariance | 4 | partial; optimal interpolation implemented, depth/covariance target open | Add a typed per-reading support/noise/role contract, build depth-aware H, preserve posterior covariance, and publish support completeness and propagated Ks uncertainty. |
| F06 — Stop substituting another date at the weather endpoint | 3 | partial; original endpoint substitution fixed, complete forcing qualification open | Use a typed weather interval object preserving source record ID, valid support, issue/availability and per-variable observed/prior status through every parse and checkpoint. |
| F07 — Remove future canopy fallback and restore evaporation memory | 3 | partial; evaporation memory repaired, canopy missingness/support open | Propagate coordinate-level missingness and support from L2; treat explicit observed zero separately from unavailable canopy. Resolve every historical coordinate independently at the step cutoff. |
| F08 — Make trajectory invalidation include parameters and predecessor content | 3 | partial; parameter/predecessor invalidation improved, content completeness open | Define one versioned canonical digest of consumed state/forcing plus immutable source receipt references; derive invalidation from that content rather than selected hand-maintained fields. |
| F09 — Persist coupled state with scoped concurrency and restart recovery | 3 | substantial repairs; broad recovery acceptance not complete | Backfill publication receipt maps for every extant scoped head during migration, and make checkpoint-backed forcing lookup use canonical scoped committed history at an explicit cutoff. |
| F10 — Repair the L3-to-L4 water boundary | 4 | open confirmed current integration defect | Extend/consume the typed L3→L4 boundary with root-support storage, profile or weighted retention, interval flux IDs, support quality and covariance; reject/qualify incompatible boundaries. |
| F11 — Correct residual nitrogen demand and expose conservative pools | 4 | partial repaired formula pool integration not closed | Define and wire a conservative N-state transition and actual application support before expanding recommendation claims. |
| F12 — Separate exposure verification from causal attribution | 4 | current reproduced defects | Separate evidence status from effect classification and repair timestamp integral at actual outcome producer. |
| F13 — Correct yield quantiles and distinguish calibrated distributions from heuristics | 5 | partial normal quantile fix distribution contract remaining | Define and transport one distribution contract, fixing mixture quantiles and expected-value consumers together. |
| F14 — Repair L7-to-L8 crop scenario mapping | 5 | current reproduced adapter defect consumer gap | Repair typed boundary and wire intended scenario policy consumer; test orchestrator-to-consumer composition. |
| F15 — Unify weather constraints and final hard action limits | 5 | partial repaired gates known unit seam full feasibility unverified | Fix known gust-only normalization and prove emitted output against original constraints plus actual dated budgets/resources. |
| F16 — Enforce quota and watchdog independently of telemetry | 6 | partial core present operational integration not accepted | Wire a supervised periodic runtime loop and recovery startup path; then verify real entrypoint quota and deadline behavior with inert hardware collaborators. |
| F17 — Keep actuator operation state until physical completion | 6 | remaining concrete driver STOP contract defect | Change each concrete adapter to return confirmed/unknown operation outcomes and preserve command ownership until a current stopped receipt/readback confirms it. |
| F18 — Reconcile ambiguous command failures before retry | 6 | conservative uncertainty present operation receipt capability missing | Keep fail-closed unknown outcomes; add an adapter with real operation receipts and a supervised recovery caller, then qualify retries and restart. |
| F19 — Implement interlock persistence, debounce and stable violation keys | 6 | debounce and dedup verified protection rehydration gap | Persist/restore active manual protection receipts independently of event reservations, then replay restart and qualifying-reset scenarios. |
| F20 — Qualify post-irrigation readings before confirming delivery | 7 | current reproduced local validation calibration defect | Require qualified actual exposure and sensor records at validator admission before confirmation/calibration. |
| F21 — Freeze training-window payloads and include partition identity | 8 | confirmed core defect open | Freeze and hash the issued manifest, preserving canonical writer identity; verify it at each downstream consumer. |
| F22 — Classify timing by event role rather than a universal causality rule | 8 | confirmed role timing defect open | Implement role-aware eligibility while keeping independent later labels as targets and plans as scenarios. |
| F23 — Commit forecast archives atomically before publishing cache entries | 8 | repaired archive foundation integration not signed off | Preserve archive mechanisms and seal issuance-time forecasts in actual prospective evaluation/corpus path. |
| F24 — Validate forecast distributions and make missing scores unavailable | 8 | partial known parser and scientific acceptance limits | Repair retained parser grammar and qualify one objective-specific target/score contract; retain valid pointmass zero. |
| F25 — Report the actual EO inference backend and normalize its input contract | 9 | open reproduced contract defect | Return backend outcome explicitly from inference; use per-artifact tensor adapters and propagate diagnostic provenance through admission. |
| F26 — Hash complete EO support and distinguish missing bands from zero | 9 | open reproduced support defect | Define an immutable raster input contract and canonical support digest, with explicit missing tokens before model preprocessing. |
| F27 — Repair MESIA link-time axes and graph topology | 9 | open static contract defect runtime unverified | Correct axis restoration and propagate masks/epoch metadata through the public forward contract; run marker fixtures with unequal link/time dimensions. |
| F28 — Make MESIA masked pretraining respect complex channel semantics | 9 | open static objective defect runtime unverified | Expose latent dimension and validity support, define paired complex masking and phase-periodic reconstruction, then evaluate separately from downstream labels. |
| F29 — Correct MESIA evaluation labels and establish independent biological validation | 9 | partial geometry and missingness controls independent validation open | Keep algebraic geometry capability distinct from per-variable biological qualification and build independent measurement/perturbation evaluation with nuisance baselines. |
| F30 — Scope conversational memory and cache identity | 10 | open: active thread identity gaps; semantic-cache activation unproved | Introduce one authorized conversation identity in storage and singleflight; make canonical advice identity include the actual conversational and scientific inputs. Trace semantic-cache callers before enabling it. |
| F31 — Close the independent public AI advice path | 10 | open: authenticated independent advice path | Route advice through the plot-authorized canonical response boundary; type provider failure separately from content and require educational mode for generic material. |
| F32 — Replace demo calendar and misleading empty/error application states | 10 | partial: statistics failure handling passes; calendar/farm/task UI remain open | Wire calendar to scoped records, render farm outage explicitly, and reconcile task state with successful persisted response before marking completion. |
| F33 — Validate photo zone ownership and database insert success | 10 | open: photo zone and raw commit boundary | Resolve zone membership, reject nonacknowledged insert outcomes and persist an idempotent evidence admission event with the created ID. |
| F34 — Separate input accounting from applied agronomic exposure | 7 | partial accounting controls exposure contract gap | Define durable accounting/stock/application contracts and attach qualified elemental/water exposure to real trajectory ingestion. |
| F35 — Repair drone driver import and complete process cleanup | 11 | optional import slice improved remaining stub and cleanup defects | Return unavailable for unimplemented real drivers, distinguish simulation in mission outputs, and close terminate-kill-wait/group-cleanup across every failure branch. |
| F36 — Require per-variable observability and independent predictive calibration | 11 | partial training gates and temporal controls per state qualification open | Introduce a required per-state qualification ledger with known uncertainty and dependence groups; preserve separate prospective and reconstruction eligibility in export. |
| F37 — Repair optional imports and establish one Python package identity | 0 | partial: selected cold imports fixed; package identity open | Choose and install one package namespace, migrate callers/entrypoints together, and certify fresh entrypoints in the declared image with explicit extras. |
| F38 — Restore failure ledgers, scoped loading and degraded publication | 10 | partial fixes present; degraded ledger/publication defects remain | Repair local variable scopes; reject unqualified namespace; derive publication relation only from the committed job receipt; verify each degraded branch through its canonical commit boundary. |
| F39 — Make telemetry persistence and replay protection concurrency safe | 3 | atomic nonce path present durable raw and retention criteria open | Implement durable immutable telemetry + admission continuity first, then bounded scoped retention and lifecycle-managed locks with replica/restart acceptance. |
| F40 — Resolve annotation consumers and close verification evidence gaps | 10 | open: deferred annotation consumers fail; verification scope bounded | Import resolvable annotation names and run supported schema consumers against the installed declared image; publish exact corpus/exclusions and separate audit receipts. |
| T01 — One canonical coupled agricultural trajectory | 12 | capability target; foundations present, coupled transition not demonstrated | Implement a versioned coupled transition contract with explicit feedback consumption and support-aware projections, then validate informative water/N perturbations against growth and conservation receipts. |
| T02 — Objective-specific longitudinal learning corpus | 12 | partial implemented learning paths objective corpus extension pending | Build one objective slice with qualified target roles and immutable blocked splits, then attach exact dataset/model lineage through actual trainer. |
| T03 — Multimodal foundation representation and local adaptation | 13 | research target primitives present capability unestablished | First close EO and RF contracts, then preregister small baseline comparisons using frozen longitudinal and instrument-held-out splits before larger foundation claims. |
| T04 — Hybrid world model with conservative multi-horizon rollout | 14 | partial mechanistic forecast foundation hybrid extension pending | Evaluate one prospectively archived multihorizon mechanistic baseline with qualified drivers before fitting bounded residual dynamics. |
| T05 — Decision economics from shared outcome distributions | 14 | heuristic baseline present scientific target not established | Preserve useful baseline while establishing shared distribution/economic context and independently evaluated policies. |
| T06 — MESIA native acquisition, metrology and capability commissioning | 13 | partial file ingestion and research gates metrology target open | Keep file ingestion/research output separate from instrument commissioning; specify native capture/time/calibration contracts and acquire independent metrology records before enabling biological authority. |
| T07 — Omega scientific investigation loop | 16 | partial surprise proposal foundation scientific loop extension pending | Demonstrate one sealed case from surprise through competing predictions, discriminating measurement and negative/replicated judgment; do not substitute KL-template gain for measured information. |
| T08 — Finish AgriWise operational records and financial workflows | 15 | target incomplete; concrete retry-reconciliation defect | Make input mutation and totals recoverable/idempotent; then implement the planned typed workflows with authorized persisted states and reconciliation. |
| T09 — Unify language, voice, map and offline product projections | 15 | target partial: canonical map foundations; inconsistent advice/rendering remains | Unify response identity across views and use canonical uncertainty distributions; guard zero/invalid yield; add accepted voice/offline reconciliation flows with fidelity checks. |
| T10 — Institutional aggregation and territorial world-model extension | 16 | planned extension; foundations verified only | Implement the proposed institutional contract and evaluate on independent regional cohorts before claiming territorial capability. |
| T11 — Operational reproducibility, provider resilience and publication integrity | 11 | target partial: substantial resilience foundations; exact publication relation open | Fix exact publication relation, provide supported immutable runtime identities and execute bounded cross-service resilience/recovery drills against actual admission/storage boundaries. |
| T12 — Independent agronomic validation and reference field program | 12 | reference program not established by inspected artifacts | Make independent reference/measurement and preregistration contracts explicit, reject missing metrology from physical QA, and execute the field program with holdout and baseline plans. |

## 10. Audit deliverables and reproducibility

The evidence bundle contains the six lane reports, all 52package assessments, current and baseline source-object metadata, normative extracts, authored scripts and raw observations. Production source copies, repository tests, historical audits as inputs and generated controller/quota/checkpoint stores are excluded. Exact Git objects can be reconstructed into a separate workspace by the supplied read-only materializer.

All **12 replay commands** completed with exit 0 from a separate reconstructed layout containing **1,393 exact source copies / 698 unique blobs**. Production bytes remained unchanged after replay. These commands cover the declared lane probe groups, coordinator resource schedules and a source inventory; their counts are not added into a repository-test total. The replay record distinguishes final script outcomes and expected counterexamples. Exit0means the declared observation was reproduced; it is not a production-pass count. The materializer does not fetch, checkout, commit or push. It is compiled/layout-verified rather than executed here against a separate complete Git checkout; selected scripts are additionally replayed from a reconstructed local layout with unchanged production bytes. Environment and POSIX/Node requirements are stated in the bundle.

The substantive conclusion is that the foundation is worth preserving, while specialist outputs still lose meaning at important boundaries. Finish the conserved state, evidence, completion and consumer contracts before treating the larger target as implemented. The appendices provide the concrete work needed to do so.


---

# Specialist appendix — Canonical trajectory and hydraulic integration

# Trajectory and hydrology work-in-progress audit

Pinned source: `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc` (2026-10-17). Scope is exactly F01–F10 and T01, including the live L0/L1/L2/L3/L4 callers needed to judge those cards. This is a broader implementation review, not a repeat of the FC repair suite. All code references below refer to this SHA; `source-manifest.json` records exact Git blobs and `runtime-source-manifest.json` records loaded production dependencies. Files staged or indexed outside those receipts are not counted as audited.

The strongest fresh results are a physical water-loss case, a full nutrient-boundary mismatch, and a missing-canopy integration boundary. Current source also contains substantial repairs: finite soil admission, exact endpoint weather selection, actual interval/analysis receipts, geometric validation, evaporation memory, parameter/predecessor-aware invalidation and durable scoped checkpoint/CAS machinery. Those improvements deserve credit without declaring all eleven cards complete.

## Method and reproducibility

The normative basis is the three original plan documents under `sr-team-review/plan` and R3 scientific sections (`AB-DAT-004/005/006/007/011/012/013`, `AB-AGR-002` through `010`, and the package-specific requirements in the JSON ledger). Plan priorities are engineering priorities, not evidence that an untested package fails. R3 explicitly requires a closed multilayer water balance; separate physical fluxes, analysis and clamps; distinct observation/prior/forecast/synthetic roles; compatible canopy/root/water/nutrient outputs; and replay of the knowledge available at issuance.

Exactly three independent authored offline probes were allocated. They import production functions and data contracts directly. No repository tests/audits, old generated outputs, field measurements, production service, hardware, or controller calls establish these fresh results. Stores are private fixtures; both qualified/unqualified worldline aliases point to the same private directory, matching production alias semantics. No production code or Git state was changed.

Reproduce from the workspace root:

```bash
PYTHONDONTWRITEBYTECODE=1 python wip-audit-2e1fbcb-2026-10-17/trajectory/probe.py
python wip-audit-2e1fbcb-2026-10-17/trajectory/build_report.py
```

Harness adaptation: early setup was blocked by unstaged production dependencies (`crop_database`, `schema_legacy`, `raster_backend`, then unrelated L10 `surface_contract`); an initial harness also requested nonexistent `water.confidence` rather than its actual `water_confidence` schema. These were harness/setup issues, not AgriBrain defects. P2 was bounded to a real-schema fixture and executed consumer integration; the unexecuted producer activation is explicitly static. Final results have no unresolved execution errors. Reused dependency bytes are verified against the current tree; source staging was coordinated centrally.

## Fresh numerical and integration results

### WIP-C01 — Valid impedance layer deletes water during saturation clipping (high priority; F03/F04)

P3 uses a valid 0–10–30–60 cm profile with theta/FC 0.30, saturation 0.45 and conductivity `[100, .01, .01]` cm/day. These are admissible heterogeneous parameters; this is not the previously repaired negative-conductivity or invalid-depth case. Supply 100 mm rainfall, zero irrigation and, in the direct transition control, zero transpiration/evaporation.

| Case | Initial→final storage mm | Infiltration mm | Drainage mm | Runoff mm | Unreconciled loss mm |
|---|---:|---:|---:|---:|---:|
| Dry, impedance profile | 180→180 | 0 | 0 | 0 | 0 |
| Rain, permeable profile | 180→180 | 100 | 100 | 0 | 0 |
| Rain, impedance profile | 180→210 | 100 | 0.10 | 0 | **69.90** |

The cascade adds water to the next layer, drains only its conductivity bound, then clips theta to saturation without returning the excess to another conserved reservoir or flux (`soil/layered_water_balance.py:153–170,194–200`). This is actual storage loss. The full `WaterIntelligenceEngine.execute_pipeline` confirms the boundary with normal ET enabled: 180→200.06 mm, infiltration100, ET10.46, drainage0.10 and loss69.38 mm.

The repaired receipt tells the truth: `mass_conserved=false`, `mass_balance_quality=0`; overall confidence drops from .938 to .588. That is a meaningful improvement over concealed closure errors. Nevertheless, the engine returns a canonical `WaterState`, `data_health_score=1.0` and an active diagnostic HOLD with confidence.75. This probe does not establish command permission, deployment, or field actuation. It establishes a nonconserved scientific state still available to ordinary downstream consumers. L4's canonical branch also does not inspect the closure flag.

Repair the overflow/perched storage accounting and explicitly qualify/fail unsupported physical states before dependent inference. Acceptance should include independently reconciled stocks and receipts for layered impedance, saturation, capillary rise, bounded extraction and serialization; dry and permeable controls must remain closed.

### WIP-C02 — Full L3→L4 execution substitutes soil state (high priority; F10)

P1 runs the complete water pipeline on a lab-labelled heterogeneous non-loam profile and then the complete nutrient standalone runner. Root depth is exactly .60 m, matching the 60 cm soil support, so no extrapolated-depth assumption is needed. It is a production caller/callee probe, not a copied branch or mocked nutrient engine.

| Coordinate | Canonical 0–60 cm supported value | L4 SWB output |
|---|---:|---:|
| Current storage | **137.57 mm** | **83.30 mm** |
| Depth-weighted FC | .295 | .300 |
| Depth-weighted WP | .0966667 | .150 |
| Depth-weighted saturation | .440 | .450 |
| TAW | 119.0 mm | 119.0 mm |

L4 correctly picks up the actual root TAW and stress, then reads absent `theta_fc`, `theta_wp`, `theta_sat`, `root_zone_storage_mm` attributes from `SoilWaterState`. Its `getattr` fallbacks replace the real fields with .30/.15/.45 and .7*TAW (`layer4_nutrients/runner.py:224–245`). It labels the boundary `OK`, `is_degraded=false`, uncertainty multiplier1. Downstream environmental losses divide the substituted storage by a fixed 300 mm while supplying root_depth_cm60 (`488–500`), which does not express this same support integration.

Consume an extended typed L3→L4 receipt carrying support-integrated storage/retention, interval drainage identity, support/uncertainty and closure status. The existing `to_layer4_boundary_receipt` has physical stress and memory fields but not the storage/profile quantities required to fix these getters. Daily drainage assigned to an `accum` field does not itself prove duplicate counting; multi-day transport was not tested in this pass.

### WIP-C03 — Degraded L2 canopy can become explicit water canopy (F01/F07/T01)

P2 executes real `VegIntOutput` data contracts matching the empty-timeseries return shape, then `Layer2CompositeOutput.from_parts`, then `_execute_canonical_water_engine`, with private scoped stores. Producer activation is **static**, not executed: importing its runner reached unrelated unstaged L10 schema dependencies, so the audit stopped expanding that dependency graph. The actual producer return at `layer2_veg_int/runner.py:247–278` uses default `CropHealthIndex`: numeric LAI0/FVC0, empty component mask and default coverage1 despite absent vegetation observations. The composite correctly advertises degraded enrichment, but its compatibility properties return those zero values. The L3 adapter consumes the values without the producer's missingness/degradation support and creates a `VegetationState`. The executed missing-canopy fixture and affirmative bare-soil zero control both yield LAI0/FVC0, Kcb.15, Ke1.108 and ASSIMILATED authority. The finite-canopy positive control yields LAI3/FVC.8, Kcb1.033 and Ke.225. Raw values and support diagnostics are in `results.json`.

This is distinct from preserving legitimate zero: observed bare soil should remain zero, while missing canopy must remain unknown or a labelled prior. Current compatibility conversion erases that distinction and can grant ASSIMILATED water authority merely because a vegetation object exists (`layer3_water/runner.py:384–389`). The finite-canopy control checks that the consumer responds to canopy values. An affirmative zero control prevents solving the missingness problem by rejecting valid zero.

## Eleven-package implementation ledger

The following entries state current implementation, verified boundaries, remaining criteria and concrete next work. A static finding is not presented as an executed experiment. Prior exact-SHA repair results are retained as context where requested; they do not substitute for fresh whole-package acceptance.

### F01 — Qualify provenance and numeric evidence at every admission boundary

**Status:** partial; admission repairs present, field-role qualification incomplete. Stage 1; requirements AB-DAT-005, AB-DAT-006, AB-ARC-005, AB-ARC-006; dependencies none.

Soil assimilation rejects nonfinite, boolean and malformed real scalars, records rejections and bases authority on admitted source labels. ASMAEObservationPayload validates finite value/variance and root-zone units. Universal dictionary and temporal gates do not enforce the same qualification.

Verified slices:

- Static: finite_real is applied before soil observation admission and weather numerical execution; typed payload has explicit units/variance.
- Executed P2: actual VegIntOutput schema fixture → production composite/water consumer compares missing canopy and affirmative zero; producer activation is static.

Remaining criteria:

- Temporal _has_numeric admits nonfinite float values; a complete surrounding provenance envelope does not establish finite scientific evidence.
- Dictionary role is not considered by _infer_data_status; reading_reliability=0 is replaced by 1 through or.
- SoilObservationVector provenance_sources is not used to qualify its fixed IN_SITU_PROBE_TDR source label; per-component role/support remains absent.

**Next implementation:** Use one component admission result carrying role, support, finite value, uncertainty and rejection reason; consume it before solver/authority selection. Preserve explicit zero reliability.

**Acceptance scope:** Boundary finite-value fixes are credited. Full F01 requires role-safe L0→L1→L2→L3 delivery, not just a typed soil entry-point check.

Source: `services/agribrain/layer0/temporal_evidence.py:20–24,44–72`; `services/agribrain/layer0/wrappers.py:127–164,280–308`; `services/agribrain/scientific_contracts/observation.py:42–66`; `services/agribrain/layer3_water/assimilation/water_state_assimilator.py:104–161`; `services/agribrain/layer3_water/runner.py:384–389`.

### F02 — Enforce observation time and availability at issuance

**Status:** partial; prospective initialization repaired, downstream issuance remains open. Stage 1; requirements AB-DAT-004, AB-DAT-014, AB-ML-008; dependencies F01.

Resilient posterior requires observed and available times before explicit cutoff and rejects dynamic forecasts as initial-state measurements. Historical extraction filters committed knowledge time. The L3 weather adapter extracts seven numerics without retaining availability, issue, revision or source role.

Verified slices:

- Static: nested prospective dynamic records are filtered by both timing classes.
- Static caller trace: run_layer3_decision passes inputs/L1 directly into _execute_canonical_water_engine, whose parser emits numerical-only forcing.

Remaining criteria:

- An exact-date weather record can be numerically valid yet unavailable at issuance; no cutoff check occurs in this L3 adapter.
- The historical extractor unconditionally quarantines knowledge time before valid time; this also excludes correctly earlier-issued future forecasts if represented as events in this window.
- Checkpoint weather archive scan selects newest file mtime without checking cycle/geometry, committed lineage or knowledge cutoff. This is a static qualification gap; foreign/orphan-weather contamination was not dynamically probed here.

**Next implementation:** Resolve forcing by valid interval plus issuance cutoff and immutable record version; keep forecast scenario time separate from measurement event time; archive queries must resolve an authorized scoped knowledge view.

**Acceptance scope:** Initial-state cutoff repair does not certify issuance-safe weather or training/scenario extraction throughout the graph.

Source: `services/agribrain/layer05_asmae/resilient_posterior.py:129–172,768–777`; `services/agribrain/world_model/historical_extractor.py:185–203`; `services/agribrain/layer3_decision/runner.py:700–763,1022–1147,1918–1938`.

### F03 — Publish the fluxes actually integrated and separate analysis increments

**Status:** partial; original flux reporting repaired, physical closure defect remains. Stage 2; requirements AB-AGR-004, AB-AGR-005, AB-AGR-008; dependencies F01.

Layered transition receipts publish integrated bounded extraction and serialized storage closure. The water pipeline records a separate analysis increment and publishes realized interval fluxes from the transition. A valid low-conductivity receiving layer can still overflow and be silently saturated by clipping.

Verified slices:

- Executed P3: dry and permeable controls close exactly; impedance-layer case loses 69.90 mm in zero-extraction transition and 69.38 mm in full pipeline.
- Executed P1: full L3 pipeline supplies real water state to full nutrient runner.
- Static: analysis increment and realized flux sources remain separate.

Remaining criteria:

- Carry saturation overflow through explicit conserved storage/return flow/runoff, instead of deleting it in theta clipping.
- A nonconserved result currently returns a canonical water state and an active diagnostic HOLD; mass quality is correctly zero, but data_health remains 1. No actuation or permission inference was tested.
- Full conservation must cover heterogeneous conductivity, saturation and quantization as well as ordinary dry-down.

**Next implementation:** Repair perched-water/overflow accounting and declare a failed/partial scientific result when physical closure exceeds tolerance; prevent downstream consumers treating it as an ordinary supported state.

**Acceptance scope:** Integrated-versus-published original is fixed in current source; full F03 physical closure remains open on a fresh valid-input counterexample.

Source: `services/agribrain/layer3_water/soil/layered_water_balance.py:153–170,194–200,238–263`; `services/agribrain/layer3_water/runner.py:264–285,299–339,373–420`; `services/agribrain/layer3_water/contracts/state_factory.py:392–424`.

### F04 — Validate soil geometry and hydraulic parameter vectors

**Status:** partial; geometry/domain gates improved, parameter round-trip limits remain. Stage 2; requirements AB-AGR-003, AB-DAT-007; dependencies F01.

Factory validates nonempty increasing positive finite depth vectors, matching vector lengths, retention ordering, positive conductivity/alpha and n>1. It preserves heterogeneous vectors but rounds hydraulic parameters before returning the contract.

Verified slices:

- Static: former nonmonotonic/negative-hydraulics paths now explicitly reject.
- Executed P1/P3: heterogeneous valid profiles enter the complete production water engine.

Remaining criteria:

- isinstance(value,(int,float)) still treats bool as a numeric depth/parameter.
- Positive conductivity below .005 cm/day rounds to 0; alpha below .00005 rounds to 0; n close enough to 1 rounds to 1. The returned contract can fail its own factory domain checks on hydration. This pass establishes this directly from serialization code, without a fourth probe.
- Suction calculations silently clamp accepted alpha/n/m to stronger minimums, so effective solver parameters may differ from the returned requested parameter values.

**Next implementation:** Use finite_real plus explicit boolean rejection; serialize sufficient precision or define a minimum accepted representable domain. Record effective parameters if physical regularization is applied.

**Acceptance scope:** Original geometry/domain checks are credited. Closure is a separate F03 defect, not invalid geometry. Round-trip and effective-parameter transparency remain acceptance gates.

Source: `services/agribrain/layer3_water/contracts/state_factory.py:51–77,115–145,149–180`; `services/agribrain/layer3_water/soil/layered_water_balance.py:89–104,227–235`.

### F05 — Use depth-aware soil observations and carry covariance

**Status:** partial; optimal interpolation implemented, depth/covariance target open. Stage 4; requirements AB-AGR-009, AB-DAT-007, AB-MES-013; dependencies F01, F04.

OI builds vertically correlated background covariance, maps profile readings by array index, computes a posterior, exposes aggregate variance reduction and clamps physical bounds. The vector lacks per-reading depths/location/time/role. Root-zone uncertainty is evaluated using its default sigma rather than the updated posterior sigma.

Verified slices:

- Static: explicit H[row,idx]=1 and position-based probe loop establish support semantics.
- Static: full P_post is computed, while only scalar variance diagnostics leave the assimilator.

Remaining criteria:

- Represent individual reading supports and create observation operators from actual depths/overlap; reordered readings cannot yet be recognized as equivalent.
- Carry layer covariance and unsupported root-depth support into root-zone and L4 products.
- Use posterior uncertainty in final root-zone evaluation; the pipeline currently passes it to forecast/overall uncertainty, not the final root-zone call.
- Thermal cooling remains a fixed conditional linear surrogate without a consumed calibration receipt; it must remain qualified.

**Next implementation:** Add a typed per-reading support/noise/role contract, build depth-aware H, preserve posterior covariance, and publish support completeness and propagated Ks uncertainty.

**Acceptance scope:** No empirical depth-observability validation was attempted. The current implementation is OI, not an ensemble Kalman filter or full root-zone observation.

Source: `services/agribrain/layer3_water/contracts/assimilation_state.py:22–32,57–95`; `services/agribrain/layer3_water/assimilation/water_state_assimilator.py:140–174,190–214,216–244`; `services/agribrain/layer3_water/runner.py:287–304,363–370`; `services/agribrain/layer3_water/contracts/state_factory.py:252–313`.

### F06 — Stop substituting another date at the weather endpoint

**Status:** partial; original endpoint substitution fixed, complete forcing qualification open. Stage 3; requirements AB-DAT-004, AB-DAT-005, AB-AGR-007, AB-AGR-013; dependencies F02.

The endpoint requires exact day matching or an explicitly supplied weather_prior; absence returns None. Intermediate gaps use a labelled persistence/climatology prior with zero rain and inflated weather sigma.

Verified slices:

- Static: exact-date endpoint search and explicit missing-weather return replace arbitrary dictionary fallback.
- Static: intermediate imputation flags, method and .08 sigma are carried to the pipeline.

Remaining criteria:

- Endpoint weather_prior is marked is_prior before parsing, but _parse_weather discards that flag and component imputation provenance. Missing variables filled from prior/humidity transformations also lose per-field role.
- Interval timezone handling and issuance eligibility are not established merely by exact date matching.
- Zero-rain imputation is visible for intermediate gaps, but its applicability must be bounded by the required qualified forcing policy.

**Next implementation:** Use a typed weather interval object preserving source record ID, valid support, issue/availability and per-variable observed/prior status through every parse and checkpoint.

**Acceptance scope:** Credit the exact-date original fix. Daily/sparse equality requires the same qualified versions and explicit missingness; it is not certified by a seven-number endpoint record.

Source: `services/agribrain/layer3_decision/runner.py:1022–1077,1079–1137,1968–1998`; `services/agribrain/layer3_water/runner.py:153–159`.

### F07 — Remove future canopy fallback and restore evaporation memory

**Status:** partial; evaporation memory repaired, canopy missingness/support open. Stage 3; requirements AB-AGR-006, AB-AGR-007, AB-AGR-008; dependencies F03, F04, F06.

Water runner restores days since wetting, derives top storage from real thickness, and applies method-specific wetting fractions. Complete absence of historical canopy no longer falls back directly to the future endpoint. Partial dictionaries still borrow missing coordinates from endpoint-derived variables.

Verified slices:

- Executed P2: the degraded producer return shape is reproduced with real VegIntOutput data contracts and reaches production composite/water code. The producer branch is statically traced, not executed; bare-soil/finite-canopy controls distinguish values from support.
- Static: evaporation days/thickness/fraction propagation is present.

Remaining criteria:

- Degraded/no-observation canopy must remain unknown or a declared prior, rather than numeric bare-soil data with assimilated authority.
- Partial historical canopy dictionaries use endpoint lai/fvc/root defaults, including the closest-prior branch; resolve each coordinate using step-eligible support.
- Depth and canopy uncertainty/support are lost in the compatibility VegetationState constructed by the decision shim.

**Next implementation:** Propagate coordinate-level missingness and support from L2; treat explicit observed zero separately from unavailable canopy. Resolve every historical coordinate independently at the step cutoff.

**Acceptance scope:** Original complete future-fallback and evaporation-memory fixes are credited. P2 is an integration defect at current missingness/authority boundaries, not a claim that every L2 output is invalid.

Source: `services/agribrain/layer2_veg_int/runner.py:219–278`; `services/agribrain/layer2_veg_int/schema.py:69–89`; `services/agribrain/layer2_intelligence/schemas.py:394–431,437–512,543–585`; `services/agribrain/layer3_decision/runner.py:1149–1220,2056–2098`; `services/agribrain/layer3_water/runner.py:174–230`; `services/agribrain/layer3_water/soil/layered_water_balance.py:201–226`.

### F08 — Make trajectory invalidation include parameters and predecessor content

**Status:** partial; parameter/predecessor invalidation improved, content completeness open. Stage 3; requirements AB-DAT-011, AB-DAT-012, AB-AGR-007; dependencies F03, F04, F06.

Forcing keys include retention, conductivity, VG parameters, parameter provenance, geometry/cycle/epoch, solver identity and predecessor. Request timestamp and ensemble fingerprints also enter. Soil state digest includes only evaporation days, omitting wetted fraction.

Verified slices:

- Static: former theta-only digest replaced by multi-coordinate profile digest.
- Static call trace: omitted few_exposed_wetted_fraction is read by the water solver and changes Ke demand.

Remaining criteria:

- Include every consumed evaporation state coordinate, particularly wetted fraction, in predecessor identity.
- Use canonical structured serialization rather than repr/str fingerprints for rich objects and define precision/volatile-field policy.
- Preserving earlier issued forecasts while appending corrected retrospective trajectories remains a broader F02/F09 integration criterion; no fresh concurrency probe was allocated here.

**Next implementation:** Define one versioned canonical digest of consumed state/forcing plus immutable source receipt references; derive invalidation from that content rather than selected hand-maintained fields.

**Acceptance scope:** Original conductivity/retention key omission is repaired. Full-content cache equivalence remains open; this pass makes a static consumed-field omission finding, not a measured output collision.

Source: `services/agribrain/layer3_decision/runner.py:2000–2031,2145–2194,2196–2208`; `services/agribrain/layer3_water/runner.py:215–227`.

### F09 — Persist coupled state with scoped concurrency and restart recovery

**Status:** substantial repairs; broad recovery acceptance not complete. Stage 3; requirements AB-DAT-003, AB-DAT-012, AB-DAT-013, AB-ARC-008, AB-AGR-006; dependencies F02, F03, F08.

RAM identities include tenant/namespace/plot/cycle/geometry; canonical hydraulic checkpoints preserve observations/history/withdrawals and publish scoped predecessor CAS under a shared store. Publication receipt maps separate allocation from published generation.

Verified slices:

- Static: current runner serializes/hydrates SoilObservationVector and complete history summaries.
- Static: canonical scoped heads, receipt maps, immutable checkpoint comparison and predecessor checks are present.
- Previously reported same-SHA original warm/cold, scope switching, CAS and recovery fixes are retained as existing work; this audit does not rerun those scripts or promote them to whole-package closure.

Remaining criteria:

- Known same-SHA 2E02 legacy receipt migration seam remains acknowledged: maps initialized for another scope can lose the older recovered publication generation on later lookups. Identity/state/global head are preserved; this is not demonstrated scientific corruption.
- Weather retention still scans physical checkpoint files by mtime without qualified scoped/committed selection (F02).
- Full acceptance still needs exact versioned correction/withdrawal/parameter semantics across restart and replicas, with archived issuance views and supported schema migrations.

**Next implementation:** Backfill publication receipt maps for every extant scoped head during migration, and make checkpoint-backed forcing lookup use canonical scoped committed history at an explicit cutoff.

**Acceptance scope:** Current narrow original fixes retain credit. 2E02 is carry-forward context from the separate exact-SHA bounded review, not freshly reexecuted evidence. No fourth concurrency/recovery probe was added.

Source: `services/agribrain/layer3_decision/runner.py:942–985,1223–1243,1368–1408,1918–1938,2653–2697`; `services/agribrain/world_model/canonical_worldline.py:263–311,370–430,467–486`; `services/agribrain/layer05_asmae/history/worldline_service.py:99–144`.

### F10 — Repair the L3-to-L4 water boundary

**Status:** open confirmed current integration defect. Stage 4; requirements AB-AGR-008, AB-AGR-010, AB-DAT-007; dependencies F03, F04, F05.

Actual orchestrator passes canonical L3 output to L4. The nutrient runner reads its root metrics/fluxes but requests absent scalar soil fields and root storage, substituting generic loam values and .7*TAW. It labels this SWB output OK/nondegraded.

Verified slices:

- Executed P1: complete water engine plus full run_layer4_standalone, not extracted AST or a stub nutrient engine.
- Actual root support is exactly 0–60 cm, eliminating unsupported-depth ambiguity in the counterexample.

Remaining criteria:

- Replace nonexistent getters with typed root-support integration; 137.57 mm current supported storage currently becomes 83.30 mm.
- Use the correct profile/depth retention parameters and support thickness in environmental losses; current code divides storage by fixed 300 mm while supplying fixed root_depth_cm60.
- Daily deep drainage must carry interval identity and be accumulated once; assignment to drainage_accum_mm alone establishes neither cumulative transport nor double counting.
- Carry water closure failure, support and uncertainty rather than unconditional OK and multiplier1.

**Next implementation:** Extend/consume the typed L3→L4 boundary with root-support storage, profile or weighted retention, interval flux IDs, support quality and covariance; reject/qualify incompatible boundaries.

**Acceptance scope:** P1 proves the generic substitution with a valid non-loam profile through full nutrient production execution. Nutrient empirical accuracy and multi-day leaching accounting were not probed.

Source: `services/agribrain/orchestrator_v2/runner.py:2649–2654`; `services/agribrain/layer4_nutrients/runner.py:189–247,488–500`; `services/agribrain/layer3_water/contracts/water_state.py:45–80,317–355`; `services/agribrain/layer3_water/contracts/assimilation_state.py:57–95`.

### T01 — One canonical coupled agricultural trajectory

**Status:** capability target; foundations present, coupled transition not demonstrated. Stage 12; requirements AB-WM-001, AB-AGR-002, AB-AGR-008, AB-ARC-001, AB-ARC-002, AB-ARC-003, AB-AGR-001; dependencies F03, F09, F10, F11.

Orchestrator connects L2→L3→L4 and publishes references/envelopes. Belief snapshots carry optional distribution/support references and cutoff/version fields. L3 emits a hydrological constraint receipt. The vegetation transition has no consumed L3/L4 feedback argument, and the live composite explicitly describes its adapter as diagnostic rather than joint dynamics.

Verified slices:

- Static end-to-end trace: registry dispatches composite L2; orchestrator runs L2 before L3 and L4 once.
- Executed P1/P2/P3 establish real boundary behavior and limitations, not joint scientific validation.

Remaining criteria:

- Define one operator-splitting order with water and nutrient feedback consumed by the next vegetation step.
- Show a receipt linking feedback IDs, predecessor, interval, model/parameter versions and resulting growth change.
- Preserve X/Z/H/M/U support and unknownness beyond shared belief IDs; diagnose unsupported and nonconserved coordinates.
- Demonstrate daily/sparse/cold/correction equivalence of the coupled trajectory after F03/F09/F10/F11 are accepted.

**Next implementation:** Implement a versioned coupled transition contract with explicit feedback consumption and support-aware projections, then validate informative water/N perturbations against growth and conservation receipts.

**Acceptance scope:** This is a planned capability extension, not a regression inferred from unchecked plan boxes. Shared identity and specialist contracts alone do not prove a canonical coupled trajectory.

Source: `services/agribrain/orchestrator_v2/registry.py:31,71–90`; `services/agribrain/orchestrator_v2/runner.py:2607–2623,2649–2654`; `services/agribrain/layer2_intelligence/composite_runner.py:41–63,143–157`; `services/agribrain/layer2_contracts/state_transition.py:130–161,268–298`; `services/agribrain/layer3_water/runner.py:424–439`; `services/agribrain/world_model/belief_snapshot.py:24–83`.

## Implementation order and limits

1. Repair and gate water closure on valid heterogeneous profiles (WIP-C01), then repair the typed L3→L4 state/support boundary (WIP-C02). Both directly affect conserved scientific quantities and later inference.
2. Make admission, missingness and issuance provenance survive the entire compatibility path: default-zero canopy, weather role/availability, per-reading soil support and reliability0. Preserve the repaired legitimate-zero and finite-number cases.
3. Close consumed-state digest completeness and canonical scoped historical queries. Preserve current scoped CAS/recovery repairs; migrate publication receipts deliberately, including known 2E02 legacy behavior.
4. Implement T01 as an explicit coupled operator with consumed water/N feedback receipts after its specialist boundaries are accepted. Do not present shared IDs or optional schema fields as empirical joint trajectory validation.

This bounded pass does not certify all workloads, empirical crop physiology, covariance calibration, multi-day N transport, controller permissions, or complete R3 acceptance. It does establish current actual caller/callee behavior for the three independent fixtures and targeted source slices across all eleven assigned cards. No card was classified solely from an unchecked acceptance box.


---

# Specialist appendix — Agronomy, outcomes, planning and economics

# Current-source decision and agronomy review

Reviewed main: `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`. Review date: 17 October 2026. Exactly eight packages: **F11, F12, F13, F14, F15, F20, F34, T05**.

The implementation contains useful repaired slices, but these eight packages do not meet their full scientific and integration criteria in the checked scope. The strongest freshly reproduced problems are unqualified moisture observations entering confirmation/calibration, exposure verification being promoted to causal attribution, and the real L7 crop option losing its crop and distribution at the L8 adapter. The residual nitrogen subtraction and Gaussian scalar quantile coefficient are repaired; those fixes must retain their limited credit.

## Method and limits

The normative sources are the supplied R3 scientific sections and all three plan documents: `AgriWise_AgriBrain_Deep_Repair_Plan_2026-10-06.md`, `AgriBrain_Execution_Sequencing_Addendum_2026-10-07.md`, and `AgriBrain_Work_Packages_Task_List_2026-10-07.md` in `sr-team-review/plan`. The addendum lines 9, 32–42 and 54–59 distinguish early slices, full package acceptance, and scientific capability. An open FA checkbox is not evidence that every implementation step is absent.

Every production file imported or cited below was freshly checked against the pinned tree's Git blob SHA. `source-manifest.json` records inspected sources and normative-document SHA256s; `import-manifest.json` records the 13 production import sources, exact loader isolation and Python/library versions. Two unchanged dependencies were copied into this lane only after matching the current tree: EOE economics and the L8 ranker. No production file was edited.

Exactly **three authored offline probe groups** ran in `probes.py`, with current outputs in `raw-results.json`; all three groups and their assertions completed. These are selected production-function compositions with explicit collaborators, not repository tests or previous audit receipts. L6 loads only the exact required dataclass/enum definitions; L7 omits its unrelated `ExecutionPlan` annotation import. No target function or class body is rewritten. Full orchestrator, database, service, controller and hardware execution were not run. The review does not establish field performance, deployment state, physical delivery, causal identification, or full F15 acceptance.

Paths below are repository-relative and resolved to the exact source/local dependency path in the manifests. Line numbers refer to those current production bytes. R3 references use `current-plan-review/R3_current_scientific_sections.txt`.

## Package coverage

| Package | Current assessed state | Verified credit and outstanding boundary |
|---|---|---|
| F11 | Partial correction; conservative-pool acceptance not established | Second subtraction removed and t/ha→% conversion corrected. L4 still passes zero applied N to the photosynthesis module, cumulative soil credits and fixed recovery/default support; no state-transition mass reconciliation demonstrated. |
| F12 | Current reproduced defects | Exposure is a separate field, and unverified execution gets association labels. Verified execution still gives PRE_POST a causal label; sample-index integration produces a false yield proxy change. |
| F13 | Correct scalar normal coefficient; distribution contract incomplete | Scalar Gaussian control has approximately P10/P90 coverage under its declared normal model. Posterior moment matching is not mixture-CDF quantiles; L7 retains heuristic bands and mean=p50. No prospective calibration demonstrated. |
| F14 | Current reproduced adapter defect; incomplete consumer integration | Actual typed L7 option is accepted but loses crop and distribution. Orchestrator calls this adapter; checked L8 ranker/runner do not consume the resulting scenario collection. |
| F15 | Material repaired gates; limited residual and full-acceptance gaps | Current source includes missing/invalid spray checks, UTC dates/past-point rejection, unit conversions, preserved leaching ceilings, lower/upper dose checks, and a final emitted-output invariant pass. Known duplicate gust-unit seam remains in source; global legal/resource/budget feasibility is not demonstrated by that invariant pass. |
| F20 | Current reproduced validator/calibration defect; active runtime exposure unestablished | No-reading control abstains and the nominal moisture-response control works. Foreign stale duplicate measurements can still confirm response and enter calibration based on target rather than actual delivered exposure. |
| F34 | Partial accounting and management infrastructure; integration gap | Auth/ownership, finite positive quantity/date checks and Prisma category enum exist. Controlled units, lifecycle/formulation/area exposure, and idempotent financial updates remain unresolved in the checked path. No purchase→historical-balance promotion was demonstrated. |
| T05 | Existing heuristic baseline; shared decision-economics target incomplete | L7 has price overrides, break-even and sensitivities; L8 excludes blocked cards from its summary. Joint contextual distributions, calibrated marginal value and independently evaluated information policies are not supplied by those baselines. |

## Fresh reproduced findings

### D1 — F20: unqualified moisture readings promote confirmation and calibration

**Evidence class:** reproduced local production-class composition, review priority P1. Plan stage 7, F20 steps 1–4; task list lines 922–947. R3 AB-EXE-005 lines 1122–1124, AB-DAT-007 lines 683–685, AB-DAT-013 lines 707–709.

P1 constructs an actual `IrrigationEvent` with target 20 mm, actual delivered volume **0 L**, effective area 1 ha, application efficiency 0.9, and COMPLETED status. The validator is configured for `sensor-A`, pre-VWC 0.2 and root depth 0.6 m. Five repeats of the same observation from `foreign-sensor`, all timestamped **30 days before** the window, report VWC 0.218.

Current result: expected rise **0.03**, observed rise **0.018**, outcome **CONFIRMED**, confidence **0.95**, reported sensor IDs **[`sensor-A`]**, and a calibration proposal with **sample_count=1, adjustment_factor=1.5, confidence=0.95**. This uses five repeated readings to inflate confidence and reports the configured device as though it contributed. At 1 ha, 0 L delivered cannot supply a 20 mm dose; a moisture association is not independent proof of delivery. The fixture intentionally supplies a contradictory completed-event record to test whether the validator verifies the exposure it relies on; it does not establish that an actuator generates such a record.

The nominal control uses 200,000 L over 1 ha, distinct in-window `sensor-A` observations at 0.23, and returns CONFIRMED with adjustment 1.0. The no-observation control returns SENSOR_OFFLINE and sample_count 0. Those controls show the failure concerns admissibility and promotion, not an inability to produce sensible nominal outputs.

Sources: `irrigation_runtime/validation.py` lines 125–149 use `event.target_volume_mm` and record the configured sensor IDs; 156–175 append without identity/time/uniqueness checks; 199–215 average the last three; 296–347 derive delivery efficiency and confidence from count and repeat configured IDs; 365–399 admit the report to calibration. `irrigation_runtime/schemas.py` lines 328–361 expose distinct actual volume/area fields that this path does not use. Reading identity has no tenant/zone/depth/calibration/measurement-ID admission contract in the checked API.

**Scope:** the direct class API is demonstrated. Search of the staged production scientific source found the singleton and definitions, but no external call to these window/read methods. Active app/runtime exposure and physical recalibration are not claimed.

**Closure:** admit provenance-bearing readings with actual contributing devices, tenant/plot/zone/depth/calibration and measurement IDs; enforce post-action support and deduplication before confidence; derive delivered depth only from qualified actual exposure and area; keep response association separate from delivery proof. This exact foreign/stale/repeated/zero-delivery fixture must contribute no confirmation confidence and no calibration, while the nominal and no-reading controls retain their behavior. Add rain/drainage/support uncertainty to the response model before claiming hydrological validation.

### D2 — F12: a sampling-only change becomes a causally attributed yield proxy

**Evidence class:** reproduced production function with actual dataclasses; caller statically traced, review priority P1. Plan stage 4, F12 steps 2–4; tasks lines 620–645. R3 AB-WM-006 lines 1060–1062, AB-OMG-008 lines 1204–1206, AB-EXE-005 lines 1122–1124.

P3 uses NDVI 0.5 at both endpoints of equal **13-day** pre and post supports, around an actual execution timestamp of 1 October. With two observations in each window, yield proxy delta is **0**. Adding one interior post-window observation at the same NDVI changes the reported proxy delta to **+0.5**, despite identical physical trajectories and elapsed-time integrals of **6.5 NDVI-days** in each support. NDVI recovery and velocity stay zero. The added observation changes the sample-index trapezoid area, not vegetation response.

Every verified-exposure output is labelled **CAUSAL_ATTRIBUTED** while method remains **PRE_POST**, without a control or identification record. The unverified-exposure control is correctly labelled OBSERVATIONAL_ASSOCIATION_ONLY; the useful exposure field should be preserved. Verification of an action's delivery does not identify its effect.

Sources: `layer6_exec/outcomes/metrics.py` lines 43–47 integrate by sample index; 65–74 grant causal classification solely from status/timestamp; 95–126 form windows/extract observations; 156–167 select PRE_POST and confidence; 205–220 emit the proxy. Lines 109–110 also use `or` for NDVI and rain: valid zero NDVI can be discarded and absent rain becomes zero. Those two latter cases were source-inspected, not additional probes. Negative deltas are not clamped in the current computation. Actual `layer6_exec/runner.py` lines 325–342 calls this function on completed tasks and supplies outcomes to calibration proposal construction; no whole L6 run was executed.

**Closure:** timestamp-weighted integration with declared support/gaps; zero-preserving extraction and explicit unknown confounding; exposure status independent of effect identification. PRE_POST must remain association unless an explicit estimand/design/assumptions/support/sensitivity record qualifies a causal estimate. The sampling-invariance control above must return zero before/after resampling, and delivery verification alone must not change association into causal effect.

### D3 — F14: the real L7 crop option loses semantics at the adapter

**Evidence class:** reproduced actual-schema boundary and static production caller, review priority P1. Plan stage 5, F14 steps 1–4; tasks lines 696–721. R3 AB-EXE-001 lines 1106–1108, AB-DEC-001 lines 1068–1070, AB-ECO-002 lines 1084–1086.

P2 creates the actual L7 nominal potato option using the actual crop library, YVE and EOE collaborators. The option contains crop **potato**, yield mean/P50 **35 t/ha**, P10 **24.5**, P90 **40.25**, and economic quantities. The adapter returns target_crop **empty string**, crop_choice **empty string**, synthetic index ID **SCN-CROP-crop_opt_0**, and `expected_yield_relative=1.0`; distribution and economics are discarded. The exact current behavior is empty string, not the older plan narrative's “unknown”, because `CropOptionEvaluation.name` defaults to `""`.

Sources: `layer7_planning/schema.py` lines 99–133 define `crop`, `yield_dist`, `econ` and empty default `name`; `layer8_prescriptive/scenario_contract.py` lines 54–72 read incompatible `crop_type`, `expected_yield` and `expected_profit` attributes and silently manufacture fallbacks. The `expected_profit` fallback at line 58 is a static dimensional violation: money is eligible to fill a field named relative yield. This extra invalid shape was not separately executed in this three-group pass.

Actual integration exists at `orchestrator_v2/runner.py` lines 2905–2912, which applies this adapter to `l7_res.output.options` and supplies L8 `candidate_scenarios`. In the checked `layer8_prescriptive/runner.py`, exact current `action_ranker.py`, and the L8 directory search, `candidate_scenarios`/`feasibility_constraints` appear as schema fields at lines 393–394, with no decision consumer traced. Thus the corruption is a real invoked contract seam, while a resulting bad operational recommendation has **not** been demonstrated. Building an adapter and carrying the field does not establish policy comparison.

**Closure:** accept the actual typed contract, retain stable option identity/crop/declared yield distribution and unit/economics/currency/support/provenance, reject incomplete shapes as unavailable, and connect scenario evaluation to the intended L8 policy consumer. The real potato fixture must preserve all quantities; money must never be accepted as yield. Verify the actual orchestrator→L8 consumer, not only an adapter unit check.

### D4 — F13/T05: correct scalar normal quantiles coexist with distribution and expectation errors

**Evidence class:** P2 numerical production-function composition, review priority P2. F13 stage 5 steps 1–4; T05 stage 14 steps 1–2. R3 AB-AGR-014 lines 898–900, AB-ML-005 lines 990–992, AB-ECO-002 lines 1084–1086.

The repaired scalar wheat control returns mean **9**, P10 **7.85**, P90 **10.15** at CV 0.1. Its implied normal CDF levels are **0.10066/0.89934**; rounding explains the small difference from 0.1/0.9. This directly credits `yield_forecast.py` lines 130–131 and does not claim empirical coverage.

With a 50/50 wheat/cotton hypothesis mixture, branch means are 9/7 t/ha and branch normal SDs are 0.9/0.7. The current posterior emits P10/P90 **6.35/9.65** from a moment-matched Gaussian. Their true mixture CDF levels under those declared branch models are **0.08909/0.88242**, versus actual mixture quantiles **6.40592/9.75759**. `yield_forecast.py` lines 218–244 add within/identity variance and then use mean±1.28155×SD; this preserves mixture moments, not mixture tail probabilities. The case uses a degenerate stage posterior, so added phenology variance is zero. The local function's `production_eligible=True` reflects its input booleans; this is not an audit of upstream posterior eligibility.

Current L7 YVE lines 20–22 construct fixed 70%/115% bands, apply threshold penalties, and line 70 returns mean=p50, explicitly described in code as an MVP simplification. Schema lines 99–113 contain no family, support, units, calibration coverage or sample/dependence contract. That is a partial baseline, not proof of a calibrated distribution.

For a separately accepted L7 contract fixture with mean **42**, median **40**, price **400 per ton**, fixed cost **3,000 per ha**, actual EOE returns expected_profit **13,000**, whereas linear expectation is **13,800**. The actual nominal YVE→EOE control, whose mean equals median, agrees with linear expectation. This fixture isolates the expectation error at the accepted schema boundary; present YVE itself always supplies mean=p50, so it does not establish a current end-to-end 800-unit realized-loss difference. Source: `layer7_planning/engines/eoe_economics.py` lines 23–28. Fixing distribution semantics must fix its consumers in the same slice.

**Closure:** a common distribution contract with explicit quantile levels, harvested quantity/support, mean/median, calibration status and versioned provenance; actual mixture CDF quantiles or justified joint samples; heuristic labels until fitted; expected margins derived from expectations/joint samples, not P50. Validate prospective empirical coverage independently. Retain the repaired scalar-normal and nominal-economics controls.

## Source-inspected remaining boundaries and repaired slices

### F11 — repaired formula, unresolved conservative N-state semantics

Plan F11 lines 416–440, stage 4, dependency F10; tasks 583–608. R3 AB-AGR-010 lines 882–884 and AB-AGR-008 lines 874–876.

`photosynthesis_nue/engine.py` lines 127–132 now converts plant-N/biomass to percent using biomass×10. Lines 160–165 use `max(0, n_needed_kg_ha)` with no second applied-N subtraction and return zero for nondeficiency. Under the plan's declared 5 t/ha, 2% critical, 50 kg/ha applied, 30 soil, and 0.60 recovery assumptions, this algebra is `(100−48)/0.60=86.67`. This pass checked that expression in source; it did not spend a fourth probe group re-executing the previously isolated formula fixture.

The same function assumes applied plus soil N are recovered at the same fixed 0.60. It estimates a season sink as daily uptake×days×0.5. At the actual caller, `layer4_nutrients/runner.py` lines 459–474 pass **n_applied=0**, and sum cumulative mineralization, fixation and residual credit as supply. Lines 483–488 pass preliminary estimated demand into a parameter named `n_applied_kg_ha` for loss calculations. Lines 565–578 assemble a supply/demand budget, including nitrogen_ppm×3, fixed 8 kg/ha deposition and cumulative terms. `layer4_nutrients/schema.py` lines 325–369 provide an algebraic budget but no applied-input or evolving stock transition in that budget object.

These are source-backed model/support concerns, not a newly reproduced stock-conservation failure. L4 carries other useful supply/loss and semantic-authority structures; this review does not call the entire N subsystem absent. Full acceptance needs explicit applied/soil/recovered/additional-dose definitions, compatible time/depth/area supports, actual management linkage, conservative pool transitions and recovery/formulation uncertainty. Demonstrate stock change equals inputs−uptake−losses across successive dates and revisions, not merely a one-time budget that sums independent season estimates.

### F15 — credit the repaired gates; do not infer full feasibility

Plan F15 lines 521–548, stage 5, dependencies F01/F06/F14; tasks 733–758. R3 AB-DEC-003 lines 1076–1078, AB-ECO-003 lines 1088–1090, AB-EXE-001 lines 1106–1108.

This bounded broad pass inspected current production; it **did not rerun the earlier 167-case repair harness**. Current code credit is precise: `runner.py` lines 292–316 normalizes finite numeric strings before modifiers; scheduler lines 345–410 normalizes planning/candidate UTC, rejects past instants and checks expiry against max(start,candidate); lines 412–473 convert m/s/knots/mph, reject invalid spray weather, and require wind/rain/min/max temperatures. Duplicate rows are checked symmetrically against action thresholds and merged conservatively at scheduler lines 179–250. `salinity_leaching.py` lines 79–175 block invalid rates/caps and inconsistent envelopes; lines 188–204 clamp adjustment inside retained bounds. Final invariants lines 61–135 reject invalid/below-min envelopes and prevent blocked confirmed schedules at 158–170. `runner.py` line 586 calls that final gate after constructing output. This credits earlier missing-weather, cap inflation, invalid-rate promotion, lower-bound and offset-past fixes without treating prior receipts as new evidence.

The **known 2E04 gust-only duplicate-unit seam is still visible**: scheduler lines 187–200 convert gusts to km/h, line 246 stores the normalized maximum, but lines 242–244 reset the common unit only when a speed value exists. With gust-only physically equal duplicates (3 m/s and 10.8 km/h), the representative inherits the first row's unit; m/s-first reparses 10.8 as 38.88 km/h at 412–426, whereas km/h-first reads 10.8. The resulting threshold classification can depend on order. This is a current-source confirmation of the known seam by direct arithmetic, not a newly executed fourth probe or a demonstrated physical actuation.

Normalization is still split: the drift gate recognizes m/s but not knots/mph at `spray_drift_gate.py` lines 41–42; scheduler recognizes all three at line 413. Scheduler is stricter for spray speed (15) than drift's speed limit (20), so the raw drift helper's result alone is not an emitted-output exploit. The final gate enforces card-local rates and statuses; it has no dated legal/budget/resource allocation evaluator in the checked function. `candidate_scenarios` and `feasibility_constraints` are not consumed by the checked ranker/runner. It does not establish immutable original constraints across arbitrary future modifiers or total area×dose budget feasibility merely because `max_safe` currently survives leaching.

Closure is F15's own four steps: one canonical normalized weather/support/quality contract before every modifier; normalize gust units independently of speed presence; preserve a source-backed original hard envelope; evaluate final aggregate resources, dated permissions, product/legal conditions and budgets after all modifiers/scheduling. Preserve all repaired controls and add both gust-only duplicate orders as a tight regression at the emitted-output seam. Daily forecast versus point-support policy must be explicit; current past-instant behavior alone cannot establish daily-interval usability or error without its intended support contract.

### F34 — valid accounting controls are not a qualified application ledger

Plan F34 lines 1017–1045, stage 7, dependencies F09/F11/F20; tasks 959–984. R3 AW-PRO-009 lines 612–614, AW-PRO-013 lines 628–630, AB-DAT-007 lines 683–685, AB-DAT-010 lines 695–697, AB-AGR-010 lines 882–884.

`src/app/api/inputs/route.ts` lines 70–110 check authentication, cycle ownership, finite positive quantity, finite cost and parseable date. Prisma `InputType` at schema lines 447–458 **does** restrict categories. The older plan statement that arbitrary types persist must not be repeated as a current finding. The route still accepts any truthy unit (line 95), defaults missing application date to now (89), permits a future date, and stores a product quantity without formulation, effective area, delivered status, event lineage or calibration/support fields. `InputLog` at schema lines 429–445 has a single appliedAt field and no purchase/stock/plan/delivery distinction. These are static contract gaps, not an executed API/database exploit.

The route creates a new input at 112–125, then separately reads costs and updates cycle total at 17–27/126. There is no request/event idempotency key or surrounding transaction in this path. A failed response after creation can leave retry semantics unresolved; concurrency/actual duplicated cost was not exercised. This should be closed at the durable accounting boundary, not by a client retry convention.

L3 already has management-event infrastructure: `layer3_decision/runner.py` lines 1638–1727 retain IDs, versions, cancellation and date-shift invalidation; 1729–1758 exclude planned/draft/proposed/pending/failed/cancelled/deleted statuses before summing irrigation. That is substantive partial credit. The compatibility intake also defaults absent status to applied (1638–1643), so it is not itself a proof-bearing delivery ledger. Checked L3/L4 targets do not read InputLog, and no InputLog→historical water/N conversion was traced in the staged scientific source. **A purchase or future InputLog contaminating the historical balance was not reproduced or established.** The remaining gap is the qualified, unit/formulation/area-correct, durable connection and lifecycle contract.

Closure: controlled dimensional units, separate financial/stock/planned/applied records, explicit elemental-N/product and L/mm-area conversions, verified application publication with namespace/provenance and an atomic idempotent cost update. Show purchase/future-plan exclusion and duplicate retry across the actual integration boundary, preserving legitimate financial zeros and current L3 cancellation/version behavior.

### T05 — heuristic economic baseline is present; empirical policy value is not established

Plan T05 lines 1350–1377, stage 14, dependencies F12/F13/F14/F15/T04; tasks 1954–1979. R3 AB-DEC-001/002/003 lines 1068–1078, AB-ECO-001/002/003/004 lines 1080–1094.

Current L7 EOE uses crop defaults or user-context price/cost overrides, calculates profit quantiles, break-even and ±10% sensitivities; those functions are present. `layer7_planning/runner.py` lines 212–245 actually uses economics to rank and derive suitability, with fixed 1000-point weights and an expected-profit/5000 scale. Its audit records user economic inputs at line 721. `ccl_crop_library.py` lines 36–53 supplies default price/cost assumptions, but those scalar defaults do not carry currency/date/location/quality/source identity. EOE sensitivities use a dollar string; other contracts carry EUR fields or InputLog DZD. No currency conversion/support contract is shown by the checked path.

L8 runner lines 477–493 excludes blocked/safe-observation cards from the action summary, then estimates cost as **sum(rate×2)**, yield percentage as impact×15, risk reduction as impact×20 and ROI from percentage yield divided by nominal cost. These are explicit heuristics, not dimensionally derived profit or ROI. `layer6_exec/outcomes/metrics.py` lines 234–266 similarly projects fixed impact coefficients. The scientific problem is not the mere existence of a baseline: joint yield/quality/price/cost dependence and observational qualification do not flow through it, and the F12 effect label is not independent policy-value evidence.

T05 remains a capability extension. Implement versioned contextual economic assumptions and shared joint samples, explicit no-action/measurement/intervention/abstention policies with the final hard feasibility gate, then evaluate policy value and information value against independent observed outcomes and all acquisition/operation costs. A useful calculator and a passing import cannot close the empirical milestones. The local skew mean-vs-median EOE case in D4 is an existing numerical contract defect; prospective decision value is a separate unimplemented/unverified target in this checked path.

## Deliverables and acceptance scope

- `package-status.json`: exactly eight package records, with verified slices, source/requirement references, dependencies, next steps and bounded acceptance.
- `probes.py` and `raw-results.json`: the three authored current-source groups and their complete outputs/controls.
- `import-manifest.json` and `source-manifest.json`: exact current production blobs, SHA256s, loader scope and normative-source identities.

These receipts support the explicit local behaviors and source integrations above. They do not close whole packages, certify main for autonomous actuation, establish causal effect, replace prospective calibration, or prove that each static gap is exploitable through a deployed UI.


---

# Specialist appendix — EO, ASMAE, MESIA and empirical qualification

# ASMAE/MESIA scientific software quality review

Reviewed commit: `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc` (frozen source supplied by the coordinator). Scope: exactly F25, F26, F27, F28, F29, F36, T03, T06 and T12. This is a bounded read-only review of scientific contracts, production call paths and implemented algorithms. It is not field acceptance, model validation or a claim about uninspected external research work.

The implementation has useful admission and validation controls, but the nine cards are not supported as complete. Three inert numerical probes reproduce EO identity/support defects and permissive weak-label eligibility. The RF learner has source-level axis, graph-mask and phase-objective defects. Existing geometric observability, ASMAE agreement and radiometric holdouts do not establish independent physiological observability or calibrated agronomic performance.

## Evidence and limits

`source-import-manifest.json` verifies the Git blob of all **24 audited production files** against the pinned tree, records SHA-256 and line count, records every imported production module used by the numerical probes, and hashes the supplied normative documents. All assigned target files were available. `assigned-cards.json` preserves the exact nine cards, including their steps, criteria, dependencies and R3 mappings. `package-status.json` has exactly nine package records with current behavior, verified slices, remaining criteria, references and bounded acceptance scope.

The normative sources were the supplied R3 scientific sections and the three repair/task/execution plans in `sr-team-review/plan`. Package status or historical audit claims were not used as implementation proof. F25–F29 are stage 9, F36 stage 11, T12 stage 12, T03/T06 stage 13. Dependencies remain as recorded in each exact card; completion of one slice does not close a whole card.

Exactly three numerical probes ran against production functions with synthetic arrays and inert objects. No repository tests, acquisition, external services, instrument access, RF transmission, training, production writes or Git mutations were used. Torch was unavailable; neither the RF network nor trainer/evaluator was executed. The EO failure probe uses a local deliberately failing session object, not a downloaded ONNX artifact. No field performance or biological meaning is inferred from these probes. Source being unchanged relative to an earlier commit is not evidence of feature absence.

Reproduce from the workspace:

```bash
PYTHONDONTWRITEBYTECODE=1 python /workspace/scratch/de6bc2428cec/wip-audit-2e1fbcb-2026-10-17/spatial/probes.py
PYTHONDONTWRITEBYTECODE=1 python /workspace/scratch/de6bc2428cec/wip-audit-2e1fbcb-2026-10-17/spatial/build_artifacts.py
```

Raw outcomes are in `raw-results.json`. The second command verifies source and builds records; it adds no numerical probe.

## Findings and passing controls

All code references below are relative to `source/services/agribrain/` at the pinned commit.

### F25: failed EO inference retains learned-backend identity

`layer1_fusion/eo_foundation_model.py:414–455` constructs a fixed statistic vector and calls the selected ONNX session. On exception it returns deterministic fallback features. `infer` still uses the selected mode to assign backend identity and confidence (`265–325`). The executed failure control produced the same embedding as explicit fallback, but reported `model_id=onnx_foundation` and mode `onnx`. The session input was `[1,48]`; the current adapter does not implement the documented image/band-specific input contracts for arbitrary foundation artifacts. This is an actual production-function fallback behavior under an injected backend failure, not a model-quality experiment.

The output contract at `65–81` does not bind artifact, preprocessing and calibration versions. Confidence uses mode/quality heuristics rather than measured domain calibration. These prevent closure of AB-ML-002, AB-ML-014 and AB-DAT-006.

The caller adds a second provenance inconsistency. `layer1_fusion/engine.py:700–805` initially marks derived EO evidence diagnostic, not production/provider truth. The common admission path calls `normalize_evidence_truth` (`807–824`); its EO branch (`truth_bridge.py:423–439`) sets `production_usable=True`, `real_provider_product=True`, `diagnostic_only=False`, irrespective of this backend outcome. **State updates, scientific surfaces and prescription permissions remain false.** The evidence therefore supports a provenance/diagnostic classification finding, not a claim that this path authorizes an irrigation prescription.

Closure requires reporting the actual backend outcome and failure reason, propagating that provenance through admission, and qualifying model-specific tensors, preprocessing, artifacts and confidence independently.

### F26: EO identity omits scientific support and missingness

The hash at `eo_foundation_model.py:611–627` consumes flattened formatted pixel values without binding band names, array dimensions, cloud mask, CRS or affine. The numerical probe found identical hashes for 2×2 and 1×4 arrays and for different band identities with equal values. Changing the cloud mask changed the embedding while preserving the hash. Missing B12 and genuine zero B12 produced identical actual 48-number feature vectors. Metadata does retain a band count, but that does not give the model a presence token. Misaligned band lengths were accepted.

Normalization at `336–405` has no common raster alignment contract. Fusion collects arrays and calls `infer(band_arrays)` without passing a cloud mask (`engine.py:710–728`). These are support-contract defects against AB-DAT-002/008/011 and AB-ML-002, not evidence that any particular geospatial product is inaccurate. Acceptance needs explicit bands/order/shape/dtype/scale/mask/CRS/affine identity, finite/alignment checks and missing tokens, followed separately by qualified radiometric/georegistration inputs.

### F27/F28: RF tensor, topology and complex-channel contracts remain open

The neural pipeline flattens `(B,L,S,features)` and restores directly to `(B,S,L,D)` (`mesia/learning/neural_receiver.py:133–144`). A reshape does not exchange link and time axes: restoring `(B,L,S,D)` followed by an explicit permutation is needed. The graph's `adjacency_mask` argument is ignored by `attn_mask=None`, and mean pooling includes every link (`59–82`); the public forward path supplies no validity or topology mask. Instrument normalization (`15–31`) has learnable parameters but no instrument-epoch input contract.

The trainer fixes decoder latent dimension at 128 (`masked_link_trainer.py:45–54`) while the receiver exposes configurable latent dimension. Magnitude and phase are masked independently at scalar entries (`57–70`), and phase reconstruction uses ordinary MSE (`79–80`). No separate padding/missingness mask excludes invalid support. These source-level defects leave AB-MES-009/010/011 and AB-ML-002/004 open. Torch was unavailable, so this audit does not claim an executed non-128 crash or measured training degradation.

Acceptance should include identity markers with unequal link/time dimensions, invalid-link and graph-path controls, a non-128 latent, paired complex masks, phase wrap equivalence and finite loss on explicit valid support. Those checks would qualify software behavior, not physiological interpretation.

### F29: geometry and teacher agreement have narrower meaning than biological validation

`mesia/learning/asmae_evaluator.py:15–46` maps four fixed labels and calculates `1 - SSres/(SStot+epsilon)`, despite Pearson wording. Configuration does not define the channel mapping, and constant targets receive an epsilon-adjusted number rather than an explicit undefined metric. ASMAE targets are a dependent teacher; agreement is not an independent biological reference.

`mesia/assimilation/observability_analyzer.py:61–127` forms kernel matrix `A`, then `AᵀA`, rank and condition. It does not construct a variable-specific biological Jacobian with measured instrument/noise/dependence covariance. The executed control correctly refused duplicated dependent profiles (rank 1 for two cells), and accepted orthogonal profiles (rank 2). The accepted certificate still reported empty strata, empty geometry epochs and depth zero. Those unknown limits are preferable to invented depth/stratum qualification, but `is_observable` should be interpreted as this algebraic geometry result only. The target capability string does not change the matrix physics.

Positive source controls exist: `likelihood_engine.py:28–140` leaves innovation/likelihood absent and support zero when observations are missing; `feature_extraction.py:168–211,248–291` distinguishes unresolved family priors with elevated uncertainty from resolved calibration and checks applicability/time bounds. These are real partial implementations. Default registered calibration records and fixed family/feature values (`feature_extraction.py:20–111,293–331`) are not evidence of a measured commissioning campaign.

AB-MES-012/014 and AB-ASM-003 require independent nuisance-discriminating measurements, per-state sensitivity/covariance and held-out biological evaluation. This probe establishes a geometric guard only.

### F36: export gates exist, but per-state qualification can be replaced by common flags

The exporter explicitly labels outputs `weak_assimilated_reference`, caps weights at 0.3, rejects global unusability and supports per-state blocked lists (`layer05_asmae/training/exporter.py:77–193`). These controls passed: global unusability zeroed every weight; blocking the first state gave `[0,0.3]` for the first two states.

With one synthetic state vector and common passing producer flags, absent uncertainty became sigma 0.1 and all thirteen coordinates received weight 0.3. This follows the default and common `retro_score`/BMA gates at `132–175`. The production export wrapper (`layer05_asmae/engine.py:1576–1599`) does not add an independent per-coordinate reference/operator qualification ledger. The probe demonstrates permissiveness of this contract, not that a real run has produced false biological values. Weak labels may be useful, but their allowed roles and uncertainty must follow each variable's actual support.

Substantial temporal/radiometric work is present. Index/state rules declare forbidden updates (`observation/index_state_mapping.py:11–64`). Radiometric code distinguishes proxy credit from per-scene/per-pixel operator checks (`constraints/radiometric.py:73–139`). Retrovalidation rebuilds training-only operators and initialization, checks forecast issuance/cutoffs, separates historical forcing from prospective forecasts, conditions event availability, and requires successful assimilation reruns (`retrovalidation/engine.py:300–330,429–490,527–550,680–700`). Its result separates prospective and reconstruction scores (`863–882`); aggregate `retro_score` can fall back to reconstruction (`757–767`). That aggregate cannot substitute for prospective skill at every coordinate/horizon.

Remaining AB-ASM-003/011/013–016 acceptance needs per-state operator/reference support, known uncertainty, dependence groups, explicit prospective/reconstruction label eligibility and independent physiological calibration. Existing holdouts and diagnostic consistency should be retained.

### T03: architecture and artifact registration are implemented primitives

The reviewed source contains EO/RF encoders and a shadow-expert registry, not evidence of completed longitudinal multimodal foundation capability. `asmae_learn/model_registry.py:12–56,84–87,135–141` has status stages, safe JSON/NPZ loading and artifact/data hash requirements. Approval requires nonempty holdout metrics (`169–172`); the inspected predictor applies `weights[0]` to `state[0]` (`177–214`). These are concrete implemented slices.

This audit did not establish frozen small baselines, independent blocked corpus gains, temporal multimodal objectives, calibrated OOD, parent/local adapter provenance and rollback, rich-to-sparse validation or distributed privacy/consent/aggregation performance. These AB-ML-002/003/004/009–013 targets require experiments and artifacts. Their absence cannot be inferred merely from an open task card or unchanged code, and no such inference is made here.

### T06: file ingestion and abstention exist; native metrology remains a separate target

`mesia/lanes/wifi/csi_extractor.py:25–99` implements CSI packing and SigMF output; native `capture_frame` explicitly raises `NotImplementedError`. The reader (`102–195`) requires data/metadata and quarantines absent/corrupt metadata, but can fill missing health quantities with defaults such as noise floor and RSSI. Pair length, native axes, two-clock uncertainty, hash verification and physical calibration are not established by this file format path.

`mesia/service.py:857–971` reads native files and uses fixed amplitude/loss/CWI transforms and heuristic confidence; missing input returns awaiting-stream rather than a physical measurement. The lattice implements consistent north-up center/inverse mapping and boundary mask checks (`assimilation/spatial_lattice.py:49–175`), but not the full rotated affine. Geometry kernels are analytical Fresnel/Gaussian assumptions (`sensitivity_kernels.py:32–72`). These provide software structure, not measured per-variable RF sensitivity.

Important positive authority boundaries remain: service validation without a qualified independent holdout stays `NOT_EVALUATED`/`RESEARCH_ONLY` (`1010–1180`), and the central scan submits `is_calibration_valid=False,is_epoch_active=False`, then abstains on unusable evidence (`2628–2668`). Diagnostic fixed drift/pose/leakage values (`2178–2197`) do not override this central gate. Thus this audit does not claim the demonstrator acquires biological authority merely because it produces a physical-looking scalar.

T06 acceptance still needs native driver/acquisition qualification, two clocks and uncertainties, instrument/antenna/firmware/pose epochs, full spatial support, measured covariance/sensitivity, nuisance controls and controlled recalibration. No instruments or radio services were used in this review.

### T12: registry QA and holdouts do not establish a field reference program

`ground_truth/schemas.py:12–39` records evidence identity, support, confidence and authority flags. `ground_truth/registry.py:25–40` keeps plot-scoped pools. Its drone QA substitutes fallback coverage/RMSE/dimensions/geography for missing metadata (`88–138,173–188`), then evaluates thresholds (`211–268`). Authority boosts also require caller flags: the finding is not that every metadata-free file is automatically physical ground truth. The quality defaults still need explicit unknown handling before they can support metrological assertions.

Training-only image holdouts and teacher agreement are implemented as described above. Neither is an independent depth-resolved water/EC, irrigation-delivery, canopy/phenology and agronomic-outcome reference campaign. The bounded code review cannot establish that no such external data or field work exists. It establishes that the reviewed artifacts do not supply the preregistered cohorts, calibrated independent measurements, perturbations, baseline comparisons and domain/horizon acceptance evidence required for T12 and AB-ASM-016, AB-AGR-011/012, AB-MES-014, AB-ML-009/010 and AB-OMG-013/015.

## Closure sequence

First repair EO identity/support and RF tensor/complex-mask contracts. Preserve the implemented missingness, abstention, weak-label and training-only holdout controls. Next require per-variable qualification and dependence/uncertainty ledgers before any aggregate score grants training eligibility or capability. Only then qualify instrument metrology and execute preregistered independent reference/model-baseline studies. Numerical software controls and scientific field acceptance are separate deliverables throughout.


---

# Specialist appendix — Execution, telemetry and drone runtime

# Runtime WIP audit — six master-plan cards

At exact commit **`2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`**, F16/F17/F18/F19/F35/F39 contain substantial implementation, but **none receives full acceptance from this bounded audit**. The strongest remaining concrete failures are transport-only STOP confirmation and mutable, non-durable raw telemetry. Debounce, stable violation keys and no-telemetry watchdog evaluation have working slices. Optional drone import handling and the ordinary supervisor timeout cleanup also deserve fixing credit.

`package-status.json` contains exactly the six assigned cards, their remaining criteria, dependencies and line-specific evidence. `source-import-manifest.json` verifies 26 reviewed production files and 16 actually imported production files against the exact Git tree, with document hashes and a bounded callsite inventory. This audit uses **three newly authored offline probes only**, not repository tests, audits or previous protocol-result artifacts.

## Findings by severity and evidence

### RT-01 — P1: concrete drivers can certify STOP from transport acceptance

**Fresh production-code counterexamples with inert transport collaborators.** A Modbus coil write returns its normal success ACK while the independent running register remains 1. Real `ModbusActuator._stop_zone` returns success; the real base STOP path changes the cache to ONLINE and removes the active delivery command. A subsequent real `get_status` reports EXECUTING, now without the command. The STOP path reads the totalizer but does not verify the running bit before its successful return: [`modbus_driver.py:334–379`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/drivers/modbus_driver.py#L334-L379), [`466–488`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/drivers/modbus_driver.py#L466-L488), and [`actuator.py:345–359`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/actuator.py#L345-L359).

The comparative LoRaWAN control supplies only successful network-server queue acceptance. Production code returns command success, and the same base cleanup clears ownership and publishes ONLINE. Its status method returns the cache; its emergency STOP also maps queue success directly to success without a device confirmation. See [`lorawan_driver.py:294–304`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/drivers/lorawan_driver.py#L294-L304), [`338–358`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/drivers/lorawan_driver.py#L338-L358).

`driver-stop-results.json` records both results. These fixtures do not establish a deployed hardware malfunction; they demonstrate that accepted transport traffic is sufficient to discard ownership despite absent or contrary stopped evidence. This leaves F17's physical-completion criterion unmet and limits F18 recovery. HTTP has an adjacent **static-only** acceptance policy: HTTP 202 counts as success and STOP forwards that result (`http_driver.py:253–254,371–384`). No vendor API meaning was commissioned here.

**Acceptance:** an adapter must distinguish accepted/confirmed/unknown. Retain ownership and STOP_REQUESTED monitoring until a current stopped receipt/readback confirms the operation.

### RT-02 — P1: immutable telemetry and replay continuity remain incomplete

**Fresh local immutability/continuity counterexample.** `storage.py` puts the caller's raw object directly in a process dictionary and returns the same reference. Changing the original payload from 20 to 99 changes stored evidence; mutating returned provenance also changes the store. Duplicate ID rejection works within that process. Reloading the storage module loses the accepted raw message. Normalized storage is likewise a process-local growing list: [`storage.py:5–20`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/sensor_runtime/storage.py#L5-L20). Evidence: `sensor-storage-results.json`.

**Static cross-module inference:** persistent nonce admission happens before nonvolatile raw storage (`ingestion.py:79–85,184–201`; `security.py:314–349`). After process loss, a nonce can survive while its only raw corpus copy does not; a retry can therefore be rejected without a recoverable raw observation. The `s3://raw-sensors/...` reference is constructed as text; this storage call does not upload it. This consequence was not exercised as a complete ingestion-crash probe.

The old split nonce check/write finding must not be repeated: eligibility and insertion now share a file lock. Full F39 acceptance still needs scoped keys, restart/replica qualification and retention. Keys use `message_id` alone, and nonce/rate identities and per-plot locks lack declared retention budgets. Some caches improved: the snapshot cache has scoped identity and periodic clearing, and surface payload memory has a two-entry limit (`main.py:475–498,3803–3830`). The bbox dictionary remains plot-ID keyed without a geometry epoch (`tile_proxy.py:65–71`); no active wrong-tile reuse or OOM was reproduced.

**Acceptance:** commit immutable raw/normalized telemetry durably with replay admission/recovery continuity, then bound caches and keyed-lock lifetimes without erasing the evidence corpus.

### RT-03 — P1: active manual protection is not rehydrated

**Fresh monitor lifecycle witness plus static persistence gap.** A five-second pressure debounce emits `[0,0,1,0,0,0]` at 0/4/5/6/7/8 seconds, including missing and NaN readings. Sustained pressure produces one active violation; missing/nonfinite values do not clear it. These fix slices pass.

A newly constructed monitor has zero active violations and restarts debounce under the same breach. Active violation and breach state are instance dictionaries (`safety.py:1772–1788`); the reviewed dispatcher restart code reconstructs events/reservations without restoring those protection dictionaries. See [`safety.py:1772–1788`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/irrigation_runtime/safety.py#L1772-L1788), `2142–2209,2471–2506`, and `safety-lifecycle-results.json`.

This is an instance lifecycle counterexample, not a full process-restart actuation-bypass proof. F19 still needs durable protection receipts and qualified reset/recovery semantics independently of water reservations.

### RT-04 — P1 static: drone capability and narrow cleanup failures remain

Missing optional drivers are now caught, so an absent mock driver no longer causes the old unconditional dispatcher-import failure (`drone_control/dispatcher.py:43–67`). The exact tree contains no mock driver, while the route still defaults to `mock` (`app/drone_routes.py:89–99`): the default capability is unavailable, rather than a verified simulator.

MAVSDK is registered as a normal driver, but its ready state and connect/arm/start ACKs are stubs; telemetry is empty. If the rest of a request passes preflight and compilation, the dispatcher treats nonterminal stream exhaustion as COMPLETED. This is a **static reachable-path assessment**, not a fourth runtime probe or proof that synthetic data has entered scientific observations: [`mavsdk_driver.py:55–102`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/drone_control/drivers/mavsdk_driver.py#L55-L102), [`119–127`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/drone_control/drivers/mavsdk_driver.py#L119-L127), `dispatcher.py:240–253`.

The ASMAE supervisor's normal timeout branch correctly terminates/waits/kills/waits. The narrower metadata-update failure branch calls kill after failed wait, then unlinks ownership and frees the executor slot without another wait: [`background_jobs.py:1927–1939`](https://github.com/webClone/AgriWise/blob/2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc/services/agribrain/layer05_asmae/background_jobs.py#L1927-L1939), versus `1975–1982`. New process sessions exist, but complete process-group termination is not demonstrated by single-child terminate/kill calls. No child was launched; do not convert this into a blanket orphan-child claim.

**Acceptance:** report unimplemented real capabilities as unavailable, gate simulation explicitly, require mission completion evidence, and confirm child/group exit before releasing ownership on every cleanup branch.

## Remaining integration and capability work

F16's core deadline calculation is monotonic and can emit without telemetry; the fresh control confirms this when `evaluate(None)` is called. It is a passive evaluation, not proof of an owned periodic timer. In **552 staged production service Python files** searched by AST, no call to `check_execution_status` or `reconcile_on_restart` was found. This is a bounded source inventory, **not an assertion that every external deployment lacks an orchestrator**. Treat periodic-owner/startup-recovery integration as an unaccepted package criterion. Quota reservation precedes dispatch without a telemetry gate (`dispatcher.py:410–425`), but this audit did not spend its probe budget on the full zero-budget telemetry matrix or concurrency conservation. The API also permits `budget=None`; missing-budget permission and critical-sensor freshness need explicit policy.

F18 has stable `OP-event` retry identity and conservative unknown-outcome handling. Its four concrete adapters do not implement `get_operation_status`; the base returns None, and the capability defaults false (`actuator.py:154–160,582–647`; `schemas.py:494`; `dispatcher.py:868–906`). This is an absent operation-receipt capability, not a new blind-retry failure. Real applied/not-applied attribution, safe own-operation retry and startup recovery remain to be demonstrated. The known current 2E01 resource-admission issue belongs to the root lane and was not reprobed here.

| Card | Stage | Current acceptance boundary |
|---|---:|---|
| F16 | 6 | Core quota/watchdog code present; periodic owner, policy and full integration acceptance open |
| F17 | 6 | Active-command machinery present; concrete STOP confirmation counterexamples remain |
| F18 | 6 | Conservative uncertainty present; concrete operation receipts and recovery integration incomplete |
| F19 | 6 | Debounce/dedup/no-normal-by-missingness verified; durable protection restoration incomplete |
| F35 | 11 | Optional imports and normal timeout cleanup improved; stub capability and exceptional cleanup gaps remain |
| F39 | 3 | Atomic nonce path improved; durable immutable corpus and scoped retention incomplete |

R3 section 183 and AB-EXE-002/003/004 govern the execution distinctions. F16 additionally maps AB-DEC-003; F18 maps AB-ARC-008; F35 maps AW-PRO-011 and AB-ARC-006/008/012; F39 maps AB-DAT-001/003/011/013 and AB-ARC-008/009. Exact master-card requirements/dependencies and all three plan hashes are recorded in the coverage and source manifest. Full acceptance undemonstrated does not mean all code is absent.

## Reproduction and limits

Run from the workspace root:

```bash
PYTHONDONTWRITEBYTECODE=1 python wip-audit-2e1fbcb-2026-10-17/runtime/probe_driver_stop.py
PYTHONDONTWRITEBYTECODE=1 python wip-audit-2e1fbcb-2026-10-17/runtime/probe_sensor_storage.py
PYTHONDONTWRITEBYTECODE=1 python wip-audit-2e1fbcb-2026-10-17/runtime/probe_safety_lifecycle.py
PYTHONDONTWRITEBYTECODE=1 python wip-audit-2e1fbcb-2026-10-17/runtime/build_manifest.py
```

The last command only hashes/parses source. Exactly three behavioral probes were used. All collaborators are inert and all files they write stay in this runtime lane. No broker, controller, drone, vendor service or network sensor was contacted; no production or Git edits occurred. Prior protocol matrices and repository tests/audits were excluded as proof. No full field commissioning, concurrency, OOM or complete process-restart experiment is claimed.


---

# Specialist appendix — Learning corpus, World Model and Omega

# Learning, world-model and Omega WIP audit — 2e1fbcb

Exact candidate: **`2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`**. Assigned scope: **F21, F22, F23, F24, T02, T04, T07**. This is a master-plan readiness audit, not another patch-only review.

There are substantive foundations: canonical payload/partition identities; a bitemporal extractor; weak-label exclusions and lineage-bearing datasets; an actual crop classifier training API with fold-local preprocessing and a separate release gate; a forecast archive; daily mechanistic forecasts and held-out observation evaluation; and an Omega surprise-to-proposal path. They do not yet compose into the objective-specific frozen learning corpus, learned conservative hybrid world model or end-to-end scientific investigation loop required by the plan.

F21/F22 still reproduce their core source defects. F23 has the repaired standalone archive mechanisms, with corpus/production integration not established here. F24 remains partial for the retained small-percent parser defect, independent-target qualification and sparse-score convention. T02/T04/T07 are **partially implemented capability extensions**, not blanket claims that all learning, dynamics or scientific investigation is absent.

## Evidence, limits and reproduction

Exactly **three new inert offline scenarios** ran against production methods; `results.json` contains raw outcomes and `probes.py` reproduces them. All **44 imported source blobs** matched the exact candidate tree; `import-manifest.json` lists them. `source-receipts.json` additionally verifies 27 statically traced files. No repository tests, audit reports or historical results were used as proof. No external jobs/services, production/Git edits or hardware were invoked. Clock substitution and model-path redirection occurred only in the private process and local fixtures.

```bash
python /workspace/scratch/de6bc2428cec/wip-audit-2e1fbcb-2026-10-17/learning/probes.py
```

Keep the sibling exact `source` tree and `git-tree.json`; the script checks core/imported blob hashes, disables bytecode writes and creates a fresh `learning/isolated` directory. It uses the production canonical file writer/extractor, ASMAE ledger builder/split/registry and Omega scalar methods. No fitting job, deployed BMA expert, experiment execution or measured field outcome was claimed. The earlier 26-case archive suite was **not rerun**; F23/F24 below distinguish current source inspection and retained known findings from these three new scenarios.

References below are relative to `source/services/agribrain/` (**HE** historical_extractor; **CW** canonical_worldline; **DB** asmae_learn/dataset_builder; **MR** asmae_learn/model_registry; **FA** world_model/forecast_archive; **FP** layer05_asmae/retrovalidation/future_projection; **RE** retrovalidation/engine; **CF** layer2_veg_int/labels/classifier). Exact full paths are in `source-receipts.json` and `package-status.json`.

## Package assessment

| Package | Current assessment | Evidence boundary |
|---|---|---|
| F21 | Core issued-window immutability defect remains; identity scope incomplete | New real writer→extractor scenario |
| F22 | Universal timing rule still rejects valid earlier-issued forecast inputs | Same new scenario, with future-measurement/late-knowledge controls |
| F23 | Repaired archive foundation present; full dependency/integration sign-off pending | Current static production source; no archive suite rerun |
| F24 | Validation repairs present; retained parser/scientific criteria incomplete | Current source, retained known 2E03 behavior; no new scoring probe |
| T02 | Several real dataset/train paths; unified objective-specific frozen corpus incomplete | New ASMAE dataset/registry scenario plus static crop-training trace |
| T04 | Actual mechanistic daily rollout/evaluation exists; learned hybrid and causal validation are target work | Static runtime call-path trace |
| T07 | Real surprise/proposal and diagnostic foundations; complete scientific case/experiment/replication loop is target work | New surprise→proposal scenario plus static runtime trace |

### F21 — frozen windows and partition identity

**Confirmed defect:** HE's frozen dataclass contains mutable dictionaries (71–89); extraction returns the same nested event objects it assembled (242–254). In scenario 1, an issued window value changes **1→99**, its `window_hash` stays unchanged, and a fresh canonical reload returns the original **1** with that same hash. This is mutation of the issued training object, not mutation of disk. `to_dict` exposes counts/hash but not a canonical event snapshot (116–130), and no digest recheck is part of this loader interface.

The hash includes only plot, time range, cutoff and sorted active IDs (229–240). It omits explicit tenant/namespace, extraction policy/schema, geometry/cycle, payload snapshots and ordered ancestry/correction resolution. **Qualification:** current canonical event identities do include payload hash and partition identity (CW 593–627). The scenario confirms nonempty canonical events and their window hashes differ across tenants. It does not reproduce a nonempty collision through that writer. Empty windows for different tenant partitions do collide. This positive canonical identity control must be preserved while fixing the window contract.

Supersession resolution uses three payload fields on knowledge-known events (HE 214–227); it is not a complete sealed retraction/revision/dependency manifest. Acceptance: immutable/deep snapshots; canonical manifest covering partition, payload/schema, geometry/cycle, extraction policy, ordered parent evidence and resolution; digest verification before dataset load and model artifact creation. Any included content change changes identity, while caller mutation cannot alter an issued object. Dependencies: F02/F09. Plan 678–702; R3 AB-DAT-011 699–701, AB-DAT-013 707–709, AB-ML-001 974–976, AB-ML-007 998–1000.

### F22 — event-role timing and input/target separation

**Confirmed defect:** HE 193–194 quarantines every event with knowledge time earlier than its event/valid time. Scenario 1 commits a weather forecast Jan 2, valid Jan 3; it is rejected as `causality_violation_knowledge_precedes_event`. A planned Jan 3 management scenario is rejected by the same rule. Future measurement and Jan 4-committed Jan 1 observation are appropriately excluded, providing positive controls. The planned action is not miscounted as applied water in this scenario; the failure is losing a legitimate known scenario input.

The extractor has one events/active-events view and a universal root cutoff (179–212). It does not emit separate objective input, later-target and retrospective manifests, or validate every child's availability and revision against cutoff. A later outcome can be a legitimate training target; applying the predictive-input cutoff to it indiscriminately would be another error. Contracts do provide action lifecycle fields and `is_physically_realized` (world_model/contracts 224–274), a usable foundation for role-aware separation.

Acceptance: observation chronology for measurements; issuance/availability checks for forecasts and plans; input-parent/revision cutoff checks; separate target/outcome and reconstruction roles, without turning a plan into realized exposure. Dependencies F02/F21. Plan 704–728; R3 AB-DAT-004 671–673, AB-DAT-014 711–713, AB-ML-008 1002–1004.

### F23 — archive foundation versus integrated prospective corpus

Current FA has complete-temp/fsync/conditional-link publication with strict JSON (30–58), ingress snapshot/validation and durable conflict resolution before cache (479–527), explicit corrupt-record errors (529–588), and durable evaluation before deduplicated cache append (720–729). These are real corrections, not stubs. Current-source inspection supports the repaired architecture; this audit does not relabel the retained 26-case receipts as new execution.

The inspected runtime paths use held-out fold state and forecasts in RE/FP; a call to commit those forecasts into `ImmutableForecastArchive` was not found in those paths. The class/export alone does not establish that every published prospective score is based on a sealed pre-observation archive. Scope this as integration/readiness evidence, not proof that no caller exists anywhere outside the inspected source. Acceptance: preserve repaired conflict/concurrency/mutation/corruption controls, wire the objective-specific forecast/evidence identity through the actual evaluation path, and satisfy F21/F22 dependencies. Plan 730–753; R3 AB-DAT-011 699–701, AB-ARC-007 746–748, AB-ARC-008 750–752, AB-ASM-014 828–830.

### F24 — supported forecasts and honest score conventions

FA now validates finite numbers, ordered/deduplicated levels, effective timezone offsets and horizon agreement (187–276, 350–405), leaves unsupported partial metrics unavailable (664–689), and uses 1.28155σ for Gaussian P10/P90 (691–697). YF base/posterior methods use the same multiplier (104–131, 224–244). These implemented slices should be retained. In particular, original FC04 bare numeric-percent metric extraction and FC06 effective-offset rejection retain their repair credit; the small-percent-prefix issue is a different known current defect. This audit inspects those current source mechanisms without claiming a fresh archive-suite execution.

The **known 2E03 small-percent defect remains in current source**: shared parser 191–201 divides p/q values only when greater than 1, so p1 aliases p100 and p0.5 becomes a median instead of a half-percent level under the prior p-percent grammar. This audit does not count it as newly discovered or rerun its earlier numeric scenario. Declare an unambiguous grammar and use it consistently through all callers.

Other retained criteria: a nonblank evidence ID is not a qualified independent target receipt; defaults `in_domain`/`observation_space` (442–443, 636–647, 707–718) do not establish variable/unit/support/role/availability. The unweighted finite pinball average (209–218, 247–255) still needs accurate naming/grid weights or a documented CRPS integration convention. A valid point mass can legitimately score zero; zero is not inherently false credit. Acceptance: supported target binding, declared interval/score levels, unavailable reasons and domain/horizon calibration. Dependencies F13/F23. Plan 755–779; R3 AB-ML-005 990–992, AB-ML-010 1010–1012, AB-ASM-016 836–838; AB-DAT-005 675–677 supports zero/missingness.

### T02 — actual learning paths and objective-specific corpus readiness

Three distinct foundations exist and should not be conflated:

1. **ASMAE state candidates:** candidate_builder 21–179 checks lineage, diagnostics and external validation; DB 23–203 replays validation/candidate/revocation records, excludes weak/visual/diagnostic/action targets, and emits lineage-bearing samples. Its deterministic hash and plot-disjoint split are real (17–21, 205–268). The weak-label exporter retains `weak_assimilated_reference`, zero-weight reasons and a maximum weight rather than claiming ground truth (layer05_asmae/training/exporter 97–193).
2. **Crop classification:** actual API `/v2/crop-model/train` (app/main 5145–5205) builds a `TrainingDatasetBuilder`, calls `HierarchicalCropClassifier.train`, and can reload saved output. Crop builder enforces trusted source/partitions and a typed feature-input receipt (labels/dataset_builder 153–231). The snapshot authority reconstructs observation identities/tensor/hash from tokens rather than trusting a self-consistent JSON hash (app/crop_training_snapshot_authority 90–156). Classifier handles partial hierarchy labels and has fold-local median imputation for validation (CF 779–900). The all-data imputer at 796–798 is used for the final fit; it is not used to impute validation folds. Training defaults to non-production and requires separate external release/calibration evidence (CF 116–218, 915–967).
3. **ASMAE expert registry:** MR verifies executable artifact bytes and safe JSON/NPZ references (39–56, 114–143), has candidate/shadow/evaluation/approved-shadow states, and a prediction path scaling the first state component (177–214). BMA can discover approved models behind its enable flag (bma/posterior 149–181), with additional downstream expert proof gates. This is not the same release contract as crop classification.

**New scenario 2:** zero target is preserved, weak-label flag excludes that run, plot splits are disjoint and artifact-byte corruption is detected. The same ledger builder admits a **NaN target** because it checks only non-None value/confidence (DB 158–163), then emits no label observation/record timestamps (185–200). This confirms dataset numeric/role eligibility is not established by external source names and nonempty lineage strings. It does not imply later labels are categorically leakage: later independent targets are valid when their role is explicit.

The isolated admin-level MR fixture reaches `approved_shadow_expert` using nonempty placeholder evaluation/holdout dictionaries (146–175). This demonstrates a local presence check, not measured model quality or a deployed production/machine authorization. `training_dataset_hash` is required as text (84–87), without loading/regenerating its dataset or verifying a frozen split artifact. These checks cannot substitute for the objective-specific ModelArtifact contract.

Remaining T02 work: per-objective tokens/masks, target-support and synthetic/partial-data eligibility; frozen content/partition/input-target ancestry manifests; farm/site/season/instrument/derived-parent holdouts before preprocessing; consent/licensing/calibration/versioned regeneration. No end-to-end byte-for-byte corpus regeneration or independent objective result was demonstrated in this bounded audit. Dependencies F21/F22/F25/F26/F36/T01. Plan 1269–1293; R3 AB-ML-001 974–976, AB-ML-006 994–996, AB-ML-007 998–1000, AB-ML-008 1002–1004, AB-ML-014 1026–1028, AB-ML-015 1030–1032.

### T04 — mechanistic prediction exists; learned hybrid/counterfactual validation remains target work

Actual path: RE reruns fold assimilation (360–378), determines training→holdout horizon (385–399), classifies archived issuance weather versus historical forcing/persistence (401–491), qualifies management availability (495–550), then calls FP (558–583). It publishes prospective and retrospective error fields separately (578–579). This is valuable existing temporal provenance handling and should survive the F22 redesign.

FP predicts through a held-out observation operator with scene/support/shape guards (17–77), computes persistence, advances via the actual shared daily `forecast_step` / `_forecast_elapsed_interval`, and evaluates the propagated state with persistence-relative skill (157–295). Assimilation/filter 755–962 contains driver-dependent water/vegetation/nutrient heuristic dynamics and bounds, including action-status checks. This is more than an empty archive contract, but it is not evidence of a fitted bounded residual transition, joint X/Z/future-observation distributions or learned memory sufficiency.

Remaining T04 criteria are target extensions: explicit conservative residual ledgers; learned residual uncertainty separated from mechanism and forcing/action; Markov/history and regime-change baselines; held-out prospective multi-horizon improvement; paired interventions only with delivered exposure/support/identification assumptions. Neither mechanistic bounds nor a field named `forecast_skill_score` establishes those scientific results. No new rollout execution or intervention experiment was run here. Dependencies T01/T02/T03/F23/F24/F12. Plan 1323–1347; R3 AB-WM-002 1044–1046, AB-WM-003 1048–1050, AB-WM-004 1052–1054, AB-WM-005 1056–1058, AB-WM-006 1060–1062.

### T07 — scientific investigation capability, not an authority label

**New scenario 3** establishes an actual first step: equal MESIA/ASMAE scalar means produce no surprise; a 0.3 VWC disagreement produces z≈6.708, KL≈64.921 bits and a referenced research experiment proposal. However, `mesia/omega/surprise_detector` compares one pair of Gaussian summaries and returns the same three hardcoded explanations (48–90); it does not test persistence across time or compare data/instrument/management/domain/parameter/structural inadequacy. `experiment_proposer` selects one of three RF band templates and defines expected gain as **0.8/0.6/0.4 × KL** (87–120). The observed 51.937 bits is exactly 0.8×KL, not measured or model-based expected discrimination between those explanations. Hierarchical aggregation uses inverse-variance mean/standard-error and count/10 coverage (hierarchical_aggregation 39–71); it does not substantiate the docstring's general spatial covariance/territorial representativeness claim.

Reusable scientific foundations also exist in diagnostic contracts: immutable evidence-linked assertions with confounders/identifiability and payload hashes (diagnostic_integration/contracts 154–232), dependency-aware contradiction/overlap findings (tribunal 151–239), and run-scoped ledger/graph finalization (runtime 57–115). The orchestrator actually ingests/finalizes that diagnostic path (orchestrator_v2/runner 3912–4020). These are useful parts of case evidence, not a completed sealed ScientificCase or epistemic theory-revision worldline. Promotion service is an operational eligibility boundary; it explicitly leaves machine execution false (promotion_service 236–244). Its existence is not scientific validation or the primary Omega result.

Remaining T07 work should be judged by a complete investigation: surprise→competing explanations and model-space adequacy→discriminating prediction→measurement-selection/cost/power/interference/stopping/consent plan→observed outcome→negative/inconclusive/falsification judgment→independent replication and domain-bound versioned knowledge. Bayesian/mechanistic likelihood/prior sensitivity, BEL/simulation adequacy, causal identification assumptions and candidate-equation physical/holdout checks must be explicit where used. No such end-to-end case was demonstrated in the inspected path. That is target readiness, not a claim that every investigation primitive is absent. Dependencies F12/F21/F36/T01/T02/T04. Plan 1405–1429; R3 AB-OMG-001…018 1176–1246, especially ScientificCase 1176–1178, experiment 1224–1226, falsification 1228–1230, replication 1232–1234 and discovery metrics 1240–1242.

## Sequencing and acceptance boundary

Use the three normative plan files in `sr-team-review/plan`, with the master plan ranges above and detailed task-card actions. Sequencing addendum lines **36/40/42/44** place F21–F24 in Stage 8, T02 in Stage 12, T04 in Stage 14 and T07 in Stage 16. The task list stages at **34/38/40/42** agree. The master plan **134** gates new training/evaluation artifacts on F21–F24 corrections; foundation existence alone does not close dependencies.

R3 references above use supplied `current-plan-review/R3_current_scientific_sections.txt`. The next useful acceptance work is a frozen objective-specific corpus slice with explicit later-label roles and holdout ancestry, connected to one prospectively archived forecast and one falsifiable scientific case. This audit does not authorize external training, experiments, promotion or machinery.


---

# Specialist appendix — AgriWise product, identity and operational publication

# Platform WIP audit — current main `2e1fbcb79ccf283d4614bfe0d5579a0597f7ddfc`

This bounded review covers exactly **11 packages**: F30,F31,F32,F33,F37,F38,F40,T08,T09,T10,T11. It reads current production source and authored offline controls; it does not adopt repository tests, audit claims, generated historical results or the unmerged PR as main behavior. No production, Git, service, DB, provider or hardware mutation occurred.

The clearest remaining defects are in active conversation identity, the independent advice path, persistence error handling, and degraded publication relation. Positive controls are retained: signed-session production API gating, owner checks on task/input mutations, dashboard503, fixed GaussianMixture/optional drone imports, accepted explicit-resolution scenes, corrected growth time spacing, and canonical map validation. Planned operational/institutional/voice/offline expansion is not counted as an automatic runtime bug.

## Evidence and count boundaries

Three authored offline probe groups ran: `memory_cache_probes.py`, `frontend_probes.cjs`, `platform_probes.py`; raw outputs have corresponding JSON files. TS functions are exact source type-erased by Node with DB/provider/auth/image seams; Python uses fresh configured subprocess imports or exact AST functions/assignments with named read/contract seams. These controls demonstrate local behavior, not a deployed service or full scientific run. Python3.12.14/Node24.19.0, dependency versions and available source corpus are recorded in `source-import-manifest.json`. The exact runtime corpus has674 matching blobs; that is not674 reviewed/imported files or full1674-file coverage. Nutrient schema count is18 dataclasses,17 resolved and1 failed; deferred annotations are not immediate import errors.

`source-receipt.json` verifies all target/ref source bytes against the current Git tree. `plan-metadata-results.json` verifies all3 normative plan blobs and all11 card requirement lists directly against master sections and supplied R3 IDs. The register has52 unique unchecked full-acceptance rows,0checked: this is register state only. Plan blobs: master08d378a65992de859369950599df198e64244f01; sequence40751038dc8760e91bc3ab115e30c5e28395953a; register8a564647af7e588802537817159117b349ff606b. R3 hash and exact per-ID line references are in metadata JSON.

## Findings that matter to acceptance

- **Conversation identity:** actual plot chat stores browser history under `agribrain_chat_<plot>` (or `default`), sends it to intent and run, while backend memory anchors by plot. More decisively, active run singleflight omits history but sends history to Python. Same plot/query/mode with different narratives coalesces into one outcome during concurrency. This proves missing identity dimensions by source trace; it is not an authorization bypass claim. The semantic-cache probe separately returns10kg for100kg across changed identities; production activation remains unproved. Its English negation token survives; Arabic tokenization is empty.
- **Advice:** `/advisor → /api/ai/chat → Gemini/static fallback` bypasses canonical claim artifacts. Signed production middleware protects the API, so this is an authenticated independent path. Missing key returns fixed fertilizer doses as success; quota errors in quick mode become successful content. getAIAdvice ignores farmContext, so browser-soil promotion is not asserted. `/v2/intent` only classifies and does not itself generate a plot response.
- **Product persistence:** five static calendar tasks; farm outage shown as empty; task optimistic UI ignores HTTP failure. Photo accepts a format-valid zone without membership query and returns success despite a raw rejected-write receipt. Input-create followed by failed total update returns500 after persistence; retry duplicates cost. The raw DB/provider seams are fixtures; no rows were written.
- **Failure/publication:** exact terminal no-data branch reads undefined ts; ASMAE failed-receipt dictionary reads undefined geometry_hash; MESIA unqualified string load uses fabricated default tenant/farm. Exact progress returns published for runA/finalA with headB after60seconds, and borrows headB when finalID absent. No canonical commit or whole orchestrator execution was performed. Caught receipt errors lose a ledger, not necessarily the original response.
- **Imports/introspection:** current selected imports pass, but qualified/bare mission enum/dataclass identities differ. Five selected annotation consumer cases fail; sensor and17of18 nutrient dataclasses pass. Full supported service/worker/CLI startup remains unvalidated in this environment.
- **Conditional numerical UI:** `AgriBrainChat.toolCalls → ToolResultRenderer.ml_predictYield → YieldChart` synthesizes a Gaussian width15%mean, labels peak-normalized values Probability%, and has step0/nonterminating loop for mean0. This is a source-level rendering contract defect; actual backend tool emission and browser manifestation were not established. No actuation effect is inferred.

## Package-by-package coverage

### F30 — Scope conversational memory and cache identity

**Status:** open: active thread identity gaps; semantic-cache activation unproved. Stage10; dependencies: F02, F09. R3: AB-L9-008, AB-L9-009, AB-DAT-013.

Layer9 opens sessions by plot only; persistent memory filenames and browser history are also plot-only. The active run singleflight key omits conversation history although executeRun sends it. The independent semantic cache ignores scope and numbers.

Verified slices:

- Exact memory class with inert schema/manager seams reuses the same session and active crop for the same plot. Exact semantic cache returns the cached 10 kg answer for a 100 kg question under a different tenant/user/plot/crop/language/policy/head after an unrelated seed entry. English not is preserved; Arabic yields no tokens.
- Fresh static caller trace: AgriBrainChat history -> intent -> authorized run; same plot/query/mode but different history produces the same execution key and concurrent callers receive one promise outcome. No production caller of semantic_cache was found in the selected current corpus.

Remaining criteria: Tenant/user/thread/cycle memory and explicit sharing authorization; cache state/policy/model/language/claim identity; quantities/negation and canonical artifact cache; production activation tracing.

Evidence: `services/agribrain/layer9_interface/runner.py:76-106`; `services/agribrain/layer9_interface/engines/conversation_memory.py:28-66,78-118`; `services/agribrain/layer9_interface/conversation_memory.py:96-145`; `services/agribrain/layer9_interface/engines/semantic_cache.py:58-66,111-140,145-199`; `src/components/farm/AgriBrainChat.tsx:464-488,548-588`; `src/app/api/agribrain/run/route.ts:179-204,459-472,851-869`.

Next step: Introduce one authorized conversation identity in storage and singleflight; make canonical advice identity include the actual conversational and scientific inputs. Trace semantic-cache callers before enabling it.

Acceptance limit: Component and static caller proof only. No live cross-user/tenant disclosure or dormant-cache production hit is claimed.

### F31 — Close the independent public AI advice path

**Status:** open: authenticated independent advice path. Stage10; dependencies: F01, F02, F15, F30. R3: AB-ARC-010, AB-L9-001, AB-L9-002, AB-L9-003, AW-PRO-018.

/advisor calls /api/ai/chat, which calls Gemini directly or static fallback without canonical claim identity. Production signed-session middleware protects this API. farmContext is accepted but getAIAdvice does not use it.

Verified slices:

- Exact current TypeScript route/provider seams: missing provider key returns success with static Arabic organic 10 t/ha and urea 100 kg/ha; quick quota failure returns HTTP200 success with error text.
- Intent proxy independently authenticates, limits query/history and calls /v2/intent; Python endpoint only classifies intent. The plot chat main pass instead calls authorized /api/agribrain/run.

Remaining criteria: Server-trusted plot evidence and plot-specific authorization in advice flow; canonical intent/claims/constraints/VisibleResponse; educational labeling, quotas/body limits and explicit unavailable provider results.

Evidence: `src/proxy.ts:19-71`; `src/app/advisor/page.tsx:68-101`; `src/app/api/ai/chat/route.ts:5-43`; `src/lib/agribrain/gemini-advisor.ts:78-147,178-267`; `src/app/api/agribrain/intent/route.ts:8-67`; `services/agribrain/app/main.py:2586-2602`; `src/app/api/agribrain/run/route.ts:831-869`.

Next step: Route advice through the plot-authorized canonical response boundary; type provider failure separately from content and require educational mode for generic material.

Acceptance limit: No anonymous production exploit, browser-soil promotion, scientific correctness of doses, or automatic actuation is asserted.

### F32 — Replace demo calendar and misleading empty/error application states

**Status:** partial: statistics failure handling passes; calendar/farm/task UI remain open. Stage10; dependencies: F09. R3: AW-PRO-008, AW-PRO-004, AB-DAT-005, AB-DAT-013.

Calendar displays five hardcoded Jan/Feb2026 tasks and readOnly checkboxes. Persisted CropTask update is owner-authorized. Farm DB exceptions become an empty list. CycleDashboard task UI does not check HTTP response status.

Verified slices:

- Exact TS DB-outage seams: stats returns503 with stats:null; farm loader returns empty farms. Static calendar has no task fetch/persist path.
- Active handleTaskToggle sends the task ID expected by the oddly named route; it updates local state before fetch, ignores res.ok, never rolls back on error and retains useState(tasks) across same-component refresh. The unused toggleTask helper is not counted as the active route bug.

Remaining criteria: Authorized date-range calendar; persistent assignment/timezone/deviation/exposure links; loading/empty/unauthorized/unavailable distinction; isolated demo namespace; HTTP-aware task rollback or retry reconciliation.

Evidence: `src/app/calendar/page.tsx:83-93,276-280`; `src/app/api/cycles/[id]/tasks/route.ts:17-52`; `src/app/farm/page.tsx:13-51,90-99`; `src/app/api/dashboard/stats/route.ts:6-75`; `src/components/farm/CycleDashboard.tsx:31-34,80-93,190`.

Next step: Wire calendar to scoped records, render farm outage explicitly, and reconcile task state with successful persisted response before marking completion.

Acceptance limit: Route DB mocks plus static React handler trace; no browser interaction/reload or real task-science linkage was executed. Development all-farm fallback is not described as production exposure.

### F33 — Validate photo zone ownership and database insert success

**Status:** open: photo zone and raw commit boundary. Stage10; dependencies: F01, F02, F09. R3: AW-PRO-005, AW-PRO-011, AB-DAT-013, AB-ARC-007.

Plot ownership and image constraints are checked; optional zone is only a 24-hex format check. Raw insert result is returned without checking success counts/write errors or canonical created evidence ID. Client AI confidence is demoted to0 and processing remains pending.

Verified slices:

- Exact TS route with authorized plot, arbitrary well-formed zone and raw {ok:1,n:0,writeErrors:[...]} inserts supplied zone in the command and returns HTTP200 success. Mock image parser isolates the persistence/ownership boundary; image validation itself was not bypassed or tested.

Remaining criteria: Resolve zone to authorized plot/geometry epoch; observation timing; canonical inserted evidence identity and checked raw outcome; durable admission/outbox and retry recovery.

Evidence: `src/app/api/evidence/add/route.ts:29-60,73-117`; `prisma/schema.prisma:162-190`; `src/lib/agribrain/authorize-plot.ts:1-100`.

Next step: Resolve zone membership, reject nonacknowledged insert outcomes and persist an idempotent evidence admission event with the created ID.

Acceptance limit: No real DB was contacted and no actual foreign-zone row was written. Future dates are parseable but the target policy remains unspecified.

### F37 — Repair optional imports and establish one Python package identity

**Status:** partial: selected cold imports fixed; package identity open. Stage0; dependencies: none. R3: AB-ARC-004, AB-ARC-008, AB-DAT-002.

GaussianMixture imports from sklearn.mixture. Optional drone drivers are isolated; no mock driver is available. Package bootstrap adds the internal agribrain directory to sys.path, permitting bare and qualified modules to coexist.

Verified slices:

- Fresh subprocess exact-current imports of segmentation and dispatcher succeed. Qualified and bare drone_mission load but MissionType and MissionIntent are distinct class objects.
- Active L1 engine imports .zone_engine. structural.py still uses bare MissionType beside qualified imports. No circular-import failure is asserted.

Remaining criteria: One installed namespace and coherent imports; all service/worker/CLI/public entrypoints under supported dependency extras; optional-backend capability disablement without unrelated failures.

Evidence: `services/agribrain/__init__.py:1-6`; `services/agribrain/layer1_fusion/segmentation.py:8`; `services/agribrain/layer1_fusion/engine.py:599`; `services/agribrain/drone_control/dispatcher.py:1-110`; `services/agribrain/layer0/perception/drone_rgb/structural.py:17-20`; `services/agribrain/app/main.py:1-70`.

Next step: Choose and install one package namespace, migrate callers/entrypoints together, and certify fresh entrypoints in the declared image with explicit extras.

Acceptance limit: Fresh configured-path subprocess controls only. Not a complete installed service image; review environment lacks FastAPI/Torch and differs from pinned NumPy/Pydantic.

### F38 — Restore failure ledgers, scoped loading and degraded publication

**Status:** partial fixes present; degraded ledger/publication defects remain. Stage10; dependencies: F01, F02, F09, F31, F37. R3: AB-DAT-005, AB-DAT-013, AB-ARC-005, AB-ARC-007, AB-ARC-008, AB-L9-002, AB-L10-001.

Terminal no-data uses undefined ts in run_orchestrator; failed ASMAE receipt uses undefined geometry_hash/inputs; progress may infer published from an unrelated head. MESIA string plot fallback creates default tenant/farm. Several earlier imports/resolution branches are fixed.

Verified slices:

- Exact AST terminal assignment raises NameError ts; exact failed receipt dictionary raises geometry_hash while original engine error remains separately returned; progress runA/finalA with headB gives published after60seconds, and missing finalID borrows headB.
- Exact MESIA raster loader with string plot performs default_tenant/default_farm lookup. Resolution10m scene and physical derivative0.05/day controls pass. statistics and IrrigationSystemType imports exist.
- Static _generate_arf_v2 has no intent parameter but reads intent in caught local compression/routing branches; user_mode is threaded. Synthetic bridge geometry names remain undefined. Guarded args in run_full_mode defaults mode; not an immediate NameError.

Remaining criteria: Committed no-data response with local timestamp; durable failure receipt; exact job-output publication relation including superseded heads; qualified MESIA scope; actual intent/mode; explicit geometry helper; durable rejected-scene diagnostics and recovery classification.

Evidence: `services/agribrain/orchestrator_v2/runner.py:1107,3005-3021`; `services/agribrain/layer05_asmae/runner.py:823-846`; `services/agribrain/app/main.py:594-629`; `services/agribrain/mesia/service.py:475-502`; `services/agribrain/orchestrator_v2/chat_adapter.py:578-589,1020-1085`; `services/agribrain/layer10_sire/l10_frontend_bridge.py:174-183`; `services/agribrain/layer05_asmae/geometry/external_scene_loader.py:1-190`; `services/agribrain/layer2_veg_int/growth_engine.py:24,285-310`; `services/agribrain/irrigation_runtime/dispatcher.py:61,934`; `services/agribrain/orchestrator_v2/run_entrypoint.py:1340-1370`.

Next step: Repair local variable scopes; reject unqualified namespace; derive publication relation only from the committed job receipt; verify each degraded branch through its canonical commit boundary.

Acceptance limit: AST isolates actual functions/assignments with explicit read seams. No entire orchestrator run, canonical commit, external provider or hardware was exercised; caught receipt loss is not a total service crash.

### F40 — Resolve annotation consumers and close verification evidence gaps

**Status:** open: deferred annotation consumers fail; verification scope bounded. Stage10; dependencies: F37, F38. R3: AB-ARC-004, AB-ARC-006, AB-ARC-012, AB-ML-014.

Module definitions generally load under postponed annotations, but selected get_type_hints consumers fail on unresolved np, PerVariableSupportLedger, Tuple and List.

Verified slices:

- Fresh imports + hints fail for Kalman.predict_missing_weather, BeliefStateSnapshot, CropDemandOutput and BoundedJobExecutor.get_active_worker_pids. Exact Correlator definition succeeds and hints fail Tuple.
- SensorDeviceRegistration hints pass.18 nutrient dataclasses inspected;17 resolve and CropDemandOutput fails. Module registry Dict annotation is not an immediate runtime import exception. Runtime/dependency versions and exact manifest supplied.

Remaining criteria: Resolve names for supported public schema consumers; inspect all18 cited files/public dataclass/Pydantic/tool registration; supported-runtime compile and cold decoration; separate secrets/history, portability and full-tree verification.

Evidence: `services/agribrain/layer0/kalman_engine.py:159`; `services/agribrain/world_model/belief_snapshot.py:46`; `services/agribrain/mesia/identity/correlators.py:10,20-24`; `services/agribrain/layer4_nutrients/schema.py:22,312`; `services/agribrain/layer05_asmae/background_jobs.py:21,147`; `services/agribrain/sensor_runtime/registry.py:7,85`.

Next step: Import resolvable annotation names and run supported schema consumers against the installed declared image; publish exact corpus/exclusions and separate audit receipts.

Acceptance limit: Five selected introspection cases, one positive schema and18 nutrient dataclasses only; not proof active tool registration fails or a full-repository syntax/security/schema certification.

### T08 — Finish AgriWise operational records and financial workflows

**Status:** target incomplete; concrete retry-reconciliation defect. Stage15; dependencies: F32, F33, F34, F09. R3: AW-PRO-001, AW-PRO-002, AW-PRO-005, AW-PRO-008, AW-PRO-009, AW-PRO-010, AW-PRO-012, AW-PRO-013, AW-PRO-014.

Farm/cycle/task/input/equipment/market/cooperative records form a persisted basis. Inputs authorize direct cycle ownership, then create/delete separately from recomputed totalCost. Typed livestock, stock/order/logistics/budget ledgers are not established by the selected schema.

Verified slices:

- Exact current input POST with DB seams: create persists100DZD; total write fails =>500; identical retry persists another100DZD row =>200,total200. No idempotency/transaction in route. Task update checks signed user and ownership.
- Schema distinguishes actual/estimated harvest yield, nullable planting evidence, inputs cost/currency, market price/trend, cooperative membership. These are foundations, not proof all target workflows exist.

Remaining criteria: Delegated farm/cycle/rotation/task resources; stock/equipment/exposure linkage; new livestock and market offer/order/quality/storage/transport domains; budget/realized/scenario reconciliation across retry/correction/cancellation.

Evidence: `src/app/api/inputs/route.ts:18-29,129-153,185-187`; `src/app/api/cycles/[id]/tasks/route.ts:17-52`; `prisma/schema.prisma:292-324,344-458,599-676`; `src/components/farm/CycleDashboard.tsx:80-93`.

Next step: Make input mutation and totals recoverable/idempotent; then implement the planned typed workflows with authorized persisted states and reconciliation.

Acceptance limit: One DB-seam retry reproduction; no actual finance database, concurrent write or full operational workflow acceptance. Planned module absence is a capability gap, not automatically a code defect.

### T09 — Unify language, voice, map and offline product projections

**Status:** target partial: canonical map foundations; inconsistent advice/rendering remains. Stage15; dependencies: F30, F31, F32, T01. R3: AW-PRO-003, AW-PRO-004, AW-PRO-006, AW-PRO-007, AW-PRO-015, AW-PRO-016, AW-PRO-017, AW-PRO-018, AB-L9-001, AB-L9-002, AB-L9-003, AB-L9-004, AB-L9-005, AB-L9-006, AB-L9-007, AB-L9-008, AB-L9-009, AB-L9-010, AB-L10-001.

Plot chat performs intent prepass then authorized run and renders ARF/text/tool results. Surface contracts validate run/publication IDs, proof and authorization metadata; latest surfaces route resolves scoped canonical head. Generic advisor remains independent. No offline mutation reconciliation or voice-fidelity flow was established in reviewed paths.

Verified slices:

- Static canonical-map positive trace: surfaces/latest authorizes plot, requests namespaced snapshot, rejects corrupt validation409 and exposes stale schema state; surface-contract checks publication-run identity and evidence/display states.
- AgriBrainChat renders ml_predictYield tool results through ToolResultRenderer -> YieldChart; widget assumes sigma15%mean, peak-normalizes curve to100 and labels tooltip Probability%. With mean0 step0 makes the loop nonterminating. Conditional source defect: actual backend tool emission was not established, no browser/probe.
- Arabic/French dictionaries exist; UI route and memory/cache claims do not establish semantic translation, accessibility or offline acceptance.

Remaining criteria: One canonical VisibleResponse/typed claim per visible answer; unified map/support/resolution; Arabic/French/voice value-negation fidelity; accessible rendering; offline pending/conflict/stale-cutoff reconciliation.

Evidence: `src/components/farm/AgriBrainChat.tsx:548-639,727-736`; `src/components/chat/widgets/ToolResultRenderer.tsx:10-18`; `src/components/chat/widgets/YieldChart.tsx:19-37,60-64`; `src/lib/agribrain/surface-contract.ts:31-110`; `src/app/api/agribrain/surfaces/latest/route.ts:35-115`; `services/agribrain/layer10_sire/runner.py:1370-1390`; `src/lib/i18n/dictionaries/ar.ts:1`; `src/lib/i18n/dictionaries/fr.ts:1`.

Next step: Unify response identity across views and use canonical uncertainty distributions; guard zero/invalid yield; add accepted voice/offline reconciliation flows with fidelity checks.

Acceptance limit: Static product trace, no browser/voice/offline runtime and no claim that absent selected voice code proves whole-tree absence. Yield widget exposure conditional; no actuation claim.

### T10 — Institutional aggregation and territorial world-model extension

**Status:** planned extension; foundations verified only. Stage16; dependencies: T04, T05, T08, T09. R3: AB-WM-007, AB-ECO-005, AW-PRO-014, AB-ARC-010, AB-ARC-011.

Cooperative membership and RegionalStats aggregate scalar/JSON product records; world_model/contracts defines validated plot state, disturbance and action vectors with optional covariance. These do not by themselves establish regional policy effects or privacy-preserving cohort authorization.

Verified slices:

- Fresh schema and world-model source trace: region keyed by wilaya/period/start; cooperative member uniqueness; plot-state physical ranges/covariance. No independent regional evaluation or cohort suppression was established in these targets.

Remaining criteria: Authorized cohorts and small-group suppression; hierarchical supply/water/market/environment uncertainty; independent territorial outcomes; scenario versus observed policy effects; sovereign licensing/egress/review/appeal.

Evidence: `prisma/schema.prisma:642-676,764-790`; `services/agribrain/world_model/contracts.py:36-80,84-142,174-194`.

Next step: Implement the proposed institutional contract and evaluate on independent regional cohorts before claiming territorial capability.

Acceptance limit: Target extension only. This pass does not label missing research/evaluation as a runtime defect and does not certify sovereign deployment.

### T11 — Operational reproducibility, provider resilience and publication integrity

**Status:** target partial: substantial resilience foundations; exact publication relation open. Stage11; dependencies: F09, F23, F25, F31, F35. R3: AB-ARC-004, AB-ARC-005, AB-ARC-006, AB-ARC-007, AB-ARC-008, AB-ARC-009, AB-ARC-010, AB-ARC-011, AB-ARC-012, AB-DAT-001, AB-DAT-002, AB-DAT-009, AB-ASM-006, AB-ASM-007, AB-ASM-008.

Request broker validates raster/temporal contracts, guards providers with circuit state and retains stale temporal evidence on failed refresh. Durable ASMAE jobs have namespaced manifests, locks, leases/generation and bounded worker recovery. Legacy LocalJsonStore writes JSON directly; it is distinct from canonical snapshot publication.

Verified slices:

- Fresh static provider trace: candidate validators and stale_available refresh failure state present. Background jobs persist manifest before exposure, use namespace compatibility, expected generation/token checks and recovery leader lock.
- F38 exact progress counterexample remains: a response can say published without the requested job output matching the head. Static LocalJsonStore direct truncating write atsave is a durability limitation, not proof canonical publication uses that path or is corrupt.
- Current ASMAE cache source retains matching writer/reader failed/timeout rejection checks; no old-artifact results are reused as fresh proof or authority promotion.

Remaining criteria: Pinned code/image/model/config identities; unified entrypoint admission/publication; bounded outage/corruption/timeout/restart/duplicate/concurrency drills across services; rejection/scope/stale/compute telemetry; exact committed response relation.

Evidence: `services/agribrain/layer0/data_gateway/request_broker.py:291-430,433-507`; `services/agribrain/layer05_asmae/background_jobs.py:275-377,639-670,2676-2782`; `services/agribrain/orchestrator_v2/storage.py:15-41`; `services/agribrain/orchestrator_v2/runner.py:1097,4044-4098`; `services/agribrain/app/main.py:594-629`; `services/agribrain/layer05_asmae/cache.py:651-670,743-762`; `services/agribrain/requirements.txt:5-11`.

Next step: Fix exact publication relation, provide supported immutable runtime identities and execute bounded cross-service resilience/recovery drills against actual admission/storage boundaries.

Acceptance limit: Static provider/job trace and isolated progress function only. No network, service restart, multiwriter, worker scheduling, real deployment or reproducibility certification; resource effects remain coordinator-owned.

## Reproduction

Run from this platform folder: `python memory_cache_probes.py`, `node frontend_probes.cjs`, `python platform_probes.py`. The scripts use the verified `runtime/` corpus and local explicit seams. They do not call network, DB or controllers. Source and runtime receipts allow the coordinator to reconstruct the exact selected corpus; no prior probe output is substituted for current behavior. `write_report.py` only assembles notes/receipts and does not execute production functions.
