from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ID, CONF_PARTITIONS, DATA_CLIENT, DATA_DEVICE_ID, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    client = data[DATA_CLIENT]
    device_id = data[DATA_DEVICE_ID]
    parts = entry.data.get(CONF_PARTITIONS, [])
    if not parts:
        return

    entities: list[IntegraClearAlarmButton] = []
    for p in parts:
        pid = int(p[CONF_ID])
        pname = str(p[CONF_NAME])
        entities.append(
            IntegraClearAlarmButton(
                client=client,
                entry_id=entry.entry_id,
                device_identifier=(DOMAIN, device_id),
                partition_id=pid,
                name=f"{pname} - Clear Alarm",
            )
        )
    add_entities(entities)


class IntegraClearAlarmButton(ButtonEntity):
    """One-click 'Clear Alarm' per partition (no wiring yet)."""

    _attr_should_poll = False
    _attr_icon = "mdi:alarm-off"

    def __init__(
        self,
        client,
        entry_id: str,
        device_identifier: tuple[str, str],
        partition_id: int,
        name: str,
    ) -> None:
        self._client = client
        self._entry_id = entry_id
        self._device_identifier = device_identifier
        self._part_id = partition_id
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}-partition-{partition_id}-clear"
        self._unsub = None
        self._available = None

    async def async_added_to_hass(self) -> None:
        self._unsub = self._client.add_partition_listener(
            self._part_id, self._on_partition_state
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={self._device_identifier})

    @property
    def available(self) -> bool | None:
        return self._available

    async def async_press(self) -> None:
        """Called when the user clicks the button."""
        await self._client.async_clear_alarm(self._part_id)

    def _on_partition_state(self, new_state: bool) -> None:
        if self._client.connected != self._available:
            self._available = self._client.connected
            self.async_write_ha_state()
