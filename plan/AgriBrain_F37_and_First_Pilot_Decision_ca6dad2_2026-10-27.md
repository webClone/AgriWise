# AgriBrain: bounded acceptance and first advisory outcome

27 October 2026 · Current review pin `ca6dad291282ded06bab88ede1f45b85306e765c`.

## Decision

Adopt the proposed outcome-driven process now. Keep the R3 target and original package criteria, but stop expanding each correction into a general repository audit. F37 is the correct first formal acceptance candidate. It cannot honestly be accepted at this pin because its original shared-class identity requirement still fails. One bounded repair plus the declared environment qualification matrix is the remaining F37 gate. Build the first advisory vertical slice concurrently; do not wait for irrigation commissioning or the research program.

The 35% overall and 61% cohort figures remain explicitly rough planning estimates. This review neither validates nor replaces them with another invented percentage. Operational progress should be reported by accepted original criteria and usable outcomes.

## 1. What was checked

Two parallel lanes reviewed current production symbols: F37 original acceptance and the existing AgriWise-to-AgriBrain plot workflow. The root repeated both authored probe scripts; both completed and retained the reported results. Successful probe completion includes demonstrated contract failures; it is not acceptance of the candidate. The current branch was independently observed at ca6dad2; the earlier 220953f review is historical and its unresolved findings are not automatically asserted against this newer revision.

No production file, Git ref, package checkbox or field hardware was changed. The physical STOP cryptographic changes in the new revision were not independently audited in this bounded gate. No claim is made that those latest changes pass or fail.

## 2. F37: freeze the original gate and finish it

The master plan defines six production targets: segmentation, Layer 1 engine, drone dispatcher, drone mission package, drone RGB structural adapter, and service main. The original criteria are cold imports for supported entrypoints, shared enum/dataclass identities, graceful optional-backend unavailability, and accurate treatment of the previously loadable import cycles. It does not require empirical crop campaigns, hardware commissioning or completion of unrelated packages.

| Frozen check | Current evidence | Disposition |
|---|---|---|
| Cold imports of segmentation, L1 engine, drone dispatcher, drone mission and structural adapter | Five targets import independently in fresh processes | Positive bounded evidence |
| Segmentation execution | Native KMeans and GMM assign 24 authored pixels across three zones | Positive bounded evidence |
| Optional drivers absent | Controlled absence leaves dispatcher import and unrelated segmentation usable; simulation is not fabricated | Positive bounded evidence, not all backend configurations certified |
| Irrigation and sensor class identities | Both qualified-first and bare-first controls preserve module/class identity | Positive bounded evidence |
| Drone mission class identity | Both orders produce different schema modules and MissionType class objects; cross-namespace isinstance fails | **Original F37 criterion fails** |
| Service / worker / CLI / installed dependency qualification | Service import stops at absent declared python-dotenv; FastAPI also absent locally. Only Python 3.12 available; local NumPy2.3.5 differs from declared <2 | **Qualification incomplete**, not an established code defect |

F37 completion task: select one coherent package identity for the supported import paths; repair the drone_mission outcome; rerun the same frozen matrix in clean supported installations with declared dependencies and optional configurations. Verify supported service, worker, CLI and public entrypoints without incidental prior imports or undisclosed sys.path injection. Carry the passing evidence forward. Once the exact criteria pass, record the pin, receipts, reviewer and sign-off and accept F37. Do not require all 52 FA rows to remain open as a blanket rule.

The local environment limitations must not be misreported as new repository import failures. Conversely, five successful imports are insufficient to certify the complete installed startup matrix. A package acceptance should state precisely which supported environments and entrypoints were qualified.

## 3. Build the existing vertical path instead of a new parallel system

The source already supplies the main route:

**Plot creation → signed AgriBrain run API → Python v2 run → orchestrator and Layer0 broker → canonical result → surfaces/latest → existing map/result UI.**

The first capability is one authorized, persisted plot producing one traceable assessment from real source data. It does not require all thirteen maps, optional RF equipment, automatic irrigation, Omega or a complete learned world model.

One directly relevant integration task is already visible. The Next.js plot route calls `/collector/register-plot` with Content-Type only, sends farm_id in the body, and does not inspect the collector's response.ok before returning plot creation success. The Python collector requires internal signed authority, while its shared auth dependency rejects farm_id body authority; the request schema also requires that field. Adding a signature alone does not resolve the request contract.

