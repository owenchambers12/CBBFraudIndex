from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd


def plot_fraud_index_x(
    ranked: pd.DataFrame,
    outpath: Path,
    *,
    title: str,
    week_label: str,
    metric_col: str = "fraud_index",
    label_col: str = "team",
    n: int = 10,
    subtitle: str = "Higher = more suspect",
    footer_left: str = "Source: ESPN schedules • NCAA D1 • Eligibility: ≤ 6 losses",
    footer_right: str = "@CBBFraudWatch",
) -> None:
    """
    X-optimized (4:5) dark-mode bar chart:
    - Big fonts, phone readable
    - Rank badges (1–10) in a dedicated left gutter (no collisions)
    - Value labels
    - Tier bands
    - Deterministic header layout (no overlapping titles)
    """
    df = ranked.copy().head(n)
    df[metric_col] = pd.to_numeric(df[metric_col], errors="coerce")
    df = df.dropna(subset=[metric_col, label_col])

    # Theme
    bg = "#0b0f14"
    fg = "#e8eef7"
    muted = "#9fb0c3"

    if df.empty:
        fig = plt.figure(figsize=(8.0, 10.0))
        fig.patch.set_facecolor(bg)
        plt.text(0.5, 0.5, "No eligible teams to plot", ha="center", va="center", fontsize=22, color=fg)
        plt.axis("off")
        fig.savefig(outpath, dpi=300, bbox_inches="tight", facecolor=bg)
        plt.close(fig)
        return

    # Put #1 at top
    df = df.reset_index(drop=True)
    df_plot = df.iloc[::-1].reset_index(drop=True)

    teams = df_plot[label_col].astype(str).tolist()
    vals = df_plot[metric_col].astype(float).tolist()

    # --- Figure setup (dark mode) ---
    fig, ax = plt.subplots(figsize=(8.0, 10.0))  # 4:5
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)

    # Grid
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, linestyle="-", linewidth=0.8, alpha=0.18, color=muted)
    ax.yaxis.grid(False)

    for s in ax.spines.values():
        s.set_visible(False)

    y = list(range(len(vals)))

    # Colors
    base_bar = "#2c6bed"
    highlight1 = "#ff4d6d"
    highlight2 = "#ff9f1c"
    highlight3 = "#ffd166"

    ranks = list(range(len(vals), 0, -1))  # y=0 => n ... y=max => 1

    colors = []
    for r in ranks:
        if r == 1:
            colors.append(highlight1)
        elif r == 2:
            colors.append(highlight2)
        elif r == 3:
            colors.append(highlight3)
        else:
            colors.append(base_bar)

    # X limits first (bands depend on it)
    vmax = max(vals)
    ax.set_xlim(0, vmax * 1.22)
    x0, x1 = ax.get_xlim()

    # --- Tier bands ---
    svals = pd.Series(vals)
    q66 = float(svals.quantile(0.66))
    q33 = float(svals.quantile(0.33))

    fraud_alert_rows = [i for i, v in enumerate(vals) if v >= q66]
    suspect_rows = [i for i, v in enumerate(vals) if q33 <= v < q66]
    monitor_rows = [i for i, v in enumerate(vals) if v < q33]

    def band(rows, label, color_hex):
        if not rows:
            return
        y_min = min(rows) - 0.5
        y_max = max(rows) + 0.5
        rect = patches.Rectangle(
            (x0, y_min),
            x1 - x0,
            y_max - y_min,
            facecolor=color_hex,
            alpha=0.10,
            edgecolor="none",
            zorder=1,
        )
        ax.add_patch(rect)
        ax.text(
            x0 + (x1 - x0) * 0.005,
            y_max - 0.35,
            label,
            color=muted,
            fontsize=11,
            fontweight="bold",
            va="top",
            ha="left",
            zorder=2,
        )


    # Bars
    bars = ax.barh(y, vals, height=0.72, color=colors, alpha=0.95, zorder=3)

    # Y labels (shrink font so nothing clips)
    ax.set_yticks(y)
    ax.set_yticklabels(teams, fontsize=12, color=fg)  # <-- was 13
    ax.tick_params(axis="x", colors=muted, labelsize=12)
    ax.tick_params(axis="y", length=0, pad=18)
    for lab in ax.get_yticklabels():
        lab.set_horizontalalignment("right")

    # --- Rank badges + value labels ---
    ytrans = ax.get_yaxis_transform()  # x in axes fraction, y in data coords

    for yi, (v, r) in enumerate(zip(vals, ranks)):
        ax.text(
            -0.05,
            yi,
            f"{r}",
            transform=ytrans,
            va="center",
            ha="center",
            fontsize=12,
            color=fg,
            fontweight="bold",
            clip_on=False,
            bbox=dict(boxstyle="round,pad=0.30", facecolor="#141c26", edgecolor="none", alpha=1.0),
            zorder=5,
        )

        ax.text(
            v + vmax * 0.02,
            yi,
            f"{v:.1f}",
            va="center",
            ha="left",
            fontsize=13,
            color=fg,
            fontweight="bold",
            zorder=5,
        )

    # --- Header text fixes ---
    # 1) Remove the “weird rectangle”: strip emoji that may not exist in matplotlib fonts.
    safe_title = title.replace("🚨", "").replace("🧾", "").strip()

    # 2) Split subtitle so "Record vs ..." is on the next line
    #    (uses your "•" separator; falls back gracefully)
    parts = [p.strip() for p in subtitle.split("•", 1)]
    sub1 = parts[0] if parts else subtitle
    sub2 = parts[1] if len(parts) > 1 else ""

    fig.suptitle(safe_title, fontsize=32, fontweight="bold", color=fg, y=0.975)
    fig.text(0.12, 0.905, f"{week_label} • Top {len(vals)}", fontsize=14, color=muted, ha="left")
    fig.text(0.12, 0.875, sub1, fontsize=12, color=muted, ha="left")
    if sub2:
        fig.text(0.12, 0.848, sub2, fontsize=12, color=muted, ha="left")

    # Axis label
    ax.set_xlabel("Fraud Index score", fontsize=12, color=muted, labelpad=14)

    # Footer
    fig.text(0.01, 0.02, footer_left, fontsize=10.5, color=muted, ha="left")
    fig.text(0.99, 0.02, footer_right, fontsize=10.5, color=muted, ha="right")

    # Layout (slightly more left room for long team names)
    fig.subplots_adjust(left=0.32, right=0.96, top=0.82, bottom=0.10)

    fig.savefig(outpath, dpi=300, facecolor=fig.get_facecolor())
    plt.close(fig)



