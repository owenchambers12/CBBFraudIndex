from __future__ import annotations

from dataclasses import dataclass
from random import sample
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .config import Config
from .utils_http import get_bytes_cached


BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
CORE_LEAGUE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball"

@dataclass(frozen=True)
class TeamRef:
    id: str
    name: str
    conference: Optional[str] = None   # e.g. "Big 12"

CORE_LEAGUE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball"

def _items_refs(dir_json: dict) -> list[str]:
    items = dir_json.get("items") or []
    return [it.get("$ref") for it in items if isinstance(it, dict) and isinstance(it.get("$ref"), str)]

def fetch_division1_root_group_refs(season: int, cfg: Config, *, force_refresh: bool = False) -> list[str]:
    """
    This endpoint exists for you already (you printed it). It returns top-level groups:
      - NCAA Division I
      - Non-NCAA Division I
    """
    # Try season and season-1 (ESPN sometimes keys seasons by start year)
    candidates = [
        f"{CORE_LEAGUE}/seasons/{season}/types/2/groups?lang=en&region=us",
        f"{CORE_LEAGUE}/seasons/{season-1}/types/2/groups?lang=en&region=us",
    ]

    last = None
    for url in candidates:
        last = _get_json(url, cfg, cache_key=f"espn_core_groups_{season}_{abs(hash(url))}", force_refresh=force_refresh)
        refs = _items_refs(last)
        if refs:
            print(f"Discovered groups dir: {url}")
            return refs

    print("Discovered groups dir (no refs found):", candidates[-1])
    return _items_refs(last or {})

def _get_group_name(g: dict) -> str:
    return (g.get("name") or g.get("shortName") or g.get("abbreviation") or g.get("groupName") or "").strip()

def _fetch_children_group_refs(group_json: dict, cfg: Config, *, force_refresh: bool = False) -> list[str]:
    """
    A group can expose children as either:
      - children: { "$ref": "..." }
      - groups:   { "$ref": "..." }
    """
    for key in ("children", "groups"):
        obj = group_json.get(key)
        if isinstance(obj, dict) and isinstance(obj.get("$ref"), str):
            d = _get_json(obj["$ref"], cfg, cache_key=f"espn_core_group_children_{abs(hash(obj['$ref']))}", force_refresh=force_refresh)
            return _items_refs(d)
    return []


def _fetch_team_refs_from_group(group_json: dict, cfg: Config, *, force_refresh: bool = False) -> list[str]:
    teams_obj = group_json.get("teams")
    if isinstance(teams_obj, dict) and isinstance(teams_obj.get("$ref"), str):
        d = _get_json(teams_obj["$ref"], cfg, cache_key=f"espn_core_group_teams_{abs(hash(teams_obj['$ref']))}", force_refresh=force_refresh)
        return _items_refs(d)
    return []

def fetch_conference_group_refs(cfg: Config, *, force_refresh: bool = False) -> list[str]:
    """
    Discover the correct groups endpoint from the league root doc,
    then return the list of group $ref URLs.
    """
    league = _get_json(CORE_LEAGUE, cfg, cache_key="espn_core_league_root", force_refresh=force_refresh)

    groups_obj = league.get("groups")
    if not isinstance(groups_obj, dict) or not isinstance(groups_obj.get("$ref"), str):
        raise RuntimeError(f"Could not find league.groups.$ref in league root. Keys: {list(league.keys())}")

    groups_dir_url = groups_obj["$ref"]
    groups_dir = _get_json(groups_dir_url, cfg, cache_key="espn_core_groups_dir", force_refresh=force_refresh)

    items = groups_dir.get("items") or []
    refs = [it.get("$ref") for it in items if isinstance(it, dict) and isinstance(it.get("$ref"), str)]

    if not refs:
        # Sometimes groups_dir is paginated; try following 'next'
        nxt = (groups_dir.get("next") or {}).get("href") if isinstance(groups_dir.get("next"), dict) else None
        while nxt:
            more = _get_json(nxt, cfg, cache_key=f"espn_core_groups_next_{abs(hash(nxt))}", force_refresh=force_refresh)
            items2 = more.get("items") or []
            refs.extend([it.get("$ref") for it in items2 if isinstance(it, dict) and isinstance(it.get("$ref"), str)])
            nxt = (more.get("next") or {}).get("href") if isinstance(more.get("next"), dict) else None

    print(f"Discovered groups dir: {groups_dir_url}")
    print(f"Found {len(refs)} group refs")
    return refs

