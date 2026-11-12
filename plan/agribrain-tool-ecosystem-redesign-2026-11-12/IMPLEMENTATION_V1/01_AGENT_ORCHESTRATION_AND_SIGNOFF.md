# Multi-Agent Implementation Governance — Roles, Review Rounds, Conflict Arbitration
**Interpretation:** These are specialist *review and implementation roles to assign*. This plan itself was authored as a structured synthesis; it does not claim nine autonomous runtime agents or independent signed audits have already executed.
## Agent roles and independently accountable outputs
| Agent | Scope | Must produce | Must challenge |
|---|---|---|---|
| A0 Program/Architecture Lead | sequence, architecture, PR boundaries, integration | ADR, dependency matrix, merge gate, GO/HOLD | over-broad changes, missing rollback |
| A1 UX/Product Designer | navigation, farmers/expert/Arabic/FR, full tool catalog | annotated prototype, component usage, states, usability matrix | hidden tools, clutter, confusing labels |
| A2 Frontend State Engineer | Next.js 16/React 19, providers, tool host, routing, concurrency | typed state model, reducer, migration proof, React tests | stale async overwrites, state resets, hydration |
| A3 Geospatial Engineer | MapLibre/DeckGL, CRS, masks, picking, GPU layers | geometry tests, materialization proof, rendered map traces | antimeridian, holes, grid mismatch, deceptive layer |
| A4 Scientific Integrity Engineer | L0–L10 contracts, ASMAE 13, lineage/uncertainty, temporal cutoff | authority matrix, proof-to-pixel trace, scientific review | proxies marketed as measured, posterior vs observation |
| A5 Backend/IoT/MESIA/Drone Adapter Engineer | sensor/drone/MESIA APIs, event persistence, schemas | scoped adapter specs, contract tests, capability status | invented location, ambiguous device health, mock transport |
| A6 Security & Actuation Safety Red Team | ownership, signed headers, permission, admission, actions | abuse cases, threat model, negative assertions | cross-tenant leaks, unauthorized actuation, fake hardware success |
| A7 QA & Verification Agent | adversarial tests, test reproducibility, CI, acceptance ledger | failed-before/fixed-after tests, CI receipts, browser traces | green unit tests with broken real browser |
| A8 Accessibility/Performance/Release | ARIA, RTL, responsive, benchmarks, flags, rollback | keyboard/touch/a11y tests, perf traces, rollout decision | hidden controls, high CPU/GPU, missing rollback |

## For each pass, perform SIX rounds
**R0 — Evidence gather (Owner + A0):** Pin upstream code SHA; identify existing contracts, route/API, attached tests, known audit findings. Record exactly what is source-supported and what is proposed.
**R1 — Independent proposals (2 specialists):** The primary author and one other specialist separately propose architecture, UI states and acceptance tests. Do not share assumptions until they produce an initial note.
**R2 — Cross-review (A4+A6 mandatory for science/operations; A3 for geometry):** Look for authority leaks, unbounded source conversion, false physics, broken historic replay and hardware ambiguity.
**R3 — Adversarial scenarios (A7):** Create at least one failure-case test that fails on old branch and passes on proposed fix. Include stale/foreign/wrong-data examples; pure code inspection is not 'adversarial execution'.
**R4 — Integration validation (A0+A2+A8):** Check connected panels, map, timeline and tool host with real browser where touched. Verify no unintentional route break, design regression or memory growth.
**R5 — Closure & signoff:** Exact SHA, artifacts, unresolved issues, owner approvals, explicit GO/HOLD. Reviewer may veto P0. No role can certify its own work alone.

## No reviewer self-attestation
- Independent means different agent/person/process/runner and distinct evidence, not only reworded report under a different persona.
- If only one engineer/one assistant is available, record **role-based review** rather than falsely claiming independent agents. Human or automated external reviewers can be added later.
- No fabricated pytest, browser, CI, security scan or field validation receipts.
- A0 cannot override an A6 actuation veto or A4 scientific-integrity veto without formal product governance.
## Assignment matrix
| Passes | Primary | Independent 1 | Independent 2 | Adversarial/Acceptance |
|---|---|---|---|---|
| P00 | A0 | A4 | A6 | A7 |
| P01 | A6 | A3 | A4 | A7 |
| P02 | A1 | A2 | A8 | A7 |
| P03 | A2 | A6 | A4 | A7 |
| P04 | A2 | A1 | A6 | A7 |
| P05 | A5 | A6 | A4 | A7 |
| P06 | A3 | A2 | A4 | A7 |
| P07 | A4 | A3 | A6 | A7 |
| P08 | A5 | A3 | A6 | A7 |
| P09 | A5 | A3 | A6 | A7 |
| P10 | A4 | A5 | A6 | A7 |
| P11 | A4 | A2 | A6 | A7 |
| P12 | A4 | A5 | A6 | A7 |
| P13 | A2 | A4 | A6 | A7 |
| P14 | A1+A8 | A3 | A2 | A7 |
| P15 | A0+A7 | A4 | A6 | A8 |
## Review artifact naming
Per PR: `plan/.../receipts/Pxx-R0-baseline.md`, `Pxx-R1-proposal-{role}.md`, `Pxx-R2-cross-review.md`, `Pxx-R3-negative-tests.md`, `Pxx-R4-browser-integration.md`, `Pxx-R5-gate-decision.md`. These are future outputs, not existing checked-off items.
## Conflict-resolution protocol
Scientific authority > tenant/security > physical safety > mathematical map truth > functional parity > product ergonomics > cosmetic consistency. Avoid false binary: safety and scientific integrity are joint hard constraints, not tradeoffs. If an agent proposes converting unknown state to estimate for smoother UI, reject. Escalate material disagreements to A0 with written alternatives, evidence and risk. Split large disagreements into a small experimental design branch with zero published action.
## Hard-stop conditions
Scope incomplete/foreign data visible; snapshot/geometry/hash mismatch still renders as authoritative; fake drone/device/receiver 'live'; simulated command appears physically acknowledged; backend cutoff/certification bypass; P1 current plot page fails before flag can roll back; tests not reproducible.
