import pandas as pd

from .config import Config
from .cbbdata_client import fetch_parquet_endpoint, get_api_key_from_env


def fetch_trank_table(season: int, cfg: Config, *, force_refresh: bool = False) -> pd.DataFrame:
    """
    Uses CBBData API (NOT barttorvik.com directly) to avoid Cloudflare blocks.

    Endpoint is defined in the official cbbdata package source as:
      base_url <- 'https://www.cbbdata.com/api/torvik/ratings?' :contentReference[oaicite:4]{index=4}

    The API key is passed as query param `key`. :contentReference[oaicite:5]{index=5}
    """
    api_key = get_api_key_from_env()
    if not api_key:
        raise RuntimeError(
            "Missing CBBData API key. Set it like:\n"
            '  export CBD_API_KEY="YOUR_KEY_HERE"\n'
            "Then rerun."
        )

    base_url = "https://www.cbbdata.com/api/torvik/ratings?"
    params = {
        "year": season,
        "key": api_key,
        # If you want the full dataset sometimes, cbbdata uses return_all=TRUE when no args. :contentReference[oaicite:6]{index=6}
        # Here we filter by year, so this is optional; leaving it off is usually fine.
    }

    df = fetch_parquet_endpoint(
        base_url=base_url,
        params=params,
        cfg=cfg,
        cache_key=f"cbbdata_torvik_ratings_{season}",
        force_refresh=force_refresh,
    )
    return df


def standardize_trank_columns(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Map CBBData Torvik ratings columns to our normalized schema.

    CBBData typically uses:
      team, conf, wins, games, adj_o, adj_d, barthag, etc. (varies slightly)
    We'll derive losses where possible and define adj_em = adj_o - adj_d if needed.
    """
    df = raw.copy()

    def pick(*candidates: str):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    col_team = pick("team", "Team")
    col_wins = pick("wins", "W", "Wins")
    col_games = pick("games", "G", "Games")
    col_losses = pick("losses", "L", "Losses")

    col_adj_o = pick("adj_o", "AdjO", "adj_off", "off_adj")
    col_adj_d = pick("adj_d", "AdjD", "adj_def", "def_adj")
    col_adj_em = pick("adj_em", "AdjEM", "adj_margin")

    out = pd.DataFrame()
    out["team"] = df[col_team].astype(str).str.strip() if col_team else pd.NA

    if col_wins:
        out["wins"] = pd.to_numeric(df[col_wins], errors="coerce")
    else:
        out["wins"] = pd.NA

    if col_losses:
        out["losses"] = pd.to_numeric(df[col_losses], errors="coerce")
    elif col_games and col_wins:
        out["losses"] = pd.to_numeric(df[col_games], errors="coerce") - out["wins"]
    else:
        out["losses"] = pd.NA

    if col_adj_em:
        out["adj_em"] = pd.to_numeric(df[col_adj_em], errors="coerce")
    elif col_adj_o and col_adj_d:
        out["adj_em"] = pd.to_numeric(df[col_adj_o], errors="coerce") - pd.to_numeric(df[col_adj_d], errors="coerce")
    else:
        out["adj_em"] = pd.NA

    # Optional extras if present
    out["opp_3p_pct_allowed"] = pd.to_numeric(df.get("opp_3p"), errors="coerce") if "opp_3p" in df.columns else pd.NA
    out["ftr"] = pd.to_numeric(df.get("off_ftr"), errors="coerce") if "off_ftr" in df.columns else pd.NA
    out["efg"] = pd.to_numeric(df.get("off_efg"), errors="coerce") if "off_efg" in df.columns else pd.NA

    return out
