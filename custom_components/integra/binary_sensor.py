from __future__ import annotations
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_NAME

from .const import (
    DOMAIN,
    DATA_DEVICE_ID,
    DATA_CLIENT,
    CONF_ZONES,
    CONF_ID,
    CONF_TYPE,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    client = data[DATA_CLIENT]
    device_id = data[DATA_DEVICE_ID]

    zones = entry.data.get(CONF_ZONES, [])
    if not zones:
        return

    ents = []
    for z in zones:
        zid = int(z[CONF_ID])
        name = str(z[CONF_NAME])
        ztype = str(z.get(CONF_TYPE, "opening")).lower()
        device_class = (
            BinarySensorDeviceClass.MOTION
            if ztype == "motion"
            else BinarySensorDeviceClass.OPENING
        )
        ents.append(
            IntegraZoneBinarySensor(
                client=client,
                entry_id=entry.entry_id,
                device_identifier=(DOMAIN, device_id),
                zone_id=zid,
                name=name,
                device_class=device_class,
                zone_type=ztype,
            )
        )
    add(ents)


class IntegraZoneBinarySensor(BinarySensorEntity):
    _attr_should_poll = False

    def __init__(
        self,
        client,
        entry_id: str,
        device_identifier,
        zone_id: int,
        name: str,
        device_class: BinarySensorDeviceClass,
        zone_type: str,
    ) -> None:
        self._client = client
        self._entry_id = entry_id
        self._device_identifier = device_identifier
        self._zone_id = zone_id
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}-zone-{zone_id}"
        self._attr_device_class = device_class
        self._zone_type = zone_type
        self._unsub = None
        self._is_on: bool | None = None

    async def async_added_to_hass(self) -> None:
        # subscribe specifically to this zone_id; callback receives NEW state (bool)
        self._unsub = self._client.add_zone_listener(self._zone_id, self._on_zone_state)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @property
    def is_on(self) -> bool:
        return bool(self._is_on)

    @property
    def available(self) -> bool:
        return self._is_on is not None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={self._device_identifier})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"zone_id": self._zone_id, "zone_type": self._zone_type}

    def _on_zone_state(self, new_state: bool) -> None:
        if self._is_on is None or new_state != self._is_on:
            self._is_on = new_state
            self.async_write_ha_state()
