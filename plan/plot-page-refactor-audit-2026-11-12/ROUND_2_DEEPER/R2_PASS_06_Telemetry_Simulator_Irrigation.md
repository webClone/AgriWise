# Akaloris Plot — Round 2 / Pass 06: live telemetry versus simulated control surfaces

**SHA:** `1ee2c20119af29dd1f0a0b46c85217d91206b744`. **Hard requirement:** observation-only pilot with `AKALORIS_LAYER0_ENABLE_VERIFIED_IRRIGATION=false`, independently asserted by backend/hardware—not presumed from client UI.

### R2-18 — P1, mock irrigation presents simulated command and E-STOP as success

[`useIrrigationState.ts#L293-L432`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/useIrrigationState.ts#L293-L432) fills fleet, schedule, water budget and safety score from `generateMock*` routines every **10s**, with default `farmId='farm-1'`. `dispatchCommand` logs a command and returns a locally generated result with `success:true`, while `emergencyStopAll` updates only React state and returns `true`. [`IrrigationDashboard.tsx#L245-L392`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/irrigation/IrrigationDashboard.tsx#L245-L392) calls this an “Irrigation Control Center” with an `E-STOP ALL` button and online/executing counts. **No physical dispatch is evidenced by code here; the hazard is a false operational acknowledgment**.

**Remediation:** do not mount this operationally styled control in observation-only pilot. If simulation is useful, label it “Non-operational simulation” persistently, rename E-STOP to `Simulate stop`, and never return physical ack/success. Real physical control requires server-signed command, device ack, immutable operation receipt and hardware interlock; the browser cannot be an actuator authority.

### R2-19 — P2, timer reinitializes local operator changes

`fetchData()` regenerates mock entities each polling interval; `approveSchedule`/`rejectSchedule`/`setAutomationMode` update local state only. The next mock refresh can overwrite those changes. This is a source-level consistency risk; visual flicker was not observed via browser instrumentation.

### R2-20 — P2, telemetry origin must remain explicitly uncertified

[`usePlotTelemetry.ts#L34-L142`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/hooks/usePlotTelemetry.ts#L34-L142) uses immutable scoped observations and guards old requests. [`telemetry-contract.mjs#L1-L150`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/telemetry-contract.mjs#L1-L150) denies self-certification. [`operational-telemetry-transport.mjs#L1-L108`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/lib/agribrain/operational-telemetry-transport.mjs#L1-L108) documents that raw sensor timestamps may be *server receipt time*, not physical acquisition; legacy data can be daily buckets. Preserve this split: operational feed != cryptographically admitted scientific manifest.

### R2-21 — P2, fake recalibration and misleading readiness

[`DecisionConfiguration.tsx#L35-L92`](https://github.com/webClone/AgriWise/blob/1ee2c20119af29dd1f0a0b46c85217d91206b744/src/components/farm/DecisionConfiguration.tsx#L35-L92) sets a timer and shows “Model Recalibrated” after two seconds regardless of scientific backend completion. “Saved & Synced” may describe a form write, but not an ASMAE calibration. `user-inputs/page.tsx` “irrigation unlock” is only configuration completeness, not command authority.

### Adversarial tests

| Situation | Assertion |
|---|---|
| Physical toggle false | 0 issuer requests, 0 hardware ack, no physical status claims |
| Simulator dispatch | Response explicitly `simulated:true`, `physicalSuccess:false` |
| Simulated E-STOP | UI clearly says simulated, no assumption equipment stopped |
| Mock schedule approved | No claim of persistence; local state does not revert silently |
| Device timestamp only server receipt | No “measured at” physical-time claim |
| Cross-tenant/plot telemetry | Entire response fails scope check, no mixed feed |
| Saved configuration, no scientific recalibration | “Recalibration required,” not “recalibrated” |

**No physical actuator tests or real logger ingestion performed.**