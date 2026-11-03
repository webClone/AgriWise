"""B2B-03A bounded SAR source, orbit and dual-pol QA counterexamples.

These are *fabricated* backend HTTP responses, not authenticated live
Sentinel-1 products or a calibration/independent SAR observation receipt.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
import json
import tarfile

import numpy as np
import pytest
import tifffile

from services.agribrain.layer0.archive.raster_store import RasterStore
from services.agribrain.layer0.asmae_scene_products.product_binding import (
    verify_exact_product_binding,
)
from services.agribrain.layer0.asmae_scene_products.scene_product_schema import SceneProduct
from services.agribrain.layer0.native_issuer.acquisition_evidence import NativeEvidenceStore
from services.agribrain.layer0.native_issuer.sentinel1_qualifier import (
    DOMAIN, S1NativeQAScreen, S1ScreenStatus, screen_sentinel1_native,
)
from services.agribrain.layer0.native_issuer.sentinel2_qualifier import TrustedPlotContext
from services.agribrain.layer0.asmae_scene_products.s1_real_scene_product_fetcher import (
    _stable_array_hash,
)

CATALOG="https://sh.dataspace.copernicus.eu/catalog/v1/search"
PROCESS="https://sh.dataspace.copernicus.eu/process/v1"
ITEM="S1A_IW_GRDH_1SDV_20261102T120000_20261102T120025_049123_05E012_0ACE"
WHEN=datetime(2026,11,2,12,tzinfo=timezone.utc)
FETCHED=datetime(2026,11,3,12,tzinfo=timezone.utc)
PLOT=TrustedPlotContext(
    plot_id="server-authorized-plot",geometry_hash="authoritative-geometry-v7",
    geometry_version=7,polygon_wgs84=((0.,0.),(1.,0.),(1.,1.),(0.,1.)),
)
CATALOG_REQUEST={
    "collections":["sentinel-1-grd"],"bbox":[0.,0.,1.,1.],
    "datetime":"2026-11-02T00:00:00Z/2026-11-02T23:59:59Z",
    "limit":15,
}
PROCESS_REQUEST={
    "input":{
        "bounds":{
            "bbox":[0.,0.,1.,1.],
            "properties":{"crs":"http://www.opengis.net/def/crs/EPSG/0/4326"},
        },
        "data":[{
            "type":"sentinel-1-grd",
            "dataFilter":{
                "mosaickingOrder":"mostRecent",
                "timeRange":{
                    "from":"2026-11-02T11:55:00Z",
                    "to":"2026-11-02T12:05:00Z",
                },
            },
            "processing":{"backCoeff":"GAMMA0_ELLIPSOID"},
        }],
    },
    "output":{
        "width":4,"height":4,
        "responses":[
            {"identifier":v,"format":{"type":"image/tiff"}}
            for v in ("VV","VH","dataMask")
        ] + [{"identifier":"userdata","format":{"type":"application/json"}}],
    },
    "evalscript":'//VERSION=3\nconst EXPECTED_PRODUCT_ID = '+json.dumps(ITEM)+';',
}
PROPS={
    "datetime":"2026-11-02T12:00:00Z",
    "sar:polarizations":["VV","VH"],
    "sar:product_type":"GRD",
    "sar:instrument_mode":"IW",
    "sat:relative_orbit":73,
    "sat:orbit_state":"ascending",
    "sat:absolute_orbit":12345,
}
TILE={
    "sentinel1ProductId":ITEM,
    "relativeOrbitNumber":73,
    "orbitDirection":"ASCENDING",
    "orbitId":12345,
}


def _resp(url,request,body):
    return SimpleNamespace(
        url=url,status_code=200,content=body,
        headers={"x-request-id":"fixture-provenance"},
        request=SimpleNamespace(
            url=url,method="POST",
            headers={"Authorization":"Bearer fixture-backend-token-reference"},
            body=json.dumps(request).encode("utf-8"),
        ),
    )


def _tar(bands,userdata):
    out=BytesIO()
    with tarfile.open(fileobj=out,mode="w") as archive:
        for name,arr in bands.items():
            file=BytesIO()
            tifffile.imwrite(file,np.asarray(arr))
            data=file.getvalue()
            info=tarfile.TarInfo(name+".tif")
            info.size=len(data)
            archive.addfile(info,BytesIO(data))
        data=json.dumps(userdata).encode("utf-8")
        info=tarfile.TarInfo("userdata.json")
        info.size=len(data)
        archive.addfile(info,BytesIO(data))
    return out.getvalue()


def _case(
    tmp_path, *, catalog_features=None, properties=None,
    process_tiles=None, process_request=None,
    vv=0.2, vh=0.1, data_mask=1, omit_band=None, source="real_raster",
    scene_orbit=73, scene_orbit_pass="ASCENDING",
    scene_product=ITEM, catalog_request=None,
):
    store=NativeEvidenceStore(tmp_path/"native")
    attrs=deepcopy(PROPS if properties is None else properties)
    features=(
        [{"id":ITEM,"collection":"sentinel-1-grd","properties":attrs}]
        if catalog_features is None else catalog_features
    )
    catalog_response=json.dumps({"features":features}).encode()
    records=deepcopy([TILE] if process_tiles is None else process_tiles)
    userdata={"userData":{"expectedProductId":ITEM,"tiles":records}}
    bands={
        "VV":np.full((4,4),vv,dtype=np.float32),
        "VH":np.full((4,4),vh,dtype=np.float32),
        "DATAMASK":np.full((4,4),data_mask,dtype=np.uint8),
    }
    if omit_band is not None:
        del bands[omit_band]
    request=deepcopy(PROCESS_REQUEST if process_request is None else process_request)
    capture_params=dict(
        sensor="S1",credential_reference="test-backend-oauth",
        retrieved_at=FETCHED,
    )
    native_catalog_request = CATALOG_REQUEST if catalog_request is None else catalog_request
    catalog=store.capture_http_response(
        response=_resp(CATALOG,native_catalog_request,catalog_response),
        endpoint=CATALOG,request_parameters=native_catalog_request,**capture_params,
    )
    process=store.capture_http_response(
        response=_resp(PROCESS,request,_tar(bands,userdata)),
        endpoint=PROCESS,request_parameters=request,
        provider_product_id=ITEM,**capture_params,
    )
    rstore=RasterStore()
    band_refs={}
    mask_refs={}
    for name,array in bands.items():
        dest=str(tmp_path/"rasters"/(name+".npz"))
        rstore.save_band(dest,array)
        if name=="DATAMASK":
            mask_refs[name]=dest
        else:
            band_refs[name]=dest
    binding=verify_exact_product_binding(scene_product,userdata,"S1")
    scene=SceneProduct(
        scene_id="s1-qualifier-fixture",sensor="S1",
        acquisition_datetime=WHEN,crs="EPSG:4326",
        transform=(0.,0.25,0.,1.,0.,-0.25),
        width=4,height=4,band_refs=band_refs,mask_refs=mask_refs,
        band_units={"VV":"linear_power","VH":"linear_power"},
        quality={"valid_fraction":1.0},
        source_reality=source,
        test_override=False,production_usable=False,diagnostic_only=True,
        provider_product_id=scene_product,catalog_item_id=ITEM,
        provider_relative_orbit=scene_orbit,provider_orbit_pass=scene_orbit_pass,
        provider_absolute_orbit=12345,
        content_hash=_stable_array_hash(bands),
        process_request_hash=process.request_sha256,
        provider_response_hash=process.response_sha256,
        native_catalog_acquisition_id=catalog.acquisition_id,
        native_process_acquisition_id=process.acquisition_id,
        native_evidence_status="CAPTURED_UNQUALIFIED",
        product_binding=binding["product_binding"],
        binding_proof=binding["proof"],
    )
    return scene,store,catalog,process,band_refs,mask_refs


def _screen(scene,store,*,plot=PLOT):
    return screen_sentinel1_native(
        scene=scene,evidence_store=store,trusted_plot=plot,
    )


def test_exact_sar_structural_replay_is_diagnostic_not_state_authority(tmp_path):
    scene,store,*_=_case(tmp_path)
    outcome=_screen(scene,store)
    assert isinstance(outcome,S1NativeQAScreen)
    assert outcome.status == S1ScreenStatus.SCREENED_NATIVE_SAR_STRUCTURE
    assert outcome.proof_hash and len(outcome.proof_hash)==64
    assert outcome.diagnostic_metrics["relative_orbit"]==73
    assert outcome.diagnostic_metrics["orbit_pass"]=="ASCENDING"
    assert outcome.diagnostic_metrics["valid_fraction"]==1.0
    assert outcome.diagnostic_metrics["incidence_angle_proven"] is False
    assert outcome.diagnostic_metrics["speckle_calibrated"] is False
    assert outcome.diagnostic_metrics["observation_sigma_calibrated"] is False
    assert outcome.eligible_for_state_grant is False
    assert outcome.scientific_publication_authorized is False
    assert scene.production_usable is False


def test_diagnostic_proof_stable_across_cold_reopen(tmp_path):
    scene,store,*_=_case(tmp_path)
    a=_screen(scene,store)
    b=_screen(scene,NativeEvidenceStore(store.root))
    assert a.proof_hash==b.proof_hash
    assert a.status == S1ScreenStatus.SCREENED_NATIVE_SAR_STRUCTURE


def test_caller_cannot_promote_signed_looking_metadata_flag(tmp_path):
    scene,store,*_=_case(tmp_path,data_mask=0)
    scene.production_usable=True
    scene.real_provider_product=True
    scene.usable_for_advisory=True
    assert _screen(scene,store).status == S1ScreenStatus.REJECTED


def test_missing_plot_authority_defers(tmp_path):
    scene,store,*_=_case(tmp_path)
    assert _screen(scene,store,plot=None).status == S1ScreenStatus.DEFERRED_NATIVE_AUTHORITY


def test_foreign_raster_extent_rejects(tmp_path):
    scene,store,*_=_case(tmp_path)
    plot=TrustedPlotContext(
        plot_id="other",geometry_hash="v7",geometry_version=7,
        polygon_wgs84=((1.5,1.5),(1.7,1.5),(1.7,1.7),(1.5,1.7)),
    )
    assert _screen(scene,store,plot=plot).reason=="sar_plot_outside_raster_extent"


def test_missing_radar_calibration_in_existing_fetch_request_defers(tmp_path):
    request=deepcopy(PROCESS_REQUEST)
    del request["input"]["data"][0]["processing"]
    scene,store,*_=_case(tmp_path,process_request=request)
    response=_screen(scene,store)
    assert response.status == S1ScreenStatus.DEFERRED_NATIVE_AUTHORITY
    assert response.reason == "sar_backscatter_calibration_not_proven"


@pytest.mark.parametrize("invalid",["VV","VH","DATAMASK"])
def test_required_polarization_or_mask_absent_rejects(tmp_path,invalid):
    scene,store,*_=_case(tmp_path,omit_band=invalid)
    assert _screen(scene,store).status == S1ScreenStatus.REJECTED


@pytest.mark.parametrize("vv,vh,mask",[
    (0.0,0.1,1),(0.2,0.0,1),(0.2,0.1,0),
    (float("nan"),0.1,1),(0.2,float("inf"),1),
    (-0.1,0.1,1),
])
def test_unusable_sar_power_or_mask_rejects(tmp_path,vv,vh,mask):
    scene,store,*_=_case(tmp_path,vv=vv,vh=vh,data_mask=mask)
    assert _screen(scene,store).reason=="sar_insufficient_clear_polarization_support"


@pytest.mark.parametrize("mask",[2,255])
def test_nonbinary_mask_rejects(tmp_path,mask):
    scene,store,*_=_case(tmp_path,data_mask=mask)
    assert _screen(scene,store).reason=="invalid_sar_data_mask"


def test_catalog_wrong_product_rejects(tmp_path):
    props=deepcopy(PROPS)
    scene,store,*_=_case(tmp_path,catalog_features=[
        {"id":"S1_WRONG_PRODUCT","collection":"sentinel-1-grd","properties":props}
    ])
    assert _screen(scene,store).reason == "missing_or_ambiguous_sar_catalog_product"


def test_duplicate_catalog_scene_rejects(tmp_path):
    item={"id":ITEM,"collection":"sentinel-1-grd","properties":deepcopy(PROPS)}
    scene,store,*_=_case(tmp_path,catalog_features=[item,item])
    assert _screen(scene,store).reason=="missing_or_ambiguous_sar_catalog_product"


def test_process_mixed_product_tiles_reject(tmp_path):
    second=deepcopy(TILE)
    second["sentinel1ProductId"]="OTHER_SAR_ITEM"
    scene,store,*_=_case(tmp_path,process_tiles=[TILE,second])
    assert _screen(scene,store).reason=="sar_catalog_process_product_mismatch"


@pytest.mark.parametrize("relative,direction",[(74,"ASCENDING"),(73,"DESCENDING")])
def test_catalog_to_process_orbit_conflict_rejects(tmp_path,relative,direction):
    tiles=deepcopy([TILE])
    tiles[0]["relativeOrbitNumber"]=relative
    tiles[0]["orbitDirection"]=direction
    scene,store,*_=_case(tmp_path,process_tiles=tiles)
    assert _screen(scene,store).reason=="sar_catalog_process_orbit_conflict"


def test_wrong_cached_scene_orbit_is_rejected(tmp_path):
    scene,store,*_=_case(tmp_path,scene_orbit=75)
    assert _screen(scene,store).reason=="sar_scene_orbit_conflicts_with_captured_provider"


def test_absent_catalog_orbit_defers_instead_of_pretending_track_independence(tmp_path):
    props=deepcopy(PROPS)
    del props["sat:relative_orbit"]
    scene,store,*_=_case(tmp_path,properties=props)
    result=_screen(scene,store)
    assert result.status == S1ScreenStatus.DEFERRED_NATIVE_AUTHORITY
    assert result.reason == "sar_orbit_not_proven_or_mixed"


def test_missing_catalog_pol_proof_defers(tmp_path):
    props=deepcopy(PROPS)
    del props["sar:polarizations"]
    scene,store,*_=_case(tmp_path,properties=props)
    assert _screen(scene,store).status == S1ScreenStatus.DEFERRED_NATIVE_AUTHORITY


@pytest.mark.parametrize("bad", [["VV","HH"],["VV"],["VV","VV"]])
def test_wrong_polarization_is_rejected(tmp_path,bad):
    props=deepcopy(PROPS)
    props["sar:polarizations"]=bad
    scene,store,*_=_case(tmp_path,properties=props)
    assert _screen(scene,store).reason=="sar_product_or_polarization_conflicts_with_required_dual_pol_grd"


def test_wrong_process_request_grid_rejects_from_retained_http_post(tmp_path):
    request=deepcopy(PROCESS_REQUEST)
    request["input"]["bounds"]["bbox"]=[0.,0.,2.,2.]
    scene,store,*_=_case(tmp_path,process_request=request)
    # A mismatch between the two original provider requests is disproved
    # before the cached scene-to-Process affine check is reached.
    result=_screen(scene,store)
    assert result.status == S1ScreenStatus.REJECTED
    assert result.reason=="sar_catalog_process_request_extent_conflict"


def test_wrong_process_request_acquisition_window_rejects(tmp_path):
    request=deepcopy(PROCESS_REQUEST)
    request["input"]["data"][0]["dataFilter"]["timeRange"]={
        "from":"2026-11-01T00:00:00Z",
        "to":"2026-11-01T01:00:00Z",
    }
    scene,store,*_=_case(tmp_path,process_request=request)
    assert _screen(scene,store).reason=="captured_sar_request_grid_time_or_product_mismatch"


def test_tampered_cache_pol_pixels_rejects(tmp_path):
    scene,store,_cat,_proc,refs,_mask=_case(tmp_path)
    RasterStore().save_band(refs["VH"],np.full((4,4),0.4,dtype=np.float32))
    assert _screen(scene,store).reason=="sar_cached_raster_differs_from_provider_bytes"


def test_tampered_cache_mask_rejects(tmp_path):
    scene,store,_cat,_proc,_refs,masks=_case(tmp_path)
    RasterStore().save_band(masks["DATAMASK"],np.zeros((4,4),dtype=np.uint8))
    assert _screen(scene,store).reason=="sar_cached_raster_differs_from_provider_bytes"


def test_corrupt_native_raw_provider_response_rejects(tmp_path):
    scene,store,_catalog,process,*_=_case(tmp_path)
    store._path("objects",process.object_id).write_bytes(b"tamper")
    assert _screen(scene,store).status==S1ScreenStatus.REJECTED


def test_missing_request_replay_defers_historical_sar(tmp_path):
    scene,store,_catalog,process,*_=_case(tmp_path)
    store._path("request_replays",process.acquisition_id).unlink()
    assert _screen(scene,store).reason=="historical_sar_request_not_retained"


def test_corrupt_request_replay_rejects_instead_of_defer(tmp_path):
    scene,store,_catalog,process,*_=_case(tmp_path)
    store._path("request_replays",process.acquisition_id).write_bytes(b'{"forged":true}')
    assert _screen(scene,store).reason=="invalid_original_sar_request_evidence"


def test_test_override_is_not_native_sar(tmp_path):
    scene,store,*_=_case(tmp_path)
    scene.test_override=True
    assert _screen(scene,store).reason=="missing_native_sar_evidence"


def test_wrong_power_units_deny(tmp_path):
    scene,store,*_=_case(tmp_path)
    scene.band_units["VV"]="db_display"
    assert _screen(scene,store).reason=="sar_power_units_not_proven"


@pytest.mark.parametrize("invalid",[0.2,1,True,float("nan"),1.1,"0.7"])
def test_caller_cannot_lower_sar_qa_floor(tmp_path,invalid):
    scene,store,*_=_case(tmp_path)
    result=screen_sentinel1_native(
        scene=scene,evidence_store=store,trusted_plot=PLOT,
        min_valid_fraction=invalid,
    )
    assert result.reason=="invalid_sar_qa_policy"


def test_sar_proof_never_claims_independent_multitemporal_evidence(tmp_path):
    scene,store,*_=_case(tmp_path)
    result=_screen(scene,store)
    assert result.status==S1ScreenStatus.SCREENED_NATIVE_SAR_STRUCTURE
    assert result.diagnostic_metrics["independent_multitemporal_eligibility"] is False
    assert result.eligible_for_state_grant is False


def test_legacy_sar_time_window_outside_data_filter_cannot_gain_source_qa(tmp_path):
    request=deepcopy(PROCESS_REQUEST)
    window=request["input"]["data"][0]["dataFilter"].pop("timeRange")
    request["input"]["data"][0]["timeRange"]=window
    scene,store,*_=_case(tmp_path,process_request=request)
    result=_screen(scene,store)
    assert result.status == S1ScreenStatus.REJECTED
    assert result.reason == "captured_sar_request_grid_time_or_product_mismatch"


def test_terrain_gamma_without_orthorectification_rejects(tmp_path):
    request=deepcopy(PROCESS_REQUEST)
    request["input"]["data"][0]["processing"]["backCoeff"]="GAMMA0_TERRAIN"
    request["input"]["data"][0]["processing"]["orthorectify"]=False
    scene,store,*_=_case(tmp_path,process_request=request)
    assert _screen(scene,store).reason == "sar_terrain_gamma_requires_orthorectification"


def test_terrain_gamma_with_orthorectification_remains_non_authorizing(tmp_path):
    request=deepcopy(PROCESS_REQUEST)
    request["input"]["data"][0]["processing"]["backCoeff"]="GAMMA0_TERRAIN"
    request["input"]["data"][0]["processing"]["orthorectify"]=True
    scene,store,*_=_case(tmp_path,process_request=request)
    outcome=_screen(scene,store)
    assert outcome.status == S1ScreenStatus.SCREENED_NATIVE_SAR_STRUCTURE
    assert outcome.eligible_for_state_grant is False
    assert outcome.diagnostic_metrics["incidence_angle_proven"] is False


def test_catalog_and_process_footprints_must_refer_to_same_region(tmp_path):
    catalog_request=deepcopy(CATALOG_REQUEST)
    catalog_request["bbox"]=[2.,2.,3.,3.]
    # Individually valid original POST records must still be cross-bound.
    scene,store,*_=_case(tmp_path,catalog_request=catalog_request)
    result=_screen(scene,store)
    assert result.status == S1ScreenStatus.REJECTED
    assert result.reason == "sar_catalog_process_request_extent_conflict"


@pytest.mark.parametrize("field,value,reason",[
    ("orbitDirection","DESCENDING","sar_requested_orbit_conflicts_with_catalog"),
    ("polarization","SH","sar_requested_polarization_conflicts_with_catalog"),
    ("acquisitionMode","EW","sar_requested_mode_conflicts_with_catalog"),
])
def test_original_process_filter_cannot_override_catalog_track(tmp_path,field,value,reason):
    request=deepcopy(PROCESS_REQUEST)
    request["input"]["data"][0]["dataFilter"][field]=value
    scene,store,*_=_case(tmp_path,process_request=request)
    assert _screen(scene,store).reason==reason


def test_s1_live_request_builder_matches_documented_capture_contract():
    from services.agribrain.layer0.asmae_scene_products.s1_real_scene_product_fetcher import (
        _build_native_s1_process_request,
    )
    actual=_build_native_s1_process_request(
        bbox=[0.,0.,1.,1.],width=4,height=4,
        start_utc="2026-11-02T11:55:00Z",
        end_utc="2026-11-02T12:05:00Z",
        evalscript=PROCESS_REQUEST["evalscript"],
    )
    assert actual == PROCESS_REQUEST
    data=actual["input"]["data"][0]
    assert "timeRange" not in data
    assert data["dataFilter"]["timeRange"]["from"].endswith("Z")
    assert data["processing"]["backCoeff"]=="GAMMA0_ELLIPSOID"


def test_stored_absolute_orbit_cannot_contradict_captured_catalog(tmp_path):
    scene,store,*_=_case(tmp_path)
    scene.provider_absolute_orbit=12346
    assert _screen(scene,store).reason=="sar_scene_absolute_orbit_conflict"