def plot_fraud_receipts_x(
    ranked: pd.DataFrame,
    outpath: Path,
    *,
    week_label: str,
    n: int = 5,
    footer_left: str = "Receipts • Source: ESPN schedules",
    footer_right: str = "@CBBFraudWatch",
) -> None:
    """
    X-optimized 'receipts' card:
    A clean dark-mode table image for the top N fraud teams with key columns.
    """
    bg = "#0b0f14"
    fg = "#e8eef7"
    muted = "#9fb0c3"
    line = "#1d2a3a"

    df = ranked.copy().head(n).copy()
    if df.empty:
        fig = plt.figure(figsize=(8.0, 6.0))
        fig.patch.set_facecolor(bg)
        plt.text(0.5, 0.5, "No eligible teams for receipts", ha="center", va="center", fontsize=20, color=fg)
        plt.axis("off")
        fig.savefig(outpath, dpi=300, bbox_inches="tight", facecolor=bg)
        plt.close(fig)
        return

    # Ensure columns exist; fill if missing
    def col(name, default=None):
        return df[name] if name in df.columns else pd.Series([default] * len(df))

    # Build display columns
    teams = col("team", "").astype(str).tolist()
    wins = pd.to_numeric(col("wins", None), errors="coerce")
    losses = pd.to_numeric(col("losses", None), errors="coerce")
    record = [f"{int(w)}-{int(l)}" if pd.notna(w) and pd.notna(l) else "—" for w, l in zip(wins, losses)]

    avg_margin = pd.to_numeric(col("avg_margin", None), errors="coerce")
    luck = pd.to_numeric(col("luck_overperformance", None), errors="coerce")
    close_win = pd.to_numeric(col("close_win_pct_5", None), errors="coerce")
    close_share = pd.to_numeric(col("close_share_5", None), errors="coerce")
    fraud = pd.to_numeric(col("fraud_index", None), errors="coerce")

    # Pretty formatting
    def fnum(x, digits=1, signed=False):
        if pd.isna(x):
            return "—"
        return f"{x:+.{digits}f}" if signed else f"{x:.{digits}f}"

    def fpct(x):
        if pd.isna(x):
            return "—"
        return f"{100.0 * float(x):.0f}%"

    rows = []
    for i in range(len(df)):
        rows.append(
            [
                str(i + 1),
                teams[i],
                record[i],
                fnum(avg_margin.iloc[i], 1, signed=True),
                fnum(luck.iloc[i], 3, signed=True),
                fpct(close_win.iloc[i]),
                fpct(close_share.iloc[i]),
                fnum(fraud.iloc[i], 1, signed=False),
            ]
        )

    headers = ["Rk", "Team", "Rec", "Avg MoV", "Luck", "Close W%", "Close Share", "Fraud"]

    # Figure (slightly shorter than main chart)
    fig, ax = plt.subplots(figsize=(8.0, 6.0))
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    ax.axis("off")

    # Title
    fig.text(0.02, 0.94, "FRAUD RECEIPTS 🧾", fontsize=20, fontweight="bold", color=fg, ha="left")
    fig.text(0.02, 0.90, f"{week_label} • Top {len(rows)}", fontsize=12.5, color=muted, ha="left")

    # Table
    table = ax.table(
        cellText=rows,
        colLabels=headers,
        loc="center",
        cellLoc="left",
        colLoc="left",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(11)

    # Column widths (tuned for 8x6)
    col_widths = {
        0: 0.06,  # Rk
        1: 0.34,  # Team
        2: 0.10,  # Rec
        3: 0.11,  # Avg MoV
        4: 0.11,  # Luck
        5: 0.11,  # Close W%
        6: 0.13,  # Close Share
        7: 0.09,  # Fraud
    }

    # Style cells
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor(line)
        cell.set_linewidth(0.8)
        cell.set_facecolor(bg)
        cell.get_text().set_color(fg)

        # Header row
        if r == 0:
            cell.set_facecolor("#141c26")
            cell.get_text().set_color(fg)
            cell.get_text().set_fontweight("bold")

        # Set column widths
        if c in col_widths:
            cell.set_width(col_widths[c])

        # Right-align numeric-ish columns
        if c in (0, 2, 3, 4, 5, 6, 7):
            cell._loc = "right"

        # Slightly taller rows
        cell.set_height(0.10)

    # Footer
    fig.text(0.01, 0.03, footer_left, fontsize=10.5, color=muted, ha="left")
    fig.text(0.99, 0.03, footer_right, fontsize=10.5, color=muted, ha="right")

    fig.tight_layout(rect=[0, 0.06, 1, 0.88])
    fig.savefig(outpath, dpi=300, bbox_inches="tight", facecolor=bg)
    plt.close(fig)
