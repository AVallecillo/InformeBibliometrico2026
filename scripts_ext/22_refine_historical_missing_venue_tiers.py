"""
22_refine_historical_missing_venue_tiers.py

Refines missing historical CORE venue priorities into:
TIER1 include, TIER2 manual review, TIER3 exclude unless appendix.
Run after 21_prioritize_historical_missing_venues.py.
"""

from pathlib import Path
import pandas as pd
import re

OUT = Path("outputs_ext")
DATA = Path("data")
INPUT = OUT / "historical_missing_venue_prioritization.csv"
OVERRIDES = DATA / "external" / "historical_venue_tier_overrides.csv"

TIER1_SEED = {
    "COLING","CoNLL","ECML","PAKDD","PKDD","ALT","EDBT","DEXA","ESWC","DBSEC","SSDBM","FOIS","EKAW",
    "CCGRID","CLUSTER","EuroPar","EuroMPI","HiPC","PPoPP","SPAA","ICPP","ICNP","IPSN","SENSYS","HOTNETS","EWSN","MOBIHOC","EMSOFT","ECRTS","CASES","ASAP","FCCM","HOTCHIPS (HCS)",
    "CONCUR","FOSSACS","FLOPS","FM","ATVA","FST&TCS","FCT","COCOON","ICLP","ISSAC","ISAAC","IPCO","RANDOM","TARK","LPAR","AiML","CC",
    "ICIP","EUROGRAPH","I3DG","DCC","RSS","UbiComp","PERVASIVE","AOSD","ECSA","ICECCS","FORTE","Coordination","CoopIS",
}
TIER2_SEED = {
    "ICIS","ECIS","AMCIS","HICSS","DESRIST","CSCL","ITiCSE","ICALT","ITS","AMIA","AIME","CSB","CogSci","ALIFE","IEEE Alife",
    "CDC","ICARCV","FUZZ-IEEE","IJCNN","ICONIP","JCDL","ICADL","ASIS&T","Interact","Group","Hypertext","DocEng","ICCS","ICSSP","IEEE SSE","K-CAP","IDA",
}
TIER3_SEED = {"AFIPS","AIIM","AID","APCOMin","Ada-Europe","DUX","DIGRA","EAAI","EMMSAD","EuroSPI","FSR","ICCL"}

CENTRAL_AREAS = {
    "NLP","Machine Learning / Data Mining","Bases de datos / Web / Conocimiento","Sistemas / HPC / Arquitectura",
    "Sistemas empotrados / Tiempo real","Teoría / Métodos formales / PL","Visión / Imagen / Gráficos",
    "Ingeniería del Software / Servicios","HCI / CSCW / Documentos",
}
ADJACENT_AREAS = {"Sistemas de información","Educación / Learning technologies","Bioinformática / Informática médica","Control / Señal / Ingeniería","Sin clasificar"}

def norm(v):
    return "" if pd.isna(v) else re.sub(r"\s+", " ", str(v).strip())

def b(x):
    if isinstance(x, bool): return x
    if pd.isna(x): return False
    return str(x).strip().lower() in {"true","1","yes","y","si","sí"}

def decide(r):
    venue = norm(r["venue"])
    area = str(r.get("inferred_area","Sin clasificar"))
    priority = str(r.get("priority_level","")).upper()
    score = float(r.get("priority_score",0) or 0)
    ever_astar = b(r.get("ever_astar",False))
    years_present = int(r.get("years_present",0) or 0)
    req_years = int(r.get("active_article_years_required",0) or 0)
    astar_years = int(r.get("astar_years",0) or 0)

    if venue in TIER3_SEED:
        return "TIER3", "venue en lista curada de baja prioridad o fuera de alcance"
    if venue in TIER1_SEED and (ever_astar or years_present >= 2 or req_years >= 8):
        return "TIER1", "venue central de informática en lista curada Tier 1"
    if venue in TIER2_SEED:
        return "TIER2", "venue relevante pero fronterizo/interdisciplinar en lista curada Tier 2"

    if area in CENTRAL_AREAS:
        if ever_astar and req_years >= 5:
            return "TIER1", "área central + A* histórico + cobertura temporal suficiente"
        if priority == "HIGH" and score >= 18 and req_years >= 10:
            return "TIER1", "área central + alta prioridad previa + persistencia"
        if priority in {"HIGH","MEDIUM"}:
            return "TIER2", "área central pero evidencia insuficiente para inclusión automática"

    if area in ADJACENT_AREAS:
        if ever_astar and astar_years >= 2 and req_years >= 10 and score >= 20:
            return "TIER2", "área adyacente pero A* histórico persistente"
        if priority == "HIGH":
            return "TIER2", "alta prioridad previa pero área adyacente/sin clasificar"
        return "TIER3", "área adyacente, interdisciplinar o sin clasificar"

    if priority == "LOW":
        return "TIER3", "baja prioridad previa"
    return "TIER2", "evidencia mixta; revisión manual"

