"""
Layer 2: Vegetation & Stress Intelligence Engine.

The first interpretive/diagnostic layer in AgriBrain.
Consumes Layer2InputContext from Layer 1 and produces explainable,
zone-aware stress attribution and vegetation intelligence.

Strict rules:
- Evidence-based vocabulary only (no prescriptions)
- Full uncertainty propagation from L1
- Deterministic (same input → same output + content_hash)
- Runtime invariants with auto-fix
- Diagnostic-only features never drive strong conclusions
"""
