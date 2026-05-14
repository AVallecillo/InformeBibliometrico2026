"""
Objetivo:
Comparar conteo completo frente a conteo fraccionario por país.
Soluciona:
- Confusión entre presencia y contribución proporcional.
- Posible sobreponderación de países con mucha coautoría internacional.

Entradas:
outputs/paper_master.csv
outputs/paper_country.csv

Salidas:
outputs_ext/fractional_vs_complete_by_window.csv
outputs_ext/fractional_vs_complete_by_area_window.csv
outputs_ext/spain_complete_fractional_summary.csv
"""
from pathlib import Path
import pandas as pd
from common import load_inputs, fractional_by_unique_country, EU27_UK, safe_rank

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
pc = pc.drop_duplicates(["paper_id","country_code"])

# Conteo completo por ventana-país.
complete = (
    pc.groupby(["window","country_code"])["paper_id"]
      .nunique()
      .reset_index(name="complete_count")
)

# Conteo fraccionario por países únicos.
frac = fractional_by_unique_country(pc)
fractional = (
    frac.groupby(["window","country_code"])["frac_country_weight"]
        .sum()
        .reset_index(name="fractional_count")
)

tab = complete.merge(fractional, on=["window","country_code"], how="outer").fillna(0)

# Denominador UE27+RU en ambos modos.
eu_complete = (
    pc[pc.country_code.isin(EU27_UK)]
    .groupby("window")["paper_id"].nunique()
    .reset_index(name="eu_complete_den")
)
eu_fractional = (
    frac[frac.country_code.isin(EU27_UK)]
    .groupby("window")["frac_country_weight"].sum()
    .reset_index(name="eu_fractional_den")
)

tab = tab.merge(eu_complete, on="window", how="left").merge(eu_fractional, on="window", how="left")
tab["complete_share_eu"] = tab["complete_count"] / tab["eu_complete_den"]
tab["fractional_share_eu"] = tab["fractional_count"] / tab["eu_fractional_den"]

tab = safe_rank(tab[tab.country_code.isin(EU27_UK)], ["window"], "complete_share_eu").rename(columns={"rank":"complete_rank"})
tab = safe_rank(tab, ["window"], "fractional_share_eu").rename(columns={"rank":"fractional_rank"})

tab.to_csv(OUT / "fractional_vs_complete_by_window.csv", index=False)

# Por área.
complete_area = (
    pc.groupby(["window","area","country_code"])["paper_id"].nunique()
      .reset_index(name="complete_count")
)
frac_area = (
    frac.groupby(["window","area","country_code"])["frac_country_weight"].sum()
        .reset_index(name="fractional_count")
)
area_tab = complete_area.merge(frac_area, on=["window","area","country_code"], how="outer").fillna(0)

eu_c_area = (
    pc[pc.country_code.isin(EU27_UK)]
    .groupby(["window","area"])["paper_id"].nunique()
    .reset_index(name="eu_complete_den")
)
eu_f_area = (
    frac[frac.country_code.isin(EU27_UK)]
    .groupby(["window","area"])["frac_country_weight"].sum()
    .reset_index(name="eu_fractional_den")
)
area_tab = area_tab.merge(eu_c_area, on=["window","area"], how="left").merge(eu_f_area, on=["window","area"], how="left")
area_tab["complete_share_eu"] = area_tab["complete_count"] / area_tab["eu_complete_den"]
area_tab["fractional_share_eu"] = area_tab["fractional_count"] / area_tab["eu_fractional_den"]
area_tab.to_csv(OUT / "fractional_vs_complete_by_area_window.csv", index=False)

spain = tab[tab.country_code == "ES"].copy()
spain["delta_share_pp_fractional_minus_complete"] = 100 * (spain["fractional_share_eu"] - spain["complete_share_eu"])
spain.to_csv(OUT / "spain_complete_fractional_summary.csv", index=False)

print("OK: fractional vs complete tables written to outputs_ext/")
