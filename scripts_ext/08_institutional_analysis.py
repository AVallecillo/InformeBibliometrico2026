"""
08_institutional_analysis.py

Institutional analysis of Spanish papers. This script is optional.
If institution-level affiliation columns are not available, it writes a SKIPPED
report and exits cleanly.
"""

from pathlib import Path
import glob
import pandas as pd

from common import load_inputs

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")

files = glob.glob("outputs/affiliation_evidence_*.csv")
if not files:
    msg = "SKIPPED: no outputs/affiliation_evidence_*.csv files found."
    (OUT / "institutional_analysis_SKIPPED.txt").write_text(msg + "\n", encoding="utf-8")
    print(msg)
    raise SystemExit(0)

frames = []
for f in files:
    try:
        df = pd.read_csv(f)
    except Exception:
        continue
    keep = [c for c in ["paper_id", "country_code", "institution_name", "institution_id", "ror_id"] if c in df.columns]
    if {"paper_id", "country_code", "institution_name"}.issubset(set(keep)):
        frames.append(df[keep].copy())

if not frames:
    msg = (
        "SKIPPED: institution_name column not found in affiliation evidence files.\n"
        "To enable this analysis, preserve OpenAlex authorships[].institutions[].display_name "
        "and optionally ROR/institution_id in the affiliation evidence files.\n"
    )
    (OUT / "institutional_analysis_SKIPPED.txt").write_text(msg, encoding="utf-8")
    print(msg.strip())
    raise SystemExit(0)

aff = pd.concat(frames, ignore_index=True).drop_duplicates()
aff = aff[aff["country_code"].eq("ES")].copy()
if aff.empty:
    msg = "SKIPPED: no Spanish institutional affiliation rows found."
    (OUT / "institutional_analysis_SKIPPED.txt").write_text(msg + "\n", encoding="utf-8")
    print(msg)
    raise SystemExit(0)

aff["institution_name"] = aff["institution_name"].astype(str).str.strip()
aff = aff.merge(pm[["paper_id", "year", "window", "venue", "level", "area"]], on="paper_id", how="left")

global_inst = (
    aff.groupby("institution_name")["paper_id"].nunique()
    .reset_index(name="papers")
    .sort_values("papers", ascending=False)
)
global_inst["rank"] = range(1, len(global_inst) + 1)
global_inst.to_csv(OUT / "spanish_institutions_global.csv", index=False)

by_area = (
    aff.groupby(["window", "area", "institution_name"])["paper_id"].nunique()
    .reset_index(name="papers")
    .sort_values(["window", "area", "papers"], ascending=[True, True, False])
)
by_area.to_csv(OUT / "spanish_institutions_by_window_area.csv", index=False)

rows = []
for (w, area), g in by_area.groupby(["window", "area"]):
    total = g["papers"].sum()
    shares = g["papers"] / total if total else g["papers"]
    rows.append({
        "window": w,
        "area": area,
        "n_institutions": g["institution_name"].nunique(),
        "total_institution_paper_links": total,
        "top5_share": g["papers"].head(5).sum() / total if total else None,
        "top10_share": g["papers"].head(10).sum() / total if total else None,
        "hhi": (shares ** 2).sum() if total else None,
    })
pd.DataFrame(rows).to_csv(OUT / "spanish_institution_concentration.csv", index=False)

print("OK: institutional analysis generated.")