def _crawl_group_for_teams(group_ref: str, cfg: Config, out: dict[str, TeamRef], *, force_refresh: bool = False, depth: int = 0) -> None:
    """
    Recursively:
    - if group has children -> recurse into children
    - else if group has teams -> add those teams, with conference = this group's name
    """
    g = _get_json(group_ref, cfg, cache_key=f"espn_core_group_{abs(hash(group_ref))}", force_refresh=force_refresh)
    gname = _get_group_name(g)

    child_refs = _fetch_children_group_refs(g, cfg, force_refresh=force_refresh)
    if child_refs:
        for cref in child_refs:
            _crawl_group_for_teams(cref, cfg, out, force_refresh=force_refresh, depth=depth+1)
        return

    # Leaf group: should be a conference (ACC/SEC/etc) with teams.$ref
    team_refs = _fetch_team_refs_from_group(g, cfg, force_refresh=force_refresh)
    if not team_refs:
        return

    for tref in team_refs:
        td = _get_json(tref, cfg, cache_key=f"espn_core_team_{abs(hash(tref))}", force_refresh=force_refresh)
        tid = str(td.get("id", "")).strip()
        name = (td.get("displayName") or td.get("name") or "").strip()
        if tid and name:
            out[tid] = TeamRef(id=tid, name=name, conference=gname or None)

def fetch_teams_from_group(group_ref: str, cfg: Config, *, force_refresh: bool = False) -> list[TeamRef]:
    g = _get_json(group_ref, cfg, cache_key=f"espn_core_group_{abs(hash(group_ref))}", force_refresh=force_refresh)

    conf_name = (g.get("name") or g.get("shortName") or g.get("abbreviation") or g.get("groupName") or "").strip() or None

    # Find teams directory ref
    teams_dir_ref = None
    teams_obj = g.get("teams")
    if isinstance(teams_obj, dict) and isinstance(teams_obj.get("$ref"), str):
        teams_dir_ref = teams_obj["$ref"]
    else:
        # Sometimes nested in 'children' groups; but we’ll just skip if absent
        return []

    teams_dir = _get_json(teams_dir_ref, cfg, cache_key=f"espn_core_group_teams_{abs(hash(group_ref))}", force_refresh=force_refresh)
    items = teams_dir.get("items") or []
    team_refs = [it.get("$ref") for it in items if isinstance(it, dict) and isinstance(it.get("$ref"), str)]

    out: dict[str, TeamRef] = {}
    for tref in team_refs:
        td = _get_json(tref, cfg, cache_key=f"espn_core_team_{abs(hash(tref))}", force_refresh=force_refresh)
        tid = str(td.get("id", "")).strip()
        name = (td.get("displayName") or td.get("name") or "").strip()
        if tid and name:
            out[tid] = TeamRef(id=tid, name=name, conference=conf_name)

    return list(out.values())


def _get_json(url: str, cfg: Config, cache_key: str, force_refresh: bool = False) -> Any:
    raw = get_bytes_cached(url, cfg, cache_key=cache_key, force_refresh=force_refresh)
    text = raw.decode("utf-8", errors="replace")
    import json
    return json.loads(text)


