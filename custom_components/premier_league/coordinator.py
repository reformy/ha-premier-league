"""Per-team polling and full-time detection."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Fixture, PremierLeagueApiError, Team, async_get_fixtures
from .const import (
    ATTR_HOME,
    ATTR_MATCH_ID,
    ATTR_OPPONENT,
    ATTR_OUTCOME,
    ATTR_SCORE,
    ATTR_TEAM,
    ATTR_TEAM_ID,
    ATTR_VENUE,
    DOMAIN,
    EVENT_MATCH_FINISHED,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True, slots=True)
class TeamData:
    """Everything the entities need about one followed team."""

    team: Team
    fixtures: list[Fixture]

    @property
    def next_fixture(self) -> Fixture | None:
        """The soonest match that has not kicked off."""
        return next((f for f in self.fixtures if f.upcoming), None)

    @property
    def live_fixture(self) -> Fixture | None:
        """The match being played right now, if any."""
        return next((f for f in self.fixtures if f.live), None)

    @property
    def last_fixture(self) -> Fixture | None:
        """The most recently completed match."""
        return next((f for f in reversed(self.fixtures) if f.completed), None)


class PremierLeagueCoordinator(DataUpdateCoordinator[TeamData]):
    """Polls one team's fixtures and announces full time."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        session: ClientSession,
        team: Team,
    ) -> None:
        """Initialise the coordinator for a single team."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{team.id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.team = team
        self._session = session

    async def _async_update_data(self) -> TeamData:
        """Fetch fixtures, and fire an event if a match has just finished."""
        try:
            fixtures = await async_get_fixtures(self._session, self.team.id)
        except PremierLeagueApiError as err:
            raise UpdateFailed(str(err)) from err

        data = TeamData(team=self.team, fixtures=fixtures)

        # self.data is still the *previous* refresh at this point. On the first
        # refresh it is None, which is what keeps a restart from re-announcing
        # a match that finished days ago.
        previous: TeamData | None = self.data
        if previous is not None:
            finished = data.last_fixture
            if finished is not None and (
                previous.last_fixture is None or previous.last_fixture.id != finished.id
            ):
                self._fire_match_finished(finished)

        return data

    def _fire_match_finished(self, fixture: Fixture) -> None:
        """Announce full time on the event bus."""
        _LOGGER.debug(
            "%s finished against %s (%s)",
            self.team.name,
            fixture.opponent,
            fixture.result,
        )
        self.hass.bus.async_fire(
            EVENT_MATCH_FINISHED,
            {
                ATTR_TEAM: self.team.name,
                ATTR_TEAM_ID: self.team.id,
                ATTR_OPPONENT: fixture.opponent,
                ATTR_HOME: fixture.home,
                ATTR_VENUE: fixture.venue,
                ATTR_SCORE: fixture.score,
                ATTR_OUTCOME: fixture.outcome,
                ATTR_MATCH_ID: fixture.id,
            },
        )
