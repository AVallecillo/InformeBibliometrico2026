"""
PASO 9 — Consolidar evidencias de afiliación en paper_country.csv

Combina las evidencias producidas por:
  - 05_resolve_affiliations_openalex_doi.py
  - 06_resolve_affiliations_openalex_venue.py
  - 07_resolve_affiliations_drops.py
  - 08_resolve_affiliations_crossref.py
  - 10_resolve_affiliations_openreview.py

y genera una tabla artículo-país deduplicada para conteo completo por país.

Entradas esperadas:
  outputs/paper_master.csv
  outputs/affiliation_evidence_openalex_doi.csv          (opcional)
  outputs/affiliation_evidence_openalex_venue.csv        (opcional)
  outputs/affiliation_evidence_drops.csv                 (opcional)
  outputs/affiliation_evidence_crossref.csv              (opcional)
  outputs/affiliation_evidence_openreview.csv            (opcional)
  outputs/affiliation_evidence_openreview_expanded.csv   (opcional)

Salidas:
  outputs/paper_country.csv
  outputs/paper_country_sources.csv
  outputs/paper_country_coverage_by_year.csv
  outputs/paper_country_coverage_by_window.csv
  outputs/paper_country_coverage_by_level.csv
  outputs/paper_country_coverage_by_area.csv
  outputs/paper_country_coverage_by_congress.csv
  outputs/paper_country_country_counts.csv
  outputs/paper_country_europe_summary.csv
  outputs/paper_country_unresolved.csv
  outputs/paper_country_report.txt
  checkpoints/step9_paper_country.json

Criterios:
  - Conteo completo por país: un artículo con autores de N países genera N filas.
  - Deduplicación por paper_id + country_code.
  - Conserva trazabilidad de fuentes en columna sources.
  - Artículo europeo = artículo con >=1 país en UE27 + Reino Unido.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step9_paper_country.json"

PAPER_MASTER = OUTPUTS / "paper_master.csv"

EVIDENCE_FILES = [
    ("openalex_doi", OUTPUTS / "affiliation_evidence_openalex_doi.csv"),
    ("openalex_venue", OUTPUTS / "affiliation_evidence_openalex_venue.csv"),
    ("drops", OUTPUTS / "affiliation_evidence_drops.csv"),
    ("crossref", OUTPUTS / "affiliation_evidence_crossref.csv"),
    ("openreview", OUTPUTS / "affiliation_evidence_openreview.csv"),
    ("openreview_expanded", OUTPUTS / "affiliation_evidence_openreview_expanded.csv"),
]

# ISO-3166 alpha-2. Nombre corto suficiente para informes y exportaciones.
COUNTRY_NAMES = {
    "AD": "Andorra", "AE": "United Arab Emirates", "AF": "Afghanistan", "AG": "Antigua and Barbuda",
    "AL": "Albania", "AM": "Armenia", "AO": "Angola", "AR": "Argentina", "AT": "Austria",
    "AU": "Australia", "AZ": "Azerbaijan", "BA": "Bosnia and Herzegovina", "BD": "Bangladesh",
    "BE": "Belgium", "BG": "Bulgaria", "BH": "Bahrain", "BI": "Burundi", "BJ": "Benin",
    "BR": "Brazil", "BS": "Bahamas", "BY": "Belarus", "CA": "Canada", "CH": "Switzerland",
    "CL": "Chile", "CM": "Cameroon", "CN": "China", "CO": "Colombia", "CR": "Costa Rica",
    "CU": "Cuba", "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany", "DK": "Denmark",
    "DZ": "Algeria", "EC": "Ecuador", "EE": "Estonia", "EG": "Egypt", "ES": "Spain",
    "ET": "Ethiopia", "FI": "Finland", "FR": "France", "GB": "United Kingdom", "GE": "Georgia",
    "GH": "Ghana", "GR": "Greece", "HK": "Hong Kong", "HR": "Croatia", "HU": "Hungary",
    "ID": "Indonesia", "IE": "Ireland", "IL": "Israel", "IN": "India", "IQ": "Iraq", "IR": "Iran",
    "IS": "Iceland", "IT": "Italy", "JO": "Jordan", "JP": "Japan", "KE": "Kenya", "KG": "Kyrgyzstan",
    "KH": "Cambodia", "KR": "South Korea", "KW": "Kuwait", "KZ": "Kazakhstan", "LB": "Lebanon",
    "LK": "Sri Lanka", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MA": "Morocco",
    "MD": "Moldova", "ME": "Montenegro", "MK": "North Macedonia", "MT": "Malta", "MU": "Mauritius", "MO": "Macao",
    "MX": "Mexico", "MY": "Malaysia", "NG": "Nigeria", "NL": "Netherlands", "NO": "Norway",
    "NP": "Nepal", "NZ": "New Zealand", "OM": "Oman", "PA": "Panama", "PE": "Peru", "PH": "Philippines",
    "PK": "Pakistan", "PL": "Poland", "PR": "Puerto Rico", "PT": "Portugal", "QA": "Qatar",
    "RO": "Romania", "RS": "Serbia", "RU": "Russia", "SA": "Saudi Arabia", "SE": "Sweden",
    "SG": "Singapore", "SI": "Slovenia", "SK": "Slovakia", "TH": "Thailand", "TN": "Tunisia",
    "TR": "Turkey", "TW": "Taiwan", "UA": "Ukraine", "UG": "Uganda", "US": "United States",
    "UY": "Uruguay", "VE": "Venezuela", "VN": "Vietnam", "ZA": "South Africa", "ZW": "Zimbabwe",
}

EU27 = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
}
EU27_PLUS_UK = EU27 | {"GB"}
EUROPE_EXTENDED = EU27_PLUS_UK | {"CH", "NO", "IS", "IL", "TR", "RS", "UA"}

SOURCE_PRIORITY = {
    "openalex_doi": 1,
    "openalex_venue": 2,
    "crossref": 3,
    "drops": 4,
    # por si más adelante añadimos fuentes nuevas
    "semantic_scholar": 5,
    "openreview": 6,
    "openreview_expanded": 7,
}


def _read_csv(path: Path, dtype: dict | None = None) -> pd.DataFrame:
    return pd.read_csv(path, dtype=dtype or {}, low_memory=False)


def _norm_country(value) -> str:
    if pd.isna(value):
        return ""
    s = str(value).strip().upper()
    if not s or s in {"NAN", "NONE", "NULL", "NA", "<NA>"}:
        return ""
    # Normalizar algunos alias comunes si aparecen.
    aliases = {"UK": "GB", "UNITED KINGDOM": "GB", "USA": "US", "UNITED STATES": "US"}
    return aliases.get(s, s)


def _clean_source(value, fallback: str) -> str:
    if pd.isna(value):
        return fallback
    s = str(value).strip()
    return s if s else fallback


def load_paper_master() -> pd.DataFrame:
    if not PAPER_MASTER.exists():
        raise FileNotFoundError(f"No se encuentra {PAPER_MASTER}. Ejecuta primero el paso 4.")

    papers = _read_csv(
        PAPER_MASTER,
        dtype={
            "paper_id": "string", "dblp_key": "string", "congress": "string", "level": "string",
            "area": "string", "window": "string", "title": "string", "doi": "string", "arxiv_id": "string",
            "booktitle": "string",
        },
    )
    required = {"paper_id", "dblp_key", "congress", "level", "area", "year", "window", "title"}
    missing = required - set(papers.columns)
    if missing:
        raise ValueError(f"Faltan columnas en paper_master.csv: {sorted(missing)}")

    papers["year"] = pd.to_numeric(papers["year"], errors="coerce").astype("Int64")
    if papers["paper_id"].duplicated().any():
        dup = papers.loc[papers["paper_id"].duplicated(), "paper_id"].head(10).tolist()
        raise ValueError(f"paper_id duplicados en paper_master.csv. Ejemplos: {dup}")
    return papers


def load_evidence() -> tuple[pd.DataFrame, list[dict]]:
    frames = []
    source_summary = []

    for label, path in EVIDENCE_FILES:
        if not path.exists():
            source_summary.append({"source_file": path.name, "source_label": label, "exists": False, "rows": 0, "papers": 0})
            continue
        df = _read_csv(path, dtype={"paper_id": "string", "dblp_key": "string", "country_code": "string"})
        if df.empty:
            source_summary.append({"source_file": path.name, "source_label": label, "exists": True, "rows": 0, "papers": 0})
            continue
        if "paper_id" not in df.columns or "country_code" not in df.columns:
            raise ValueError(f"{path.name} debe tener columnas paper_id y country_code")

        df = df.copy()
        df["country_code"] = df["country_code"].map(_norm_country)
        df = df[df["country_code"].str.fullmatch(r"[A-Z]{2}", na=False)]
        df["evidence_file"] = path.name
        if "source" not in df.columns:
            df["source"] = label
        else:
            df["source"] = df["source"].map(lambda x: _clean_source(x, label))
            # Estandarizar OpenAlex DOI/Venue usando el nombre de fichero para no perder el método.
            if label in {"openalex_doi", "openalex_venue"}:
                df["source"] = label

        if "method" not in df.columns:
            df["method"] = label
        if "confidence" not in df.columns:
            df["confidence"] = pd.NA
        if "matched_by" not in df.columns:
            df["matched_by"] = pd.NA
        if "source_work_id" not in df.columns:
            df["source_work_id"] = pd.NA

        frames.append(df)
        source_summary.append({
            "source_file": path.name,
            "source_label": label,
            "exists": True,
            "rows": int(len(df)),
            "papers": int(df["paper_id"].nunique()),
            "countries": int(df["country_code"].nunique()),
        })

    if not frames:
        raise FileNotFoundError("No se encontró ninguna tabla de evidencias de afiliación.")

    evidence = pd.concat(frames, ignore_index=True)
    evidence["source_priority"] = evidence["source"].map(SOURCE_PRIORITY).fillna(99).astype(int)
    return evidence, source_summary


def consolidate_evidence(papers: pd.DataFrame, evidence: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    valid_paper_ids = set(papers["paper_id"].astype(str))
    evidence = evidence[evidence["paper_id"].astype(str).isin(valid_paper_ids)].copy()

    if evidence.empty:
        raise ValueError("No quedan evidencias válidas tras cruzar con paper_master.csv")

    # Tabla de trazabilidad por paper-country-source-method.
    source_cols = [
        "paper_id", "country_code", "source", "method", "matched_by", "source_work_id",
        "confidence", "evidence_file", "source_priority",
    ]
    for col in source_cols:
        if col not in evidence.columns:
            evidence[col] = pd.NA

    trace = evidence[source_cols].drop_duplicates().copy()
    trace = trace.sort_values(["paper_id", "country_code", "source_priority", "source", "method"])

    def _join_unique(values: Iterable) -> str:
        out = []
        seen = set()
        for v in values:
            if pd.isna(v):
                continue
            s = str(v).strip()
            if not s or s in {"nan", "None", "<NA>"}:
                continue
            if s not in seen:
                seen.add(s)
                out.append(s)
        return "|".join(out)

    grouped = trace.groupby(["paper_id", "country_code"], as_index=False).agg(
        sources=("source", _join_unique),
        methods=("method", _join_unique),
        matched_by=("matched_by", _join_unique),
        source_work_ids=("source_work_id", _join_unique),
        evidence_files=("evidence_file", _join_unique),
        n_sources=("source", "nunique"),
        best_source_priority=("source_priority", "min"),
    )

    meta_cols = ["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "title", "doi", "booktitle"]
    meta_cols = [c for c in meta_cols if c in papers.columns]
    paper_country = grouped.merge(papers[meta_cols], on="paper_id", how="left")
    paper_country["country_name"] = paper_country["country_code"].map(COUNTRY_NAMES).fillna(paper_country["country_code"])
    paper_country["is_eu27"] = paper_country["country_code"].isin(EU27)
    paper_country["is_eu27_plus_uk"] = paper_country["country_code"].isin(EU27_PLUS_UK)
    paper_country["is_europe_extended"] = paper_country["country_code"].isin(EUROPE_EXTENDED)
    paper_country["is_spain"] = paper_country["country_code"].eq("ES")

    order = [
        "paper_id", "dblp_key", "congress", "level", "area", "year", "window", "country_code", "country_name",
        "is_spain", "is_eu27", "is_eu27_plus_uk", "is_europe_extended", "sources", "methods",
        "matched_by", "source_work_ids", "evidence_files", "n_sources", "title", "doi", "booktitle",
    ]
    order = [c for c in order if c in paper_country.columns]
    paper_country = paper_country[order].sort_values(["paper_id", "country_code"])

    return paper_country, trace


def build_coverage_tables(papers: pd.DataFrame, paper_country: pd.DataFrame) -> dict[str, pd.DataFrame]:
    resolved_papers = paper_country[["paper_id"]].drop_duplicates()
    papers_cov = papers.merge(resolved_papers.assign(has_country=True), on="paper_id", how="left")
    papers_cov["has_country"] = papers_cov["has_country"].fillna(False).astype(bool)

    def coverage(group_cols: list[str]) -> pd.DataFrame:
        g = papers_cov.groupby(group_cols, dropna=False).agg(
            total_papers=("paper_id", "count"),
            resolved_papers=("has_country", "sum"),
        ).reset_index()
        g["unresolved_papers"] = g["total_papers"] - g["resolved_papers"]
        g["coverage_pct"] = (g["resolved_papers"] / g["total_papers"] * 100).round(2)
        return g

    # Indicadores de España y Europa por artículo.
    flags = paper_country.groupby("paper_id").agg(
        has_ES=("is_spain", "max"),
        has_EU27=("is_eu27", "max"),
        has_EU27_UK=("is_eu27_plus_uk", "max"),
        has_Europe_Ext=("is_europe_extended", "max"),
        n_countries=("country_code", "nunique"),
    ).reset_index()
    flags = papers[["paper_id", "year", "window", "level", "area", "congress"]].merge(flags, on="paper_id", how="left")
    for col in ["has_ES", "has_EU27", "has_EU27_UK", "has_Europe_Ext"]:
        flags[col] = flags[col].fillna(False).astype(bool)
    flags["n_countries"] = flags["n_countries"].fillna(0).astype(int)

    europe_summary = flags.groupby(["window"], as_index=False).agg(
        total_papers=("paper_id", "count"),
        resolved_papers=("n_countries", lambda s: int((s > 0).sum())),
        papers_ES=("has_ES", "sum"),
        papers_EU27=("has_EU27", "sum"),
        papers_EU27_UK=("has_EU27_UK", "sum"),
        papers_Europe_Ext=("has_Europe_Ext", "sum"),
    )
    europe_summary["ES_share_world_resolved_pct"] = (
        europe_summary["papers_ES"] / europe_summary["resolved_papers"].replace(0, pd.NA) * 100
    ).round(3)
    europe_summary["ES_share_EU27_UK_pct"] = (
        europe_summary["papers_ES"] / europe_summary["papers_EU27_UK"].replace(0, pd.NA) * 100
    ).round(3)

    country_counts = paper_country.groupby(["country_code", "country_name"], as_index=False).agg(
        papers=("paper_id", "nunique"),
        evidence_rows=("paper_id", "count"),
    ).sort_values("papers", ascending=False)

    source_counts = paper_country.assign(source_split=paper_country["sources"].str.split("|")).explode("source_split")
    source_counts = source_counts.groupby("source_split", as_index=False).agg(
        paper_country_rows=("paper_id", "count"),
        papers=("paper_id", "nunique"),
    ).rename(columns={"source_split": "source"}).sort_values("paper_country_rows", ascending=False)

    unresolved = papers_cov[~papers_cov["has_country"]].copy()
    unresolved_cols = ["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "title", "doi", "booktitle"]
    unresolved_cols = [c for c in unresolved_cols if c in unresolved.columns]
    unresolved = unresolved[unresolved_cols].sort_values(["year", "congress", "paper_id"])

    return {
        "by_year": coverage(["year"]),
        "by_window": coverage(["window"]),
        "by_level": coverage(["level"]),
        "by_area": coverage(["area"]),
        "by_congress": coverage(["congress", "level", "area"]).sort_values(["coverage_pct", "total_papers"]),
        "country_counts": country_counts,
        "europe_summary": europe_summary,
        "source_counts": source_counts,
        "unresolved": unresolved,
        "paper_flags": flags,
    }


def write_report(
    papers: pd.DataFrame,
    paper_country: pd.DataFrame,
    trace: pd.DataFrame,
    source_summary: list[dict],
    tables: dict[str, pd.DataFrame],
) -> str:
    n_papers = len(papers)
    resolved = int(paper_country["paper_id"].nunique())
    unresolved = n_papers - resolved
    n_pc_rows = len(paper_country)
    n_countries = int(paper_country["country_code"].nunique()) if not paper_country.empty else 0

    flags = tables["paper_flags"]
    n_es = int(flags["has_ES"].sum())
    n_eu27uk = int(flags["has_EU27_UK"].sum())
    es_share_eu = (n_es / n_eu27uk * 100) if n_eu27uk else float("nan")

    lines = []
    lines.append("=== PASO 9 — CONSOLIDACIÓN PAPER-COUNTRY ===\n")
    lines.append(f"Artículos en paper_master: {n_papers:,}")
    lines.append(f"Artículos con >=1 país consolidado: {resolved:,}")
    lines.append(f"Artículos sin país consolidado: {unresolved:,}")
    lines.append(f"Cobertura acumulada: {resolved / n_papers * 100:.2f}%")
    lines.append(f"Filas paper-país: {n_pc_rows:,}")
    lines.append(f"Países distintos: {n_countries:,}")
    lines.append(f"Artículos con España: {n_es:,}")
    lines.append(f"Artículos UE27+Reino Unido: {n_eu27uk:,}")
    lines.append(f"Cuota España dentro de UE27+UK: {es_share_eu:.3f}%\n")

    lines.append("=== FUENTES DE EVIDENCIA DISPONIBLES ===")
    for s in source_summary:
        mark = "sí" if s.get("exists") else "no"
        lines.append(
            f"  {s['source_label']:16s} existe={mark:2s} filas={s.get('rows', 0):10,} papers={s.get('papers', 0):10,}"
        )
    lines.append("")

    lines.append("=== CONTRIBUCIÓN CONSOLIDADA POR FUENTE ===")
    for _, row in tables["source_counts"].iterrows():
        lines.append(f"  {row['source']:16s} paper-país={int(row['paper_country_rows']):10,} papers={int(row['papers']):10,}")
    lines.append("")

    lines.append("=== COBERTURA POR VENTANA ===")
    for _, row in tables["by_window"].sort_values("window").iterrows():
        lines.append(
            f"  {row['window']}: total={int(row['total_papers']):7,} resueltos={int(row['resolved_papers']):7,} "
            f"sin_pais={int(row['unresolved_papers']):7,} cobertura={row['coverage_pct']:.2f}%"
        )
    lines.append("")

    lines.append("=== COBERTURA POR NIVEL ===")
    for _, row in tables["by_level"].sort_values("level").iterrows():
        lines.append(
            f"  {row['level']}: total={int(row['total_papers']):7,} resueltos={int(row['resolved_papers']):7,} "
            f"sin_pais={int(row['unresolved_papers']):7,} cobertura={row['coverage_pct']:.2f}%"
        )
    lines.append("")

    lines.append("=== COBERTURA POR ÁREA ===")
    for _, row in tables["by_area"].sort_values("area").iterrows():
        lines.append(
            f"  {row['area']}: total={int(row['total_papers']):7,} resueltos={int(row['resolved_papers']):7,} "
            f"sin_pais={int(row['unresolved_papers']):7,} cobertura={row['coverage_pct']:.2f}%"
        )
    lines.append("")

    lines.append("=== TOP 30 PAÍSES POR ARTÍCULOS ===")
    for _, row in tables["country_counts"].head(30).iterrows():
        lines.append(f"  {row['country_code']}: {int(row['papers']):7,}  {row['country_name']}")
    lines.append("")

    lines.append("=== RESUMEN EUROPA/ESPAÑA POR VENTANA ===")
    for _, row in tables["europe_summary"].sort_values("window").iterrows():
        lines.append(
            f"  {row['window']}: ES={int(row['papers_ES']):5,} EU27+UK={int(row['papers_EU27_UK']):7,} "
            f"ES/EU27+UK={row['ES_share_EU27_UK_pct']:.3f}%"
        )
    lines.append("")

    lines.append("=== CONGRESOS CON MENOR COBERTURA (>=100 artículos) ===")
    low = tables["by_congress"]
    low = low[low["total_papers"] >= 100].sort_values(["coverage_pct", "total_papers"]).head(30)
    for _, row in low.iterrows():
        lines.append(
            f"  {row['congress']:18s} {row['level']:2s} {str(row['area'])[:22]:22s} "
            f"total={int(row['total_papers']):6,} resueltos={int(row['resolved_papers']):6,} cobertura={row['coverage_pct']:6.2f}%"
        )
    lines.append("")

    lines.append("=== SALIDAS GENERADAS ===")
    for name in [
        "paper_country.csv", "paper_country_sources.csv", "paper_country_coverage_by_year.csv",
        "paper_country_coverage_by_window.csv", "paper_country_coverage_by_level.csv",
        "paper_country_coverage_by_area.csv", "paper_country_coverage_by_congress.csv",
        "paper_country_country_counts.csv", "paper_country_europe_summary.csv",
        "paper_country_unresolved.csv", "paper_country_report.txt",
    ]:
        lines.append(f"  outputs/{name}")

    return "\n".join(lines)


def run(force: bool = False) -> None:
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭  Paso 9 ya completado (usa --force para repetir).")
        return

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    print("  Cargando paper_master...")
    papers = load_paper_master()
    print(f"  Artículos: {len(papers):,}")

    print("  Cargando evidencias...")
    evidence, source_summary = load_evidence()
    print(f"  Evidencias brutas válidas: {len(evidence):,}")

    print("  Consolidando paper_id + country_code...")
    paper_country, trace = consolidate_evidence(papers, evidence)
    print(f"  Filas paper-país: {len(paper_country):,}")
    print(f"  Papers con >=1 país: {paper_country['paper_id'].nunique():,}")

    print("  Construyendo tablas de cobertura...")
    tables = build_coverage_tables(papers, paper_country)

    paper_country.to_csv(OUTPUTS / "paper_country.csv", index=False)
    trace.to_csv(OUTPUTS / "paper_country_sources.csv", index=False)
    tables["by_year"].to_csv(OUTPUTS / "paper_country_coverage_by_year.csv", index=False)
    tables["by_window"].to_csv(OUTPUTS / "paper_country_coverage_by_window.csv", index=False)
    tables["by_level"].to_csv(OUTPUTS / "paper_country_coverage_by_level.csv", index=False)
    tables["by_area"].to_csv(OUTPUTS / "paper_country_coverage_by_area.csv", index=False)
    tables["by_congress"].to_csv(OUTPUTS / "paper_country_coverage_by_congress.csv", index=False)
    tables["country_counts"].to_csv(OUTPUTS / "paper_country_country_counts.csv", index=False)
    tables["europe_summary"].to_csv(OUTPUTS / "paper_country_europe_summary.csv", index=False)
    tables["unresolved"].to_csv(OUTPUTS / "paper_country_unresolved.csv", index=False)

    report = write_report(papers, paper_country, trace, source_summary, tables)
    (OUTPUTS / "paper_country_report.txt").write_text(report, encoding="utf-8")

    result = {
        "step": 9,
        "status": "COMPLETE",
        "total_papers": int(len(papers)),
        "resolved_papers": int(paper_country["paper_id"].nunique()),
        "unresolved_papers": int(len(papers) - paper_country["paper_id"].nunique()),
        "paper_country_rows": int(len(paper_country)),
        "n_countries": int(paper_country["country_code"].nunique()),
        "sources": source_summary,
    }
    CHECKPOINT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + report.split("\n\n")[0])
    print("\n  ✅ Paso 9 completado → outputs/paper_country.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Repetir aunque exista checkpoint")
    args = parser.parse_args()

    print("=" * 70)
    print("PASO 9 — Consolidación paper-country")
    print("=" * 70)
    try:
        run(force=args.force)
    except Exception as exc:
        print(f"❌ Error: {exc}")
        raise SystemExit(1)
