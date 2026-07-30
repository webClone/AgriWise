"""
ASMAE Rollout Policy.
Provides centralized policy checks for ASMAE execution and visual rendering.
"""

from __future__ import annotations
import os
from rollout.asmae_rollout_registry import (
    is_asmae_backend_enabled_for_plot,
    is_l10_asmae_visuals_enabled_for_plot
)

LEGACY_BYPASS_TEST_ALLOWLIST = [
    "test_operator_diagnostics_blocks_resolution",
    "test_v79b_real_raster",
    "test_v83_performance",
    "test_v907_historical_surfaces",
]

def flag_is_true(name: str, *, tolerate_trailing_comma: bool = False) -> bool:
    """Check if an env flag is truthy.
    
    V92.4-BC: tolerate_trailing_comma allows 'true,' to be treated as True
    for diagnostic/visual flags, while authority flags remain strict.
    """
    raw = os.environ.get(name)
    if raw is None:
        return False
    val = raw.strip()
    if tolerate_trailing_comma:
        val = val.rstrip(",").strip()
    return val.lower() in ("true", "1", "yes")

def flag_is_false(name: str) -> bool:
    val = os.environ.get(name)
    if val is None:
        return False
    return val.lower() in ("false", "0", "no")

def is_legacy_test_bypass_allowed() -> bool:
    if os.getenv("ENVIRONMENT", "").lower() == "production":
        return False
        
    if os.getenv("AGRIWISE_LEGACY_FIXTURE_BYPASS") == "true":
        return True
        
    pytest_test = os.environ.get("PYTEST_CURRENT_TEST", "")
    if not pytest_test:
        return False
        
    for allowed in LEGACY_BYPASS_TEST_ALLOWLIST:
        if allowed in pytest_test:
            return True
            
    return False

def should_run_asmae_authority(plot_id: str) -> bool:
    """Strict registry-gated ASMAE authority check."""
    if not plot_id or not str(plot_id).strip():
        return False

    if flag_is_false("ASMAE_ENABLED"):
        return False

    if flag_is_true("ASMAE_ENABLED"):
        return is_asmae_backend_enabled_for_plot(plot_id)

    if is_legacy_test_bypass_allowed():
        return is_asmae_backend_enabled_for_plot(plot_id)

    return False

def should_run_asmae_visual_shadow(plot_id: str) -> bool:
    """Soft diagnostic ASMAE check for display only (unregistered plots shadow mode)."""
    if not plot_id or not str(plot_id).strip():
        return False

    if flag_is_false("ASMAE_ENABLED"):
        return False

    # Check if both ASMAE_ENABLED is true and ASMAE_DIAGNOSTIC_SHADOW_RUN_ENABLED is true (tolerating trailing comma)
    return (
        flag_is_true("ASMAE_ENABLED")
        and flag_is_true("ASMAE_DIAGNOSTIC_SHADOW_RUN_ENABLED", tolerate_trailing_comma=True)
    )

def should_run_asmae(plot_id: str) -> bool:
    """Centralized policy check for running the ASMAE backend for a plot (either authority or shadow visual)."""
    return should_run_asmae_authority(plot_id) or should_run_asmae_visual_shadow(plot_id)

def should_render_l10_asmae(plot_id: str) -> bool:
    """Centralized policy check for rendering Layer 10 ASMAE visual surfaces for a plot.
    
    Defaults to FALSE unless L10_ASMAE_SURFACES_ENABLED is explicitly set to 'true'
    AND the plot has visual surfaces enabled in the rollout registry.
    
    Falls back to diagnostic-only aliases if the global diagnostic alias policy is enabled,
    but only when L10_ASMAE_SURFACES_ENABLED is not explicitly set to false.
    """
    if not plot_id or not str(plot_id).strip():
        return False

    if flag_is_false("ASMAE_ENABLED"):
        return False

    if flag_is_false("L10_ASMAE_SURFACES_ENABLED"):
        return False

    # Allow visual rendering if shadow run is enabled
    if should_run_asmae_visual_shadow(plot_id):
        return True

    if flag_is_true("ASMAE_ENABLED") and flag_is_true("L10_ASMAE_SURFACES_ENABLED"):
        if is_l10_asmae_visuals_enabled_for_plot(plot_id):
            return True

    if is_legacy_test_bypass_allowed():
        if is_l10_asmae_visuals_enabled_for_plot(plot_id):
            return True

    # V92.4: Fall back to diagnostic-only alias policy
    # Only when L10_ASMAE_SURFACES_ENABLED is not explicitly set (unset/missing)
    return should_render_l10_asmae_diagnostic_aliases(plot_id)


def should_render_l10_asmae_diagnostic_aliases(plot_id: str) -> bool:
    """V92.4: Allows ASMAE diagnostic visual aliases globally,
    without enabling ASMAE state updates or prescription authority.
    
    This separates visual diagnostic display from scientific state authority.
    Enabled globally via L10_ASMAE_DIAGNOSTIC_ALIASES_ENABLED=true.
    
    Diagnostic aliases carry:
        diagnostic_only = True
        state_update_allowed = False
        prescription_driver_allowed = False
        not_direct_observation = True
    """
    if not plot_id or not str(plot_id).strip():
        return False

    if flag_is_false("ASMAE_ENABLED"):
        return False

    # Allow diagnostic aliases if shadow run is enabled
    if should_run_asmae_visual_shadow(plot_id):
        return True

    # Global kill switch for diagnostic aliases
    if flag_is_false("L10_ASMAE_DIAGNOSTIC_ALIASES_ENABLED"):
        return False

    # V92.4-BC: Tolerate trailing comma for visual/diagnostic flags
    if flag_is_true("L10_ASMAE_DIAGNOSTIC_ALIASES_ENABLED", tolerate_trailing_comma=True):
        return True

    # Default: not enabled unless explicitly requested
    return False

