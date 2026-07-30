"""
Irrigation Runtime — Actuator Registry v1.0.0

Central registry that maps device_ids to IrrigationActuator driver instances.
Supports hot-reload, auto-discovery from sensor_runtime, and zone-based lookups.

Usage:
    registry = ActuatorRegistry()
    registry.register(registration, driver_instance)
    actuators = registry.get_actuators_for_zone("zone_a")
    await actuators[0].execute_with_safety(command)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from irrigation_runtime.actuator import IrrigationActuator
from irrigation_runtime.schemas import (
    ActuatorRegistration,
    ActuatorStatus,
    DriverProtocol,
    IrrigationZone,
    VendorId,
)

logger = logging.getLogger(__name__)


class ActuatorRegistry:
    """Central registry for all irrigation actuators on a farm.

    Responsibilities:
      - Map device_id → IrrigationActuator instance
      - Provide zone/plot-based lookups
      - Support hot-reload when new devices are registered
      - Track global actuator health metrics
    """

    def __init__(self):
        self._actuators: Dict[str, IrrigationActuator] = {}
        self._registrations: Dict[str, ActuatorRegistration] = {}
        self._zones: Dict[str, IrrigationZone] = {}
        self._driver_factories: Dict[DriverProtocol, Type[IrrigationActuator]] = {}

    # ================================================================
    # Driver Factory Registration
    # ================================================================

    def register_driver_factory(
        self,
        protocol: DriverProtocol,
        factory_class: Type[IrrigationActuator],
    ) -> None:
        """Register a driver class for a given protocol.

        This allows automatic instantiation of the correct driver
        when a new actuator is registered.

        Args:
            protocol: The communication protocol this driver handles
            factory_class: The IrrigationActuator subclass to instantiate
        """
        self._driver_factories[protocol] = factory_class
        logger.info("Registered driver factory for protocol %s: %s",
                     protocol.value, factory_class.__name__)

    # ================================================================
    # Actuator Registration
    # ================================================================

    def register(
        self,
        registration: ActuatorRegistration,
        driver: Optional[IrrigationActuator] = None,
    ) -> IrrigationActuator:
        """Register an irrigation actuator.

        If no driver instance is provided, the registry will attempt to
        auto-instantiate from the registered driver factories based on
        the registration's protocol.

        Args:
            registration: Full actuator registration with capabilities
            driver: Optional pre-configured driver instance

        Returns:
            The registered IrrigationActuator instance

        Raises:
            ValueError: If registration is invalid or no driver available
        """
        # Validate registration
        errors = registration.validate()
        if errors:
            raise ValueError(
                f"Invalid actuator registration for {registration.device_id}: "
                f"{'; '.join(errors)}"
            )

        # Auto-instantiate driver if not provided
        if driver is None:
            factory = self._driver_factories.get(registration.protocol)
            if factory is None:
                raise ValueError(
                    f"No driver factory registered for protocol "
                    f"{registration.protocol.value}. Register one with "
                    f"register_driver_factory() first."
                )
            driver = factory(registration)

        self._actuators[registration.device_id] = driver
        self._registrations[registration.device_id] = registration

        logger.info(
            "Registered actuator %s (vendor=%s, protocol=%s, zones=%s)",
            registration.device_id,
            registration.vendor.value,
            registration.protocol.value,
            registration.zone_ids,
        )

        return driver

    def unregister(self, device_id: str) -> None:
        """Remove an actuator from the registry."""
        self._actuators.pop(device_id, None)
        self._registrations.pop(device_id, None)
        logger.info("Unregistered actuator %s", device_id)

    # ================================================================
    # Zone Management
    # ================================================================

    def register_zone(self, zone: IrrigationZone) -> None:
        """Register an irrigation zone."""
        self._zones[zone.zone_id] = zone
        logger.info("Registered irrigation zone %s (%s, %.2f ha)",
                     zone.zone_id, zone.zone_name, zone.area_ha)

    def get_zone(self, zone_id: str) -> Optional[IrrigationZone]:
        """Get a zone by ID."""
        return self._zones.get(zone_id)

    def get_zones_for_plot(self, plot_id: str) -> List[IrrigationZone]:
        """Get all zones belonging to a plot."""
        return [z for z in self._zones.values() if z.plot_id == plot_id]

    # ================================================================
    # Lookups
    # ================================================================

    def get_actuator(self, device_id: str) -> Optional[IrrigationActuator]:
        """Get a single actuator by device ID."""
        return self._actuators.get(device_id)

    def get_registration(self, device_id: str) -> Optional[ActuatorRegistration]:
        """Get registration data for a device."""
        return self._registrations.get(device_id)

    def get_actuators_for_zone(self, zone_id: str) -> List[IrrigationActuator]:
        """Get all actuators serving a specific irrigation zone."""
        results = []
        for device_id, reg in self._registrations.items():
            if zone_id in reg.zone_ids:
                actuator = self._actuators.get(device_id)
                if actuator:
                    results.append(actuator)
        return results

    def get_actuators_for_plot(self, plot_id: str) -> List[IrrigationActuator]:
        """Get all actuators on a plot."""
        results = []
        for device_id, reg in self._registrations.items():
            if reg.plot_id == plot_id:
                actuator = self._actuators.get(device_id)
                if actuator:
                    results.append(actuator)
        return results

    def get_actuators_by_protocol(
        self, protocol: DriverProtocol
    ) -> List[IrrigationActuator]:
        """Get all actuators using a specific communication protocol."""
        results = []
        for device_id, reg in self._registrations.items():
            if reg.protocol == protocol:
                actuator = self._actuators.get(device_id)
                if actuator:
                    results.append(actuator)
        return results

    def get_actuators_by_vendor(
        self, vendor: VendorId
    ) -> List[IrrigationActuator]:
        """Get all actuators from a specific vendor."""
        results = []
        for device_id, reg in self._registrations.items():
            if reg.vendor == vendor:
                actuator = self._actuators.get(device_id)
                if actuator:
                    results.append(actuator)
        return results

    def get_all_actuators(self) -> List[IrrigationActuator]:
        """Get all registered actuators."""
        return list(self._actuators.values())

    def get_all_registrations(self) -> List[ActuatorRegistration]:
        """Get all registration records."""
        return list(self._registrations.values())

    # ================================================================
    # Health & Status
    # ================================================================

    def get_fleet_status(self) -> Dict[str, Dict]:
        """Get aggregated health status across all actuators."""
        status_counts: Dict[str, int] = {}
        devices = []

        for device_id, actuator in self._actuators.items():
            reg = self._registrations.get(device_id)
            status = actuator.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
            devices.append({
                "device_id": device_id,
                "vendor": reg.vendor.value if reg else "UNKNOWN",
                "protocol": reg.protocol.value if reg else "UNKNOWN",
                "status": status,
                "zones": reg.zone_ids if reg else [],
                "is_connected": actuator.is_connected,
            })

        return {
            "total_actuators": len(self._actuators),
            "total_zones": len(self._zones),
            "status_summary": status_counts,
            "devices": devices,
        }

    async def connect_all(self) -> Dict[str, bool]:
        """Attempt to connect all registered actuators.

        Returns:
            Dict mapping device_id → connection success
        """
        results = {}
        for device_id, actuator in self._actuators.items():
            try:
                success = await actuator.connect()
                results[device_id] = success
                if success:
                    logger.info("Connected to actuator %s", device_id)
                else:
                    logger.warning("Failed to connect to actuator %s", device_id)
            except Exception as exc:
                logger.error("Error connecting to actuator %s: %s", device_id, exc)
                results[device_id] = False
        return results

    async def disconnect_all(self) -> None:
        """Disconnect all actuators gracefully."""
        for device_id, actuator in self._actuators.items():
            try:
                await actuator.disconnect()
                logger.info("Disconnected actuator %s", device_id)
            except Exception as exc:
                logger.error("Error disconnecting actuator %s: %s", device_id, exc)

    async def emergency_stop_all(self) -> Dict[str, bool]:
        """Emergency stop ALL actuators across the entire farm.

        Returns:
            Dict mapping device_id → stop success
        """
        results = {}
        for device_id, actuator in self._actuators.items():
            try:
                result = await actuator.emergency_stop()
                results[device_id] = result.success
                logger.critical("Emergency stop sent to %s: success=%s",
                                device_id, result.success)
            except Exception as exc:
                logger.error("Emergency stop FAILED for %s: %s", device_id, exc)
                results[device_id] = False
        return results

    def __len__(self) -> int:
        return len(self._actuators)

    def __contains__(self, device_id: str) -> bool:
        return device_id in self._actuators

    def __repr__(self) -> str:
        return f"<ActuatorRegistry actuators={len(self._actuators)} zones={len(self._zones)}>"


# Singleton registry instance
actuator_registry = ActuatorRegistry()
