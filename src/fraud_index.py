import pandas as pd


def zscore(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    mu = s.mean(skipna=True)
    sd = s.std(skipna=True, ddof=0)
    if sd == 0 or pd.isna(sd):
        return s * 0.0
    return (s - mu) / (sd + 1e-9)


def minmax_0_100(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    mn = s.min(skipna=True)
    mx = s.max(skipna=True)
    if pd.isna(mn) or pd.isna(mx) or mx == mn:
        return s * 0.0
    return 100.0 * (s - mn) / (mx - mn + 1e-9)


def compute_fraud_index(team_df: pd.DataFrame) -> pd.DataFrame:
    """
    Input schema (minimum):
      team, wins, losses, adj_em

    Optional (improves fraud signal):
      close_share_5, close_win_pct_5, opp_3p_pct_allowed, ftr, efg

    Output adds:
      win_pct, fraud_score_raw, fraud_index
    """
    df = team_df.copy()

    if "luck_overperformance" in df.columns:
    # This is already "winning too much" per Pythag expectation
        signal_mismatch = zscore(df["luck_overperformance"])
    else:
        signal_mismatch = zscore(df["win_pct"]) - zscore(df["adj_em"])

    df["wins"] = pd.to_numeric(df.get("wins"), errors="coerce")
    df["losses"] = pd.to_numeric(df.get("losses"), errors="coerce")
    df["adj_em"] = pd.to_numeric(df.get("adj_em"), errors="coerce")

    df["games"] = (df["wins"] + df["losses"]).clip(lower=1)
    df["win_pct"] = df["wins"] / df["games"]

    # Optional fields (may be NaN)
    df["close_share_5"] = pd.to_numeric(df.get("close_share_5"), errors="coerce")
    df["close_win_pct_5"] = pd.to_numeric(df.get("close_win_pct_5"), errors="coerce")
    df["opp_3p_pct_allowed"] = pd.to_numeric(df.get("opp_3p_pct_allowed"), errors="coerce")
    df["ftr"] = pd.to_numeric(df.get("ftr"), errors="coerce")
    df["efg"] = pd.to_numeric(df.get("efg"), errors="coerce")

    # Signals (higher => more fraudulent)
    # A) mismatch: winning a lot despite mediocre efficiency
    signal_mismatch = zscore(df["win_pct"]) - zscore(df["adj_em"])

    # B) close-game luck: lots of close games + high close win%
    signal_close_luck = zscore(df["close_share_5"]) + zscore(df["close_win_pct_5"])

    # C) shooting luck proxy: unusually low opponent 3P% allowed
    # (careful framing later: "regression risk" not "fake defense")
    signal_shoot_luck = -zscore(df["opp_3p_pct_allowed"])

    # D) FT reliance proxy: high FTr but mediocre eFG
    signal_ft_reliance = zscore(df["ftr"]) - zscore(df["efg"])

    # If optional columns are missing, those signals will be ~0 due to NaNs;
    # weights still work, but index becomes mostly mismatch-based.
    df["fraud_score_raw"] = (
        0.30 * signal_mismatch +
        0.25 * signal_close_luck.fillna(0.0) +
        0.20 * signal_shoot_luck.fillna(0.0) +
        0.10 * signal_ft_reliance.fillna(0.0)
    )

    df["fraud_index"] = minmax_0_100(df["fraud_score_raw"])
    df = df.sort_values("fraud_index", ascending=False).reset_index(drop=True)

    return df
