"""
Akaloris / AgriBrain — Shared Canonical Geometry Contract (v1)

Enforces cross-language byte-for-byte deterministic geometry hashing
between Python and TypeScript / JavaScript runtimes.

Contract:
- Canonicalize GeoJSON: recursively sort object keys, traverse arrays
- Deterministic Number Formatting: exact ECMAScript 262 Number::toString(10) / JSON.stringify
  - Normalizes negative zero (-0.0) to 0
  - Rejects non-finite numbers (NaN, Infinity, -Infinity)
  - Decimal notation for -6 < n <= 21, scientific notation with no exponent zero-padding for n <= -6 or n > 21
  - Byte-for-byte equivalence with V8 / Node / browser JavaScript JSON.stringify
- Compact serialization: separators=(",", ":"), ensure_ascii=False
- Digest format: sha256:{hex64}
"""

import hashlib
import json
import math
from typing import Any, Union


GEOMETRY_CONTRACT_VERSION = "canonical_geojson_sha256_v1"


def canonical_number_to_str(val: Union[int, float]) -> str:
    """Format an integer or float according to ECMAScript 262 Number::toString(10).

    Guarantees byte-for-byte serialization equivalence with JavaScript JSON.stringify:
    - Normalizes -0.0 to '0'
    - Rejects NaN, Infinity, -Infinity with ValueError
    - Formats floats in shortest exact decimal or scientific notation matching V8/ECMAScript:
      e.g. 0.000001 -> '0.000001', 0.0000001 -> '1e-7', 1e20 -> '100000000000000000000', 10.0 -> '10'
    """
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        if abs(val) >= 10**21:
            return canonical_number_to_str(float(val))
        return str(val)
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"Non-finite number in canonical GeoJSON: {val}")
        if val == 0.0:
            return "0"
        sign = "-" if math.copysign(1.0, val) < 0 else ""
        abs_val = abs(val)

        s = repr(abs_val)
        if "e" in s or "E" in s:
            mantissa, exp_str = s.lower().split("e")
            exp = int(exp_str)
        else:
            mantissa = s
            exp = 0

        if "." in mantissa:
            int_part, frac_part = mantissa.split(".")
            frac_part = frac_part.rstrip("0")
            if not frac_part:
                digits = int_part
            else:
                digits = int_part + frac_part
                exp -= len(frac_part)
        else:
            digits = mantissa

        digits = digits.lstrip("0")
        if not digits:
            return "0"

        k = len(digits)
        n = exp + k

        if k <= n <= 21:
            res = digits + ("0" * (n - k))
        elif 0 < n <= 21:
            res = digits[:n] + "." + digits[n:]
        elif -6 < n <= 0:
            res = "0." + ("0" * (-n)) + digits
        else:
            if k == 1:
                m = digits
            else:
                m = digits[0] + "." + digits[1:]
            sign_exp = "+" if (n - 1) >= 0 else "-"
            res = m + "e" + sign_exp + str(abs(n - 1))

        return sign + res
    return str(val)


def canonical_json_dumps(value: Any) -> str:
    """Serialize canonical GeoJSON with sorted keys and canonical numbers."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return canonical_number_to_str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        items = [canonical_json_dumps(elem) for elem in value]
        return "[" + ",".join(items) + "]"
    if isinstance(value, dict):
        items = [
            json.dumps(k, ensure_ascii=False) + ":" + canonical_json_dumps(value[k])
            for k in sorted(value.keys())
        ]
        return "{" + ",".join(items) + "}"
    raise TypeError(f"Object of type {type(value).__name__} is not serializable in canonical GeoJSON")


def canonicalize_geojson(value: Any) -> Any:
    """Recursively canonicalize GeoJSON structures.

    Sorts dictionary keys alphabetically, preserves array order,
    normalizes -0.0 and integer-valued floats, and validates numbers.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [canonicalize_geojson(item) for item in value]
    if isinstance(value, dict):
        return {key: canonicalize_geojson(value[key]) for key in sorted(value.keys())}
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"Non-finite number in canonical GeoJSON: {value}")
        if value == 0.0:
            return 0
        if value.is_integer() and abs(value) < 1e21:
            return int(value)
        return value
    if isinstance(value, int):
        return value
    return value


def compute_geometry_hash(geometry: Union[dict, list, str, None]) -> str:
    """Compute cross-language deterministic geometry hash with 'sha256:' prefix.

    Matches TypeScript computeGeometryHash() byte-for-byte across all
    GeoJSON geometries, features, holes, multipolygons, and numeric coordinate representations.
    """
    if not geometry:
        return "empty_geometry"
    if isinstance(geometry, str):
        trimmed = geometry.strip()
        if not trimmed:
            return "empty_geometry"
        try:
            target = json.loads(trimmed)
            if isinstance(target, dict) and len(target) == 0:
                return "empty_geometry"
        except Exception:
            digest = hashlib.sha256(geometry.encode("utf-8")).hexdigest()
            return f"sha256:{digest}"
    else:
        target = geometry

    if isinstance(target, dict) and len(target) == 0:
        return "empty_geometry"

    canonical = canonicalize_geojson(target)
    canonical_str = canonical_json_dumps(canonical)
    digest = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