The exact auth decision code was exercised with minimal Request/HTTPException stand-ins because FastAPI is absent: the existing unsigned body returns401; the same body with a valid controlled signature returns400 for body authority; a signed namespace-only auth control passes that dependency. This is **AST-isolated decision evidence plus source caller/callee inspection**, not a deployed FastAPI/HTTP/browser test. The complete namespace-only request still must satisfy the endpoint schema after repair.

This bootstrap defect does **not** establish that the separate on-demand broker run is blocked. If the first pilot deliberately uses the existing signed on-demand run and meets its exit criteria, automatic background registration can remain a tracked follow-up with honest unavailable/pending status. Do not turn an unused bootstrap feature into a universal pilot prerequisite.

Fix caller and collector together: reuse the existing signing contract, derive tenant/farm authority from the authenticated namespace, align the request schema and handler, and make registration readiness explicit. A plot may remain persisted while registration is pending if that state has durable retry/error handling; it must not be presented as data-ready merely because plot persistence succeeded. Preserve ownership enforcement rather than weakening auth to make the demo pass.

## 4. Four delivery owners and one result

| Owner | Concrete work | Outcome gate |
|---|---|---|
| Foundation / integrator | Finish F37's namespace identity and declared startup matrix; own shared API contracts | Original F37 criteria pass and formal acceptance is recorded |
| Platform integration | Plot persistence, ownership, signed registration/run handoff, explicit pending/error/retry states | A real authorized plot reaches AgriBrain; a second tenant cannot consume it |
| Evidence / science | Acquire real satellite and weather inputs; preserve source, timing, valid support, missingness and units | One real-data receipt reaches computation with an honest bounded assessment |
| Result / product | Persist canonical result and expose the existing API/UI workflow with explanations and retry/reload | Farmer/agronomist completes the advisory workflow without developer intervention |

Physical execution remains an independent specialist stream with its own deployment gates. It must not block read-only monitoring simply because its commissioning is incomplete. Equally, the advisory deployment must enforce the separation on the server: remove or disable live command submission and autonomous actuation routes/tools for that deployment, verify the deployed restriction, and do not rely only on hidden UI buttons. No physical controller operation is part of this first-pilot gate.

The four owners integrate against one frozen contract and one pinned candidate. They should not independently edit shared schema/signing conventions. They can deliver small reviewable changes, but acceptance is evaluated once against the agreed capability result.

## 5. Pilot definition of done

1. An authenticated farmer or agronomist creates a real plot polygon and the tenant/farm/plot identity persists.
2. Registration and run submission are authorized and observable: ready, pending, failed and retryable states have precise meanings. A failed upstream response cannot silently become successful data acquisition.
3. At least one genuine usable satellite acquisition and weather record are acquired or an authentic archived acquisition is deliberately replayed. Label archival replay and its cutoff; do not call it fresh provider execution. Retain product/source IDs, observation time, availability/issuance time, units and spatial support.
4. One relevant bounded assessment is computed from qualified inputs. Separate observed vegetation signals from modelled water estimates and hypotheses. Missing data stays unavailable; no generic healthy defaults are presented as measured science.
5. The persisted result links to one canonical artifact, run/commit/model identity, evidence, uncertainty and qualification. Maps, numbers and explanation refer to the same result/support.
6. The user can reload, understand limitations and retry a failed acquisition without a developer patch, duplicate records or an unrelated result replacing their plot's result.
7. An empty/cloudy acquisition, provider failure and wrong-tenant request have honest visible outcomes. These controls are part of a usable pilot, not additional research features.
8. Advisory execution is proven unable to dispatch live actuators. A farmer or agronomist completes the agreed workflow and supplies an acceptance receipt.

This gate does not establish calibrated agronomic accuracy, yield benefit or causal treatment efficacy. Those claims retain their scientific/empirical criteria. It does demonstrate the intended software workflow with genuine evidence and visible limits.

## 6. Apply a bounded release-impact rule

Classify every finding by the release or package it affects, its reproduced input/path, expected versus actual result, severity and owner.

