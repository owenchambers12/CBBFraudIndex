"""
Optional: later you can use NCAA game results for real close-game luck.

This file is a placeholder because different NCAA endpoints / wrappers vary.
When you're ready, you'll implement a function that returns a tidy games table:

columns:
  team, opp, team_score, opp_score, date

Then plug it into metrics.summarize_close_games(...)
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import requests

from .config import Config


@dataclass(frozen=True)
class GameRow:
    date: str
    team: str
    opp: str
    team_score: int
    opp_score: int


def fetch_json(url: str, cfg: Config) -> Any:
    headers = {"User-Agent": cfg.user_agent}
    r = requests.get(url, headers=headers, timeout=cfg.request_timeout_s)
    r.raise_for_status()
    return r.json()


def parse_scoreboard_payload(payload: Dict[str, Any]) -> List[GameRow]:
    """
    TODO: Implement based on whatever scoreboard JSON you choose.
    """
    raise NotImplementedError("Implement NCAA scoreboard parsing when you pick an endpoint.")
