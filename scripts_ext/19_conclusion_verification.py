"""
19_conclusion_verification.py

Verifies and reformulates key conclusions using the observed data and, when
available, the extended robustness outputs. This is a bridge from diagnostics
to revised report wording.
"""
from pathlib import Path
import pandas as pd
import numpy as np
from common import load_inputs, EU27_UK, safe_rank

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
pc = pc.drop_duplicates(["paper_id", "country_code"])

windows = [w for w in ["2001-2005","2006-2010","2011-2015","2016-2020","2021-2025"] if w in set(pm.window.dropna())]

# Basic window stats.
rows = []
for w in windows:
    g = pc[pc.window == w]
    es = g[g.country_code == "ES"].paper_id.nunique()
    eu = g[g.country_code.isin(EU27_UK)].paper_id.nunique()
    rows.append({"window": w, "spain": es, "eu27_uk": eu, "share_pct": 100*es/eu if eu else np.nan})
ws = pd.DataFrame(rows)

verifications = []

def add(cid, original, status, evidence, reformulation):
    verifications.append({
        "conclusion_id": cid,
        "original": original,
        "status": status,
        "evidence": evidence,
        "recommended_reformulation": reformulation,
    })

# C1: growth wording.
sp = ws.set_index("window")["spain"]
drops = []
for a, b in zip(windows[:-1], windows[1:]):
    if sp.loc[b] < sp.loc[a]:
        drops.append(f"{a}→{b}: {sp.loc[a]}→{sp.loc[b]}")
add(
    "C1",
    "España registra crecimiento absoluto continuo.",
    "requires_rewording" if drops else "ok",
    "; ".join(drops) if drops else "No intermediate drop detected.",
    "España crece en volumen absoluto entre la primera y la última ventana, pero no de forma monótona; debe mencionarse la caída intermedia " + ", ".join(drops) + "." if drops else "España crece de forma monótona en volumen absoluto."
)

# C2/C3 rankings under complete counting.
rank_rows = []
for w in windows:
    g = pc[pc.window == w]
    den = g[g.country_code.isin(EU27_UK)].paper_id.nunique()
    for c in EU27_UK:
        num = g[g.country_code == c].paper_id.nunique()
        rank_rows.append({"window": w, "country_code": c, "count": num, "share": num/den if den else np.nan})
ranks = safe_rank(pd.DataFrame(rank_rows), ["window"], "share")
es_ranks = ranks[ranks.country_code == "ES"]
add(
    "C3",
    "La posición europea de España baja del entorno del 5.º al 8.º puesto.",
    "ok_with_caution",
    es_ranks[["window","rank","share"]].to_string(index=False),
    "Bajo conteo completo, España baja en el ranking observado de presencia. Debe reportarse como ranking de presencia no excluyente y acompañarse de conteo fraccionario/rangos de incertidumbre."
)

# Redes denominator caution.
red = pc[(pc.area == "Redes") & (pc.window == "2021-2025")]
red_venue = red.groupby("venue").apply(lambda g: pd.Series({
    "ES": g[g.country_code == "ES"].paper_id.nunique(),
    "EU27_UK": g[g.country_code.isin(EU27_UK)].paper_id.nunique(),
})).reset_index()
red_venue["share_pct"] = 100*red_venue["ES"] / red_venue["EU27_UK"].replace(0, np.nan)
small = red_venue[red_venue.EU27_UK < 200].sort_values("share_pct", ascending=False)
add(
    "C6",
    "Redes destaca positivamente.",
    "ok_with_caution",
    red_venue.sort_values("ES", ascending=False).head(10).to_string(index=False),
    "Redes es una fortaleza observada, pero la magnitud debe acompañarse de recuentos absolutos e intervalos: algunos venues tienen denominadores europeos pequeños " + (small.venue.astype(str).str.cat(sep=', ') if len(small) else "") + "."
)

# IA/ML coverage caution.
pm_iaml = pm[pm.area == "IA/ML"].paper_id.nunique()
pc_iaml = pc[pc.area == "IA/ML"].paper_id.nunique()
cov = 100*pc_iaml/pm_iaml if pm_iaml else np.nan
add(
    "C7",
    "IA/ML muestra pérdida relativa intensa.",
    "ok_with_caution",
    f"Cobertura IA/ML observada: {cov:.2f}% ({pc_iaml}/{pm_iaml}).",
    "La pérdida relativa en IA/ML debe formularse como resultado observado bajo cobertura parcial y conteo completo; validar con fraccionario, sensibilidad de cobertura y expansión del corpus."
)

# Fractional evidence if present.
frac_path = OUT/"spain_complete_fractional_summary.csv"
if frac_path.exists():
    fr = pd.read_csv(frac_path)
    add(
        "FRACTIONAL",
        "Conteo completo y fraccionario deben compararse.",
        "available",
        fr.to_string(index=False),
        "Incorporar la tabla completo vs fraccionario en resultados principales y ajustar la narrativa si rankings/cuotas divergen."
    )
else:
    add("FRACTIONAL", "Conteo fraccionario.", "pending", "No se encontró outputs_ext/spain_complete_fractional_summary.csv", "Ejecutar 01_fractional_vs_complete.py antes de cerrar conclusiones.")

# Inflation evidence if present.
infl_path = OUT/"overlap_inflation_by_window.csv"
if infl_path.exists():
    inf = pd.read_csv(infl_path)
    add("INFLATION", "Cuotas no excluyentes.", "available", inf.to_string(index=False), "Incluir factor de inflación y suma de cuotas por ventana junto a ES/UE27+RU.")

# Compose outputs.
df = pd.DataFrame(verifications)
df.to_csv(OUT/"conclusion_verification.csv", index=False)
with open(OUT/"conclusion_reformulations.txt", "w", encoding="utf-8") as f:
    f.write("VERIFICACIÓN Y REFORMULACIÓN DE CONCLUSIONES\n")
    f.write("="*72 + "\n\n")
    f.write("DATOS BASE POR VENTANA\n")
    f.write(ws.to_string(index=False))
    f.write("\n\n")
    for r in verifications:
        f.write(f"[{r['conclusion_id']}] {r['original']}\n")
        f.write(f"  Estado: {r['status']}\n")
        f.write(f"  Evidencia:\n{r['evidence']}\n")
        f.write(f"  Redacción recomendada: {r['recommended_reformulation']}\n\n")
print("OK: conclusion verification generated.")