- **Current release blocker:** breaks the agreed pilot, corrupts/forges scientific state or evidence, crosses tenant/auth/privacy boundaries, corrupts persisted results, or enables unsafe actions. Repair within the responsible owner lane and recheck its connected boundary.
- **Package acceptance blocker:** violates that package's frozen original criterion. Drone MissionType identity is this kind of failure, even if a particular advisory screen does not import it. It blocks F37 sign-off, not every independent implementation task.
- **Backlog improvement:** outside the agreed release/criterion and without demonstrated impact on its supported path. Record it with an owner and revisit through its package; it does not create a fresh general audit cycle.
- **Empirical obligation:** calibration, independent field references, controller commissioning and scientific validation follow their actual package criteria. Test totals neither waive them nor make them prerequisites for unrelated software outcomes.

An identifiable security or corruption risk need not cause real customer harm before it qualifies as a blocker. A controlled reproduction or clear supported-path contract violation is sufficient. The purpose is proportionate verification, not acceptance by exhaustion.

Review each integrated candidate against this frozen gate. Reuse accepted evidence unless changed paths invalidate it. Newly discovered failures of the named gate must still be fixed; scope freezing does not waive its original requirements. Unrelated findings stay in their assigned backlog.

## 7. Progress dashboard

Track F37 accepted; first integrated plot; first verified real-data pipeline; first canonical assessment; first independent pilot completion. For each, show implementing SHA, verifying SHA, evidence, merge/deployment state and remaining blocker. Keep package software acceptance, empirical validation and deployment readiness separate. Do not sum successive test or remediation counts into completion.

The current task register still contains225 numeric tickets,8 early slices and52 FA milestones, all open. Not all285 are full acceptances and not all FAs require field data. Reconcile completed software tickets against evidence, and close FAs individually when their own full criteria pass. There is no reason to keep a satisfied package open to preserve a program-wide0/52 count.

## Immediate decision

**Proceed with the process change. Finish the one F37 identity repair and its missing environment qualifications while fixing the plot handoff and building the advisory pilot in parallel.** Do not request another exhaustive audit before starting that work. Do not claim F37 already accepted at ca6dad2. The next exit review has two concrete subjects: the original F37 gate and the first authorized real-data assessment workflow.

The R3 monograph remains the full target. This first release is a deliberately bounded capability increment toward it, not a replacement of its agronomic, AI, architecture or economics requirements.


---

# Bounded review appendix: f37

# F37 bounded acceptance check — ca6dad2

Candidate: `ca6dad291282ded06bab88ede1f45b85306e765c`, review branch `feat/f36-t09-asmae-13-state-publication`. Original scope is the master repair plan's F37 card and ST00-F37-01…04/FA. This review does not expand F37 into irrigation commissioning, all scientific capability acceptance, frontend release, or unrelated package repairs.

## Decision

**F37 is a sensible first package to close, but it cannot be formally accepted on this candidate yet.** One exact original acceptance criterion still fails: qualified and internal drone-mission callers do not share `MissionType` class identity. This is not a speculative edge case or newly added requirement. Fix that single identity outcome, complete the declared-environment startup matrix, and close the package when its original criteria pass. Keep the independent vertical slice moving while this bounded correction is made.

No source code, Git ref or acceptance checkbox was edited. Native functions and fresh interpreters were used; repository tests and repair narratives were not the oracle.

## Exact scope and receipts

The six original production targets are segmentation.py, layer1_fusion/engine.py, drone_control/dispatcher.py, drone_mission/__init__.py, layer0/perception/drone_rgb/structural.py and app/main.py. The card requires: cold imports without incidental earlier imports; shared qualified/internal enum/dataclass identities; optional backend unavailability must not break unrelated science; and the previously successful import cycles must not be misreported as demonstrated circular-import failures.

| Original outcome | Fresh-process result | Disposition |
|---|---|---|
| Correct GaussianMixture import and native segmentation | Imports from sklearn.mixture; KMeans and GMM each cluster 24 authored pixels into three zones | Pass for exercised control. No agronomic calibration claim. |
| Cold original target imports | Five targets import independently with only the source root supplied | Pass for those five targets in the current review environment. |
| Service cold import | app.main stops at missing `dotenv` | Environment qualification incomplete, not established repository defect: python-dotenv==1.0.1 is declared. |
| Shared sensor-runtime registration identity | Module and SensorDeviceRegistration are identical in both import orders | Pass. |
| Shared irrigation-runtime enum identity | Module and ActuatorStatus are identical in both orders; cross-isinstance succeeds | Pass. |
| Shared drone-mission enum identity | Both orders produce different module objects and different MissionType classes; cross-isinstance fails | **Original F37 acceptance failure.** |
| Optional driver absence isolation | Explicitly deny DJI/MAVSDK/mock imports; dispatcher still imports, registry is empty, missing driver returns None, unrelated segmentation constructs | Pass for bounded optional-driver isolation. No simulation/hardware capability is fabricated. |
| Full supported service/worker/CLI and dependency extras | Not fully executed in matching declared environments | Missing qualification evidence; not a fresh code defect or growing-season obligation. |

