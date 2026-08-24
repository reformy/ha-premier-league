"""Config and options flow: pick the teams to follow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import PremierLeagueApiError, Team, async_get_teams
from .const import CONF_TEAMS, DOMAIN


def _teams_schema(teams: list[Team], selected: list[str]) -> vol.Schema:
    """Build the team picker, pre-ticking whatever is already followed."""
    return vol.Schema(
        {
            vol.Required(CONF_TEAMS, default=selected): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=team.id, label=team.name)
                        for team in teams
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                    sort=False,
                )
            )
        }
    )


class PremierLeagueConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which teams to follow."""
        try:
            teams = await async_get_teams(async_get_clientsession(self.hass))
        except PremierLeagueApiError:
            return self.async_abort(reason="cannot_connect")

        errors: dict[str, str] = {}
        selected: list[str] = []

        if user_input is not None:
            selected = user_input[CONF_TEAMS]
            if selected:
                return self.async_create_entry(
                    title="Premier League", data={CONF_TEAMS: selected}
                )
            errors["base"] = "no_teams"

        return self.async_show_form(
            step_id="user",
            data_schema=_teams_schema(teams, selected),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> PremierLeagueOptionsFlow:
        """Return the options flow."""
        return PremierLeagueOptionsFlow()


class PremierLeagueOptionsFlow(OptionsFlowWithReload):
    """Change the followed teams after setup.

    OptionsFlowWithReload reloads the config entry for us once the selection
    changes, which is what brings the new teams' entities into being and takes
    the removed ones away.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-ask which teams to follow."""
        try:
            teams = await async_get_teams(async_get_clientsession(self.hass))
        except PremierLeagueApiError:
            return self.async_abort(reason="cannot_connect")

        current = self.config_entry.options.get(CONF_TEAMS) or self.config_entry.data.get(
            CONF_TEAMS, []
        )

        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_TEAMS]:
                return self.async_create_entry(data=user_input)
            errors["base"] = "no_teams"
            current = user_input[CONF_TEAMS]

        return self.async_show_form(
            step_id="init",
            data_schema=_teams_schema(teams, list(current)),
            errors=errors,
        )
