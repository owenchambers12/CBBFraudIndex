<!-- .github/copilot-instructions.md: Project-specific instructions for AI coding agents -->

# CBBFraudIndex — Copilot Instructions

Purpose: give an AI coding agent the exact, actionable context it needs to be productive in this repo.

- **Primary script / pipeline**: `src/render_post.py` — orchestrates data fetch (ESPN), feature derivation, fraud-index calculation, plotting, and writing outputs.
- **Data flow**: `src/espn_api.py` -> `src/build_dataset_espn.py` -> `src/quality_from_schedule.py` -> `src/fraud_index.py` -> `src/viz.py` -> outputs in `outputs/week_<WEEK_LABEL>/`.

Key files to read before editing:
- `src/config.py`: central `Config` dataclass. Holds `cache_dir`, `outputs_dir`, HTTP timeouts and retries.
- `src/build_dataset_espn.py`: builds the tidy team DataFrame. This is where `adj_em` is set (currently `avg_margin`) — change here to swap the efficiency proxy.
- `src/espn_api.py`: external API fetch logic (caching, rate limits). Respect `Config` and `--force_refresh` semantics.
- `src/quality_from_schedule.py`: computes per-team features (ppg, margins, close games, pythag expectation).
- `src/fraud_index.py`: computes z-scores, min-max scaling and the `fraud_index` logic and weights — modify only after understanding downstream plotting/outputs.
- `src/render_post.py`: the CLI entrypoint for weekly runs and the best example for end-to-end behavior.
- `src/viz.py`: plotting helpers used by `render_post.py` to create `fraud_top10.png` and `fraud_receipts.png`.

Run / developer workflows
- Install deps and run the pipeline locally (macOS / zsh):
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt

  # example run (creates outputs/week_Feb_16_2026/...)
  python -m src.render_post --season 2026 --week_label "Feb 16 2026"
  ```
- To re-fetch API data ignoring the cache add `--force_refresh` to the `render_post` command.
- Concurrency for API calls is controlled with `--max_workers` (default 10) in `render_post.py` -> `build_team_dataset()`.
- Outputs are written to `outputs/week_<week_label>/` and include `all_d1_teams_dataset.csv`, `fraud_table.csv`, `fraud_top10.png`, `fraud_receipts.png`, and `post.txt`.

Project conventions & patterns
- Use the `Config` dataclass for paths/timeouts. New code should accept a `cfg: Config` when interacting with HTTP or file locations.
- Dataframes: functions return pandas DataFrames (see `build_team_dataset` and `compute_fraud_index`). Prefer non-destructive copies when mutating (the code already uses `df = df.copy()` patterns).
- Numeric coercion: this repo consistently uses `pd.to_numeric(..., errors='coerce')` and `dropna` for robust numeric processing. Follow the same pattern when adding new derived columns.
- Small, surgical edits: keep changes localized — e.g., to adjust how `adj_em` is computed, edit only `build_dataset_espn.py` where the `adj_em` field is set.

Integration / external points to respect
- ESPN API: `src/espn_api.py` (network reliability, caching). The code uses a local file cache under `data/raw/http_cache` (see `Config.cache_dir`). Don't bypass this cache unless `--force_refresh` is explicitly requested.
- Threading: `build_team_dataset` uses `ThreadPoolExecutor` for parallel fetches. Avoid heavy CPU work in those worker functions; keep them I/O-bound or increase `max_workers` explicitly.

What to watch for when changing scoring/weights
- `fraud_score_raw` weights and the handling of missing optional signals (they are filled with `0.0` before aggregation). If you change signals or weights, update tests or downstream text that references the methodology (see `render_post.build_post_text`).

Style & testing notes
- Code is annotated with type hints and small helper functions. Follow existing typing patterns.
- There are no test files in the repo root — when adding tests, mirror the code style and ensure they can run without network calls (mock `espn_api` or add a `--offline` mode).

Example quick edits
- Change efficiency proxy:
  - Edit `src/build_dataset_espn.py` near the end of `work()` where the dictionary contains `"adj_em": qual["avg_margin"]`.
- Add a new plot:
  - Implement a helper in `src/viz.py` and call it from `render_post.py` right after the existing `plot_fraud_index_x` call; use the same `outdir` and `week_label` patterns.

If uncertain, follow this checklist before submitting a patch:
1. Read `src/render_post.py` to confirm end-to-end behavior.
2. Run locally and confirm outputs appear in `outputs/week_<label>/`.
3. Preserve `Config` usage and `--force_refresh` semantics.
4. Keep changes minimal and document rationale in the PR description.

If anything in this file is unclear or you want it expanded (examples, more file pointers, or sample PR templates), tell me which areas to elaborate.