def fetch_all_teams(cfg: Config, season: int, *, force_refresh: bool = False) -> list[TeamRef]:
    """
    Returns NCAA Division I teams by:
    1) fetching the 2 top-level groups (NCAA DI / Non-NCAA DI)
    2) selecting NCAA Division I
    3) recursively crawling its children to conference leaves and collecting teams
    """
    top_refs = fetch_division1_root_group_refs(season, cfg, force_refresh=force_refresh)
    if not top_refs:
        print("fetch_all_teams: no top-level group refs found")
        return []

    # Find the NCAA Division I group
    ncaa_d1_ref = None
    for ref in top_refs:
        g = _get_json(ref, cfg, cache_key=f"espn_core_top_group_{abs(hash(ref))}", force_refresh=force_refresh)
        if _get_group_name(g).lower().strip() == "ncaa division i":
            ncaa_d1_ref = ref
            break

    if not ncaa_d1_ref:
        # Fallback: pick the one that contains "NCAA" and "Division I"
        for ref in top_refs:
            g = _get_json(ref, cfg, cache_key=f"espn_core_top_group2_{abs(hash(ref))}", force_refresh=force_refresh)
            nm = _get_group_name(g).lower()
            if "ncaa" in nm and "division i" in nm:
                ncaa_d1_ref = ref
                break

    if not ncaa_d1_ref:
        print("fetch_all_teams: could not locate NCAA Division I group")
        return []

    teams: dict[str, TeamRef] = {}
    _crawl_group_for_teams(ncaa_d1_ref, cfg, teams, force_refresh=force_refresh)

    print(f"fetch_all_teams(DI via groups): found {len(teams)} teams")
    return list(teams.values())

