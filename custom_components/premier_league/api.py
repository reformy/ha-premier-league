"""Thin async client for ESPN's public football API.

Everything this integration knows about the upstream API lives here, including
its two significant quirks:

1. The team schedule endpoint is really *two* endpoints that return disjoint
   sets of matches. `?fixture=true` returns only matches that have not been
   played; the bare endpoint returns only matches that have. A finished match
   does not flip `completed` to true in the `fixture=true` payload -- it leaves
   that payload entirely and appears in the other one. Both must be fetched to
   see a whole season, which is why `async_get_fixtures` merges them.

2. A competitor's `score` is a bare string in some payloads and a dict shaped
   `{"value": 2.0, "displayValue": "2"}` in others. `_parse_score` accepts both.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from homeassistant.util import dt as dt_util

from .const import API_BASE, LEAGUE, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class PremierLeagueApiError(Exception):
    """The upstream API could not be reached or could not be understood."""


@dataclass(frozen=True, kw_only=True, slots=True)
class Team:
    """A club, as offered in the config flow's picker."""

    id: str
    name: str
    short_name: str
    abbreviation: str
    logo: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class Fixture:
    """One match, from the point of view of the team being followed."""

    id: str
    kickoff: datetime
    opponent: str
    opponent_id: str
    opponent_logo: str | None
    home: bool
    venue: str | None
    state: str
    completed: bool
    status: str
    team_score: int | None
    opponent_score: int | None

    @property
    def live(self) -> bool:
        """Whether the match is being played right now."""
        return self.state == "in"

    @property
    def upcoming(self) -> bool:
        """Whether the match has not kicked off yet."""
        return self.state == "pre"

    @property
    def score(self) -> str | None:
        """Score as `us-them`, or None if the match has no score yet."""
        if self.team_score is None or self.opponent_score is None:
            return None
        return f"{self.team_score}-{self.opponent_score}"

    @property
    def outcome(self) -> str | None:
        """W, D or L from the followed team's point of view."""
        if self.team_score is None or self.opponent_score is None:
            return None
        if self.team_score > self.opponent_score:
            return "W"
        if self.team_score < self.opponent_score:
            return "L"
        return "D"

    @property
    def result(self) -> str | None:
        """Human-readable result, e.g. `0-2 L`."""
        if (score := self.score) is None or (outcome := self.outcome) is None:
            return None
        return f"{score} {outcome}"


def _parse_score(raw: Any) -> int | None:
    """Read a score that may be a string, a dict, or absent."""
    if isinstance(raw, dict):
        raw = raw.get("value", raw.get("displayValue"))
    if raw is None:
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _parse_logo(team: dict[str, Any]) -> str | None:
    """Pull a crest URL out of a team object, whichever shape it arrived in."""
    if isinstance(logos := team.get("logos"), list) and logos:
        if isinstance(logos[0], dict) and (href := logos[0].get("href")):
            return str(href)
    if href := team.get("logo"):
        return str(href)
    return None


def _parse_team(team: dict[str, Any]) -> Team:
    name = team.get("displayName") or team.get("name") or "Unknown"
    return Team(
        id=str(team["id"]),
        name=name,
        short_name=team.get("shortDisplayName") or name,
        abbreviation=team.get("abbreviation") or "",
        logo=_parse_logo(team),
    )


def _parse_fixture(event: dict[str, Any], team_id: str) -> Fixture | None:
    """Convert one ESPN event into a Fixture, or None if it is unusable."""
    competitions = event.get("competitions") or []
    if not competitions:
        return None
    competition = competitions[0]

    competitors = competition.get("competitors") or []
    us = next((c for c in competitors if str(c.get("id")) == team_id), None)
    them = next((c for c in competitors if str(c.get("id")) != team_id), None)
    if us is None or them is None:
        return None

    kickoff = dt_util.parse_datetime(str(event.get("date", "")))
    if kickoff is None:
        return None

    status_type = (competition.get("status") or {}).get("type") or {}
    opponent_team = them.get("team") or {}
    venue = (competition.get("venue") or {}).get("fullName")

    return Fixture(
        id=str(event.get("id") or competition.get("id") or kickoff.isoformat()),
        kickoff=dt_util.as_utc(kickoff),
        opponent=opponent_team.get("displayName")
        or opponent_team.get("name")
        or "Unknown",
        opponent_id=str(them.get("id", "")),
        opponent_logo=_parse_logo(opponent_team),
        home=us.get("homeAway") == "home",
        venue=venue,
        state=str(status_type.get("state") or "pre"),
        completed=bool(status_type.get("completed")),
        status=str(status_type.get("detail") or status_type.get("description") or ""),
        team_score=_parse_score(us.get("score")),
        opponent_score=_parse_score(them.get("score")),
    )


async def _get(session: ClientSession, url: str) -> dict[str, Any]:
    """GET one JSON document, translating every failure into our own error."""
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            response = await session.get(url)
            response.raise_for_status()
            # ESPN serves JSON as text/plain on some paths.
            return await response.json(content_type=None)
    except TimeoutError as err:
        raise PremierLeagueApiError(f"Timeout fetching {url}") from err
    except ClientError as err:
        raise PremierLeagueApiError(f"Error fetching {url}: {err}") from err
    except ValueError as err:
        raise PremierLeagueApiError(f"Invalid JSON from {url}: {err}") from err


async def async_get_teams(session: ClientSession) -> list[Team]:
    """List every club in the league, for the config flow's picker."""
    data = await _get(session, f"{API_BASE}/{LEAGUE}/teams")
    try:
        entries = data["sports"][0]["leagues"][0]["teams"]
    except (KeyError, IndexError, TypeError) as err:
        raise PremierLeagueApiError("Unexpected teams payload") from err

    teams = [_parse_team(e["team"]) for e in entries if isinstance(e.get("team"), dict)]
    if not teams:
        raise PremierLeagueApiError("Teams payload contained no teams")
    return sorted(teams, key=lambda t: t.name)


async def async_get_fixtures(session: ClientSession, team_id: str) -> list[Fixture]:
    """Return every known match for a team, played and unplayed alike.

    See the module docstring: the two URLs return disjoint halves of the season,
    so both are fetched and merged. They are requested concurrently, and a
    fixture id seen in both payloads resolves to whichever copy is further
    along, so a match that moves between them mid-refresh cannot regress.
    """
    base = f"{API_BASE}/{LEAGUE}/teams/{team_id}/schedule"
    played, upcoming = await asyncio.gather(
        _get(session, base),
        _get(session, f"{base}?fixture=true"),
    )

    merged: dict[str, Fixture] = {}
    for payload in (upcoming, played):
        for event in payload.get("events") or []:
            if not isinstance(event, dict):
                continue
            if (fixture := _parse_fixture(event, team_id)) is None:
                continue
            existing = merged.get(fixture.id)
            if existing is None or (fixture.completed and not existing.completed):
                merged[fixture.id] = fixture

    if not merged:
        raise PremierLeagueApiError(f"No fixtures returned for team {team_id}")

    return sorted(merged.values(), key=lambda f: f.kickoff)
