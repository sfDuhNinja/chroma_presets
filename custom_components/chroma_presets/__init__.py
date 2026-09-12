import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    ATTR_BRIGHTNESS,
    ATTR_PRESET_ID,
    ATTR_TARGETS,
    ATTR_TRANSITION,
    DOMAIN,
    SERVICE_APPLY_PRESET,
)
from .presets import apply_preset
from .util import ensure_list, resolve_targets

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

APPLY_PRESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PRESET_ID): cv.string,
        vol.Required(ATTR_TARGETS): vol.Any(dict),
        vol.Optional(ATTR_BRIGHTNESS): vol.Coerce(int),
        vol.Optional(ATTR_TRANSITION, default=1): vol.Coerce(int),
    }
)


async def async_setup(hass, config):
    async def apply_preset_service(call):
        preset_id = call.data[ATTR_PRESET_ID]
        targets = call.data[ATTR_TARGETS]
        brightness_override = call.data.get(ATTR_BRIGHTNESS)
        transition = call.data.get(ATTR_TRANSITION, 1)

        entity_ids = resolve_targets(
            hass,
            ensure_list(targets.get("entity_id")),
            ensure_list(targets.get("area_id")),
            ensure_list(targets.get("device_id")),
        )

        await apply_preset(hass, preset_id, entity_ids, brightness_override, transition)

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_PRESET,
        apply_preset_service,
        schema=APPLY_PRESET_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return True
