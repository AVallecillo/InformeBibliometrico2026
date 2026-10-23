"""
Objetivo:
Comparar el corpus fijo CORE/ICORE 2026 con la clasificación CORE histórica
vigente en el año de publicación de cada artículo.

Versión 2 (octubre de 2026). Corrige la versión anterior, que asignaba a cada
artículo la versión histórica más cercana EN QUE APARECÍA EL CONGRESO. Como
core_historical.csv solo contiene congresos A* y A, esa regla no podía excluir
ningún artículo y el escenario histórico coincidía por construcción con el corpus fijo.

Entradas:
  outputs/paper_master.csv, outputs/paper_country.csv
  data/core_historical/core_historical.csv  (venue, core_year, level ∈ {A*, A})
  generado por scripts_ext/build_core_historical.py (v2)

Regla:
  1. Versión vigente de un artículo publicado en el año y = la versión CORE más
     reciente con core_year <= y. Para y anterior a la primera versión (2008)
     se usa la primera versión.
  2. Un congreso que no figura en la lista A*/A de la versión vigente se considera
     «no A*/A» en ese año (B, C, sin clasificar, retirado o pendiente de clasificar).

Escenarios:
  fixed_2026_Astar_A             corpus fijo del informe
  historical_strict_Astar_A      A* o A en la versión vigente
  historical_gaptolerant_Astar_A como el anterior, pero una ausencia entre dos
                                 versiones en que el congreso sí figura se trata
                                 como hueco administrativo (p. ej., MICRO 2020-2023)
  historical_strict_Astar_only   A* en la versión vigente (ERA 2010 según la regla
                                 de inferencia de build_core_historical.py)

Salidas:
  outputs_ext/core_historical_sensitivity.csv
  outputs_ext/core_historical_corpus_retained.csv
  outputs_ext/paper_master_with_historical_core.csv
"""
from pathlib import Path
import pandas as pd
from common import load_inputs, EU27_UK, safe_rank

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
hist_path = Path("data/core_historical/core_historical.csv")
if not hist_path.exists():
    (OUT / "core_historical_sensitivity_SKIPPED.txt").write_text(
        "SKIPPED: data/core_historical/core_historical.csv no existe. "
        "Ejecuta scripts_ext/build_core_historical.py.\n", encoding="utf-8")
    print("SKIPPED: data/core_historical/core_historical.csv no existe.")
    raise SystemExit(0)

hist = pd.read_csv(hist_path)
hist["core_year"] = hist["core_year"].astype(int)
versions = sorted(hist["core_year"].unique())

# Nivel por (congreso, versión); ausente = no A*/A.
level = {(v, y): l for v, y, l in hist[["venue", "core_year", "level"]].itertuples(index=False)}
present_years = hist.groupby("venue")["core_year"].apply(set).to_dict()


def applicable_version(year):
    prior = [v for v in versions if v <= year]
    return prior[-1] if prior else versions[0]


pm = pm.copy()
pm["hist_core_year"] = pm["year"].astype(int).map(applicable_version)
pm["hist_level"] = [level.get((v, y)) for v, y in zip(pm["venue"], pm["hist_core_year"])]


def gap_tolerant(venue, y):
    yrs = present_years.get(venue, set())
    return any(u < y for u in yrs) and any(u > y for u in yrs)


pm["hist_gap"] = [
    pd.isna(lvl) and gap_tolerant(v, y)
    for v, y, lvl in zip(pm["venue"], pm["hist_core_year"], pm["hist_level"])
]
pm.to_csv(OUT / "paper_master_with_historical_core.csv", index=False)

base = pm.level.isin(["A*", "A"])
scenarios = {
    "fixed_2026_Astar_A": set(pm.loc[base, "paper_id"]),
    "historical_strict_Astar_A": set(pm.loc[pm.hist_level.isin(["A*", "A"]), "paper_id"]),
    "historical_gaptolerant_Astar_A": set(pm.loc[pm.hist_level.isin(["A*", "A"]) | pm.hist_gap, "paper_id"]),
    "historical_strict_Astar_only": set(pm.loc[pm.hist_level.eq("A*"), "paper_id"]),
}

rows, kept = [], []
for scenario, paper_ids in scenarios.items():
    sel = pm.paper_id.isin(paper_ids)
    for w, g in pm.groupby("window"):
        kept.append({"scenario": scenario, "window": w, "papers": int(sel[g.index].sum()),
                     "papers_fixed_corpus": len(g), "retained_share": sel[g.index].mean()})
    x = pc[pc.paper_id.isin(paper_ids)]
    for w, wdf in x.groupby("window"):
        den = wdf[wdf.country_code.isin(EU27_UK)]["paper_id"].nunique()
        for c in EU27_UK:
            num = wdf[wdf.country_code == c]["paper_id"].nunique()
            rows.append({"scenario": scenario, "window": w, "country_code": c, "count": num,
                         "eu_den": den, "share": num / den if den else None})

res = safe_rank(pd.DataFrame(rows), ["scenario", "window"], "share")
res.to_csv(OUT / "core_historical_sensitivity.csv", index=False)
pd.DataFrame(kept).to_csv(OUT / "core_historical_corpus_retained.csv", index=False)

es = res[res.country_code == "ES"].pivot_table(index="scenario", columns="window", values=["share", "rank"])
print(es.round(4))
print("OK: CORE historical sensitivity (v2) generated.")
