"""B2B shared Process-contract regression tests for S1/S2.

No live Copernicus provider, KMS or scientific publication authority.
"""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from services.agribrain.layer0.asmae_scene_products.product_binding import (
    exact_binding_proof_valid, verify_exact_product_binding,
)
from services.agribrain.layer0.native_issuer.process_operator_contract import (
    OPERATOR_POLICY, native_process_operator_sha256,
    render_native_process_operator, verify_native_process_operator,
)

IDS = {
    "S1": "S1A_IW_GRDH_1SDV_20261102T120000_20261102T120025_049123_05E012_0ACE",
    "S2": "S2A_MSIL2A_20261102T120000_N0100_R101_T31SAA_20261102T140000",
}
FIELDS = {"S1": "sentinel1ProductId", "S2": "sentinel2ProductId"}


def _proof(sensor, tiles, count=0):
    return verify_exact_product_binding(IDS[sensor], {
        "userData": {
            "expectedProductId": IDS[sensor],
            "unidentifiedTileCount": count,
            "tiles": tiles,
        }
    }, sensor)


@pytest.mark.parametrize("sensor", ["S1","S2"])
def test_all_tiles_explicitly_identified_can_receive_v2_exact_binding(sensor):
    source=IDS[sensor]
    identified=[{FIELDS[sensor]: source, "tileId":"tile-1"},
                {"productId":source+".SAFE","tileId":"tile-2"}]
    result=_proof(sensor,identified,0)
    assert result["is_exact"] is True
    assert result["proof"]["binding_schema_version"]=="exact_catalog_process_v2"
    assert result["proof"]["identified_tile_count"]==2
    assert result["proof"]["unidentified_tile_count"]==0
    assert result["proof"]["all_returned_tiles_identified"] is True
    assert exact_binding_proof_valid(source,result["proof"]) is True


@pytest.mark.parametrize("sensor",["S1","S2"])
@pytest.mark.parametrize("unknown", [
    {"tileId":"unknown-tile"},
    {"id":"GENERIC-ID-NOT-PRODUCT"},
    {},
    None,
])
def test_one_identified_and_one_unidentified_tile_never_bind(sensor,unknown):
    tiles=[{FIELDS[sensor]:IDS[sensor]},unknown]
    result=_proof(sensor,tiles,0)
    assert result["is_exact"] is False
    assert result["proof"]["all_returned_tiles_identified"] is False
    assert result["proof"]["unidentified_tile_count"]==1
    assert exact_binding_proof_valid(IDS[sensor],result["proof"]) is False


@pytest.mark.parametrize("sensor",["S1","S2"])
def test_generic_tile_id_equal_to_expected_is_still_unidentified(sensor):
    r=_proof(sensor,[{FIELDS[sensor]:IDS[sensor]},{"id":IDS[sensor]}])
    assert r["is_exact"] is False


@pytest.mark.parametrize("sensor",["S1","S2"])
def test_conflicting_typed_product_fields_must_not_bind(sensor):
    result=_proof(sensor,[
        {FIELDS[sensor]:IDS[sensor], "productId":"ANOTHER_PRODUCT"}
    ])
    assert result["proof"]["conflicting_tile_count"]==1
    assert result["is_exact"] is False


@pytest.mark.parametrize("sensor",["S1","S2"])
@pytest.mark.parametrize("count",[1,-1,1.0,True,"0"])
def test_unknown_tile_telemetry_must_be_exact_integer_zero(sensor,count):
    result=_proof(sensor,[{FIELDS[sensor]:IDS[sensor]}],count)
    assert result["is_exact"] is False
    assert exact_binding_proof_valid(IDS[sensor],result["proof"]) is False


@pytest.mark.parametrize("sensor",["S1","S2"])
def test_wrong_expected_product_claim_fails(sensor):
    r=verify_exact_product_binding(IDS[sensor],{
        "userData":{
            "expectedProductId":"UNRELATED_CATALOG_PRODUCT",
            "unidentifiedTileCount":0,
            "tiles":[{FIELDS[sensor]:IDS[sensor]}],
        }
    },sensor)
    assert r["is_exact"] is False


