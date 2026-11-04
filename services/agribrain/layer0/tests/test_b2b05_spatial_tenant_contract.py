"""B2B-05 contract counterexamples; do not treat a request body as IAM proof."""
from dataclasses import replace

import pytest

from services.agribrain.layer0.spatial_tenant_contract import (
    AuthenticatedPrincipal, ScopedPlotRequest, PlotOwnershipRecord,
    SpatialTenantDenied, canonical_geometry_hash, authorize_plot_scope,
    verify_pixel_footprint, package_spatial_provenance,
)


def box(w, s, e, n):
    return {
        "type": "Polygon",
        "coordinates": [[
            [w, s], [e, s], [e, n], [w, n], [w, s],
        ]],
    }


PLOT = box(3.0, 36.0, 3.002, 36.002)
HASH = canonical_geometry_hash(PLOT)
OWNER = PlotOwnershipRecord("tenant-A", "plot-A", 2, HASH, PLOT)
PRINCIPAL = AuthenticatedPrincipal("tenant-A", "user-A", True)
REQUEST = ScopedPlotRequest("tenant-A", "plot-A", HASH, 2)


def resolve(plot_id):
    return OWNER if plot_id == "plot-A" else None


def grant():
    return authorize_plot_scope(PRINCIPAL, REQUEST, resolve)


def test_verified_tenant_plot_geometry_scope_is_non_authorizing():
    scope = grant()
    assert scope.tenant_id == "tenant-A"
    assert scope.geometry_hash == HASH
    assert scope.geometry_version == 2
    assert scope.source_qualified is False
    assert scope.eligible_for_state_grant is False
    assert grant().scope_hash == scope.scope_hash


@pytest.mark.parametrize("principal,plot_request", [
    (AuthenticatedPrincipal("tenant-A", "user-A", False), REQUEST),
    (AuthenticatedPrincipal("tenant-B", "user-B", True), REQUEST),
    (PRINCIPAL, replace(REQUEST, tenant_id="tenant-B")),
    (PRINCIPAL, replace(REQUEST, plot_id="plot-B")),
    (PRINCIPAL, replace(REQUEST, geometry_hash="foreign")),
    (PRINCIPAL, replace(REQUEST, geometry_version=3)),
    (PRINCIPAL, replace(REQUEST, geometry_version=True)),
])
def test_missing_or_foreign_tenant_plot_epoch_never_admitted(principal, plot_request):
    with pytest.raises(SpatialTenantDenied):
        authorize_plot_scope(principal, plot_request, resolve)


def test_resolver_is_mandatory_and_must_not_be_an_untrusted_request_record():
    with pytest.raises(SpatialTenantDenied):
        authorize_plot_scope(PRINCIPAL, REQUEST, None)
    with pytest.raises(SpatialTenantDenied):
        authorize_plot_scope(PRINCIPAL, REQUEST, lambda plot_id: replace(OWNER, tenant_id="tenant-B"))


def test_stale_stored_geometry_hash_or_epoch_fails_closed():
    with pytest.raises(SpatialTenantDenied):
        authorize_plot_scope(PRINCIPAL, REQUEST, lambda _: replace(OWNER, geometry_hash="stale"))
    with pytest.raises(SpatialTenantDenied):
        authorize_plot_scope(PRINCIPAL, REQUEST, lambda _: replace(OWNER, geometry_version=1))


def test_full_inside_pixel_is_fractionally_supported_but_never_state_granted():
    scope = grant()
    support = verify_pixel_footprint(scope, box(3.0002, 36.0002, 3.0004, 36.0004))
    assert support.classification == "FULL_CONTAINED"
    assert support.containment_fraction == pytest.approx(1.0, abs=1e-8)
    assert support.geometry_support_verified is True
    packet = package_spatial_provenance(scope, support, claimed_source_evidence_ids=["unverified-provider-ref"])
    assert packet["tenant_id"] == "tenant-A"
    assert packet["geometry_hash"] == HASH
    assert packet["authority"] == "spatial_diagnostic_only"
    assert packet["source_qualified"] is False
    assert packet["eligible_for_state_grant"] is False


def test_pixel_center_inside_does_not_convert_partial_area_to_full_plot_evidence():
    scope = grant()
    # At the right edge: center near inside, but most area is outside the polygon.
    support = verify_pixel_footprint(scope, box(3.0019, 36.0005, 3.0023, 36.0009))
    assert support.classification == "FRACTIONAL_BOUNDARY"
    assert 0.0 < support.containment_fraction < 0.5
    assert support.geometry_support_verified is False
    assert support.eligible_for_state_grant is False
    assert support.external_area_m2 > 0


def test_outside_footprint_is_quarantined():
    support = verify_pixel_footprint(grant(), box(3.003, 36.0, 3.004, 36.001))
    assert support.classification == "EXTERNAL_QUARANTINE"
    assert support.containment_fraction == 0.0
    assert support.geometry_support_verified is False


def test_geometry_attestation_rejects_invalid_polygon_and_unknown_crs():
    invalid = {"type": "Polygon", "coordinates": [[
        [3.0,36.0],[3.002,36.002],[3.002,36.0],[3.0,36.002],[3.0,36.0],
    ]]}
    for geom in (invalid, {"type": "Point", "coordinates": [3.0, 36.0]},
                 box(190.0, 36.0, 191.0, 37.0)):
        with pytest.raises(SpatialTenantDenied):
            canonical_geometry_hash(geom)


def test_scope_mismatch_cannot_lend_spatial_support_to_another_plot():
    scope = grant()
    support = verify_pixel_footprint(scope, box(3.0003,36.0003,3.0005,36.0005))
    with pytest.raises(SpatialTenantDenied):
        package_spatial_provenance(replace(scope, scope_hash="another-plot"), support)


def test_claimed_provider_receipt_never_self_qualifies():
    scope = grant()
    support = verify_pixel_footprint(scope, box(3.0002,36.0002,3.0003,36.0003))
    result = package_spatial_provenance(scope, support, claimed_source_evidence_ids=("anything",))
    assert result["claimed_source_evidence_ids"] == ["anything"]
    assert result["source_qualified"] is False
    assert result["eligible_for_state_grant"] is False
