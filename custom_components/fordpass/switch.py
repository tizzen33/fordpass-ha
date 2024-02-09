"""Fordpass Switch Entities"""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant import exceptions


from . import FordPassEntity
from .const import DOMAIN, SWITCHES, COORDINATOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add the Switch from the config."""
    entry = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    # switches = [Switch(entry)]
    # async_add_entities(switches, False)
    for key in SWITCHES:
        sw = Switch(entry, key, config_entry.options)
        # Only add guard entity if supported by the car
        if key == "guardmode":
            if "guardstatus" in sw.coordinator.data:
                if sw.coordinator.data["guardstatus"]["returnCode"] == 200:
                    async_add_entities([sw], False)
                else:
                    _LOGGER.debug("Guard mode not supported on this vehicle")
        if key == "evcharging":
            vicmetrics = sw.coordinator.data.get('metrics', {})
            if "xevBatteryStateOfCharge" in vicmetrics:
                _LOGGER.debug("Adding charging switch for electric vehicle")
                async_add_entities([sw], False)
            else:
                _LOGGER.debug("Vehicle does not have charging capability")
        else:
            async_add_entities([sw], False)


class Switch(FordPassEntity, SwitchEntity):
    """Define the Switch for turning ignition off/on"""

    def __init__(self, coordinator, switch, options):
        """Initialize"""
        self._device_id = "fordpass_" + switch
        self.switch = switch
        self.coordinator = coordinator
        self.data = coordinator.data.get("metrics", {})
        # Required for HA 2022.7
        self.coordinator_context = object()

    async def async_turn_on(self, **kwargs):
        """Send request to vehicle on switch status on"""
        if self.switch == "ignition":
            await self.coordinator.hass.async_add_executor_job(
                self.coordinator.vehicle.start
            )
            await self.coordinator.async_request_refresh()
        elif self.switch == "guardmode":
            await self.coordinator.hass.async_add_executor_job(
                self.coordinator.vehicle.enableGuard
            )
            await self.coordinator.async_request_refresh()
        elif self.switch == "evcharging":
            plug_status = self.data.get("xevPlugChargerStatus", {}).get("value")
            if plug_status == "NOT_READY":
                _LOGGER.debug("Plug status is NOT READY, cannot start charging")
                raise exceptions.HomeAssistantError(f"EV Plug Status is {plug_status}: Cannot start charging")
            # Not working, still need to tinker
            await self.coordinator.hass.async_add_executor_job(
                self.coordinator.vehicle.charge_start
            )
            await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Send request to vehicle on switch status off"""
        if self.switch == "ignition":
            await self.coordinator.hass.async_add_executor_job(
                self.coordinator.vehicle.stop
            )
            await self.coordinator.async_request_refresh()
        elif self.switch == "guardmode":
            await self.coordinator.hass.async_add_executor_job(
                self.coordinator.vehicle.disableGuard
            )
            await self.coordinator.async_request_refresh()
        elif self.switch == "evcharging":
            # Not working, still need to tinker
            await self.coordinator.hass.async_add_executor_job(
                self.coordinator.vehicle.charge_pause
            )
            await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @property
    def name(self):
        """return switch name"""
        return "fordpass_" + self.switch + "_Switch"

    @property
    def device_id(self):
        """return switch device id"""
        return self.device_id

    @property
    def is_on(self):
        """Check status of switch"""
        if self.switch == "ignition":
            # Return None if both ignitionStatus and remoteStartCountdownTimer are None
            metrics = self.coordinator.data.get("metrics", {})
            ignition_status = metrics.get("ignitionStatus", {}).get("value")
            countdown_timer = metrics.get("remoteStartCountdownTimer", {}).get("value")
            if ignition_status == "ON" or countdown_timer is not None and countdown_timer > 0:
                return True
            return False

        if self.switch == "guardmode":
            # Need to find the correct response for enabled vs disabled so this may be spotty at the moment
            guardstatus = self.coordinator.data["guardstatus"]

            _LOGGER.debug(guardstatus)
            if guardstatus["returnCode"] == 200:
                if "gmStatus" in guardstatus:
                    if guardstatus["session"]["gmStatus"] == "enable":
                        return True
                    return False
                return False
            return False

        if self.switch == "evcharging":
            metrics = self.coordinator.data.get("metrics", {})
            charge_status = metrics.get("xevBatteryChargeDisplayStatus", {}).get("value")
            _LOGGER.debug("Charging Display Status")
            _LOGGER.debug(charge_status)
            if charge_status == "IN_PROGRESS":# or "COMPLETED":
                return True
            return False
        return False

    @property
    def icon(self):
        """Return icon for switch"""
        return SWITCHES[self.switch]["icon"]
