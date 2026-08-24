"""The Premier League integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PremierLeagueApiError, async_get_teams
from .const import CONF_TEAMS, DOMAIN
from .coordinator import PremierLeagueCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR]

type PremierLeagueConfigEntry = ConfigEntry[dict[str, PremierLeagueCoordinator]]


def followed_team_ids(entry: ConfigEntry) -> list[str]:
    """Team ids for this entry, preferring the options flow's newer choice."""
    teams = entry.options.get(CONF_TEAMS) or entry.data.get(CONF_TEAMS) or []
    return [str(team_id) for team_id in teams]


async def async_setup_entry(
    hass: HomeAssistant, entry: PremierLeagueConfigEntry
) -> bool:
    """Set up a coordinator per followed team."""
    session = async_get_clientsession(hass)

    try:
        teams = await async_get_teams(session)
    except PremierLeagueApiError as err:
        raise ConfigEntryNotReady(f"Could not load the team list: {err}") from err

    by_id = {team.id: team for team in teams}
    wanted = followed_team_ids(entry)

    coordinators: dict[str, PremierLeagueCoordinator] = {}
    for team_id in wanted:
        team = by_id.get(team_id)
        if team is None:
            # A club that left the league still has a config entry pointing at
            # it. Skip it rather than failing setup for the other teams.
            _LOGGER.warning(
                "Team id %s is no longer in the league and will be skipped",
                team_id,
            )
            continue
        coordinators[team_id] = PremierLeagueCoordinator(hass, entry, session, team)

    if not coordinators:
        raise ConfigEntryNotReady("None of the configured teams could be resolved")

    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinators

    _async_remove_stale_devices(hass, entry, set(coordinators))

    # Changing the followed teams reloads the entry via OptionsFlowWithReload,
    # so no update listener is needed here.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: PremierLeagueConfigEntry
) -> bool:
    """Unload the config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _async_remove_stale_devices(
    hass: HomeAssistant, entry: ConfigEntry, keep: set[str]
) -> None:
    """Drop devices for teams that are no longer followed.

    Without this, unticking a team in the options flow leaves its device and
    entities behind as unavailable clutter.
    """
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        team_ids = {
            identifier for domain, identifier in device.identifiers if domain == DOMAIN
        }
        if team_ids and not team_ids & keep:
            _LOGGER.debug("Removing device for unfollowed team(s) %s", team_ids)
            registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )
