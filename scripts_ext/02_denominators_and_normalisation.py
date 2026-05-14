"""
Objetivo:
Añadir denominadores alternativos y normalización por tamaño del sistema.
Soluciona:
- Dependencia exclusiva de UE27+RU.
- Comparaciones no ajustadas por tamaño nacional.

Entradas adicionales opcionales:
data/external/country_normalisers.csv con columnas:
country_code,population_millions,researchers_fte,gerd_musd,cs_faculty_or_researchers
"""
from pathlib import Path
import pandas as pd
from common import load_inputs, EU27_UK, EUROPE_EXTENDED, COMPARABLE

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
pc = pc.drop_duplicates(["paper_id","country_code"])

GROUPS = {
    "world_resolved": set(pc.country_code.dropna().unique()),
    "eu27_uk": EU27_UK,
    "europe_extended": EUROPE_EXTENDED,
    "comparable": COMPARABLE,
}

rows = []
for window, wdf in pc.groupby("window"):
    for group_name, countries in GROUPS.items():
        den = wdf.loc[wdf.country_code.isin(countries), "paper_id"].nunique()
        for c in sorted(countries):
            num = wdf.loc[wdf.country_code == c, "paper_id"].nunique()
            rows.append({
                "window": window,
                "denominator_group": group_name,
                "country_code": c,
                "count": num,
                "denominator": den,
                "share": num / den if den else None,
            })

df = pd.DataFrame(rows)
df.to_csv(OUT / "alternative_denominators.csv", index=False)

norm_path = Path("data/external/country_normalisers.csv")
if norm_path.exists():
    norm = pd.read_csv(norm_path)
    x = df[df.denominator_group == "world_resolved"].merge(norm, on="country_code", how="left")
    x["articles_per_million_population"] = x["count"] / x["population_millions"]
    x["articles_per_1000_researchers_fte"] = x["count"] / x["researchers_fte"] * 1000
    x["articles_per_billion_gerd_usd"] = x["count"] / (x["gerd_musd"] / 1000)
    if "cs_faculty_or_researchers" in x.columns:
        x["articles_per_100_cs_researchers"] = x["count"] / x["cs_faculty_or_researchers"] * 100
    x.to_csv(OUT / "normalised_country_indicators.csv", index=False)
else:
    print("WARNING: data/external/country_normalisers.csv not found; only denominator table generated.")

print("OK: denominator and normalisation outputs written.")
