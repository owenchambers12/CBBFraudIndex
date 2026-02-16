from __future__ import annotations

from typing import Any, Dict, List


def _score_to_float(score_field: Any) -> float:
    """
    ESPN competitor['score'] can be:
      - dict: {'value': 106.0, 'displayValue': '106'}
      - str: '106'
      - number
    """
    if score_field is None:
        raise ValueError("Missing score")

    if isinstance(score_field, dict):
        # Prefer numeric value
        if "value" in score_field and score_field["value"] is not None:
            return float(score_field["value"])
        if "displayValue" in score_field and score_field["displayValue"] is not None:
            return float(score_field["displayValue"])

        raise ValueError(f"Unusable score dict: {score_field}")

    # string or numeric
    return float(score_field)


def team_quality_from_schedule(schedule_json: Dict[str, Any], team_id: str) -> Dict[str, float]:
    events = schedule_json.get("events") or []

    margins: List[float] = []
    pf = 0.0
    pa = 0.0

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
        status_type = (comp.get("status") or {}).get("type") or {}
        if not bool(status_type.get("completed")):
            continue

        competitors = comp.get("competitors") or []
        if len(competitors) != 2:
            continue

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
            us_score = _score_to_float(us.get("score"))
            them_score = _score_to_float(them.get("score"))
        except Exception:
            # If ESPN marks completed but score is missing/odd, skip
            continue

        games += 1
        pf += us_score
        pa += them_score

        margin = us_score - them_score
        margins.append(margin)

        us_winner = bool(us.get("winner"))
        if us_winner:
            wins += 1
        else:
            losses += 1

        if abs(margin) <= 5:
            close_games += 1
            if us_winner:
                close_wins += 1
            else:
                close_losses += 1

    win_pct = wins / games if games else 0.0
    avg_margin = sum(margins) / games if games else 0.0
    ppg_for = pf / games if games else 0.0
    ppg_against = pa / games if games else 0.0

    return {
        "games": float(games),
        "wins": float(wins),
        "losses": float(losses),
        "win_pct": float(win_pct),
        "avg_margin": float(avg_margin),
        "ppg_for": float(ppg_for),
        "ppg_against": float(ppg_against),
        "close_games_5": float(close_games),
        "close_wins_5": float(close_wins),
        "close_losses_5": float(close_losses),
        "close_share_5": float(close_games / games) if games else 0.0,
        "close_win_pct_5": float(close_wins / close_games) if close_games else 0.0,
    }


def pythag_expectation(ppg_for: float, ppg_against: float, exponent: float = 11.5) -> float:
    if ppg_for <= 0 or ppg_against <= 0:
        return 0.0
    a = ppg_for ** exponent
    b = ppg_against ** exponent
    return a / (a + b)
