"""Constants for the Premier League integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "premier_league"

CONF_TEAMS: Final = "teams"

# ESPN's public site API: no key, no account, no registration.
API_BASE: Final = "https://site.api.espn.com/apis/site/v2/sports/soccer"
LEAGUE: Final = "eng.1"

UPDATE_INTERVAL: Final = timedelta(minutes=30)
REQUEST_TIMEOUT: Final = 30

# Fired when a followed team's match reaches full time. See README.
EVENT_MATCH_FINISHED: Final = f"{DOMAIN}_match_finished"

ATTR_TEAM: Final = "team"
ATTR_TEAM_ID: Final = "team_id"
ATTR_OPPONENT: Final = "opponent"
ATTR_HOME: Final = "home"
ATTR_VENUE: Final = "venue"
ATTR_KICKOFF: Final = "kickoff"
ATTR_SCORE: Final = "score"
ATTR_OUTCOME: Final = "outcome"
ATTR_MATCH_ID: Final = "match_id"
