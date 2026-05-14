"""
Objetivo:
Descomponer la pérdida de cuota española en:
1) efecto composición: cambia el peso europeo de las áreas/niveles,
2) efecto rendimiento interno: cambia la cuota española dentro de cada segmento.

Soluciona:
- Narrativa causal insuficientemente cuantificada.
- Necesidad de saber qué parte de la caída agregada se debe a IA/ML/A* y qué parte a caída intra-área.

Método:
Sea s_t = sum_k w_{k,t} * q_{ES,k,t}
w_{k,t}: peso del segmento k en UE27+RU.
q_{ES,k,t}: cuota española dentro del segmento k.
Contrafactual composición: sum_k w_{k,t1} * q_{ES,k,t0}
Contrafactual rendimiento: sum_k w_{k,t0} * q_{ES,k,t1}
"""
from pathlib import Path
import pandas as pd
from common import load_inputs, EU27_UK

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")
pc = pc.drop_duplicates(["paper_id","country_code"])
pc["segment"] = pc["area"].fillna("NA") + " | " + pc["level"].fillna("NA")

# Tabla segmento-ventana: UE denominator y ES numerator.
rows = []
for (w, seg), g in pc.groupby(["window","segment"]):
    eu_den = g[g.country_code.isin(EU27_UK)]["paper_id"].nunique()
    es_num = g[g.country_code == "ES"]["paper_id"].nunique()
    rows.append({"window": w, "segment": seg, "eu_den": eu_den, "es_num": es_num})
seg = pd.DataFrame(rows)
seg["q_es"] = seg["es_num"] / seg["eu_den"]

# Peso de cada segmento dentro del denominador europeo de la ventana.
total_eu = seg.groupby("window")["eu_den"].sum().reset_index(name="eu_total_segment_sum")
seg = seg.merge(total_eu, on="window")
seg["w_segment"] = seg["eu_den"] / seg["eu_total_segment_sum"]

seg.to_csv(OUT / "shift_share_segment_table.csv", index=False)

def decompose(t0, t1):
    a = seg[seg.window == t0][["segment","w_segment","q_es"]].rename(columns={"w_segment":"w0","q_es":"q0"})
    b = seg[seg.window == t1][["segment","w_segment","q_es"]].rename(columns={"w_segment":"w1","q_es":"q1"})
    m = a.merge(b, on="segment", how="outer").fillna(0)

    s0 = (m.w0 * m.q0).sum()
    s1 = (m.w1 * m.q1).sum()
    comp_effect = (m.w1 * m.q0).sum() - s0
    perf_effect = (m.w0 * m.q1).sum() - s0
    interaction = s1 - s0 - comp_effect - perf_effect

    m["contribution_total_change"] = m.w1*m.q1 - m.w0*m.q0
    m["composition_contribution"] = m.w1*m.q0 - m.w0*m.q0
    m["performance_contribution"] = m.w0*m.q1 - m.w0*m.q0
    m["interaction_contribution"] = m["contribution_total_change"] - m["composition_contribution"] - m["performance_contribution"]

    summary = pd.DataFrame([{
        "from": t0, "to": t1,
        "share_t0": s0, "share_t1": s1,
        "delta": s1-s0,
        "composition_effect": comp_effect,
        "performance_effect": perf_effect,
        "interaction": interaction
    }])
    return summary, m.sort_values("contribution_total_change")

summaries = []
details = []
for t0, t1 in [("2006-2010","2021-2025"), ("2011-2015","2021-2025")]:
    s, d = decompose(t0, t1)
    summaries.append(s)
    d["from"] = t0
    d["to"] = t1
    details.append(d)

pd.concat(summaries).to_csv(OUT / "shift_share_summary.csv", index=False)
pd.concat(details).to_csv(OUT / "shift_share_segment_contributions.csv", index=False)
print("OK: shift-share decomposition generated.")
