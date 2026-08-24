# Premier League for Home Assistant

Follow one or more Premier League clubs. Each club you follow gets a device
with sensors for its next and last match, plus a calendar of the whole season.
When a match reaches full time the integration fires an event, so automations
can react to it — put a "watch the recording" reminder on a to-do list, flash a
light in the team's colours, announce the score at breakfast.

Built because kickoffs in England land in the middle of the night in Australia,
and a reminder waiting on the kitchen tablet in the morning beats remembering.
And to my fellow Aussies: it's called *football*, not *soccer*.

![Two followed clubs on a dashboard tile](https://raw.githubusercontent.com/reformy/ha-premier-league/main/docs/fixtures-tile.png)

*Two followed clubs in one tile — see [`examples/two-club-tile.yaml`](examples/two-club-tile.yaml).*

## Installation

### HACS

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/reformy/ha-premier-league`, category **Integration**
3. Install **Premier League**, then restart Home Assistant
4. **Settings → Devices & Services → Add Integration → Premier League**

### Manual

Copy `custom_components/premier_league` into your `/config/custom_components/`
directory and restart Home Assistant.

## Configuration

All of it is in the UI. The setup dialog lists the twenty current clubs; tick
as many as you want to follow. To change the selection later, use
**Configure** on the integration — teams you untick have their device and
entities removed.

There is no YAML configuration, and nothing to put in `configuration.yaml`.

## Entities

Per followed team, where `<team>` is the club slug (`crystal_palace`):

| Entity | Example | Notes |
| --- | --- | --- |
| `sensor.<team>_next_match` | `2026-08-28T19:00:00+00:00` | Timestamp of the next kickoff |
| `sensor.<team>_next_opponent` | `Manchester City` | |
| `sensor.<team>_next_venue` | `home` | `home` or `away` (shown as Home/Away in the UI) |
| `sensor.<team>_last_match` | `2026-08-22T14:00:00+00:00` | Timestamp of the last completed match |
| `sensor.<team>_last_opponent` | `Everton` | |
| `sensor.<team>_last_result` | `0-2 L` | Score and outcome, from your team's point of view |
| `calendar.<team>_fixtures` | | Every fixture, played and unplayed |

Both `next_*` and `last_*` sensors carry the full fixture as attributes —
`opponent`, `opponent_short` (`Man City`), `opponent_abbr` (`MNC`), `home`,
`venue`, `kickoff`, `score`, `outcome`, `opponent_logo`, `team_logo`,
`status`, `match_id` — so a dashboard card usually needs only the one entity.
`team_logo` is the followed club's own crest, which lets a tile show whose
fixture it is without a second entity.

Fixtures are polled every 30 minutes.

## Reacting to full time

The integration fires `premier_league_match_finished` once per completed match:

```yaml
event_type: premier_league_match_finished
data:
  team: Crystal Palace
  team_id: "384"
  opponent: Everton
  home: false
  venue: Hill Dickinson Stadium
  score: 0-2
  outcome: L
  match_id: "401879300"
```

It fires when a match newly appears as completed, and never on the first
refresh after a restart — so restarting Home Assistant will not re-announce a
match you already know about.

### When both clubs are followed

If you follow two teams and they play each other, the match reaches both of
their coordinators. It is still announced **once**: the home side raises the
event and the away side stays quiet. So a Palace–City derby produces one
reminder, not two, and the event's `team` is whichever club was at home.

`sensor.<team>_last_result` is unaffected and stays correct from each team's
own point of view — the same derby reads `2-1 W` on one and `1-2 L` on the
other.

### The to-do blueprint

`blueprints/automation/premier_league/watch_match_todo.yaml` turns that event
into a to-do item reading **"Watch Crystal Palace - Everton match"**. Copy it
to `/config/blueprints/automation/premier_league/`, then create an automation
from it and choose your to-do list.

Or write it yourself:

```yaml
triggers:
  - trigger: event
    event_type: premier_league_match_finished
actions:
  - action: todo.add_item
    target:
      entity_id: todo.house_to_do
    data:
      item: >-
        Watch {{ trigger.event.data.team }} -
        {{ trigger.event.data.opponent }} match
```

## Dashboard

Three examples, all reading everything from `sensor.<team>_next_match`:

- [`examples/two-club-tile.yaml`](examples/two-club-tile.yaml) — the tile
  pictured above: two clubs stacked, both crests per fixture, kickoff times in
  each viewer's own 12- or 24-hour preference. Needs
  [button-card](https://github.com/custom-cards/button-card).
- [`examples/next-match-card.yaml`](examples/next-match-card.yaml) — a single
  club on one line, turning red inside 24 hours. Also button-card.
- [`examples/next-match-markdown.yaml`](examples/next-match-markdown.yaml) —
  the same with no custom cards at all.

Kickoff times in the button-card examples come from `helpers.formatTime()`,
Home Assistant's own locale-aware formatter, so they follow each user's
Profile → Time Format rather than a format baked into the card.

## How the fixture data works

Data comes from ESPN's public site API. No key, no account, no registration.

Two quirks are worth knowing, because both look like bugs from the outside and
both are handled in `api.py`:

**The schedule endpoint is really two endpoints.** `schedule?fixture=true`
returns only matches that have *not* been played; `schedule` with no parameters
returns only matches that *have*. A finished match does not flip `completed` to
true in the first payload — it disappears from it and shows up in the second.
Reading only one of them gives you either fixtures that never produce a result,
or results with no upcoming fixtures. This integration fetches both
concurrently and merges them.

**Scores change shape.** A competitor's `score` is a bare string in some
payloads and `{"value": 2.0, "displayValue": "2"}` in others. Both are parsed.

A postponed match reports `state: post` with `completed: false`, so it drops
out of both the next-match and last-match sensors rather than pinning either
one to a game that never kicked off. While a match is being played its state is
`in`; it is excluded from "next" and not yet in "last", and the calendar
entity's current event covers it.

## Migrating from REST sensors

If you previously did this with `rest:` sensors in YAML, delete that
configuration **before** installing, and remove the old entities under
**Settings → Devices & Services → Entities**. Otherwise the old
`sensor.crystal_palace_next_match` still holds that entity id in the registry
and the integration's sensor becomes `sensor.crystal_palace_next_match_2`,
silently breaking every card and automation that referenced it.

## Limitations

- Premier League only. The upstream API covers other competitions and the code
  is parameterised by league id, but nothing selects it yet.
- League fixtures only — no cups, no European competition.
- Kickoff times for matches months away are provisional, as they are everywhere.

## Disclaimer

Not affiliated with or endorsed by the Premier League, any club, or ESPN. It
reads a public endpoint that carries no usage terms for this purpose and could
change or disappear at any time.

## Licence

MIT
