import argparse
from pathlib import Path
import pandas as pd

from .config import Config
from .build_dataset_espn import build_team_dataset
from .fraud_index import compute_fraud_index
from .viz import plot_fraud_index_x, plot_fraud_receipts_x
from .build_dataset_espn import is_power_conf


def build_post_text(df_ranked, week_label: str) -> str:
    top = df_ranked.head(10)

    lines = []
    lines.append(f"🚨 FRAUD INDEX — {week_label} 🚨")
    lines.append("")
    lines.append("Top 10 most suspect teams (data-driven):")
    for i, r in enumerate(top.itertuples(index=False), start=1):
        lines.append(f"{i:>2}) {r.team} — {r.fraud_index:.1f}")

    # Add a tiny methodology footer for credibility
    lines.append("")
    lines.append("Method (high-level): efficiency proxy + close-game luck + FT reliance signals.")
    lines.append("If your team is here: I regret nothing. Drop a team for receipts 👇")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True, help="e.g., 2026")
    ap.add_argument("--week_label", type=str, required=True, help='e.g., "Feb 16 2026"')
    ap.add_argument("--force_refresh", action="store_true", help="Ignore cache and refetch")
    ap.add_argument("--max_workers", type=int, default=10, help="API concurrency")
    ap.add_argument(
        "--power_only",
        action="store_true",
        help="Only include power-conference teams in Fraud Index universe"
    )
    args = ap.parse_args()

    cfg = Config()
    outdir = cfg.outputs_dir / f"week_{args.week_label.replace(' ', '_')}"
    outdir.mkdir(parents=True, exist_ok=True)

    # 1) Build dataset from ESPN
    teams = build_team_dataset(
        season=args.season,
        cfg=cfg,
        force_refresh=args.force_refresh,
        max_workers=args.max_workers,
    )

    teams.to_csv(outdir / "all_d1_teams_dataset.csv", index=False)

    # Only rank "relevant" teams (your definition)
    teams_rank = teams.copy()

    # Optional power-conference filter
    if args.power_only:
        teams_rank = teams_rank[teams_rank["conference"].apply(is_power_conf)]
        print(f"Power-conference filter applied: {len(teams_rank)} teams remain")

    # Loss threshold filter
    teams_rank["losses"] = pd.to_numeric(teams_rank["losses"], errors="coerce")
    teams_rank = teams_rank.dropna(subset=["losses"])
    teams_rank = teams_rank[teams_rank["losses"] <= 6].copy()

    print(f"Teams eligible for Fraud Index (losses <= 6): {len(teams_rank)}")


    print(f"Teams eligible for Fraud Index (losses <= 6): {len(teams_rank)}")

    # 2) Fraud Index
    ranked = compute_fraud_index(teams_rank)

    # 3) Outputs
    ranked.to_csv(outdir / "fraud_table.csv", index=False)

    plot_fraud_index_x(
        ranked,
        outdir / "fraud_top10.png",
        title="CBB FRAUD WATCH 🚨",
        week_label=args.week_label,
        n=10,
        footer_left="Source: ESPN schedules • NCAA D1 • Eligibility: ≤ 6 losses",
        footer_right="@CBBFraudWatch",
    )

    plot_fraud_receipts_x(
        ranked,
        outdir / "fraud_receipts.png",
        week_label=args.week_label,
        n=5,
        footer_left="Receipts • Luck = Win% − PythagExp% • Close = games decided by ≤5",
        footer_right="@CBBFraudWatch",
    )



    (outdir / "post.txt").write_text(build_post_text(ranked, args.week_label), encoding="utf-8")

    print(f"Saved:\n- {outdir / 'fraud_table.csv'}\n- {outdir / 'fraud_top10.png'}\n- {outdir / 'post.txt'}\n- {outdir / 'fraud_receipts.png'}")


if __name__ == "__main__":
    main()
