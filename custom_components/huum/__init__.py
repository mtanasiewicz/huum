from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS, CONF_USERNAME, CONF_PASSWORD
from .huum import Huum
import logging
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("Starting setup of HUUM integration with entry: %s", entry.as_dict())

    huum_handler = Huum(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    try:
        entry_status = await huum_handler.status_from_status_or_stop()
        _LOGGER.debug("Successfully retrieved status %s from HUUM API", str(entry_status))
    except Exception as e:
        _LOGGER.error("Error setting up HUUM integration: %s", e, exc_info=True)
        raise ConfigEntryNotReady from e

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "handler": huum_handler,
        "status": entry_status
    }

    for platform in PLATFORMS:
        _LOGGER.debug("Setting up platform: %s", platform)
        await hass.config_entries.async_forward_entry_setup(entry, platform)

    _LOGGER.debug("HUUM integration setup completed")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