The canonical-first drone identity counterexample needs only the normal qualified source root. Import `services.agribrain.drone_mission.schemas`, then `drone_mission.schemas`: both imports succeed, but `a is b` and `a.MissionType is b.MissionType` are False. `isinstance(list(a.MissionType)[0], b.MissionType)` is False. The bare-first case under the existing legacy path configuration also fails. String-enum members may still compare equal by value, so equality alone would miss the class-identity defect. The two schema slots point at distinct objects despite the new aliasing bridge.

This follows the package's exact original shared-identity criterion. It does not imply every application path currently crashes, nor does it establish a circular import. Do not relabel successful imports as cycles merely because dependency graphs contain a cycle.

## Bounded completion gate

1. Make the canonical and compatibility drone imports resolve to one executed schema module and the same class objects in both fresh import orders. Preserve the passing sensor/irrigation identity controls.
2. Declare the supported service, worker, CLI and public entrypoints and dependency profiles once. Run each independently under that configuration; do not depend on pytest's import prewarming or a previous successful import.
3. Run with optional backends absent and available where supported, retain explicit unavailability and simulation labeling, and confirm unrelated science still loads.
4. Record the pin, commands, environment, results and reviewer decision against F37's original tickets. If all original criteria pass, mark F37 accepted; do not wait for physical field commissioning or add unrelated research requirements.

No need for another whole-repository audit after this correction. The same fixed acceptance matrix is the exit gate. A source-root import fixture is not a substitute for a successfully installed-package qualification, so keep those evidence labels distinct.

## Reproduction and limitations

Run `python -B outcome-ca6dad2/f37/probes.py`. It executes fourteen fresh-process scenarios: six cold targets, six identity order controls, optional-driver absence and native clustering. The top-level runner records child failures rather than presenting its own exit0 as acceptance success. `results.json` retains the actual outcomes; `identity-results.json` is an earlier independent same-case receipt.

Current runtime is Python 3.12.14 with NumPy 2.3.5, whereas the repository declares NumPy<2 and python-dotenv among its production dependencies. Python 3.13 is not available here. Thus these results cannot certify the declared production environment or both requested Python versions. Missing dotenv is explicitly classified as review-environment incompleteness, not a production defect. No vendor connection, mission dispatch, service network listener, provider retrieval, browser or hardware was operated.

The production files fetched/reused for this check were verified against the candidate Git tree. Fresh fetches were normalized only to remove apply_patch's extra final newline when that restored the exact Git blob. No production semantics were modified.


## Exact probe receipts

