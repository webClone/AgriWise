"""C1B: mandatory Layer 0 scientific-state admission at Layer 1's intake.

This is a structural, fail-closed handoff over trusted *in-process* state
objects. Recomputing a package root detects mutation but is not issuer
authentication; a separate server-derived tenant/plot scope attestation
remains necessary before public/remote callers may submit such a package.
"""
from __future__ import annotations

import hmac
from typing import Any

from services.agribrain.layer0.source_package import Layer0StatePackage


class Layer1StateAdmissionError(ValueError):
    """A supplied Layer 0 state cannot be trusted by Layer 1."""


def require_admissible_layer0_state(package: Any, *, plot_id: str) -> None:
    """Refuse malformed, unauthorized or unqualified Layer 0 state exports.

    A Layer 0 state is optional for fusion; this function is called only when
    the caller supplied a non-None package. No model predictions are promoted
    into raw external observations by passing this gate.
    """
    if not isinstance(package, Layer0StatePackage):
        raise Layer1StateAdmissionError("layer0_state_not_canonical_object")
    if (
        not isinstance(plot_id, str) or not plot_id
        or not package.plot_id or package.plot_id != plot_id
    ):
        raise Layer1StateAdmissionError("layer0_state_plot_scope_mismatch")
    if (
        package.contract_version != "layer0-state-package-v1"
        or not isinstance(package.run_id, str)
        or not package.run_id
        or not isinstance(package.geometry_hash, str)
        or not package.geometry_hash
        or type(package.geometry_version) is not int
        or package.geometry_version < 1
    ):
        raise Layer1StateAdmissionError("layer0_state_invalid_scientific_identity")
    health = package.health_report
    provenance = package.provenance
    if (
        not isinstance(health, dict)
        or health.get("scientific_state_admissible") is not True
        or not isinstance(provenance, dict)
        or provenance.get("scientific_state_integrity") != "PASSED_RUNTIME_BOUNDARY"
        or provenance.get("run_id") != package.run_id
    ):
        raise Layer1StateAdmissionError("layer0_state_integrity_not_qualified")
    audit = health.get("audit")
    structural = audit.get("structural_audit") if isinstance(audit, dict) else None
    if (
        not isinstance(structural, dict)
        or structural.get("status") != "PASS"
        or type(structural.get("checks_run")) is not int
        or structural["checks_run"] <= 0
        or type(structural.get("checks_failed")) is not int
        or structural["checks_failed"] != 0
    ):
        raise Layer1StateAdmissionError("layer0_state_structural_audit_not_passed")
    if (
        package.scientific_publication_authorized is not False
        or package.actuator_control_authorized is not False
    ):
        raise Layer1StateAdmissionError("layer0_state_unexpected_execution_authority")
    if (
        not isinstance(package.daily_state, dict)
        or not package.daily_state
        or not isinstance(package.state_uncertainty, dict)
        or set(package.daily_state) != set(package.state_uncertainty)
    ):
        raise Layer1StateAdmissionError("layer0_state_missing_scientific_export")
    output_hash = package.output_hash
    if (
        not isinstance(output_hash, str)
        or not output_hash
        or not hmac.compare_digest(output_hash, package._generate_output_hash())
    ):
        raise Layer1StateAdmissionError("layer0_state_content_hash_mismatch")
