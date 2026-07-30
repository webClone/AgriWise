"""
Irrigation Runtime — Vendor-Specific Adapters

Protocol-level adapters are handled by the drivers (MQTT, Modbus, LoRaWAN, HTTP).
This package provides vendor-specific command encoding, status decoding, and
default configuration templates.

Each vendor module exports:
  - DEFAULT_CONFIG: dict of connection_config defaults
  - DEFAULT_CAPABILITIES: ActuatorCapabilities with vendor specs
  - encode_command(): vendor-specific payload encoding (if non-standard)
  - decode_status(): vendor-specific status response parsing
"""

from irrigation_runtime.schemas import (
    ActuatorCapabilities,
    ActuatorRegistration,
    DriverProtocol,
    FailSafeState,
    IrrigationSystemType,
    VendorId,
)

# ============================================================================
# Vendor Capability Profiles
# ============================================================================

VENDOR_PROFILES = {
    # ----------------------------------------------------------------
    # Hunter (WiFi sprinkler controllers — HTTP/MQTT)
    # ----------------------------------------------------------------
    VendorId.HUNTER: {
        "models": {
            "HC-1200i": ActuatorCapabilities(
                system_type=IrrigationSystemType.SPRINKLER,
                max_flow_rate_lpm=200,
                min_flow_rate_lpm=5,
                max_pressure_bar=6.0,
                min_pressure_bar=1.5,
                max_duration_minutes=360,
                valve_count=12,
                application_efficiency=0.80,
                uniformity_coefficient=0.82,
                supports_pulse=False,
                supports_variable_rate=False,
            ),
            "Pro-HC": ActuatorCapabilities(
                system_type=IrrigationSystemType.SPRINKLER,
                max_flow_rate_lpm=500,
                min_flow_rate_lpm=5,
                max_pressure_bar=8.0,
                min_pressure_bar=1.5,
                max_duration_minutes=720,
                valve_count=24,
                application_efficiency=0.82,
                uniformity_coefficient=0.84,
                supports_pulse=True,
                supports_variable_rate=False,
            ),
        },
        "default_protocol": DriverProtocol.HTTP_REST,
        "fail_safe": FailSafeState.NORMALLY_CLOSED,
    },

    # ----------------------------------------------------------------
    # Rain Bird (WiFi/wired sprinkler controllers — HTTP/Modbus)
    # ----------------------------------------------------------------
    VendorId.RAIN_BIRD: {
        "models": {
            "ESP-ME3": ActuatorCapabilities(
                system_type=IrrigationSystemType.SPRINKLER,
                max_flow_rate_lpm=400,
                min_flow_rate_lpm=5,
                max_pressure_bar=7.0,
                min_pressure_bar=1.0,
                max_duration_minutes=720,
                valve_count=22,
                application_efficiency=0.80,
                uniformity_coefficient=0.83,
                supports_pulse=True,
                supports_variable_rate=False,
            ),
            "ESP-RZXe": ActuatorCapabilities(
                system_type=IrrigationSystemType.SPRINKLER,
                max_flow_rate_lpm=150,
                min_flow_rate_lpm=5,
                max_pressure_bar=6.0,
                min_pressure_bar=1.0,
                max_duration_minutes=360,
                valve_count=8,
                application_efficiency=0.78,
                uniformity_coefficient=0.80,
                supports_pulse=False,
                supports_variable_rate=False,
            ),
        },
        "default_protocol": DriverProtocol.HTTP_REST,
        "fail_safe": FailSafeState.NORMALLY_CLOSED,
    },

    # ----------------------------------------------------------------
    # Netafim (Precision drip — HTTP)
    # ----------------------------------------------------------------
    VendorId.NETAFIM: {
        "models": {
            "NetBeat-A": ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=1000,
                min_flow_rate_lpm=1,
                max_pressure_bar=4.0,
                min_pressure_bar=0.5,
                max_duration_minutes=1440,
                valve_count=48,
                application_efficiency=0.95,
                uniformity_coefficient=0.92,
                fertigation_capable=True,
                fertigation_injector_count=4,
                supports_pulse=True,
                supports_variable_rate=True,
            ),
            "NetBeat-C": ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=500,
                min_flow_rate_lpm=1,
                max_pressure_bar=4.0,
                min_pressure_bar=0.5,
                max_duration_minutes=1440,
                valve_count=24,
                application_efficiency=0.95,
                uniformity_coefficient=0.90,
                fertigation_capable=True,
                fertigation_injector_count=2,
                supports_pulse=True,
                supports_variable_rate=True,
            ),
        },
        "default_protocol": DriverProtocol.HTTP_REST,
        "fail_safe": FailSafeState.NORMALLY_CLOSED,
    },

    # ----------------------------------------------------------------
    # Lindsay (Center pivots — HTTP)
    # ----------------------------------------------------------------
    VendorId.LINDSAY: {
        "models": {
            "Zimmatic-9500": ActuatorCapabilities(
                system_type=IrrigationSystemType.CENTER_PIVOT,
                max_flow_rate_lpm=5000,
                min_flow_rate_lpm=100,
                max_pressure_bar=5.0,
                min_pressure_bar=1.0,
                max_duration_minutes=2880,
                valve_count=1,
                pivot_radius_m=400,
                pivot_speed_range=(1.0, 100.0),
                pivot_nozzle_count=120,
                application_efficiency=0.85,
                uniformity_coefficient=0.88,
                supports_pulse=False,
                supports_variable_rate=True,
            ),
            "FieldNET-Advisor": ActuatorCapabilities(
                system_type=IrrigationSystemType.CENTER_PIVOT,
                max_flow_rate_lpm=8000,
                min_flow_rate_lpm=200,
                max_pressure_bar=6.0,
                min_pressure_bar=1.5,
                max_duration_minutes=4320,
                valve_count=1,
                pivot_radius_m=500,
                pivot_speed_range=(1.0, 100.0),
                pivot_nozzle_count=180,
                application_efficiency=0.87,
                uniformity_coefficient=0.90,
                supports_pulse=False,
                supports_variable_rate=True,
            ),
        },
        "default_protocol": DriverProtocol.HTTP_REST,
        "fail_safe": FailSafeState.NORMALLY_CLOSED,
    },

    # ----------------------------------------------------------------
    # Valley (Center pivots + Linears — HTTP)
    # ----------------------------------------------------------------
    VendorId.VALLEY: {
        "models": {
            "ICON-Link": ActuatorCapabilities(
                system_type=IrrigationSystemType.CENTER_PIVOT,
                max_flow_rate_lpm=6000,
                min_flow_rate_lpm=150,
                max_pressure_bar=5.5,
                min_pressure_bar=1.0,
                max_duration_minutes=2880,
                valve_count=1,
                pivot_radius_m=450,
                pivot_speed_range=(1.0, 100.0),
                pivot_nozzle_count=140,
                application_efficiency=0.86,
                uniformity_coefficient=0.89,
                supports_pulse=False,
                supports_variable_rate=True,
            ),
            "Linear-8120": ActuatorCapabilities(
                system_type=IrrigationSystemType.LINEAR_MOVE,
                max_flow_rate_lpm=4000,
                min_flow_rate_lpm=100,
                max_pressure_bar=5.0,
                min_pressure_bar=1.0,
                max_duration_minutes=2880,
                valve_count=1,
                application_efficiency=0.88,
                uniformity_coefficient=0.91,
                supports_variable_rate=True,
            ),
        },
        "default_protocol": DriverProtocol.HTTP_REST,
        "fail_safe": FailSafeState.NORMALLY_CLOSED,
    },

    # ----------------------------------------------------------------
    # Toro (Commercial controllers — HTTP/Modbus)
    # ----------------------------------------------------------------
    VendorId.TORO: {
        "models": {
            "Sentinel": ActuatorCapabilities(
                system_type=IrrigationSystemType.SPRINKLER,
                max_flow_rate_lpm=800,
                min_flow_rate_lpm=10,
                max_pressure_bar=8.0,
                min_pressure_bar=1.5,
                max_duration_minutes=720,
                valve_count=200,
                application_efficiency=0.82,
                uniformity_coefficient=0.85,
                supports_pulse=True,
                supports_variable_rate=False,
            ),
        },
        "default_protocol": DriverProtocol.HTTP_REST,
        "fail_safe": FailSafeState.NORMALLY_CLOSED,
    },

    # ----------------------------------------------------------------
    # Galcon (Cloud drip/sprinkler — HTTP/MQTT)
    # ----------------------------------------------------------------
    VendorId.GALCON: {
        "models": {
            "GSI-AC24": ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=300,
                min_flow_rate_lpm=1,
                max_pressure_bar=4.0,
                min_pressure_bar=0.5,
                max_duration_minutes=720,
                valve_count=24,
                application_efficiency=0.93,
                uniformity_coefficient=0.88,
                fertigation_capable=True,
                fertigation_injector_count=2,
                supports_pulse=True,
                supports_variable_rate=False,
            ),
        },
        "default_protocol": DriverProtocol.HTTP_REST,
        "fail_safe": FailSafeState.NORMALLY_CLOSED,
    },

    # ----------------------------------------------------------------
    # Bermad (Hydraulic valves — Modbus)
    # ----------------------------------------------------------------
    VendorId.BERMAD: {
        "models": {
            "IR-410-XL": ActuatorCapabilities(
                system_type=IrrigationSystemType.DRIP,
                max_flow_rate_lpm=2000,
                min_flow_rate_lpm=10,
                max_pressure_bar=10.0,
                min_pressure_bar=0.5,
                max_duration_minutes=1440,
                valve_count=1,
                application_efficiency=0.94,
                uniformity_coefficient=0.90,
                supports_variable_rate=True,
            ),
        },
        "default_protocol": DriverProtocol.MODBUS_TCP,
        "fail_safe": FailSafeState.NORMALLY_CLOSED,
    },
}


def get_vendor_profile(vendor: VendorId, model: str = "") -> dict:
    """Get vendor capability profile.

    Args:
        vendor: The vendor identifier
        model: Optional specific model name

    Returns:
        Dict with capabilities, protocol, and fail_safe
    """
    profile = VENDOR_PROFILES.get(vendor)
    if not profile:
        return {}

    if model and model in profile.get("models", {}):
        capabilities = profile["models"][model]
    else:
        # Return first model as default
        models = profile.get("models", {})
        capabilities = next(iter(models.values())) if models else ActuatorCapabilities()

    return {
        "capabilities": capabilities,
        "default_protocol": profile.get("default_protocol", DriverProtocol.HTTP_REST),
        "fail_safe": profile.get("fail_safe", FailSafeState.NORMALLY_CLOSED),
    }
