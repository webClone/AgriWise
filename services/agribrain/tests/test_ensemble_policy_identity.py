from services.agribrain.layer05_asmae.job_manifest import (
    ENSEMBLE_POLICY_CONTRACT_VERSION,
    build_job_identity,
)


def test_job_identity_binds_runtime_ensemble_policy():
    identity = build_job_identity(
        "plot-identity", {"geometry_hash": "geometry"}, {},
    )

    assert identity["ensemble_policy_contract_version"] == ENSEMBLE_POLICY_CONTRACT_VERSION
    assert identity["ensemble_policy"]["standard"] == 30
    assert identity["ensemble_policy"]["certification"] == 50
    assert identity["ensemble_policy"]["offline"] == 80