```json
{
  "cold:services.agribrain.layer1_fusion.segmentation": {
    "exit_code": 0,
    "loaded": "services.agribrain.layer1_fusion.segmentation",
    "stderr": ""
  },
  "cold:services.agribrain.layer1_fusion.engine": {
    "exit_code": 0,
    "loaded": "services.agribrain.layer1_fusion.engine",
    "stderr": ""
  },
  "cold:services.agribrain.drone_control.dispatcher": {
    "exit_code": 0,
    "loaded": "services.agribrain.drone_control.dispatcher",
    "stderr": ""
  },
  "cold:services.agribrain.drone_mission": {
    "exit_code": 0,
    "loaded": "services.agribrain.drone_mission",
    "stderr": ""
  },
  "cold:services.agribrain.layer0.perception.drone_rgb.structural": {
    "exit_code": 0,
    "loaded": "services.agribrain.layer0.perception.drone_rgb.structural",
    "stderr": ""
  },
  "cold:services.agribrain.app.main": {
    "exit_code": 1,
    "stdout": "",
    "stderr": "Traceback (most recent call last):\n  File \"/workspace/scratch/de6bc2428cec/outcome-ca6dad2/f37/probes.py\", line 17, in <module>\n    m=importlib.import_module(sys.argv[2]);print(json.dumps({'loaded':m.__name__}))\n      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/importlib/__init__.py\", line 90, in import_module\n    return _bootstrap._gcd_import(name[level:], package, level)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"<frozen importlib._bootstrap>\", line 1387, in _gcd_import\n  File \"<frozen importlib._bootstrap>\", line 1360, in _find_and_load\n  File \"<frozen importlib._bootstrap>\", line 1331, in _find_and_load_unlocked\n  File \"<frozen importlib._bootstrap>\", line 935, in _load_unlocked\n  File \"<frozen importlib._bootstrap_external>\", line 999, in exec_module\n  File \"<frozen importlib._bootstrap>\", line 488, in _call_with_frames_removed\n  File \"/workspace/scratch/de6bc2428cec/outcome-ca6dad2/source/services/agribrain/app/main.py\", line 11, in <module>\n    from dotenv import load_dotenv\nModuleNotFoundError: No module named 'dotenv'\n"
  },
  "identity:drone_mission:canonical_first": {
    "exit_code": 0,
    "same_module": false,
    "same_class": false,
    "cross_instance": false,
    "first": "services.agribrain.drone_mission.schemas",
    "second": "drone_mission.schemas",
    "stderr": ""
  },
  "identity:drone_mission:bare_first": {
    "exit_code": 0,
    "same_module": false,
    "same_class": false,
    "cross_instance": false,
    "first": "drone_mission.schemas",
    "second": "services.agribrain.drone_mission.schemas",
    "stderr": ""
  },
  "identity:irrigation_runtime:canonical_first": {
    "exit_code": 0,
    "same_module": true,
    "same_class": true,
    "cross_instance": true,
    "first": "services.agribrain.irrigation_runtime.schemas",
    "second": "irrigation_runtime.schemas",
    "stderr": ""
  },
  "identity:irrigation_runtime:bare_first": {
    "exit_code": 0,
    "same_module": true,
    "same_class": true,
    "cross_instance": true,
    "first": "irrigation_runtime.schemas",
    "second": "services.agribrain.irrigation_runtime.schemas",
    "stderr": ""
  },
  "identity:sensor_runtime:canonical_first": {
    "exit_code": 0,
    "same_module": true,
    "same_class": true,
    "cross_instance": null,
    "first": "services.agribrain.sensor_runtime.registry",
    "second": "sensor_runtime.registry",
    "stderr": ""
  },
  "identity:sensor_runtime:bare_first": {
    "exit_code": 0,
    "same_module": true,
    "same_class": true,
    "cross_instance": null,
    "first": "sensor_runtime.registry",
    "second": "services.agribrain.sensor_runtime.registry",
    "stderr": ""
  },
  "optional_absent": {
    "exit_code": 0,
    "driver_registry": [],
    "missing_driver_returns_none": true,
    "unrelated_segmentation_constructs": true,
    "simulation_not_fabricated": true,
    "stderr": ""
  },
  "clustering": {
    "exit_code": 0,
    "kmeans": {
      "count": 24,
      "zones": [
        0,
        1,
        2
      ]
    },
    "gmm": {
      "count": 24,
      "zones": [
        0,
        1,
        2
      ]
    },
    "stderr": ""
  }
}
```


---

# Bounded review appendix: vertical

# First advisory vertical slice — source trace and bounded delivery gate

Candidate: `ca6dad291282ded06bab88ede1f45b85306e765c`, 27 October 2026. This is a read-only integration trace and one exact-code auth decision probe. It is **not** a claim that a real provider, database, browser or deployed HTTP workflow has been executed successfully.

## Decision

The proposal is executable against substantial existing code. Build and qualify the smallest advisory workflow using the current canonical run/publication path. Do not create a second orchestration stack, wait for all 13 maps, or require all 52 full acceptances first. Physical actuation and advanced research acceptance must remain separate from this pilot's release decision.

The route structure exists, but source presence is not end-to-end acceptance. One concrete caller/callee mismatch already exposes why this outcome-based integration test is useful: automatic plot registration is not compatible with the backend's authenticated request contract. Treat its two aspects as **one vertical integration task**, not another general audit cycle.

