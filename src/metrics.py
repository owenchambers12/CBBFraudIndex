import pandas as pd


def summarize_close_games(games_df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a tidy games dataframe with:
      team, team_score, opp_score

    Returns per-team:
      games, close_games_5, close_wins_5, close_losses_5, close_share_5, close_win_pct_5
    """
    df = games_df.copy()
    df["team_score"] = pd.to_numeric(df["team_score"], errors="coerce")
    df["opp_score"] = pd.to_numeric(df["opp_score"], errors="coerce")

    df = df.dropna(subset=["team", "team_score", "opp_score"])

    df["margin_abs"] = (df["team_score"] - df["opp_score"]).abs()
    df["is_close_5"] = df["margin_abs"] <= 5
    df["win"] = df["team_score"] > df["opp_score"]

    # Aggregate
    agg = df.groupby("team").agg(
        games=("team", "size"),
        close_games_5=("is_close_5", "sum"),
        close_wins_5=("win", lambda s: int(((df.loc[s.index, "is_close_5"]) & (s)).sum())),
        close_losses_5=("win", lambda s: int(((df.loc[s.index, "is_close_5"]) & (~s)).sum())),
    ).reset_index()

    agg["close_share_5"] = agg["close_games_5"] / agg["games"].clip(lower=1)
    agg["close_win_pct_5"] = agg["close_wins_5"] / agg["close_games_5"].clip(lower=1)

    return agg
