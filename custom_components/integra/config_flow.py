from __future__ import annotations
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import DOMAIN, CONF_CODE


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        # YAML only
        return self.async_abort(reason="not_user_configurable")

    async def async_step_import(self, conf) -> config_entries.ConfigFlowResult:
        """Import from YAML at startup."""
        unique = f"{conf[CONF_HOST]}:{conf[CONF_PORT]}"
        await self.async_set_unique_id(unique)

        # If an entry with this unique_id already exists:
        for ent in self._async_current_entries():
            if ent.unique_id == unique:
                # Update stored data; DO NOT reload here
                self.hass.config_entries.async_update_entry(ent, data=conf, title=f"Integra {unique}")
                return self.async_abort(reason="already_configured")

        # First-time import → create entry
        return self.async_create_entry(title=f"Integra {unique}", data=conf)
