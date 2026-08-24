"""Shared entity plumbing."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PremierLeagueCoordinator, TeamData


class PremierLeagueEntity(CoordinatorEntity[PremierLeagueCoordinator]):
    """Base entity: one HA device per followed team."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PremierLeagueCoordinator) -> None:
        """Attach the entity to its team's device."""
        super().__init__(coordinator)
        team = coordinator.team
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, team.id)},
            name=team.name,
            manufacturer="Premier League",
            model=team.short_name,
        )

    @property
    def team_data(self) -> TeamData:
        """The current refresh for this entity's team."""
        return self.coordinator.data
