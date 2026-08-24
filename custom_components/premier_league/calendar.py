"""A calendar of every fixture for each followed team."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PremierLeagueConfigEntry
from .api import Fixture
from .coordinator import PremierLeagueCoordinator
from .entity import PremierLeagueEntity

# ESPN gives a kickoff time but no end time. Ninety minutes plus half time and
# stoppage lands close enough for a calendar block.
MATCH_DURATION = timedelta(hours=2)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PremierLeagueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one calendar per followed team."""
    async_add_entities(
        PremierLeagueCalendar(coordinator) for coordinator in entry.runtime_data.values()
    )


class PremierLeagueCalendar(PremierLeagueEntity, CalendarEntity):
    """Every known fixture for one team, as calendar events."""

    _attr_translation_key = "fixtures"

    def __init__(self, coordinator: PremierLeagueCoordinator) -> None:
        """Initialise the calendar."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.team.id}_fixtures"

    def _to_event(self, fixture: Fixture) -> CalendarEvent:
        """Render one fixture as a calendar event."""
        team = self.coordinator.team.name
        home, away = (team, fixture.opponent) if fixture.home else (fixture.opponent, team)

        description = f"{'Home' if fixture.home else 'Away'} — Premier League"
        if (result := fixture.result) is not None:
            description = f"{description}\nResult: {result} (for {team})"

        return CalendarEvent(
            start=fixture.kickoff,
            end=fixture.kickoff + MATCH_DURATION,
            summary=f"{home} v {away}",
            description=description,
            location=fixture.venue,
            uid=fixture.id,
        )

    @property
    def event(self) -> CalendarEvent | None:
        """The match in progress, or the next one due."""
        data = self.team_data
        fixture = data.live_fixture or data.next_fixture
        return self._to_event(fixture) if fixture else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return every fixture overlapping the requested window."""
        return [
            self._to_event(fixture)
            for fixture in self.team_data.fixtures
            if fixture.kickoff < end_date
            and fixture.kickoff + MATCH_DURATION > start_date
        ]
