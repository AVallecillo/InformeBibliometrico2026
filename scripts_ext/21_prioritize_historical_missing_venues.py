"""
21_prioritize_historical_missing_venues.py

Prioritises historical CORE A*/A venues missing from the fixed 2026 corpus.
Run after 20_historical_mobile_corpus_gap.py.
"""

from pathlib import Path
import pandas as pd
import numpy as np
import re

OUT = Path("outputs_ext")
DATA = Path("data")
MISSING_PATH = OUT / "historical_core_missing_venues.csv"
REQ_PATH = OUT / "historical_mobile_corpus_requirements.csv"
CORE_PATH = DATA / "core_historical" / "core_historical.csv"
OVERRIDE_PATH = DATA / "external" / "historical_venue_review_overrides.csv"

HIGH_RELEVANCE = {
    "COLING","CoNLL","ECML","ALT","PAKDD","PKDD","EDBT","DEXA","ESWC","EKAW","FOIS","DBSEC",
    "CCGRID","CLUSTER","HiPC","EuroPar","EuroMPI","ECRTS","EMSOFT","CASES","ASAP","FCCM",
    "HOTCHIPS (HCS)","HOTNETS","EWSN","CONCUR","FOSSACS","FST&TCS","FCT","COCOON","FLOPS",
    "FM","ATVA","CPAIOR","ICLP","CC","ICIP","ICIAP","CAIP","EUROGRAPH","CGI","I3DG","DCC",
    "AOSD","CBSE","ECSA","ICECCS","Coordination","FORTE","CoopIS","ECSCW","Group","Hypertext","DocEng"
}
MEDIUM_RELEVANCE = {"AMCIS","ECIS","ICIS","HICSS","DESRIST","ICALT","CSCL","AMIA","AIME","CSB","CDC","ICARCV","CEC","FUZZ-IEEE","ICADL","ASIS&T","DIGRA","DUX"}
LOW_RELEVANCE_HINTS = {"APCOMin","Ada-Europe","AIIM","AID","AFIPS"}

AREA_RULES = [
    ("NLP", {"COLING","CoNLL"}),
    ("Machine Learning / Data Mining", {"ECML","ALT","PAKDD","PKDD","DSAA"}),
    ("Bases de datos / Web / Conocimiento", {"EDBT","DEXA","DOOD","FODO","ESWC","EKAW","FOIS","DBSEC","SSDBM"}),
    ("Sistemas / HPC / Arquitectura", {"CCGRID","CLUSTER","HiPC","EuroPar","EuroMPI","ASAP","FCCM","HOTCHIPS (HCS)","HOTNETS","GRID","MassPar","PPoPP","SPAA","ICPP","ICNP"}),
    ("Sistemas empotrados / Tiempo real", {"EMSOFT","CASES","ECRTS","EWSN","IPSN","SENSYS"}),
    ("Teoría / Métodos formales / PL", {"CONCUR","FOSSACS","FST&TCS","FCT","COCOON","FLOPS","FM","ATVA","CPAIOR","ICLP","CC","ISSAC","ISAAC","IPCO","RANDOM","TARK","LPAR","AiML"}),
    ("Visión / Imagen / Gráficos", {"ICIP","ICIAP","CAIP","EUROGRAPH","CGI","I3DG","DCC"}),
    ("Ingeniería del Software / Servicios", {"AOSD","CBSE","ECSA","ICECCS","Coordination","FORTE","CoopIS"}),
    ("HCI / CSCW / Documentos", {"ECSCW","Group","Hypertext","DocEng","UbiComp","PERVASIVE"}),
    ("Sistemas de información", {"AMCIS","ECIS","ICIS","HICSS","DESRIST"}),
    ("Educación / Learning technologies", {"ICALT","CSCL","ITiCSE","ITS"}),
    ("Bioinformática / Informática médica", {"AMIA","AIME","CSB"}),
    ("Control / Señal / Ingeniería", {"CDC","ICARCV","CEC","FUZZ-IEEE","IJCNN","ICONIP"}),
]

def norm(v):
    return "" if pd.isna(v) else re.sub(r"\s+", " ", str(v).strip())

