"""
Objetivo:
Medir colaboración internacional de España.
Soluciona:
- Diferenciar presencia aislada, coautoría internacional y dependencia de socios.
- Interpretar por qué conteo completo y fraccionario pueden divergir.

Salidas:
outputs_ext/spain_collaboration_by_window_area.csv
outputs_ext/spain_partner_countries.csv
"""
from pathlib import Path
import itertools
import pandas as pd
from common import load_inputs

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
pc = pc.drop_duplicates(["paper_id","country_code"])

paper_countries = pc.groupby("paper_id")["country_code"].apply(lambda s: sorted(set(s.dropna()))).reset_index()
paper_countries["n_countries"] = paper_countries["country_code"].apply(len)
paper_countries["has_ES"] = paper_countries["country_code"].apply(lambda xs: "ES" in xs)
paper_countries["ES_only"] = paper_countries["country_code"].apply(lambda xs: xs == ["ES"])
paper_countries = paper_countries.merge(pm[["paper_id","window","area","level","venue"]], on="paper_id", how="left")

es_papers = paper_countries[paper_countries.has_ES].copy()
summary = (
    es_papers.groupby(["window","area"])
    .agg(
        es_papers=("paper_id","nunique"),
        es_only=("ES_only","sum"),
        avg_countries=("n_countries","mean"),
        median_countries=("n_countries","median"),
    )
    .reset_index()
)
summary["share_es_only"] = summary["es_only"] / summary["es_papers"]
summary["share_international"] = 1 - summary["share_es_only"]
summary.to_csv(OUT / "spain_collaboration_by_window_area.csv", index=False)

partner_rows = []
for _, r in es_papers.iterrows():
    partners = [c for c in r["country_code"] if c != "ES"]
    for p in partners:
        partner_rows.append({"paper_id": r.paper_id, "window": r.window, "area": r.area, "partner_country": p})
partners = pd.DataFrame(partner_rows)
if not partners.empty:
    partner_summary = partners.groupby(["window","area","partner_country"])["paper_id"].nunique().reset_index(name="collab_papers")
    partner_summary.sort_values(["window","area","collab_papers"], ascending=[True, True, False]).to_csv(OUT / "spain_partner_countries.csv", index=False)

print("OK: collaboration profiles generated.")
