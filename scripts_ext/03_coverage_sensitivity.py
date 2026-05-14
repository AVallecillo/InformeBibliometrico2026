"""
Objetivo:
Repetir resultados excluyendo congresos con baja cobertura.
Soluciona:
- Sesgo por cobertura desigual por congreso, área o ventana.
- Robustez de las conclusiones ante umbrales de cobertura.

Salidas:
outputs_ext/coverage_by_venue_window.csv
outputs_ext/sensitivity_threshold_*.csv
"""
from pathlib import Path
import pandas as pd
from common import load_inputs, EU27_UK, safe_rank

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
pc = pc.drop_duplicates(["paper_id","country_code"])

coverage = (
    pm.groupby(["venue","window","area","level"])["paper_id"].nunique().reset_index(name="total_papers")
    .merge(
        pc.groupby(["venue","window"])["paper_id"].nunique().reset_index(name="resolved_papers"),
        on=["venue","window"], how="left"
    )
)
coverage["resolved_papers"] = coverage["resolved_papers"].fillna(0)
coverage["coverage"] = coverage["resolved_papers"] / coverage["total_papers"]
coverage.to_csv(OUT / "coverage_by_venue_window.csv", index=False)

def compute_for_allowed(allowed_venues, label):
    xpc = pc[pc.venue.isin(allowed_venues)].copy()
    rows = []
    for w, wdf in xpc.groupby("window"):
        den = wdf[wdf.country_code.isin(EU27_UK)]["paper_id"].nunique()
        for c in EU27_UK:
            num = wdf[wdf.country_code == c]["paper_id"].nunique()
            rows.append({"window": w, "country_code": c, "count": num, "eu_den": den, "share": num/den if den else None})
    out = pd.DataFrame(rows)
    out = safe_rank(out, ["window"], "share")
    out["scenario"] = label
    return out

all_results = []
for thr in [0.30, 0.50, 0.70, 0.80, 0.90]:
    # Exigir que el congreso-ventana supere umbral. Para conservar granularidad, filtramos paper_id.
    good_vw = coverage[coverage.coverage >= thr][["venue","window"]]
    good_keys = set(map(tuple, good_vw.to_numpy()))
    allowed_papers = pm[pm[["venue","window"]].apply(tuple, axis=1).isin(good_keys)]["paper_id"]
    xpc = pc[pc.paper_id.isin(allowed_papers)]
    rows = []
    for w, wdf in xpc.groupby("window"):
        den = wdf[wdf.country_code.isin(EU27_UK)]["paper_id"].nunique()
        for c in EU27_UK:
            num = wdf[wdf.country_code == c]["paper_id"].nunique()
            rows.append({"window": w, "country_code": c, "count": num, "eu_den": den, "share": num/den if den else None})
    res = pd.DataFrame(rows)
    res = safe_rank(res, ["window"], "share")
    res["coverage_threshold"] = thr
    res.to_csv(OUT / f"sensitivity_threshold_{int(thr*100)}.csv", index=False)
    all_results.append(res)

pd.concat(all_results, ignore_index=True).to_csv(OUT / "coverage_sensitivity_all_thresholds.csv", index=False)
print("OK: coverage sensitivity generated.")
