"""
Objetivo:
Comparar corpus fijo CORE/ICORE 2026 contra ranking CORE histórico.
Soluciona:
- Sesgo retrospectivo de prestigio.
- Cambios de categoría A*/A a lo largo del tiempo.

Entradas adicionales:
data/core_historical/core_historical.csv con columnas mínimas:
venue,core_year,level
donde level puede ser A*, A, B, C, etc.

Estrategia:
Para cada paper, asignar la versión CORE más cercana anterior o igual al año de publicación.
Si no existe anterior, se usa la más cercana posterior y se marca fallback=True.
"""
from pathlib import Path
import pandas as pd
from common import load_inputs, EU27_UK, safe_rank

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
hist_path = Path("data/core_historical/core_historical.csv")
if not hist_path.exists():
    OUT.mkdir(exist_ok=True)
    (OUT / "core_historical_sensitivity_SKIPPED.txt").write_text("SKIPPED: data/core_historical/core_historical.csv no existe. Ejecuta scripts_ext/build_core_historical.py.\n", encoding="utf-8")
    print("SKIPPED: data/core_historical/core_historical.csv no existe.")
    raise SystemExit(0)

hist = pd.read_csv(hist_path)
hist["core_year"] = hist["core_year"].astype(int)

def assign_historical_level(row):
    h = hist[hist.venue == row["venue"]].copy()
    if h.empty:
        return pd.Series({"hist_level": None, "hist_core_year": None, "hist_fallback": True})
    prior = h[h.core_year <= int(row["year"])]
    if not prior.empty:
        r = prior.sort_values("core_year").iloc[-1]
        return pd.Series({"hist_level": r["level"], "hist_core_year": r["core_year"], "hist_fallback": False})
    r = h.assign(dist=(h.core_year - int(row["year"])).abs()).sort_values("dist").iloc[0]
    return pd.Series({"hist_level": r["level"], "hist_core_year": r["core_year"], "hist_fallback": True})

assigned = pm.join(pm.apply(assign_historical_level, axis=1))
assigned.to_csv(OUT / "paper_master_with_historical_core.csv", index=False)

# Escenarios.
scenarios = {
    "fixed_2026_Astar_A": set(pm.loc[pm.level.isin(["A*","A"]), "paper_id"]),
    "historical_Astar_A": set(assigned.loc[assigned.hist_level.isin(["A*","A"]), "paper_id"]),
    "historical_Astar_only": set(assigned.loc[assigned.hist_level.eq("A*"), "paper_id"]),
    "stable_Astar_A_both": set(pm.loc[pm.level.isin(["A*","A"]), "paper_id"]) & set(assigned.loc[assigned.hist_level.isin(["A*","A"]), "paper_id"]),
}

rows = []
for scenario, paper_ids in scenarios.items():
    x = pc[pc.paper_id.isin(paper_ids)]
    for w, wdf in x.groupby("window"):
        den = wdf[wdf.country_code.isin(EU27_UK)]["paper_id"].nunique()
        for c in EU27_UK:
            num = wdf[wdf.country_code == c]["paper_id"].nunique()
            rows.append({"scenario": scenario, "window": w, "country_code": c, "count": num, "eu_den": den, "share": num/den if den else None})
res = pd.DataFrame(rows)
res = safe_rank(res, ["scenario","window"], "share")
res.to_csv(OUT / "core_historical_sensitivity.csv", index=False)
print("OK: CORE historical sensitivity generated.")