## Existing canonical flow

| Step | Current production files / behavior | Pilot receipt |
|---|---|---|
| User creates plot | `src/app/api/plots/route.ts:59–146` checks session and farm ownership, creates Prisma plot, then attempts background collector registration | Persisted plot ID, owned farm, valid polygon and declared area/crop cycle; creation remains successful independently of collection |
| User requests assessment | `src/app/api/agribrain/run/route.ts:218+` loads authorized plot/cycle data; `:480–513` signs namespace-bound request and calls Python `/v2/run` | User/session authorization, tenant/farm/plot namespace, geometry identity, request/run ID, chosen interval |
| Python selects canonical mode | `services/agribrain/app/main.py:3869+` requires internal authentication and checks context plot ID | Authenticated namespace and exact context agreement |
| Real acquisition and science | `orchestrator_v2/run_entrypoint.py:454+` calls `run_orchestrator`; `runner.py:1130+` resolves geometry, `:1205+` requests S2, S1 and Open-Meteo archive from the broker, with SoilGrids and optional ASMAE scene stacks | Provider/product/source identity, acquisition and availability time, missing or degraded source statuses, evidence used by assessment |
| Publication and persistence | `app/main.py` canonical plot snapshot routes; source includes canonical worker publication; Next `/surfaces/latest` uses signed `/v2/plots/{plot_id}/snapshot` and validates contract flags | Canonical snapshot/publication ID and hash, scientific values and qualifications, stable reload |
| Browser consumption | `src/hooks/useLayer10.ts:1113–1235` cache-first canonical head; on miss `/run` is a trigger; UI polls `/surfaces/latest` and accepts only validated canonical publications | UI values/explanation/map match one canonical artifact; progress, missingness, failed/stale publication visible |

The map hook already distinguishes triggering a computation from accepting the scientific result. Preserve that design. A text/summary assessment can also use the existing full/chat paths, but its persistence/reload must be demonstrated explicitly: the orchestrator's local artifact store is optional (`runner.py:4430`) and a response alone does not prove durable user-facing retrieval.

## One concrete integration task: plot bootstrap protocol compatibility

The plot creation route posts `/collector/register-plot` with only `Content-Type`, body `farm_id`/`plot_id` and no signed internal headers (`plots/route.ts:98–140`). The Python endpoint requires `require_internal_service_request` (`app/main.py:4606–4624`). Default authenticated operation therefore rejects this request. The caller does not inspect `response.ok`, and still returns plot creation HTTP 201. Network exceptions are logged, but upstream HTTP 401 is not an exception to `fetch`.

Adding signatures alone is insufficient. The shared auth dependency rejects JSON body `farm_id` as caller-supplied authority (`internal_service_auth.py:257–265`), while `PlotRegistrationRequest` currently requires `farm_id` and the endpoint compares it with the namespace. Resolve authority coherently: derive farm/tenant from the authenticated namespace, update the registration DTO/caller together, and keep the appropriate plot/body identity checks. Do not disable authentication to make the demo pass.

The exact auth decision code was executed in an AST-isolated harness because FastAPI is not installed in this review environment. The harness supplies simple request/exception objects and executes the unchanged module decision functions; it is not an ASGI test and no endpoint was called:

- Existing unsigned body → 401, missing internal headers.
- Same body with valid controlled signature → 400, body `farm_id` denied.
- Namespace-only signed auth positive → dependency admits namespace T/F/P. This does not establish that the current registration DTO accepts that body.

The source also uses `PYTHON_API_URL` for plot registration and `AGRIBRAIN_API_URL` for the run route. Pilot configuration must deliberately resolve both to the same intended backend or document their split. No deployment misconfiguration is asserted from those two names alone.

This gap affects claimed automatic prefetch/bootstrap. It does **not** prove that every on-demand assessment fails: the canonical orchestrator independently acquires sources through its broker. The smallest pilot can use that explicit on-demand path while fixing registration in the same vertical integration lane. Missing/failed bootstrap must be visible rather than silently mistaken for an active collection subscription.

## Freeze this pilot definition of done

Use one consenting user's real, valid plot and one supported crop/assessment scenario. Select a period with at least one usable real satellite product and actual weather inputs; a cloudy/no-scene control should produce a truthful degraded or unavailable result rather than manufactured evidence. An archive-based assessment is acceptable if clearly labelled retrospective; it must not be reported as prospective forecast skill.

