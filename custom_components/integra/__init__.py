from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv


from .client import IntegraClient
from .const import (
    CONF_CODE,
    CONF_ID,
    CONF_PARTITIONS,
    CONF_TYPE,
    CONF_ZONES,
    DATA_CLIENT,
    DATA_DEVICE_ID,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

# ---------- YAML schema ----------
ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_TYPE, default="opening"): vol.In(["opening", "motion"]),
    }
)

PART_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
    }
)


def _ensure_unique_ids(items, what: str):
    ids = [it[CONF_ID] for it in items]
    if len(ids) != len(set(ids)):
        raise vol.Invalid(f"duplicate {what} id")
    return items


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_PORT, default=7094): cv.port,
                    vol.Required(CONF_CODE): cv.string,
                    vol.Optional(CONF_ZONES, default=[]): vol.All(
                        cv.ensure_list,
                        [ZONE_SCHEMA],
                        lambda v: _ensure_unique_ids(v, "zone"),
                    ),
                    vol.Optional(CONF_PARTITIONS, default=[]): vol.All(
                        cv.ensure_list,
                        [PART_SCHEMA],
                        lambda v: _ensure_unique_ids(v, "partition"),
                    ),
                }
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


# ---------- Setup ----------
async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Import YAML into a ConfigEntry (one entry only)."""
    conf = config.get(DOMAIN)
    if not conf:
        return True
    # Create/update config entry from YAML
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=conf,
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Create device, client, coordinator, forward platforms."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    code: str = entry.data[CONF_CODE]

    device_id = f"{host}:{port}"
    devreg = dr.async_get(hass)
    devreg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device_id)},
        manufacturer="Satel",
        model="Integra",
        name=f"Integra {device_id}",
        sw_version="n/a",
    )

    client = IntegraClient(hass, host, port, code)
    await client.async_start()

    # prune stale zone entities
    reg = er.async_get(hass)
    keep_ids = {
        f"{entry.entry_id}-zone-{int(z[CONF_ID])}"
        for z in entry.data.get(CONF_ZONES, [])
    }
    for e in list(reg.entities.values()):
        if e.config_entry_id == entry.entry_id and e.unique_id.startswith(
            f"{entry.entry_id}-zone-"
        ):
            if e.unique_id not in keep_ids:
                reg.async_remove(e.entity_id)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_DEVICE_ID: device_id,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data and DATA_CLIENT in data:
        try:
            await data[DATA_CLIENT].async_stop()
        except Exception:
            pass
    return ok
