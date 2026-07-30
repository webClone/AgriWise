"""
Irrigation Runtime — Driver Factory

Routes actuator registrations to the correct protocol driver implementation.
Supports: MQTT, Modbus RTU/TCP, LoRaWAN, HTTP/REST.
"""

from __future__ import annotations

from typing import Dict, Type

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.schemas import ActuatorRegistration, DriverProtocol


def get_driver(registration: ActuatorRegistration) -> IrrigationActuator:
    """Instantiate the correct driver for a given actuator registration.

    Args:
        registration: The actuator's full registration record

    Returns:
        An IrrigationActuator subclass instance configured for the device

    Raises:
        ValueError: If the protocol is not supported
    """
    protocol = registration.protocol

    if protocol == DriverProtocol.MQTT:
        from irrigation_runtime.drivers.mqtt_driver import MQTTActuator
        return MQTTActuator(registration)

    elif protocol in (DriverProtocol.MODBUS_RTU, DriverProtocol.MODBUS_TCP):
        from irrigation_runtime.drivers.modbus_driver import ModbusActuator
        return ModbusActuator(registration)

    elif protocol == DriverProtocol.LORAWAN:
        from irrigation_runtime.drivers.lorawan_driver import LoRaWANActuator
        return LoRaWANActuator(registration)

    elif protocol == DriverProtocol.HTTP_REST:
        from irrigation_runtime.drivers.http_driver import HTTPActuator
        return HTTPActuator(registration)

    else:
        raise ValueError(
            f"Unsupported driver protocol: {protocol.value}. "
            f"Supported: MQTT, MODBUS_RTU, MODBUS_TCP, LORAWAN, HTTP_REST"
        )