def fetch_team_detail(team_id: str, cfg: Config, *, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Team detail endpoint. The Public-ESPN-API doc shows pattern /teams/{id}
    and mentions enabling stats via enable=... :contentReference[oaicite:4]{index=4}
    """
    url = f"{BASE}/teams/{team_id}?enable=stats"
    return _get_json(url, cfg, cache_key=f"espn_team_{team_id}", force_refresh=force_refresh)


def fetch_team_schedule(team_id: str, season: int, cfg: Config, *, force_refresh: bool = False) -> Dict[str, Any]:
    # Try given season and season-1 (ESPN sometimes keys by start year)
    seasons_to_try = [season, season - 1]
    last = None
    for s in seasons_to_try:
        url = f"{BASE}/teams/{team_id}/schedule?season={s}&seasontype=2"
        last = _get_json(url, cfg, cache_key=f"espn_sched_{team_id}_{s}", force_refresh=force_refresh)
        # If it has events, we’re good
        if (last.get("events") or []):
            return last
    return last or {}


def _extract_stat_value(stats_block: Any, keys: List[str]) -> Optional[float]:
    """
    ESPN stats blocks vary. Try multiple ways:
    - list of dicts with 'name'/'displayName' and 'value'
    - nested 'statistics' arrays
    """
    if stats_block is None:
        return None

    # normalize keys
    keys_l = [k.lower() for k in keys]

    def try_list(lst: List[Dict[str, Any]]) -> Optional[float]:
        for item in lst:
            nm = str(item.get("name") or item.get("displayName") or item.get("abbreviation") or "").lower()
            if nm in keys_l:
                val = item.get("value")
                try:
                    return float(val)
                except Exception:
                    return None
        return None

    if isinstance(stats_block, list) and stats_block and isinstance(stats_block[0], dict):
        v = try_list(stats_block)
        if v is not None:
            return v

    if isinstance(stats_block, dict):
        # common nesting: stats -> categories -> stats
        for k in ("stats", "statistics"):
            if k in stats_block and isinstance(stats_block[k], list):
                v = try_list(stats_block[k])
                if v is not None:
                    return v
        for k, v0 in stats_block.items():
            v = _extract_stat_value(v0, keys)
            if v is not None:
                return v

    return None


def team_season_statline(team_detail: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """
    Extract per-game season stats from ESPN team detail payload.
    ESPN often nests stats under: team -> statistics -> splits -> categories -> stats
    We recursively search for matching stat names.
    """
    stats_root = (team_detail.get("team") or {}).get("statistics") \
        or team_detail.get("statistics") \
        or team_detail

    # helper: find all stats dicts with name/value
    def iter_stat_items(node):
        if isinstance(node, dict):
            # common container
            if "stats" in node and isinstance(node["stats"], list):
                for it in node["stats"]:
                    if isinstance(it, dict) and ("name" in it or "displayName" in it):
                        yield it
            for v in node.values():
                yield from iter_stat_items(v)
        elif isinstance(node, list):
            for v in node:
                yield from iter_stat_items(v)

    # build lookup map of stat name -> value
    lookup = {}
    for it in iter_stat_items(stats_root):
        name = str(it.get("name") or it.get("displayName") or it.get("abbreviation") or "").strip()
        if not name:
            continue
        val = it.get("value")
        try:
            lookup[name.lower()] = float(val)
        except Exception:
            continue

    def get(*keys):
        for k in keys:
            v = lookup.get(k.lower())
            if v is not None:
                return v
        return None

    # Common-ish ESPN names (vary by sport/season). We include several aliases.
    ppg = get("pointsPerGame", "ppg", "points per game")
    oppg = get("opponentPointsPerGame", "oppPointsPerGame", "oppg", "points allowed per game")

    fga = get("fieldGoalsAttemptedPerGame", "fgaPerGame", "fga")
    fta = get("freeThrowsAttemptedPerGame", "ftaPerGame", "fta")
    orb = get("offensiveReboundsPerGame", "orbPerGame", "offRebPerGame", "offensive rebounds per game")
    tov = get("turnoversPerGame", "tovPerGame", "toPerGame", "turnovers per game")

    # Optional extras (if present)
    ftr = get("freeThrowAttemptRate", "ftr")
    efg = get("effectiveFieldGoalPercentage", "efg", "eFG%")
    opp3p = get("opponentThreePointPct", "opp3p%", "opp 3pt%", "opp3p")

    return {
        "ppg": ppg,
        "oppg": oppg,
        "fga": fga,
        "fta": fta,
        "orb": orb,
        "tov": tov,
        "ftr": ftr,
        "efg": efg,
        "opp_3p_pct_allowed": opp3p,
    }



def compute_efficiency_proxy(statline: Dict[str, Optional[float]]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Possessions per game proxy (Dean Oliver-ish):
      poss ≈ FGA - ORB + TO + 0.475*FTA
    Then:
      off_rtg = 100 * PPG / poss
      def_rtg = 100 * OPPG / poss
      adj_em_proxy = off_rtg - def_rtg
    """
    ppg, oppg = statline.get("ppg"), statline.get("oppg")
    fga, fta, orb, tov = statline.get("fga"), statline.get("fta"), statline.get("orb"), statline.get("tov")

    if any(v is None for v in [ppg, oppg, fga, fta, orb, tov]):
        return None, None, None

    poss = float(fga) - float(orb) + float(tov) + 0.475 * float(fta)
    if poss <= 1e-6:
        return None, None, None

    off = 100.0 * float(ppg) / poss
    deff = 100.0 * float(oppg) / poss
    em = off - deff
    return off, deff, em


def close_game_luck_from_schedule(schedule_json: Dict[str, Any], team_id: str) -> Dict[str, float]:
    """
    Extract close-game stats AND W/L from a team's schedule.
    We identify the team's competitor entry by matching competitor['team']['id'] == team_id.
    """
    events = schedule_json.get("events") or []
    games = 0
    wins = 0
    losses = 0

    close_games = 0
    close_wins = 0
    close_losses = 0

    for ev in events:
        competitions = ev.get("competitions") or []
        if not competitions:
            continue
        comp = competitions[0]
        status = (comp.get("status") or {}).get("type") or {}
        if not bool(status.get("completed")):
            continue

        competitors = comp.get("competitors") or []
        if len(competitors) != 2:
            continue

        # Find "us" by team id
        us = None
        them = None
        for c in competitors:
            tid = str((c.get("team") or {}).get("id", "")).strip()
            if tid == str(team_id):
                us = c
            else:
                them = c
        if us is None or them is None:
            continue

        try:
            us_score = int(float(us.get("score")))
            them_score = int(float(them.get("score")))
        except Exception:
            continue

        games += 1

        us_winner = bool(us.get("winner"))
        if us_winner:
            wins += 1
        else:
            losses += 1

        margin = abs(us_score - them_score)
        if margin <= 5:
            close_games += 1
            if us_winner:
                close_wins += 1
            else:
                close_losses += 1

    close_share = close_games / games if games else 0.0
    close_win_pct = close_wins / close_games if close_games else 0.0

    return {
        "games": float(games),
        "wins": float(wins),
        "losses": float(losses),
        "close_games_5": float(close_games),
        "close_wins_5": float(close_wins),
        "close_losses_5": float(close_losses),
        "close_share_5": float(close_share),
        "close_win_pct_5": float(close_win_pct),
    }

