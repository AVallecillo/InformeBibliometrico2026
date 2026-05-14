"""
Objetivo:
Comprobar si la ventana 2021-2025 depende excesivamente de 2025.
Soluciona:
- Riesgo de incompletitud temporal de la última ventana.

Salidas:
outputs_ext/maturity_2021_2024_vs_2021_2025.csv
"""
from pathlib import Path
import pandas as pd
from common import load_inputs, EU27_UK, safe_rank

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
pc = pc.drop_duplicates(["paper_id","country_code"])

scenarios = {
    "2021_2025_full": set(pm[(pm.year >= 2021) & (pm.year <= 2025)].paper_id),
    "2021_2024_excl_2025": set(pm[(pm.year >= 2021) & (pm.year <= 2024)].paper_id),
    "2025_only": set(pm[pm.year == 2025].paper_id),
}

rows = []
for scenario, ids in scenarios.items():
    x = pc[pc.paper_id.isin(ids)]
    den = x[x.country_code.isin(EU27_UK)]["paper_id"].nunique()
    for c in EU27_UK:
        num = x[x.country_code == c]["paper_id"].nunique()
        rows.append({"scenario": scenario, "country_code": c, "count": num, "eu_den": den, "share": num/den if den else None})

res = pd.DataFrame(rows)
res = safe_rank(res, ["scenario"], "share")
res.to_csv(OUT / "maturity_2021_2024_vs_2021_2025.csv", index=False)
print("OK: 2025 maturity check generated.")
