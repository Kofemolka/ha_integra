from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
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
    CONF_PARTITIONS,
    CONF_ID,
)

STATE_MAP = {
    "disarmed": "disarmed",
    "armed_home": "armed_home",
    "armed_away": "armed_away",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    device_id = data[DATA_DEVICE_ID]
    client = data[DATA_CLIENT]
    parts = entry.data.get(CONF_PARTITIONS, [])
    if not parts:
        return

    entities = [
        IntegraPartitionPanel(
            client=client,
            entry_id=entry.entry_id,
            device_identifier=(DOMAIN, device_id),
            part_id=int(p[CONF_ID]),
            name=str(p[CONF_NAME]),
        )
        for p in parts
    ]
    add(entities)


class IntegraPartitionPanel(AlarmControlPanelEntity):
    _attr_should_poll = False
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_code_arm_required = False

    def __init__(
        self,
        client,
        entry_id: str,
        device_identifier,
        part_id: int,
        name: str,
    ) -> None:
        self._client = client
        self._entry_id = entry_id
        self._device_identifier = device_identifier
        self._part_id = part_id
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}-partition-{part_id}"
        self._state: bool | None = None
        self._unsub = None

    async def async_added_to_hass(self) -> None:
        # subscribe specifically to this part_id; callback receives NEW state (str)
        self._unsub = self._client.add_partition_listener(
            self._part_id, self._on_partition_state
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @property
    def state(self) -> str | None:
        return self._state

    @property
    def available(self) -> bool:
        return self._state is not None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={self._device_identifier})

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self._client.async_disarm(self._part_id)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self._client.async_arm(self._part_id)

    async def async_clear_alarm(self) -> None:
        await self._client.async_clear_alarm(self._part_id)

    def _on_partition_state(self, new_state: bool) -> None:
        if new_state != self._state:
            self._state = new_state
            self.async_write_ha_state()
