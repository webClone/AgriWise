from typing import Any, Literal, Optional, Tuple

def normalize_wind_direction(direction: float) -> float:
    """Ensure wind direction is circularized 0-360 degrees."""
    return direction % 360.0


def validate_rain_mode(mode: str) -> Literal["incremental", "cumulative", "event_total"]:
    if mode not in ["incremental", "cumulative", "event_total"]:
        raise ValueError(f"Unknown rainfall mode: {mode}")
    return mode


def apply_unit_conversion(
    original_value: Any,
    original_unit: str,
    target_unit: str
) -> float:
    """
    Handle unit conversion strictly. Reject unknown scales to prevent silent VWC misinterpretation.
    """
    if original_value is None:
        raise ValueError("Cannot convert None value")

    val = float(original_value)
    source = original_unit.lower()
    target = target_unit.lower()

    if source == target:
        return val

    # Conversions
    if source == "percent" and target == "fraction":
        return val / 100.0
    if source == "fraction" and target == "percent":
        return val * 100.0
        
    if source in ("f", "fahrenheit") and target in ("c", "celsius", "centigrade"):
        return (val - 32) * 5.0 / 9.0
        
    if source in ("mph", "miles_per_hour") and target in ("m/s", "ms", "m_s"):
        return val * 0.44704
    if source in ("km/h", "kmh") and target in ("m/s", "ms", "m_s"):
        return val / 3.6
        
    if source in ("in", "inches", "inch") and target == "mm":
        return val * 25.4
        
    if source == "psi" and target == "bar":
        return val * 0.0689476
        
    if source in ("ms/cm", "milli_siemens_per_cm") and target in ("ds/m", "deci_siemens_per_m"):
        return val # 1 mS/cm = 1 dS/m
        
    raise ValueError(f"Unknown or unsupported unit conversion: {source} -> {target}")


def process_rainfall(
    rainfall_value: float,
    mode: Literal["incremental", "cumulative", "event_total"]
) -> float:
    """
    Handle rainfall semantics. 
    Cumulative requires state, handled later in Aggregation. Here we just enforce non-negative.
    """
    if rainfall_value < 0:
        raise ValueError("Negative rainfall is invalid.")
    return rainfall_value
