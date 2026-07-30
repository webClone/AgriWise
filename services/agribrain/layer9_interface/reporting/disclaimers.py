# Central registry of standardized legal/institutional disclaimers

VISUAL_ONLY_1M_DISCLAIMER = (
    "⚠️ WARNING (1m Detail Limitations): Experimental visual detail — not a direct 1m satellite observation. "
    "Visual-only details are generated for user visualization and diagnostics only, and must not be treated "
    "as certified observation evidence."
)

SHADOW_ML_DISCLAIMER = (
    "⚠️ WARNING (Shadow ML Restriction): Shadow ML Diagnostics are strictly experimental and run in shadow mode "
    "for internal evaluation. They do not represent validated evidence and must never be used as institutional "
    "proof or certified observations for compliance, regulatory, or insurance claims."
)

NOT_CLAIM_DECISION_DISCLAIMER = (
    "This report provides evidence support and plausibility assessment. It is not an automatic insurance "
    "claim approval or denial."
)

ROI_CLAIM_BLOCKED_DISCLAIMER = (
    "⚠️ WARNING: ROI and performance claims are blocked due to missing validated economic records."
)

YIELD_CLAIM_BLOCKED_DISCLAIMER = (
    "⚠️ WARNING: Yield improvement claims are blocked due to missing validated harvest records."
)

PRIVACY_SUPPRESSION_DISCLAIMER = (
    "⚠️ Data Suppressed: This region does not meet privacy aggregation thresholds (minimum 5 plots and 3 owners)."
)

def prepare_standard_disclaimers(classified_items, base_disclaimers=None):
    from layer9_interface.reporting.schemas import ReportDisclaimer
    disclaimers = list(base_disclaimers or [])
    
    has_shadow_ml = any(item.tier == "shadow_ml_diagnostic" for item in classified_items)
    has_uncertified_1m = any(item.tier in ("visual_only_1m", "uncertified_1m") for item in classified_items)
    
    # Check if they are already in the list to prevent duplicates
    if has_shadow_ml:
        if not any(d.reason == "shadow_ml_restriction" for d in disclaimers):
            disclaimers.append(
                ReportDisclaimer(
                    text=SHADOW_ML_DISCLAIMER,
                    reason="shadow_ml_restriction",
                    severity="WARNING"
                )
            )
            
    if has_uncertified_1m:
        if not any(d.reason == "uncertified_1m_detail" for d in disclaimers):
            disclaimers.append(
                ReportDisclaimer(
                    text=VISUAL_ONLY_1M_DISCLAIMER,
                    reason="uncertified_1m_detail",
                    severity="WARNING"
                )
            )
            
    return disclaimers

