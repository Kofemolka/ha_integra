from __future__ import annotations
import asyncio

from collections import defaultdict, abc

from homeassistant.core import HomeAssistant
from homeassistant.components.alarm_control_panel import AlarmControlPanelState

from satel_integra.satel_integra import AsyncSatel, AlarmState


ZoneListener = abc.Callable[[bool], None]
PartitionListener = abc.Callable[[AlarmControlPanelState], None]


class IntegraClient:
    def __init__(self, hass: HomeAssistant, host, port, code) -> None:
        self._hass = hass

        self._stl = AsyncSatel(host, port, hass.loop)
        self._security_code = code

        self._zone_listeners: dict[int, set[ZoneListener]] = defaultdict(set)
        self._partition_listeners: dict[int, set[PartitionListener]] = defaultdict(set)

        self._zones: dict[int, bool] = {}

        self._lock = asyncio.Lock()
        self._tasks: list[asyncio.Task] = []

    async def async_start(self) -> None:
        async with self._lock:
            await self._stl.connect()

            self._tasks.append(self._hass.loop.create_task(self._stl.keep_alive()))
            self._tasks.append(
                self._hass.loop.create_task(
                    self._stl.monitor_status(
                        zone_changed_callback=self._zone_status_changed,
                        alarm_status_callback=self._alarm_status_changed,
                    )
                )
            )

    async def async_stop(self) -> None:
        async with self._lock:
            self._stl.close()

            for t in self._tasks:
                t.cancel()
            self._tasks.clear()

    async def async_arm(self, partition_id: int) -> None:
        await self._stl.arm(self._security_code, [partition_id])

    async def async_disarm(self, partition_id: int) -> None:
        await self._stl.disarm(self._security_code, [partition_id])

    async def async_clear_alarm(self, partition_id: int) -> None:
        await self._stl.clear_alarm(self._security_code, [partition_id])

    @property
    def connected(self):
        return self._stl.connected

    def get_zone_state(self, zone_id: int) -> bool:
        if not self.connected:
            return None
        
        return zone_id in self._stl.violated_zones

    def add_zone_listener(self, zone_id: int, cb: ZoneListener):
        zone_id = int(zone_id)
        self._zone_listeners[zone_id].add(cb)

        def _unsub() -> None:
            s = self._zone_listeners.get(zone_id)
            if s:
                s.discard(cb)
                if not s:
                    self._zone_listeners.pop(zone_id, None)

        self._hass.loop.call_soon(cb, self.get_zone_state(zone_id))

        return _unsub

    def get_partition_state(self, partition_id: int) -> AlarmControlPanelState:
        state_map = {
            AlarmState.TRIGGERED: AlarmControlPanelState.TRIGGERED,
            AlarmState.TRIGGERED_FIRE: AlarmControlPanelState.TRIGGERED,
            AlarmState.ENTRY_TIME: AlarmControlPanelState.DISARMING,
            AlarmState.ARMED_MODE3: AlarmControlPanelState.ARMED_AWAY,
            AlarmState.ARMED_MODE2: AlarmControlPanelState.ARMED_AWAY,
            AlarmState.ARMED_MODE1: AlarmControlPanelState.ARMED_AWAY,
            AlarmState.ARMED_MODE0: AlarmControlPanelState.ARMED_AWAY,
            AlarmState.EXIT_COUNTDOWN_OVER_10: AlarmControlPanelState.PENDING,
            AlarmState.EXIT_COUNTDOWN_UNDER_10: AlarmControlPanelState.PENDING,
        }

        partition_state = AlarmControlPanelState.DISARMED

        for satel_state, ha_state in state_map.items():
            if (
                satel_state in self._stl.partition_states
                and partition_id in self._stl.partition_states[satel_state]
            ):
                partition_state = ha_state
                break

        return partition_state

    def add_partition_listener(self, partition_id: int, cb: PartitionListener):
        partition_id = int(partition_id)
        self._partition_listeners[partition_id].add(cb)

        def _unsub() -> None:
            s = self._partition_listeners.get(partition_id)
            if s:
                s.discard(cb)
                if not s:
                    self._partition_listeners.pop(partition_id, None)

        self._hass.loop.call_soon(cb, self.get_partition_state(int(partition_id)))

        return _unsub

    def _zone_status_changed(self, status):
        for zone_id, callbacks in list(self._zone_listeners.items()):
            state = self.get_zone_state(zone_id)
            for cb in tuple(callbacks):
                cb(state)

    def _alarm_status_changed(self):
        for pid, callbacks in list(self._partition_listeners.items()):
            state = self.get_partition_state(int(pid))
            for cb in tuple(callbacks):
                cb(state)
