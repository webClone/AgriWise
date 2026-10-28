"""
Cross-language deterministic geometry hash contract verification.

Validates that Python compute_geometry_hash() matches the frontend
TypeScript / JavaScript computeGeometryHash() implementation byte-for-byte
against shared golden test vectors.
"""

from services.agribrain.geometry_contract import (
    GEOMETRY_CONTRACT_VERSION,
    canonicalize_geojson,
    compute_geometry_hash,
)


GOLDEN_VECTORS = [
    {
        "name": "standard_polygon",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[35.1, 31.2], [35.2, 31.2], [35.2, 31.3], [35.1, 31.3], [35.1, 31.2]]
            ],
        },
        "expected_hash": "sha256:fdef6f34da332b92acbbf0224e7de33b5c3649cfc2cc065dd15f3976453de233",
    },
    {
        "name": "feature_with_properties",
        "geometry": {
            "type": "Feature",
            "properties": {"name": "Parcel A"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[10.0, 20.0], [10.5, 20.0], [10.5, 20.5], [10.0, 20.0]]
                ],
            },
        },
        "expected_hash": "sha256:4b83c8f9a4bbed965380b7767317a8dde6b75e3a4860fd5c7aa1ac43921dfc36",
    },
    {
        "name": "multipolygon",
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                [[[2, 2], [3, 2], [3, 3], [2, 2]]],
            ],
        },
        "expected_hash": "sha256:7c7e3149ba1bb8f2051e64c4b32db9d91ee9295e6278911f801d3d20e71b0ebe",
    },
    {
        "name": "polygon_with_hole",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[10.0, 10.0], [20.0, 10.0], [20.0, 20.0], [10.0, 20.0], [10.0, 10.0]],
                [[12.0, 12.0], [18.0, 12.0], [18.0, 18.0], [12.0, 18.0], [12.0, 12.0]],
            ],
        },
        "expected_hash": "sha256:a49fc79a81f0d940bbe6c92271f871325674bb690ef01ecc41ba231e3376d6a0",
    },
    {
        "name": "feature_with_arabic_and_high_precision",
        "geometry": {
            "type": "Feature",
            "properties": {"title": "مزرعة النخيل", "id": 42},
            "geometry": {
                "type": "Point",
                "coordinates": [9.12345678, 34.98765432],
            },
        },
        "expected_hash": "sha256:a25d081a1fa5d93d7829e59556a6e00543da5072b0886bf8e32f5363cea28e47",
    },
]


def test_geometry_contract_version():
    assert GEOMETRY_CONTRACT_VERSION == "canonical_geojson_sha256_v1"


def test_empty_geometry_hash():
    assert compute_geometry_hash(None) == "empty_geometry"
    assert compute_geometry_hash("") == "empty_geometry"
    assert compute_geometry_hash({}) == "empty_geometry"


def test_golden_vectors_match():
    for vector in GOLDEN_VECTORS:
        actual = compute_geometry_hash(vector["geometry"])
        assert actual == vector["expected_hash"], f"Mismatch for vector {vector['name']}: got {actual}"


def test_coordinate_collision_prevention():
    f1 = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[35.1, 31.2], [35.2, 31.2], [35.2, 31.3], [35.1, 31.3], [35.1, 31.2]]],
        },
    }
    f2 = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[36.1, 32.2], [36.2, 32.2], [36.2, 32.3], [36.1, 32.3], [36.1, 32.2]]],
        },
    }
    h1 = compute_geometry_hash(f1)
    h2 = compute_geometry_hash(f2)
    assert h1 != h2
    assert h1.startswith("sha256:")
    assert h2.startswith("sha256:")