1. **Create:** authenticated user persists owned farm/plot/cycle and valid geometry, reloads it, and receives truthful bootstrap status. No developer edits to DB or cache are needed.
2. **Acquire:** trigger one run through the browser-supported API. Capture provider/product references, dates, knowledge cutoff, geometry and provenance. A valid prior can support inference but cannot masquerade as an observed source. Real provider calls, not fixture injection, are required for this milestone.
3. **Assess:** AgriBrain returns at least one meaningful agronomic finding tied to evidence, uncertainty/support, missing drivers and limitations. The gate is not 'all layers return success' or 'all states produce colored pixels'.
4. **Publish/reload:** persist one canonical assessment/publication identity. Browser numbers, explanations and any rendered map refer to that identity. Browser refresh and a separate process retrieve the same accepted result; display stale/failed/unavailable state honestly.
5. **Authorize:** a second unauthorized user cannot trigger/read this plot's result. Signed service requests retain tenant/farm/plot scope and no client-supplied authority overrides it.
6. **Keep advisory-only:** the tested scenario issues zero physical controller/drone commands. Disable or deny actuation routes/capabilities and credentials in this pilot environment; test that boundary. Source inspection of the selected orchestrator found no direct `submit_event`/`execute_with_safety` call, but this is not sufficient proof of deployment-wide isolation.
7. **Use:** a farmer or agronomist completes create→run→understand→reload without developer intervention, can identify source dates and uncertainty, and sees a recoverable message when data/service is unavailable. Record observed completion and the concrete failure if any; do not invent a pass rate or completion-time target after the run.

These seven criteria provide an objective stopping point. A successful result is a capability receipt, not full agronomic validation, all product workflows, or field-controller commissioning.

## Four owners with one integrated exit

| Owner | Bounded outcome | Integration contract |
|---|---|---|
| Foundation / integrator | Finish original F37 qualification and reconcile accepted tickets; own shared namespace/auth DTOs | One supported startup profile and caller/callee namespace contract, exact commit pin |
| Product workflow | Browser plot creation, visible acquisition/run state, traceable assessment and reload | Current run and canonical snapshot APIs; no new parallel result store |
| Data / science | Real acquisition for selected plot and qualified evidence→assessment receipt | Real data and unavailable control, source/time/support/uncertainty preserved |
| High-risk execution | Continue physical irrigation authentication/recovery/commissioning separately | Pilot execution denied at deployment capability boundary; its software/field gate does not block unrelated advisory UI |

After all three non-hardware owners integrate, evaluate the frozen pilot criteria once on a pinned SHA. A reproducible defect that corrupts its scientific result, exposes another tenant, causes physical action or prevents completion is a blocker. An unrelated improvement or unexercised theoretical concern remains assigned to its original package. A risk with a demonstrated reachable path can block before a field incident; 'no field accident yet' is not a waiver.

## Evidence limits

The selected production files were matched to current Git blobs; four additional fetched files were verified after staging (`run_entrypoint.py`, `refresh_worker.py`, the TS signer and authorizer). No production source was modified. No real plot was created, provider data acquired, backend started, browser used or hardware operated. The missing FastAPI installation is an environment qualification limitation, not a proven repository dependency defect. `probes.py` and `results.json` preserve the exact-decision control and its explicit framework boundary. A real database/provider/browser run remains the next capability evidence, not a completed milestone.


## Exact probe receipts

```json
{
  "original_plot_registration_unsigned": {
    "accepted": false,
    "status": 401,
    "detail": "Missing required internal service authentication headers"
  },
  "same_body_signed": {
    "accepted": false,
    "status": 400,
    "detail": "Client payload must not specify tenant_id, tenantId, farm_id, or farmId. Authority is derived exclusively from authenticated tokens."
  },
  "namespace_only_signed_auth_positive": {
    "accepted": true,
    "namespace": {
      "tenant": "T",
      "farm": "F",
      "plot": "P"
    }
  }
}

```

## Root repeat execution

```json
[
  {
    "script": "f37/probes.py",
    "exit": 0,
    "seconds": 9.21
  },
  {
    "script": "vertical/probes.py",
    "exit": 0,
    "seconds": 0.14
  }
]
```