def infer_area(v):
    v = norm(v)
    for area, venues in AREA_RULES:
        if v in venues:
            return area
    return "Sin clasificar"

def relevance_class(v):
    v = norm(v)
    if v in HIGH_RELEVANCE:
        return "high_seed"
    if v in MEDIUM_RELEVANCE:
        return "medium_seed"
    if v in LOW_RELEVANCE_HINTS:
        return "low_seed"
    area = infer_area(v)
    if area in {"NLP","Machine Learning / Data Mining","Bases de datos / Web / Conocimiento","Sistemas / HPC / Arquitectura","Sistemas empotrados / Tiempo real","Teoría / Métodos formales / PL","Visión / Imagen / Gráficos","Ingeniería del Software / Servicios","HCI / CSCW / Documentos"}:
        return "likely_core_cs"
    if area != "Sin clasificar":
        return "adjacent_or_interdisciplinary"
    return "unknown"

def rel_score(cls):
    return {"high_seed":5,"likely_core_cs":3,"medium_seed":2,"adjacent_or_interdisciplinary":1,"unknown":0,"low_seed":-1}.get(cls,0)

def main():
    OUT.mkdir(exist_ok=True)
    if not (MISSING_PATH.exists() and REQ_PATH.exists() and CORE_PATH.exists()):
        msg = "SKIPPED: run 20_historical_mobile_corpus_gap.py and build_core_historical.py first."
        (OUT / "historical_missing_venue_prioritization_SKIPPED.txt").write_text(msg + "\n", encoding="utf-8")
        print(msg)
        raise SystemExit(0)

    missing = pd.read_csv(MISSING_PATH)
    req = pd.read_csv(REQ_PATH)
    core = pd.read_csv(CORE_PATH)
    for df in [missing, req, core]:
        df["venue"] = df["venue"].map(norm)

    missing_venues = set(missing["venue"])
    req = req[req["venue"].isin(missing_venues)].copy()
    core = core[core["venue"].isin(missing_venues)].copy()

    hist = core.groupby("venue").agg(
        first_core_year=("core_year","min"),
        last_core_year=("core_year","max"),
        years_present=("core_year","nunique"),
        years_list=("core_year", lambda s: "|".join(map(str, sorted(set(s))))),
        levels_list=("level", lambda s: "|".join(sorted(set(map(str, s))))),
        astar_years=("level", lambda s: sum(str(x) == "A*" for x in s)),
        a_years=("level", lambda s: sum(str(x) == "A" for x in s)),
    ).reset_index()
    hist["ever_astar"] = hist["astar_years"] > 0

    if {"article_year_start","article_year_end"}.issubset(req.columns):
        req["required_years"] = (req["article_year_end"].astype(int) - req["article_year_start"].astype(int) + 1).clip(lower=0)
        req_agg = req.groupby("venue").agg(
            active_article_years_required=("required_years","sum"),
            first_article_year_required=("article_year_start","min"),
            last_article_year_required=("article_year_end","max"),
            required_core_years=("core_year", lambda s: "|".join(map(str, sorted(set(s))))),
            required_levels=("level", lambda s: "|".join(sorted(set(map(str, s))))),
        ).reset_index()
    else:
        req_agg = pd.DataFrame({"venue": list(missing_venues)})

    df = pd.DataFrame({"venue": sorted(missing_venues)}).merge(hist, on="venue", how="left").merge(req_agg, on="venue", how="left")
    for c in ["years_present","astar_years","a_years","active_article_years_required"]:
        df[c] = df[c].fillna(0).astype(int)
    df["ever_astar"] = df["ever_astar"].fillna(False)
    df["inferred_area"] = df["venue"].map(infer_area)
    df["relevance_class"] = df["venue"].map(relevance_class)

    df["priority_score"] = (
        np.where(df["ever_astar"], 5, 2)
        + df["years_present"].clip(upper=6)
        + df["astar_years"].clip(upper=4)
        + np.select([df["last_core_year"].fillna(0).astype(int)>=2020, df["last_core_year"].fillna(0).astype(int)>=2017, df["last_core_year"].fillna(0).astype(int)>=2013],[3,2,1], default=0)
        + np.where(df["first_core_year"].fillna(9999).astype(int)<=2008, 2, 0)
        + (df["active_article_years_required"]/5).clip(upper=4)
        + df["relevance_class"].map(rel_score)
    ).round(2)

    df["priority_level"] = np.select(
        [df["priority_score"] >= 15, df["priority_score"] >= 10],
        ["HIGH", "MEDIUM"],
        default="LOW",
    )
    df["recommended_action"] = np.select(
        [df["priority_level"].eq("HIGH"), df["priority_level"].eq("MEDIUM")],
        ["Extraer DBLP y resolver afiliaciones en fase prioritaria", "Revisión manual antes de extraer DBLP"],
        default="Probable exclusión o apéndice separado",
    )
    df["rationale"] = df.apply(lambda r: f"{'A* histórico' if r.ever_astar else 'solo A histórico'}; {r.years_present} versiones CORE; {r.active_article_years_required} años-artículo requeridos; relevancia={r.relevance_class}; área={r.inferred_area}", axis=1)

    if OVERRIDE_PATH.exists():
        ov = pd.read_csv(OVERRIDE_PATH)
        ov["venue"] = ov["venue"].map(norm)
        df = df.merge(ov, on="venue", how="left")
        if "priority_override" in df.columns:
            mask = df["priority_override"].notna() & df["priority_override"].astype(str).str.len().gt(0)
            df.loc[mask, "priority_level"] = df.loc[mask, "priority_override"].astype(str).str.upper()
        if "area_override" in df.columns:
            mask = df["area_override"].notna() & df["area_override"].astype(str).str.len().gt(0)
            df.loc[mask, "inferred_area"] = df.loc[mask, "area_override"]

    order = {"HIGH":0,"MEDIUM":1,"LOW":2}
    df["priority_sort"] = df["priority_level"].map(order).fillna(9)
    df = df.sort_values(["priority_sort","priority_score","venue"], ascending=[True,False,True])

    df.to_csv(OUT / "historical_missing_venue_prioritization.csv", index=False)
    df[df["priority_level"].isin(["HIGH","MEDIUM"])].to_csv(OUT / "historical_missing_venue_dblp_extraction_candidates.csv", index=False)

    summary = df.groupby(["priority_level","inferred_area"]).agg(
        venues=("venue","nunique"),
        ever_astar=("ever_astar","sum"),
        total_required_years=("active_article_years_required","sum"),
        mean_score=("priority_score","mean"),
    ).reset_index()
    summary.to_csv(OUT / "historical_missing_venue_priority_summary.csv", index=False)

    review = df[["venue","priority_level","priority_score","inferred_area","ever_astar","years_present","active_article_years_required","recommended_action"]].copy()
    review["manual_include"] = ""
    review["manual_area"] = ""
    review["manual_dblp_key_or_booktitle"] = ""
    review["manual_notes"] = ""
    review.to_csv(OUT / "historical_missing_venue_review_template.csv", index=False)

    high = int((df["priority_level"]=="HIGH").sum())
    med = int((df["priority_level"]=="MEDIUM").sum())
    low = int((df["priority_level"]=="LOW").sum())
    with open(OUT / "historical_missing_venue_prioritization_report.txt", "w", encoding="utf-8") as f:
        f.write("Historical missing CORE venues prioritization\n")
        f.write("="*72 + "\n\n")
        f.write(f"Total missing historical venues analysed: {df['venue'].nunique()}\n")
        f.write(f"HIGH priority:   {high}\n")
        f.write(f"MEDIUM priority: {med}\n")
        f.write(f"LOW priority:    {low}\n\n")
        f.write("Top HIGH-priority candidates\n")
        f.write("-"*72 + "\n")
        for _, r in df[df["priority_level"].eq("HIGH")].head(80).iterrows():
            f.write(f"{r['venue']:20s} score={r['priority_score']:5.2f} A*={str(bool(r['ever_astar'])):<5s} years={int(r['active_article_years_required']):2d} area={r['inferred_area']} | {r['recommended_action']}\n")

    print("OK: historical missing venue prioritization written to outputs_ext/")
    print(f"HIGH={high}, MEDIUM={med}, LOW={low}")

if __name__ == "__main__":
    main()
