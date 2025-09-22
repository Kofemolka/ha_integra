from __future__ import annotations
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import DOMAIN, CONF_CODE


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        # YAML only
        return self.async_abort(reason="not_user_configurable")

    async def async_step_import(self, conf):
        unique = f"{conf[CONF_HOST]}:{conf[CONF_PORT]}"
        await self.async_set_unique_id(unique)

        return self.async_create_entry(title=f"Integra {unique}", data=conf)
