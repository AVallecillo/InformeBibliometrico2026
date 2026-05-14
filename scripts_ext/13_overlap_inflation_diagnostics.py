"""
Objetivo:
Cuantificar la inflación del denominador UE27+RU bajo conteo completo.

Problema que resuelve:
El denominador europeo se define como artículos con >=1 país UE27+RU, pero las cuotas
nacionales no son excluyentes. La suma de cuotas puede superar el 100 %. Este script mide:
- suma de cuotas nacionales por ventana y área;
- número medio de países europeos por artículo europeo;
- porcentaje de artículos europeos con colaboración intraeuropea;
- inflación del conteo completo europeo frente a artículos únicos europeos.

Entradas:
outputs/paper_master.csv
outputs/paper_country.csv

Salidas:
outputs_ext/overlap_inflation_by_window.csv
outputs_ext/overlap_inflation_by_area_window.csv
outputs_ext/european_country_multiplicity_distribution.csv
"""
from pathlib import Path
import pandas as pd
from common import load_inputs, EU27_UK

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
pc = pc.drop_duplicates(["paper_id", "country_code"])

def inflation_table(df, group_cols):
    eu = df[df.country_code.isin(EU27_UK)].copy()
    paper_eu_countries = (
        eu.groupby(group_cols + ["paper_id"])["country_code"]
          .nunique()
          .reset_index(name="n_eu_countries")
    )
    article_den = paper_eu_countries.groupby(group_cols)["paper_id"].nunique().reset_index(name="unique_european_articles")
    complete_sum = paper_eu_countries.groupby(group_cols)["n_eu_countries"].sum().reset_index(name="sum_complete_country_counts")
    intra = (
        paper_eu_countries.assign(is_intra_eu_collab=lambda x: x.n_eu_countries > 1)
        .groupby(group_cols)
        .agg(
            mean_eu_countries_per_article=("n_eu_countries", "mean"),
            median_eu_countries_per_article=("n_eu_countries", "median"),
            share_intra_eu_collab=("is_intra_eu_collab", "mean")
        )
        .reset_index()
    )
    out = article_den.merge(complete_sum, on=group_cols).merge(intra, on=group_cols)
    out["inflation_factor_complete_over_unique"] = out["sum_complete_country_counts"] / out["unique_european_articles"]
    out["sum_of_all_country_shares"] = out["inflation_factor_complete_over_unique"]
    return out

w = inflation_table(pc, ["window"])
w.to_csv(OUT / "overlap_inflation_by_window.csv", index=False)

aw = inflation_table(pc, ["window", "area"])
aw.to_csv(OUT / "overlap_inflation_by_area_window.csv", index=False)

dist = (
    pc[pc.country_code.isin(EU27_UK)]
    .groupby(["window", "paper_id"])["country_code"].nunique()
    .reset_index(name="n_eu_countries")
    .groupby(["window", "n_eu_countries"])["paper_id"].nunique()
    .reset_index(name="articles")
)
dist["share"] = dist["articles"] / dist.groupby("window")["articles"].transform("sum")
dist.to_csv(OUT / "european_country_multiplicity_distribution.csv", index=False)

print("OK: overlap/inflation diagnostics generated.")