def action(tier):
    return {"TIER1":"Incluir en extracción DBLP prioritaria","TIER2":"Revisión manual antes de decidir extracción","TIER3":"Excluir del corpus principal salvo apéndice o cambio de alcance"}.get(tier,"Revisión manual")

def main():
    OUT.mkdir(exist_ok=True)
    if not INPUT.exists():
        msg = "SKIPPED: run 21_prioritize_historical_missing_venues.py first."
        (OUT / "historical_missing_venue_tiers_SKIPPED.txt").write_text(msg + "\n", encoding="utf-8")
        print(msg)
        raise SystemExit(0)

    df = pd.read_csv(INPUT)
    df["venue"] = df["venue"].map(norm)
    dec = df.apply(decide, axis=1, result_type="expand")
    df["tier"] = dec[0]
    df["tier_reason"] = dec[1]
    df["tier_action"] = df["tier"].map(action)

    if OVERRIDES.exists():
        ov = pd.read_csv(OVERRIDES)
        ov["venue"] = ov["venue"].map(norm)
        df = df.merge(ov, on="venue", how="left")
        if "tier_override" in df.columns:
            mask = df["tier_override"].notna() & df["tier_override"].astype(str).str.len().gt(0)
            df.loc[mask, "tier"] = df.loc[mask, "tier_override"].astype(str).str.upper()
            df.loc[mask, "tier_reason"] = "manual override"
            df.loc[mask, "tier_action"] = df.loc[mask, "tier"].map(action)
        if "area_override" in df.columns:
            mask = df["area_override"].notna() & df["area_override"].astype(str).str.len().gt(0)
            df.loc[mask, "inferred_area"] = df.loc[mask, "area_override"]

    order = {"TIER1":0,"TIER2":1,"TIER3":2}
    df["tier_sort"] = df["tier"].map(order).fillna(9)
    df = df.sort_values(["tier_sort","priority_score","venue"], ascending=[True,False,True])
    df.to_csv(OUT / "historical_missing_venue_tiers.csv", index=False)
    df[df["tier"].eq("TIER1")].to_csv(OUT / "historical_missing_venue_tier1_dblp_candidates.csv", index=False)

    review_cols = ["venue","tier","tier_reason","tier_action","priority_level","priority_score","inferred_area","ever_astar","years_present","active_article_years_required"]
    review_cols = [c for c in review_cols if c in df.columns]
    review = df[review_cols].copy()
    review["manual_include"] = ""
    review["manual_area"] = ""
    review["manual_dblp_key_or_booktitle"] = ""
    review["manual_notes"] = ""
    review.to_csv(OUT / "historical_missing_venue_manual_review.csv", index=False)

    summary = df.groupby(["tier","inferred_area"]).agg(
        venues=("venue","nunique"),
        ever_astar=("ever_astar","sum"),
        total_required_years=("active_article_years_required","sum"),
        mean_score=("priority_score","mean"),
    ).reset_index()
    summary.to_csv(OUT / "historical_missing_venue_tier_summary.csv", index=False)

    t1 = int((df["tier"]=="TIER1").sum())
    t2 = int((df["tier"]=="TIER2").sum())
    t3 = int((df["tier"]=="TIER3").sum())
    with open(OUT / "historical_missing_venue_tier_report.txt", "w", encoding="utf-8") as f:
        f.write("Historical missing CORE venues refined tiers\n")
        f.write("="*72 + "\n\n")
        f.write(f"TIER1 include: {t1}\nTIER2 review:  {t2}\nTIER3 exclude: {t3}\n\n")
        f.write("Top TIER1 candidates\n")
        f.write("-"*72 + "\n")
        for _, r in df[df["tier"].eq("TIER1")].head(100).iterrows():
            f.write(f"{r['venue']:20s} score={float(r.get('priority_score',0)):5.2f} area={r.get('inferred_area','')} | {r.get('tier_reason','')}\n")

    print("OK: refined historical venue tiers written to outputs_ext/")
    print(f"TIER1={t1}, TIER2={t2}, TIER3={t3}")

if __name__ == "__main__":
    main()
