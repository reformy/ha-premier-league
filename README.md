# Premier League for Home Assistant

Follow one or more Premier League clubs. Each club you follow gets a device
with sensors for its next and last match, plus a calendar of the whole season.
When a match reaches full time the integration fires an event, so automations
can react to it — put a "watch the recording" reminder on a to-do list, flash a
light in the team's colours, announce the score at breakfast.

Built because kickoffs in England land in the middle of the night in Australia,
and a reminder waiting on the kitchen tablet in the morning beats remembering.

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
| `sensor.<team>_next_venue` | `Home` | `Home` or `Away` |
| `sensor.<team>_last_match` | `2026-08-22T14:00:00+00:00` | Timestamp of the last completed match |
| `sensor.<team>_last_opponent` | `Everton` | |
| `sensor.<team>_last_result` | `0-2 L` | Score and outcome, from your team's point of view |
| `calendar.<team>_fixtures` | | Every fixture, played and unplayed |

Both `next_*` and `last_*` sensors carry the full fixture as attributes —
`opponent`, `home`, `venue`, `kickoff`, `score`, `outcome`, `opponent_logo`,
`status`, `match_id` — so a dashboard card usually needs only the one entity.

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

`examples/next-match-card.yaml` is a compact tile showing the opponent, the
kickoff in local time and how far away it is, turning red inside 24 hours. It
needs [button-card](https://github.com/custom-cards/button-card).
`examples/next-match-markdown.yaml` does the same with no custom cards.

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
