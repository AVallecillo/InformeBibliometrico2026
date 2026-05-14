"""
Audit whether a mobile historical CORE A*/A corpus requires extra DBLP venues.
This script does not download DBLP; it produces the missing venue/year extraction plan.
"""
from pathlib import Path
import pandas as pd
from common import standardise_master_columns

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)
pm_path = Path("outputs/paper_master.csv")
hist_path = Path("data/core_historical/core_historical.csv")
if not pm_path.exists():
    raise FileNotFoundError("Missing outputs/paper_master.csv")
if not hist_path.exists():
    (OUT / "historical_mobile_corpus_gap_SKIPPED.txt").write_text(
        "SKIPPED: data/core_historical/core_historical.csv missing. Run scripts_ext/build_core_historical.py first.\n",
        encoding="utf-8"
    )
    print("SKIPPED: data/core_historical/core_historical.csv missing.")
    raise SystemExit(0)

pm = standardise_master_columns(pd.read_csv(pm_path))
hist = pd.read_csv(hist_path)
hist["venue"] = hist["venue"].astype(str).str.strip()
current_venues = set(pm["venue"].dropna().astype(str).str.strip())
venue_years = pm.groupby("venue")["year"].agg(min_year="min", max_year="max", n_papers="count").reset_index()
hist_venue = hist.groupby("venue").agg(
    first_core_year=("core_year", "min"),
    last_core_year=("core_year", "max"),
    years_list=("core_year", lambda s: "|".join(map(str, sorted(set(s))))),
    levels_list=("level", lambda s: "|".join(sorted(set(s))))
).reset_index()
hist_venue["in_current_2026_corpus"] = hist_venue["venue"].isin(current_venues)
present = hist_venue[hist_venue["in_current_2026_corpus"]].merge(venue_years, on="venue", how="left")
missing = hist_venue[~hist_venue["in_current_2026_corpus"]].copy()
present.to_csv(OUT / "historical_core_present_venues.csv", index=False)
missing.to_csv(OUT / "historical_core_missing_venues.csv", index=False)

hist_years = sorted(hist["core_year"].unique())
boundaries = {}
for i, y in enumerate(hist_years):
    start = max(2001, int(y))
    end = min(2025, int(hist_years[i+1]) - 1 if i + 1 < len(hist_years) else 2025)
    if start <= end:
        boundaries[int(y)] = (start, end)
rows = []
for _, r in hist.iterrows():
    y = int(r["core_year"])
    if y not in boundaries:
        continue
    start, end = boundaries[y]
    in_current = str(r["venue"]) in current_venues
    rows.append({
        "venue": r["venue"], "core_year": y, "level": r["level"],
        "article_year_start": start, "article_year_end": end,
        "in_current_2026_corpus": in_current,
        "needs_dblp_extraction": not in_current,
    })
req = pd.DataFrame(rows).drop_duplicates()
req.to_csv(OUT / "historical_mobile_corpus_requirements.csv", index=False)
with open(OUT / "historical_mobile_corpus_requirements.txt", "w", encoding="utf-8") as f:
    f.write("Historical mobile CORE corpus gap analysis\n")
    f.write("="*70 + "\n\n")
    f.write(f"Current fixed-corpus venues: {len(current_venues)}\n")
    f.write(f"Historical CORE A*/A venues: {hist_venue['venue'].nunique()}\n")
    f.write(f"Historical venues present in current corpus: {present['venue'].nunique()}\n")
    f.write(f"Historical venues missing from current corpus: {missing['venue'].nunique()}\n\n")
    f.write("Missing historical venues by first CORE year:\n")
    if not missing.empty:
        f.write(missing.groupby("first_core_year")["venue"].nunique().to_string())
        f.write("\n\nTop missing venues (first 100):\n")
        f.write("\n".join(sorted(missing["venue"].astype(str).unique())[:100]))
    else:
        f.write("None.\n")
    f.write("\n\nIf this list is large, 04_core_historical_sensitivity.py is a fixed-corpus historical-classification sensitivity, not a full mobile historical CORE corpus.\n")
print("OK: historical mobile corpus gap analysis written to outputs_ext/")
