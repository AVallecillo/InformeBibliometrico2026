"""
Objetivo:
Calcular bandas de ranking bajo escenarios extremos de afiliaciones faltantes.
Soluciona:
- Rankings potencialmente inestables por cobertura incompleta.

Escenarios:
- observed: solo papers con país resuelto.
- optimistic_ES: todos los papers no resueltos del denominador europeo potencial se asignan a España.
- pessimistic_ES: los no resueltos se asignan a otros países europeos, no a España.
Este bound es conservador; sirve para detectar si la conclusión de ranking es robusta.
"""
from pathlib import Path
import pandas as pd
from common import load_inputs, EU27_UK, safe_rank

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
pc = pc.drop_duplicates(["paper_id","country_code"])

resolved_ids = set(pc.paper_id.unique())
pm["resolved"] = pm.paper_id.isin(resolved_ids)

rows = []
for w, papers_w in pm.groupby("window"):
    pc_w = pc[pc.window == w]
    unresolved = papers_w.loc[~papers_w.resolved, "paper_id"].nunique()
    observed_den = pc_w[pc_w.country_code.isin(EU27_UK)]["paper_id"].nunique()
    observed_counts = {c: pc_w[pc_w.country_code == c]["paper_id"].nunique() for c in EU27_UK}

    for scenario in ["observed", "optimistic_ES", "pessimistic_ES"]:
        for c in EU27_UK:
            count = observed_counts[c]
            den = observed_den
            if scenario == "optimistic_ES":
                den = observed_den + unresolved
                if c == "ES":
                    count = count + unresolved
            elif scenario == "pessimistic_ES":
                den = observed_den + unresolved
                # ES no recibe nada; otros países no se reparten aquí porque el objetivo es bound de ES.
            rows.append({"window": w, "scenario": scenario, "country_code": c, "count": count, "eu_den": den, "share": count/den if den else None})

res = pd.DataFrame(rows)
res = safe_rank(res, ["window","scenario"], "share")
res.to_csv(OUT / "rank_uncertainty_bounds.csv", index=False)
print("OK: rank uncertainty bounds generated.")
