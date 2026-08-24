"""Sensors for each followed team."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PremierLeagueConfigEntry
from .api import Fixture
from .const import (
    ATTR_HOME,
    ATTR_KICKOFF,
    ATTR_MATCH_ID,
    ATTR_OPPONENT,
    ATTR_OUTCOME,
    ATTR_SCORE,
    ATTR_VENUE,
)
from .coordinator import PremierLeagueCoordinator, TeamData
from .entity import PremierLeagueEntity


def _fixture_attrs(fixture: Fixture | None) -> dict[str, Any]:
    """Expose the whole fixture as attributes, for templates and cards."""
    if fixture is None:
        return {}
    return {
        ATTR_OPPONENT: fixture.opponent,
        "opponent_short": fixture.opponent_short,
        "opponent_abbr": fixture.opponent_abbr,
        ATTR_HOME: fixture.home,
        ATTR_VENUE: fixture.venue,
        ATTR_KICKOFF: fixture.kickoff,
        ATTR_SCORE: fixture.score,
        ATTR_OUTCOME: fixture.outcome,
        ATTR_MATCH_ID: fixture.id,
        "opponent_logo": fixture.opponent_logo,
        "status": fixture.status,
    }


@dataclass(frozen=True, kw_only=True)
class PremierLeagueSensorDescription(SensorEntityDescription):
    """Describes one Premier League sensor."""

    value_fn: Callable[[TeamData], str | datetime | None]
    attrs_fn: Callable[[TeamData], dict[str, Any]] = lambda _: {}


SENSORS: tuple[PremierLeagueSensorDescription, ...] = (
    PremierLeagueSensorDescription(
        key="next_match",
        translation_key="next_match",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: (f.kickoff if (f := data.next_fixture) else None),
        attrs_fn=lambda data: _fixture_attrs(data.next_fixture),
    ),
    PremierLeagueSensorDescription(
        key="next_opponent",
        translation_key="next_opponent",
        value_fn=lambda data: (f.opponent if (f := data.next_fixture) else None),
        attrs_fn=lambda data: _fixture_attrs(data.next_fixture),
    ),
    PremierLeagueSensorDescription(
        key="next_venue",
        translation_key="next_venue",
        device_class=SensorDeviceClass.ENUM,
        # Enum states are slugs; the display text lives in strings.json.
        options=["home", "away"],
        value_fn=lambda data: (
            ("home" if f.home else "away") if (f := data.next_fixture) else None
        ),
    ),
    PremierLeagueSensorDescription(
        key="last_match",
        translation_key="last_match",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: (f.kickoff if (f := data.last_fixture) else None),
        attrs_fn=lambda data: _fixture_attrs(data.last_fixture),
    ),
    PremierLeagueSensorDescription(
        key="last_opponent",
        translation_key="last_opponent",
        value_fn=lambda data: (f.opponent if (f := data.last_fixture) else None),
        attrs_fn=lambda data: _fixture_attrs(data.last_fixture),
    ),
    PremierLeagueSensorDescription(
        key="last_result",
        translation_key="last_result",
        value_fn=lambda data: (f.result if (f := data.last_fixture) else None),
        attrs_fn=lambda data: _fixture_attrs(data.last_fixture),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PremierLeagueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors for every followed team."""
    async_add_entities(
        PremierLeagueSensor(coordinator, description)
        for coordinator in entry.runtime_data.values()
        for description in SENSORS
    )


class PremierLeagueSensor(PremierLeagueEntity, SensorEntity):
    """A single fact about a team's fixtures."""

    entity_description: PremierLeagueSensorDescription

    def __init__(
        self,
        coordinator: PremierLeagueCoordinator,
        description: PremierLeagueSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.team.id}_{description.key}"

    @property
    def native_value(self) -> str | datetime | None:
        """Return the sensor's state."""
        return self.entity_description.value_fn(self.team_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the whole fixture alongside the state."""
        attrs = self.entity_description.attrs_fn(self.team_data)
        # The followed club's own crest, so a card can show whose fixture this
        # is without needing a second entity.
        if attrs and (logo := self.coordinator.team.logo):
            attrs["team_logo"] = logo
        return attrs
