# Task A09: MESIA Qualification & Evidence Integrity Verification Gaps

## 1. Finding Overview
* **Finding ID:** A09
* **Severity:** **P0 — Security & Scientific Authority Governance Defect**
* **Component:** MESIA Governance & Integration Spine
* **Primary Target Files:**
  - [`services/agribrain/mesia/assimilation/capability_governance.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/assimilation/capability_governance.py) (line 56)
  - [`services/agribrain/mesia/integration.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/mesia/integration.py) (lines 78, 129–135)

---

## 2. Technical Analysis & Code Audit

### Defect 1: Empty String Passes Qualification Signature Gate
In `services/agribrain/mesia/assimilation/capability_governance.py`, line 56:
```python
# Phase 2: Require independent validation signature
is_qualified = all_passed and validation_signature is not None
```
- If all boolean gates are set to `True` and `validation_signature = ""` (an empty string), `validation_signature is not None` evaluates to `True`.
- The capability transitions to `state="QUALIFIED"` and gains `"STATE_PROPOSAL"` authority without any real cryptographic signature, valid approval board, or expiration date (`expires_at=None`).

---

### Defect 2: Mock "Length == 64" Hash Verification
In `services/agribrain/mesia/integration.py`, line 78:
```python
# 0. Verify native evidence exists (Audit Finding #4)
native_uri = getattr(packet, "native_data_uri", None) or ""
native_hash = getattr(packet, "native_data_hash", None) or ""

# Phase 3: Strict hash verification logic
is_hash_valid = len(native_hash) == 64
```
- `is_hash_valid` checks only that the string length is 64 characters (`len("0"*64) == 64`).
- It does **not** read the file at `native_uri` or verify that the payload matches the cryptographic hash. Corrupt, fabricated, or non-existent files are admitted as valid native evidence.

---

### Defect 3: Capability Selection Ignores Expiry, Domain, and Revocation
In `services/agribrain/mesia/integration.py`, lines 129–136:
```python
is_qualified = False
for cap in self.list_active_capabilities():
    if likelihood.target_variable == cap.target_variable:
        if packet.source_profile.split("/")[0] in cap.supported_radio_families:
            is_qualified = True
            break
```
- The loop verifies only target variable and radio family string prefix.
- It fails to check:
  1. Whether `cap.state == "QUALIFIED"` (a `REVOKED` or `EXPIRED` capability can match!).
  2. Whether `cap.expires_at > now`.
  3. Whether the plot is within `cap.geographic_domain` or `cap.supported_crop_types`.

---

## 3. Agronomical & Systemic Impact
- **Circumvention of Scientific Governance:** Experimental or uncalibrated radio signals can be marked as "qualified production evidence" by dummy test scripts or unverified payloads.
- **Unchecked Model Drift:** If a sensor or radio tower undergoes hardware modification or environment drift, revoked capabilities continue to authorize data updates.

---

## 4. Implementation Plan

### Step 1: Real Cryptographic Signature Check
In `services/agribrain/mesia/assimilation/capability_governance.py`:
- Require a non-empty, validated signature string.
- If public key infrastructure is configured, verify signature against the authority record payload; otherwise require non-trivial token matching known science board keys:
```python
if not validation_signature or len(validation_signature.strip()) < 32:
    is_qualified = False
else:
    # Verify cryptographic signature format and validity
    is_qualified = all_passed and _verify_board_signature(capability_id, validation_signature)
```
- Ensure `expires_at` is always populated (e.g. `now + timedelta(days=renewal_cadence_days)`).

### Step 2: Genuine Hash Verification of Native Evidence
In `services/agribrain/mesia/integration.py`:
- Verify hash against the actual raw bytes of the packet / file payload:
```python
import hashlib

def _verify_payload_hash(uri: str, expected_hash: str, packet_payload: bytes = None) -> bool:
    if not expected_hash or len(expected_hash) != 64:
        return False
    if packet_payload is not None:
        computed = hashlib.sha256(packet_payload).hexdigest()
        return computed.lower() == expected_hash.lower()
    # If URI points to local file
    if uri.startswith("file://") or os.path.exists(uri):
        with open(uri.replace("file://", ""), "rb") as f:
            computed = hashlib.sha256(f.read()).hexdigest()
            return computed.lower() == expected_hash.lower()
    return False
```

### Step 3: Comprehensive Capability Matching
Update `list_active_capabilities()` and matching logic:
- Check `cap.state == "QUALIFIED"`.
- Check `cap.expires_at and cap.expires_at > datetime.now(timezone.utc)`.
- Ensure crop and soil texture match current plot properties.

---

## 5. Verification & Test Plan

### Automated Tests
1. **Empty Signature Rejection:**
   - Attempt to issue authority record with `validation_signature=""`.
   - Assert `record.state == "UNQUALIFIED_PENDING_EVIDENCE"`.
2. **Tampered Hash Rejection:**
   - Pass packet with payload bytes `"data1"` and `native_data_hash = hashlib.sha256(b"data2").hexdigest()`.
   - Assert admission is rejected (`l0_record.is_usable_for_assimilation == False`).
3. **Revocation & Expiry Enforcement:**
   - Create expired capability (`expires_at = now - 1 day`).
   - Run ingestion and assert `is_qualified == False`.

---

## 6. Progress Tracking Checklist
- [ ] Empty signature loophole closed in `capability_governance.py`.
- [ ] Real SHA-256 payload byte verification implemented in `integration.py`.
- [ ] Expiry, revocation, and geographic domain checks added to capability matching.
- [ ] Automated security and governance tests written and passing.
