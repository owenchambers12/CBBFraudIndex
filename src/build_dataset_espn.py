from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from collections import Counter

import pandas as pd

from .config import Config
from .espn_api import (
    fetch_all_teams,
    fetch_team_schedule,
)
from .quality_from_schedule import team_quality_from_schedule, pythag_expectation

POWER_CONFERENCES = {
    # current “power” men’s hoops branding varies; keep it simple and editable
    "ACC",
    "Big Ten",
    "Big 12",
    "SEC",
    "Big East",
    # Optional: add "Pac-12" if you want legacy/realignment tracking
}

def is_power_conf(conf: str | None) -> bool:
    if not conf:
        return False
    c = conf.lower()
    return any(k in c for k in [
        "atlantic coast", "acc",
        "big ten",
        "big 12",
        "southeastern", "sec",
        "big east",
    ])



def build_team_dataset(
    season: int,
    cfg: Config,
    *,
    force_refresh: bool = False,
    max_workers: int = 10,
    min_games: int = 5,
) -> pd.DataFrame:
    """
    Build a tidy team-level dataset from ESPN schedule results only.

    Outputs columns used by fraud_index.py + extras for auditing:
      team_id, team, wins, losses, games,
      win_pct, avg_margin, ppg_for, ppg_against,
      pyth_win_pct, luck_overperformance,
      close_share_5, close_win_pct_5, close_games_5, close_wins_5, close_losses_5

    Notes:
    - We derive W/L from completed games in each team schedule.
    - We derive "quality" from scoring profile (avg margin + Pythag expectation).
    - We set adj_em to avg_margin as an MVP quality proxy (can be replaced later).
    """
    teams = fetch_all_teams(cfg, season=season, force_refresh=force_refresh)
    conf_counts = Counter((t.conference or "UNKNOWN") for t in teams)
    print("Top conferences by count:")
    for conf, ct in conf_counts.most_common(30):
        print(f"{ct:>3}  {conf}")

    # show what your filter is actually including
    power = [t for t in teams if is_power_conf(t.conference)]
    print(f"Power-conference teams: {len(power)}")

    # show teams whose conf *sounds* power-ish but got excluded (debug)
    keywords = ["acc", "atlantic", "big ten", "big 12", "southeastern", "sec", "big east"]
    excluded_suspects = []
    for t in teams:
        c = (t.conference or "").lower()
        if any(k in c for k in keywords) and not is_power_conf(t.conference):
            excluded_suspects.append((t.name, t.conference))
    print("Excluded suspects (name, conference):")
    for row in excluded_suspects[:50]:
        print(row)
    # teams = [t for t in teams if is_power_conf(t.conference)]
    # print(f"Power-conference teams: {len(teams)}")

    # if not teams:
    #     cols = [
    #         "team_id","team","wins","losses","games","adj_em",
    #         "win_pct","avg_margin","ppg_for","ppg_against",
    #         "pyth_win_pct","luck_overperformance",
    #         "close_share_5","close_win_pct_5","close_games_5","close_wins_5","close_losses_5",
    #     ]
    #     return pd.DataFrame(columns=cols)

    rows: List[Dict] = []

    def work(team_id: str, team_name: str, conf: str | None) -> Dict:
        sched = fetch_team_schedule(team_id, season, cfg, force_refresh=force_refresh)

        qual = team_quality_from_schedule(sched, team_id)
        pyth = pythag_expectation(qual["ppg_for"], qual["ppg_against"])
        qual["pyth_win_pct"] = pyth
        qual["luck_overperformance"] = qual["win_pct"] - pyth

        return {
            "team_id": team_id,
            "team": team_name,
            "conference": conf,

            "games": qual["games"],
            "wins": qual["wins"],
            "losses": qual["losses"],

            "win_pct": qual["win_pct"],
            "avg_margin": qual["avg_margin"],
            "ppg_for": qual["ppg_for"],
            "ppg_against": qual["ppg_against"],

            "pyth_win_pct": qual["pyth_win_pct"],
            "luck_overperformance": qual["luck_overperformance"],

            "close_share_5": qual["close_share_5"],
            "close_win_pct_5": qual["close_win_pct_5"],
            "close_games_5": qual["close_games_5"],
            "close_wins_5": qual["close_wins_5"],
            "close_losses_5": qual["close_losses_5"],

            # MVP "efficiency margin" proxy: replace with true AdjEM later
            "adj_em": qual["avg_margin"],
        }

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(work, t.id, t.name, t.conference) for t in teams]
        for fut in as_completed(futs):
            rows.append(fut.result())

    df = pd.DataFrame(rows)

    # Coerce numerics
    num_cols = [
        "games", "wins", "losses", "win_pct", "avg_margin",
        "ppg_for", "ppg_against",
        "pyth_win_pct", "luck_overperformance",
        "close_share_5", "close_win_pct_5",
        "close_games_5", "close_wins_5", "close_losses_5",
        "adj_em",
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Filter out teams with no completed games / missing basics
    df = df.dropna(subset=["wins", "losses", "adj_em", "games"])
    df = df[df["games"] >= min_games].copy()

    # Sort for sanity
    df = df.sort_values(["wins", "adj_em"], ascending=[False, False]).reset_index(drop=True)

    # Helpful debug (leave on for now)
    print("Built rows:", len(df))
    print("Non-null wins:", df["wins"].notna().sum())
    print("Non-null losses:", df["losses"].notna().sum())
    print("Non-null adj_em:", df["adj_em"].notna().sum())
    print(df[["team", "wins", "losses", "games", "adj_em", "luck_overperformance"]].head(10))

    return df
