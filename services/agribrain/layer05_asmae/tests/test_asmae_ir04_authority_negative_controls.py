"""IR-04/R01 adversarial authority tests — no made-up precision or uncertainty."""
from __future__ import annotations

import copy
import math

from services.agribrain.layer05_asmae.resolution.policy import apply_policies
from services.agribrain.layer05_asmae.resolution.evaluator import EvaluationResult
from services.agribrain.layer05_asmae.reintegration import _complete_uncertainty_for_states


def _candidates():
    return {
        1: EvaluationResult(resolution_m=1, composite_score=.99, operator_quality=.99),
        2: EvaluationResult(resolution_m=2, composite_score=.95, operator_quality=.95),
        10: EvaluationResult(resolution_m=10, composite_score=.90, operator_quality=.90),
    }


def test_p1_legacy_retro_score_cannot_certify_1m():
    result = apply_policies(_candidates(), scenes=[],
                            retro_scores={1: 1.0, 2: 1.0, 10: 1.0})
    assert result.safe_for_1m_claim is False
    assert result.effective_resolution_m != 1
    assert result.research_resolution_m == 1
    assert any(d["reason"] == "missing_qualified_state_cell_1m_evidence"
               for d in result.demoted_candidates)


def test_p1_even_prior_certification_is_not_a_state_cell_proof():
    from services.agribrain.layer05_asmae.schema import ASMAECertification

    certification = ASMAECertification(
        plot_id="plot", certification_level="certified",
        max_certified_resolution_m=1, retro_score=.99,
    )
    result = apply_policies(_candidates(), scenes=[], certification=certification,
                            retro_scores={1: .99, 2: .99, 10: .99})
    assert result.safe_for_1m_claim is False
    assert result.effective_resolution_m != 1


def test_p1_complete_posterior_sigma_accepted():
    assert _complete_uncertainty_for_states(
        {"vigor": .45, "root_zone_water": .30},
        {"vigor": .08, "root_zone_water": .12},
    )


def test_p1_explicit_zero_is_not_implicitly_invented():
    assert _complete_uncertainty_for_states({"vigor": .45}, {"vigor": 0.0})
    assert not _complete_uncertainty_for_states({"vigor": .45}, None)


def test_p1_missing_partial_and_extra_sigma_denied():
    assert not _complete_uncertainty_for_states({"vigor": .45, "lai": 1.2}, {"vigor": .05})
    assert not _complete_uncertainty_for_states({"vigor": .45}, {"vigor": .05, "lai": .1})
    assert not _complete_uncertainty_for_states({"vigor": .45}, {})


def test_p1_nonfinite_negative_and_nonnumeric_sigma_denied():
    for invalid in (float("nan"), float("inf"), float("-inf"), -.1, "unknown", True):
        assert not _complete_uncertainty_for_states({"vigor": .45}, {"vigor": invalid})
    assert not _complete_uncertainty_for_states({"vigor": float("nan")}, {"vigor": .1})


def test_p1_covariance_matrix_is_not_sigma_dictionary():
    assert not _complete_uncertainty_for_states({"vigor": .45}, {"vigor": [[.03]]})


def test_p1_empty_posterior_cannot_claim_authority():
    assert not _complete_uncertainty_for_states({}, {})
    assert not _complete_uncertainty_for_states(None, {})
