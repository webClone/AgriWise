"""Pinned Sentinel Hub Process operators shared by trusted S1/S2 producers and read-only QA.

Only these exact, parameterized Evalscript v3 templates have bounded
structural semantics. This is a software allowlist, NOT independent source
attestation, immutable deployed binaries, physical calibration or an issuer.
Changing the program changes the operator contract and requires code review.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


S1_PROCESS_OPERATOR_TEMPLATE = """
    //VERSION=3
    const EXPECTED_PRODUCT_ID = __EXPECTED_PRODUCT_ID__;
    function normalizeProductId(value) {
        return String(value || "").toUpperCase().replace(".SAFE", "").replace(".ZIP", "");
    }
    function tileProductId(tile) {
        return tile.sentinel1ProductId || tile.productId || "";
    }
    function setup() {
        return {
            input: [{bands: ["VV", "VH", "dataMask"]}],
            output: [
                {id: "VV", bands: 1, sampleType: "FLOAT32"},
                {id: "VH", bands: 1, sampleType: "FLOAT32"},
                {id: "dataMask", bands: 1, sampleType: "UINT8"}
            ],
            mosaicking: "TILE"
        };
    }
    let unidentifiedTileCount = 0;
    function preProcessScenes(collections) {
        const tiles = (collections.scenes && collections.scenes.tiles) || [];
        unidentifiedTileCount = tiles.filter(function(tile) {
            return !tileProductId(tile);
        }).length;
        collections.scenes.tiles = tiles.filter(function(tile) {
            return normalizeProductId(tileProductId(tile)) === normalizeProductId(EXPECTED_PRODUCT_ID);
        });
        return collections;
    }
    function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {
        const tiles = (scenes && scenes.tiles) || [];
        outputMetadata.userData = {
            expectedProductId: EXPECTED_PRODUCT_ID,
            unidentifiedTileCount: unidentifiedTileCount,
            tiles: tiles.map(function(tile) {
                return {
                    sentinel1ProductId: tile.sentinel1ProductId,
                    productId: tile.productId,
                    id: tile.id,
                    tileId: tile.tileId,
                    shId: tile.shId,
                    dataPath: tile.dataPath,
                    date: tile.date,
                    orbitId: tile.orbitId,
                    relativeOrbitNumber: tile.relativeOrbitNumber,
                    orbitDirection: tile.orbitDirection
                };
            })
        };
    }
    function value(sample, name, fallback) {
        return sample && sample[name] !== undefined ? sample[name] : fallback;
    }
    function evaluatePixel(samples) {
        const sample = samples && samples.length ? samples[0] : null;
        return {
            VV: [value(sample, "VV", NaN)],
            VH: [value(sample, "VH", NaN)],
            dataMask: [value(sample, "dataMask", 0)]
        };
    }
"""
S2_PROCESS_OPERATOR_TEMPLATE = """
    //VERSION=3
    const EXPECTED_PRODUCT_ID = __EXPECTED_PRODUCT_ID__;
    function normalizeProductId(value) {
        return String(value || "").toUpperCase().replace(".SAFE", "").replace(".ZIP", "");
    }
    function tileProductId(tile) {
        return tile.sentinel2ProductId || tile.productId || "";
    }
    function setup() {
        return {
            input: [{bands: ["B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12", "SCL", "dataMask"]}],
            output: [
                {id: "B02", bands: 1, sampleType: "FLOAT32"},
                {id: "B03", bands: 1, sampleType: "FLOAT32"},
                {id: "B04", bands: 1, sampleType: "FLOAT32"},
                {id: "B05", bands: 1, sampleType: "FLOAT32"},
                {id: "B06", bands: 1, sampleType: "FLOAT32"},
                {id: "B07", bands: 1, sampleType: "FLOAT32"},
                {id: "B08", bands: 1, sampleType: "FLOAT32"},
                {id: "B8A", bands: 1, sampleType: "FLOAT32"},
                {id: "B11", bands: 1, sampleType: "FLOAT32"},
                {id: "B12", bands: 1, sampleType: "FLOAT32"},
                {id: "SCL", bands: 1, sampleType: "UINT8"},
                {id: "dataMask", bands: 1, sampleType: "UINT8"}
            ],
            mosaicking: "TILE"
        };
    }
    let unidentifiedTileCount = 0;
    function preProcessScenes(collections) {
        const tiles = (collections.scenes && collections.scenes.tiles) || [];
        unidentifiedTileCount = tiles.filter(function(tile) {
            return !tileProductId(tile);
        }).length;
        collections.scenes.tiles = tiles.filter(function(tile) {
            return normalizeProductId(tileProductId(tile)) === normalizeProductId(EXPECTED_PRODUCT_ID);
        });
        return collections;
    }
    function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {
        const tiles = (scenes && scenes.tiles) || [];
        outputMetadata.userData = {
            expectedProductId: EXPECTED_PRODUCT_ID,
            unidentifiedTileCount: unidentifiedTileCount,
            tiles: tiles.map(function(tile) {
                return {
                    sentinel2ProductId: tile.sentinel2ProductId,
                    productId: tile.productId,
                    id: tile.id,
                    tileId: tile.tileId,
                    shId: tile.shId,
                    dataPath: tile.dataPath,
                    date: tile.date,
                    orbitId: tile.orbitId,
                    orbitDirection: tile.orbitDirection
                };
            })
        };
    }
    function value(sample, name, fallback) {
        return sample && sample[name] !== undefined ? sample[name] : fallback;
    }
    function evaluatePixel(samples) {
        const sample = samples && samples.length ? samples[0] : null;
        return {
            B02: [value(sample, "B02", NaN)],
            B03: [value(sample, "B03", NaN)],
            B04: [value(sample, "B04", NaN)],
            B05: [value(sample, "B05", NaN)],
            B06: [value(sample, "B06", NaN)],
            B07: [value(sample, "B07", NaN)],
            B08: [value(sample, "B08", NaN)],
            B8A: [value(sample, "B8A", NaN)],
            B11: [value(sample, "B11", NaN)],
            B12: [value(sample, "B12", NaN)],
            SCL: [value(sample, "SCL", 0)],
            dataMask: [value(sample, "dataMask", 0)]
        };
    }
"""
_OPERATOR_TEMPLATES = {
    "S1": S1_PROCESS_OPERATOR_TEMPLATE,
    "S2": S2_PROCESS_OPERATOR_TEMPLATE,
}
OPERATOR_POLICY = "akaloris/layer0/native-s1-s2-process-operator/v2"


def render_native_process_operator(sensor: str, product_id: str) -> str:
    """Render the sole reviewed operator, never from untrusted JSON code."""
    if sensor not in _OPERATOR_TEMPLATES:
        raise ValueError("unsupported native sensor")
    if not isinstance(product_id, str) or not product_id.strip():
        raise ValueError("missing native product")
    return _OPERATOR_TEMPLATES[sensor].replace(
        "__EXPECTED_PRODUCT_ID__", json.dumps(product_id, ensure_ascii=False),
    )


def verify_native_process_operator(
    sensor: str, product_id: str, candidate_script: Any,
) -> bool:
    """Require byte-for-byte equality, not token presence or partial AST."""
    if not isinstance(candidate_script, str):
        return False
    try:
        return candidate_script == render_native_process_operator(sensor, product_id)
    except ValueError:
        return False


def native_process_operator_sha256(sensor: str, product_id: str) -> str:
    return hashlib.sha256(
        render_native_process_operator(sensor, product_id).encode("utf-8")
    ).hexdigest()
