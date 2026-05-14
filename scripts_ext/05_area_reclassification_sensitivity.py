"""
05_area_reclassification_sensitivity.py

Sensitivity analysis for alternative thematic classifications of boundary venues.
If data/external/venue_area_scenarios.csv is missing, a default conservative
scenario file is created automatically and the analysis continues.
"""

from pathlib import Path
import pandas as pd

from common import load_inputs, EU27_UK

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

sc_path = Path("data/external/venue_area_scenarios.csv")
if not sc_path.exists():
    sc_path.parent.mkdir(parents=True, exist_ok=True)
    default = pd.DataFrame([
        {"scenario": "baseline", "venue": "WWW", "area_alt": "Bases de datos"},
        {"scenario": "baseline", "venue": "SIGIR", "area_alt": "Bases de datos"},
        {"scenario": "baseline", "venue": "CIKM", "area_alt": "Bases de datos"},
        {"scenario": "baseline", "venue": "KDD", "area_alt": "IA/ML"},
        {"scenario": "WWW_as_IAML", "venue": "WWW", "area_alt": "IA/ML"},
        {"scenario": "SIGIR_CIKM_as_IAML", "venue": "SIGIR", "area_alt": "IA/ML"},
        {"scenario": "SIGIR_CIKM_as_IAML", "venue": "CIKM", "area_alt": "IA/ML"},
        {"scenario": "KDD_as_DB", "venue": "KDD", "area_alt": "Bases de datos"},
        {"scenario": "WWW_SIGIR_CIKM_as_IAML_KDD_as_DB", "venue": "WWW", "area_alt": "IA/ML"},
        {"scenario": "WWW_SIGIR_CIKM_as_IAML_KDD_as_DB", "venue": "SIGIR", "area_alt": "IA/ML"},
        {"scenario": "WWW_SIGIR_CIKM_as_IAML_KDD_as_DB", "venue": "CIKM", "area_alt": "IA/ML"},
        {"scenario": "WWW_SIGIR_CIKM_as_IAML_KDD_as_DB", "venue": "KDD", "area_alt": "Bases de datos"},
    ])
    default.to_csv(sc_path, index=False)
    print(f"Created default scenario file: {sc_path}")

pm, pc = load_inputs("outputs")
pc = pc.drop_duplicates(["paper_id", "country_code"])
sc = pd.read_csv(sc_path)

required = {"scenario", "venue", "area_alt"}
if not required.issubset(sc.columns):
    msg = f"SKIPPED: {sc_path} must contain columns {sorted(required)}"
    (OUT / "area_reclassification_sensitivity_SKIPPED.txt").write_text(msg + "\n", encoding="utf-8")
    print(msg)
    raise SystemExit(0)

rows = []
for scenario, sdf in sc.groupby("scenario"):
    x = pc.copy()
    mapping = dict(zip(sdf["venue"].astype(str), sdf["area_alt"].astype(str)))
    x["area_scenario"] = x["venue"].astype(str).map(mapping).fillna(x["area"])

    for (w, area), g in x.groupby(["window", "area_scenario"], dropna=False):
        den = g.loc[g["country_code"].isin(EU27_UK), "paper_id"].nunique()
        es = g.loc[g["country_code"].eq("ES"), "paper_id"].nunique()
        rows.append({
            "scenario": scenario,
            "window": w,
            "area": area,
            "ES": es,
            "EU27_UK": den,
            "ES_share": es / den if den else None,
        })

res = pd.DataFrame(rows)
res.to_csv(OUT / "area_reclassification_sensitivity.csv", index=False)

# Focus table for Spain in latest window.
if not res.empty:
    latest = sorted(res["window"].dropna().unique())[-1]
    pivot = res[res["window"].eq(latest)].pivot_table(
        index="area", columns="scenario", values="ES_share", aggfunc="first"
    )
    pivot["max_diff_pp"] = (pivot.max(axis=1) - pivot.min(axis=1)) * 100
    pivot.sort_values("max_diff_pp", ascending=False).to_csv(
        OUT / "area_reclassification_sensitivity_latest_window_pivot.csv"
    )

print("OK: area reclassification sensitivity generated.")
