"""L0-001 bounded forcing-content identity regressions.

Package hashes must bind actual forcing values, not only record count.
These are content integrity tests, not admission or publication signatures.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import math

import pytest

from services.agribrain.layer0.source_package import Layer0SourcePackage


@dataclass
class _SampleForcing:
    event_id: str
    amount_mm: float
    observed_at: datetime


def _pkg(forcing):
    return Layer0SourcePackage(
        source_family="sensor",
        plot_id="plot-A",
        geometry_hash="geom-A",
        geometry_version=1,
        process_forcing=forcing,
    )


def test_same_count_different_water_depth_changes_package_hash():
    one = _pkg([{"event_id": "same", "amount_mm": 1.0}])
    nine = _pkg([{"event_id": "same", "amount_mm": 9.0}])
    assert one.package_id == nine.package_id
    assert one.package_hash != nine.package_hash


def test_typed_dataclass_forcing_contents_affect_hash():
    now = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
    one = _pkg([_SampleForcing("e1", 0.0, now)])
    two = _pkg([_SampleForcing("e1", 7.5, now)])
    later = _pkg([_SampleForcing("e1", 0.0, datetime(2026, 11, 1, 11, tzinfo=timezone.utc))])
    assert len({one.package_hash, two.package_hash, later.package_hash}) == 3


def test_equivalent_dict_key_order_produces_same_hash():
    a = _pkg([{"event_id": "e", "amount_mm": 2, "metadata": {"zone": "A", "depth": 5}}])
    b = _pkg([{"metadata": {"depth": 5, "zone": "A"}, "amount_mm": 2, "event_id": "e"}])
    assert a.package_hash == b.package_hash


def test_record_order_is_bound_to_identity():
    a = _pkg([{"id": "a", "mm": 1}, {"id": "b", "mm": 2}])
    b = _pkg([{"id": "b", "mm": 2}, {"id": "a", "mm": 1}])
    assert a.package_hash != b.package_hash


def test_measured_zero_differs_from_missing_value():
    zero = _pkg([{"precipitation_mm": 0.0}])
    missing = _pkg([{"precipitation_mm": None}])
    assert zero.package_hash != missing.package_hash


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_forcing_values_fail_closed(value):
    with pytest.raises(ValueError, match="nonfinite process-forcing"):
        _pkg([{"amount_mm": value}])


def test_unsupported_object_cannot_be_hashed_via_repr():
    with pytest.raises(TypeError, match="unsupported process-forcing identity type"):
        _pkg([object()])


def test_repeated_creation_with_identical_forcing_is_deterministic():
    forcing = [{"data": [0.0, 1.23], "source": "instrument"}]
    assert _pkg(forcing).package_hash == _pkg(forcing).package_hash
