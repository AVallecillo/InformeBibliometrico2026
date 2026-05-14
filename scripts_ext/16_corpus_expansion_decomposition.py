"""
Objetivo:
Separar el efecto de expansión del corpus/venues del cambio real de cuota.

Problema que resuelve:
Aplicar CORE/ICORE 2026 retrospectivamente mezcla:
- crecimiento de venues ya existentes,
- aparición de venues nuevos,
- crecimiento explosivo de venues recientes como ICLR,
- cambios de volumen editorial.

Este script descompone el cambio entre dos ventanas en:
1) venues presentes en ambas ventanas;
2) venues nuevos o sin artículos en la ventana base;
3) venues que desaparecen o no tienen artículos en la ventana final.

Salidas:
outputs_ext/corpus_expansion_venue_decomposition.csv
outputs_ext/corpus_expansion_summary.csv
"""
from pathlib import Path
import pandas as pd
from common import load_inputs, EU27_UK

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
pc = pc.drop_duplicates(["paper_id", "country_code"])

def venue_window_counts():
    rows = []
    for (w, venue), g in pc.groupby(["window", "venue"]):
        eu = g[g.country_code.isin(EU27_UK)]["paper_id"].nunique()
        es = g[g.country_code == "ES"]["paper_id"].nunique()
        rows.append({"window": w, "venue": venue, "eu": eu, "es": es})
    return pd.DataFrame(rows)

vw = venue_window_counts()

def decompose(t0, t1):
    a = vw[vw.window == t0][["venue", "eu", "es"]].rename(columns={"eu": "eu0", "es": "es0"})
    b = vw[vw.window == t1][["venue", "eu", "es"]].rename(columns={"eu": "eu1", "es": "es1"})
    m = a.merge(b, on="venue", how="outer").fillna(0)
    m["status"] = "present_both"
    m.loc[(m.eu0 == 0) & (m.eu1 > 0), "status"] = "new_or_zero_in_base"
    m.loc[(m.eu0 > 0) & (m.eu1 == 0), "status"] = "disappeared_or_zero_in_final"
    m["share0_venue"] = m["es0"] / m["eu0"].replace(0, pd.NA)
    m["share1_venue"] = m["es1"] / m["eu1"].replace(0, pd.NA)
    m["delta_es"] = m["es1"] - m["es0"]
    m["delta_eu"] = m["eu1"] - m["eu0"]
    m["from"] = t0
    m["to"] = t1

    total0 = m.es0.sum() / m.eu0.sum()
    total1 = m.es1.sum() / m.eu1.sum()

    summary = (
        m.groupby("status")
        .agg(es0=("es0", "sum"), eu0=("eu0", "sum"), es1=("es1", "sum"), eu1=("eu1", "sum"))
        .reset_index()
    )
    summary["share0"] = summary["es0"] / summary["eu0"].replace(0, pd.NA)
    summary["share1"] = summary["es1"] / summary["eu1"].replace(0, pd.NA)
    summary["from"] = t0
    summary["to"] = t1
    summary["overall_share0"] = total0
    summary["overall_share1"] = total1
    return m, summary

details = []
summaries = []
for t0, t1 in [("2001-2005", "2021-2025"), ("2006-2010", "2021-2025"), ("2011-2015", "2021-2025")]:
    d, s = decompose(t0, t1)
    details.append(d)
    summaries.append(s)

pd.concat(details, ignore_index=True).to_csv(OUT / "corpus_expansion_venue_decomposition.csv", index=False)
pd.concat(summaries, ignore_index=True).to_csv(OUT / "corpus_expansion_summary.csv", index=False)

print("OK: corpus expansion decomposition generated.")