@pytest.mark.parametrize("sensor",["S1","S2"])
def test_legacy_v1_cached_exact_label_cannot_promote_to_v2(sensor):
    result=_proof(sensor,[{FIELDS[sensor]:IDS[sensor]}])
    legacy=deepcopy(result["proof"])
    legacy["binding_schema_version"]="exact_catalog_process_v1"
    assert legacy["exact_match"] is True
    assert exact_binding_proof_valid(IDS[sensor],legacy) is False


@pytest.mark.parametrize("sensor",["S1","S2"])
def test_cached_v2_proof_count_forgeries_rejected(sensor):
    r=_proof(sensor,[{FIELDS[sensor]:IDS[sensor]}])
    valid=r["proof"]
    for key,value in [
        ("returned_tile_count",2),
        ("identified_tile_count",2),
        ("unidentified_tile_count",1),
        ("conflicting_tile_count",1),
        ("reported_unidentified_tile_count",True),
        ("all_returned_tiles_identified",False),
    ]:
        tampered=deepcopy(valid)
        tampered[key]=value
        assert exact_binding_proof_valid(IDS[sensor],tampered) is False, key


@pytest.mark.parametrize("sensor",["S1","S2"])
def test_operator_exact_script_policy_requires_full_program_not_partial_tokens(sensor):
    script=render_native_process_operator(sensor,IDS[sensor])
    assert "__EXPECTED_PRODUCT_ID__" not in script
    assert "unidentifiedTileCount" in script
    assert "let unidentifiedTileCount = -1;" in script
    assert "function preProcessScenes(collections)" in script
    assert "function evaluatePixel(samples)" in script
    assert verify_native_process_operator(sensor,IDS[sensor],script) is True
    assert len(native_process_operator_sha256(sensor,IDS[sensor]))==64
    assert OPERATOR_POLICY.endswith("/v2")
    assert " || tile.id || " not in script
    for altered in (
        script.replace('dataMask: [value(sample, "dataMask", 0)]',
                       'dataMask: [1]'),
        script.replace("function preProcessScenes(collections)",
                       "function preProcessScenesDisabled(collections)"),
        script + "\n// appended untrusted code",
    ):
        assert altered != script
        assert verify_native_process_operator(sensor,IDS[sensor],altered) is False


@pytest.mark.parametrize("sensor",["S1","S2"])
def test_different_product_selection_changes_operator_hash(sensor):
    original=native_process_operator_sha256(sensor,IDS[sensor])
    alternative=native_process_operator_sha256(sensor,"DIFFERENT_NATIVE_PRODUCT")
    assert original != alternative


@pytest.mark.parametrize("sensor",["S1","S2"])
def test_missing_prefilter_count_cannot_claim_v2_exact(sensor):
    userdata={"userData":{
        "expectedProductId":IDS[sensor],
        "tiles":[{FIELDS[sensor]:IDS[sensor]}],
    }}
    result=verify_exact_product_binding(IDS[sensor],userdata,sensor)
    assert result["is_exact"] is False
    assert result["proof"]["reported_unidentified_tile_count"] is None


@pytest.mark.parametrize("sensor",["S1","S2"])
def test_unexecuted_operator_prefilter_sentinel_value_denied(sensor):
    result=_proof(sensor,[{FIELDS[sensor]:IDS[sensor]}],-1)
    assert result["is_exact"] is False
    assert result["proof"]["reported_unidentified_tile_count"] == -1


@pytest.mark.parametrize("sensor",["S1","S2"])
def test_missing_selected_product_claim_cannot_bind(sensor):
    userdata={"userData":{
        "unidentifiedTileCount":0,
        "tiles":[{FIELDS[sensor]:IDS[sensor]}],
    }}
    assert verify_exact_product_binding(IDS[sensor],userdata,sensor)["is_exact"] is False
