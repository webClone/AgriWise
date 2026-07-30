"""
Irrigation Runtime — Hardware-Agnostic Smart Irrigation Control System

This package bridges AgriBrain's agronomic intelligence (L3 Water → L6 Execution
→ L8 Prescriptive) to physical irrigation hardware across diverse protocols
(MQTT, LoRaWAN, Modbus RTU/TCP, HTTP/REST).

Architecture:
  L8 ActionCard (IRRIGATE)
    → IrrigationScheduler (weather/quota/phenology merge)
    → CommandDispatcher (state machine)
    → ActuatorRegistry (device → driver mapping)
    → HardwareDriver (protocol-specific payload)
    → SafetyMonitor (interlocks + fail-safe)
    → IrrigationValidator (closed-loop soil moisture verification)

Supported Hardware:
  - Drip systems (solenoid valves via MQTT/LoRaWAN)
  - Center pivots (Lindsay FieldNET, Valley ICON via HTTP)
  - Sprinkler systems (Hunter, Rain Bird, Toro via MQTT/Modbus)
  - Flood/furrow (gate actuators via Modbus)
  - Micro-spray (Netafim via HTTP/MQTT)
  - Subsurface drip (SDI controllers via Modbus)

Automation Modes:
  - MANUAL: farmer triggers all irrigation events
  - SEMI_AUTO: L8 recommends, farmer confirms, L6 executes
  - FULL_AUTO: critical events execute autonomously (configurable)

Contract version: 1.0.0
"""

__version__ = "1.0.0"
