"""
Objetivo:
Diagnosticar si la falta de país resuelto parece aleatoria o sistemática.

Problema que resuelve:
El informe reporta cobertura global y por área, pero no evalúa si los artículos sin país
identificado se concentran por venue, año, editor, DOI, fuente o tipo de metadato.

Entradas:
outputs/paper_master.csv
outputs/paper_country.csv
Opcionales si existen en paper_master:
doi, publisher, booktitle, source, has_doi

Salidas:
outputs_ext/missingness_by_year_window_area_level.csv
outputs_ext/missingness_by_venue.csv
outputs_ext/missingness_logit_dataset.csv
outputs_ext/missingness_logit_summary.txt

Nota:
El modelo logístico no prueba sesgo por país en artículos totalmente sin país, porque el país
es desconocido; sí prueba no-aleatoriedad observable en la probabilidad de resolver país.
"""
from pathlib import Path
import pandas as pd
import numpy as np
from common import load_inputs

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
resolved = set(pc.paper_id.unique())
df = pm.copy()
df["country_resolved"] = df.paper_id.isin(resolved).astype(int)

if "doi" in df.columns:
    df["has_doi"] = df["doi"].notna() & df["doi"].astype(str).str.len().gt(3)
elif "has_doi" not in df.columns:
    df["has_doi"] = np.nan

group_cols = ["window", "area", "level"]
summary = (
    df.groupby(group_cols)
    .agg(
        total=("paper_id", "nunique"),
        resolved=("country_resolved", "sum"),
        coverage=("country_resolved", "mean")
    )
    .reset_index()
)
summary.to_csv(OUT / "missingness_by_year_window_area_level.csv", index=False)

venue = (
    df.groupby(["venue", "area", "level"])
    .agg(
        total=("paper_id", "nunique"),
        resolved=("country_resolved", "sum"),
        coverage=("country_resolved", "mean")
    )
    .reset_index()
    .sort_values(["coverage", "total"], ascending=[True, False])
)
venue.to_csv(OUT / "missingness_by_venue.csv", index=False)

# Dataset para inspección y modelado externo.
model_cols = [c for c in ["paper_id", "year", "window", "venue", "area", "level", "has_doi", "country_resolved"] if c in df.columns]
df[model_cols].to_csv(OUT / "missingness_logit_dataset.csv", index=False)

# Intento de modelo logístico si statsmodels está instalado.
try:
    import statsmodels.formula.api as smf
    mdf = df.copy()
    mdf["has_doi"] = mdf["has_doi"].fillna(False).astype(int)
    # Fórmula deliberadamente simple para evitar explosión de parámetros.
    model = smf.logit("country_resolved ~ C(window) + C(area) + C(level) + has_doi", data=mdf).fit(disp=False)
    with open(OUT / "missingness_logit_summary.txt", "w", encoding="utf-8") as f:
        f.write(str(model.summary()))
except Exception as e:
    with open(OUT / "missingness_logit_summary.txt", "w", encoding="utf-8") as f:
        f.write("Logit model not run. Reason:\n")
        f.write(str(e))

print("OK: missingness diagnostics generated.")
