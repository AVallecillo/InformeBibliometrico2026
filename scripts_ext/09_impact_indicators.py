"""
09_impact_indicators.py

Impact indicators based on outputs/openalex_work_metrics.csv.
This script is optional. If the metrics file is absent, it writes a SKIPPED report
and exits cleanly. Use 18_fetch_openalex_metrics.py first if you want citations.
"""

from pathlib import Path
import numpy as np
import pandas as pd

from common import load_inputs

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

metrics_path = Path("outputs/openalex_work_metrics.csv")
if not metrics_path.exists():
    msg = (
        "SKIPPED: Missing outputs/openalex_work_metrics.csv.\n"
        "Run: python scripts_ext/18_fetch_openalex_metrics.py --mailto your_email@example.org\n"
        "Then rerun this script.\n"
    )
    (OUT / "impact_indicators_SKIPPED.txt").write_text(msg, encoding="utf-8")
    print(msg.strip())
    raise SystemExit(0)

pm, pc = load_inputs("outputs")
metrics = pd.read_csv(metrics_path)

required = {"paper_id", "cited_by_count"}
if not required.issubset(metrics.columns):
    msg = f"SKIPPED: {metrics_path} must contain columns {sorted(required)}"
    (OUT / "impact_indicators_SKIPPED.txt").write_text(msg + "\n", encoding="utf-8")
    print(msg)
    raise SystemExit(0)

df = pm.merge(metrics[["paper_id", "cited_by_count"]], on="paper_id", how="left")
df["cited_by_count"] = df["cited_by_count"].fillna(0)
df["log_cites"] = np.log1p(df["cited_by_count"])

df["venue_year_mean"] = df.groupby(["venue", "year"])["log_cites"].transform("mean")
df["venue_year_std"] = df.groupby(["venue", "year"])["log_cites"].transform("std").replace(0, np.nan)
df["norm_cite_z"] = (df["log_cites"] - df["venue_year_mean"]) / df["venue_year_std"]
df["cite_percentile_venue_year"] = df.groupby(["venue", "year"])["cited_by_count"].rank(pct=True)

country_df = pc[["paper_id", "country_code"]].drop_duplicates().merge(
    df[["paper_id", "window", "area", "level", "venue", "year", "cited_by_count", "norm_cite_z", "cite_percentile_venue_year"]],
    on="paper_id",
    how="left",
)

summary = (
    country_df.groupby(["window", "country_code"])
    .agg(
        papers=("paper_id", "nunique"),
        mean_cites=("cited_by_count", "mean"),
        median_cites=("cited_by_count", "median"),
        mean_norm_z=("norm_cite_z", "mean"),
        top10_share=("cite_percentile_venue_year", lambda s: (s >= 0.90).mean()),
        top1_share=("cite_percentile_venue_year", lambda s: (s >= 0.99).mean()),
    )
    .reset_index()
)
summary.to_csv(OUT / "impact_by_country_window.csv", index=False)

spain_area = (
    country_df[country_df["country_code"].eq("ES")]
    .groupby(["window", "area"])
    .agg(
        papers=("paper_id", "nunique"),
        mean_cites=("cited_by_count", "mean"),
        mean_norm_z=("norm_cite_z", "mean"),
        top10_share=("cite_percentile_venue_year", lambda s: (s >= 0.90).mean()),
    )
    .reset_index()
)
spain_area.to_csv(OUT / "spain_impact_by_area_window.csv", index=False)

print("OK: impact indicators generated.")
