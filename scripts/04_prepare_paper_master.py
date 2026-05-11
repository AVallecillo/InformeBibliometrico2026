"""
PASO 4 — Crear tabla maestra de artículos DBLP

Entrada:
  outputs/dblp_inproceedings.csv   (generado por el paso 3)
  outputs/conf_dblp_map.csv        (170 congresos CORE/ICORE 2026 A*/A)

Salidas:
  outputs/paper_master.csv
  outputs/paper_master_summary.csv
  outputs/paper_counts_by_year.csv
  outputs/paper_counts_by_congress.csv
  outputs/paper_counts_by_congress_year.csv
  outputs/paper_counts_by_area.csv
  outputs/paper_counts_by_level.csv
  outputs/paper_counts_by_window.csv
  outputs/paper_counts_by_area_window.csv
  outputs/paper_counts_by_level_window.csv
  outputs/paper_master_report.txt
  checkpoints/step4.json

Objetivo:
  Construir una tabla estable de artículos con un identificador interno paper_id
  y producir denominadores base para el informe bibliométrico.

Uso:
  python scripts/04_prepare_paper_master.py --force
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step4.json"

YEAR_MIN = 2001
YEAR_MAX = 2025
EXPECTED_ASTAR = 62
EXPECTED_A = 108
EXPECTED_TOTAL_CONFERENCES = EXPECTED_ASTAR + EXPECTED_A
EXPECTED_WINDOWS = ["2001-2005", "2006-2010", "2011-2015", "2016-2020", "2021-2025"]

REQUIRED_DBLP_COLUMNS = {
    "dblp_key",
    "congress",
    "level",
    "area",
    "year",
    "title",
    "doi",
    "arxiv_id",
    "authors",
    "booktitle",
}

REQUIRED_MAP_COLUMNS = {
    "acronym",
    "title",
    "level",
    "area",
    "dblp_key",
}


def year_to_window(year: int) -> str:
    """Asigna cada año al quinquenio no solapado correspondiente."""
    if 2001 <= year <= 2005:
        return "2001-2005"
    if 2006 <= year <= 2010:
        return "2006-2010"
    if 2011 <= year <= 2015:
        return "2011-2015"
    if 2016 <= year <= 2020:
        return "2016-2020"
    if 2021 <= year <= 2025:
        return "2021-2025"
    raise ValueError(f"Año fuera del rango esperado {YEAR_MIN}-{YEAR_MAX}: {year}")


def load_official_map() -> pd.DataFrame:
    path = OUTPUTS / "conf_dblp_map.csv"
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra {path}. Ejecuta antes el paso 2.")

    df = pd.read_csv(path, dtype=str).fillna("")
    missing = sorted(REQUIRED_MAP_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en conf_dblp_map.csv: {missing}")

    df["acronym"] = df["acronym"].str.strip()
    df["level"] = df["level"].str.strip()
    df["area"] = df["area"].str.strip()
    df["dblp_key"] = df["dblp_key"].str.strip()

    n_astar = int((df["level"] == "A*").sum())
    n_a = int((df["level"] == "A").sum())
    if len(df) != EXPECTED_TOTAL_CONFERENCES or n_astar != EXPECTED_ASTAR or n_a != EXPECTED_A:
        raise ValueError(
            "conf_dblp_map.csv no coincide con el corpus oficial esperado: "
            f"esperado {EXPECTED_ASTAR} A* + {EXPECTED_A} A = {EXPECTED_TOTAL_CONFERENCES}; "
            f"encontrado {n_astar} A* + {n_a} A = {len(df)}."
        )

    duplicated_acronyms = sorted(df[df["acronym"].duplicated()]["acronym"].unique())
    if duplicated_acronyms:
        raise ValueError(f"Acrónimos duplicados en conf_dblp_map.csv: {duplicated_acronyms}")

    empty_keys = df[df["dblp_key"] == ""]["acronym"].tolist()
    if empty_keys:
        raise ValueError(f"Congresos sin dblp_key en conf_dblp_map.csv: {empty_keys}")

    return df


def load_dblp_articles() -> pd.DataFrame:
    path = OUTPUTS / "dblp_inproceedings.csv"
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra {path}. Ejecuta antes el paso 3.")

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = sorted(REQUIRED_DBLP_COLUMNS - set(df.columns))
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en dblp_inproceedings.csv: {missing}")

    # Normalización básica de campos textuales.
    for col in ["dblp_key", "congress", "level", "area", "title", "doi", "arxiv_id", "authors", "booktitle"]:
        df[col] = df[col].astype(str).str.strip()

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    if df["year"].isna().any():
        examples = df[df["year"].isna()][["dblp_key", "congress", "year"]].head(10).to_dict("records")
        raise ValueError(f"Hay registros con año no numérico. Ejemplos: {examples}")
    df["year"] = df["year"].astype(int)

    outside = df[(df["year"] < YEAR_MIN) | (df["year"] > YEAR_MAX)]
    if not outside.empty:
        examples = outside[["dblp_key", "congress", "year"]].head(10).to_dict("records")
        raise ValueError(
            f"Hay {len(outside)} registros fuera del rango {YEAR_MIN}-{YEAR_MAX}. Ejemplos: {examples}"
        )

    duplicated_keys = df[df["dblp_key"].duplicated(keep=False)]
    if not duplicated_keys.empty:
        examples = duplicated_keys[["dblp_key", "congress", "year", "title"]].head(20).to_dict("records")
        raise ValueError(
            f"Hay {duplicated_keys['dblp_key'].nunique()} dblp_key duplicadas en dblp_inproceedings.csv. "
            f"Ejemplos: {examples}"
        )

    return df


def validate_against_map(df_articles: pd.DataFrame, df_map: pd.DataFrame) -> None:
    official_acronyms = set(df_map["acronym"])
    article_acronyms = set(df_articles["congress"])

    outside = sorted(article_acronyms - official_acronyms)
    if outside:
        raise ValueError(f"dblp_inproceedings.csv contiene congresos fuera del corpus oficial: {outside}")

    missing = sorted(official_acronyms - article_acronyms)
    if missing:
        raise ValueError(f"Hay congresos oficiales sin artículos en dblp_inproceedings.csv: {missing}")

    official_meta = df_map.set_index("acronym")[["level", "area"]].to_dict("index")
    mismatches = []
    for row in df_articles[["congress", "level", "area"]].drop_duplicates().itertuples(index=False):
        expected = official_meta.get(row.congress)
        if not expected:
            continue
        if row.level != expected["level"] or row.area != expected["area"]:
            mismatches.append(
                {
                    "congress": row.congress,
                    "level_found": row.level,
                    "level_expected": expected["level"],
                    "area_found": row.area,
                    "area_expected": expected["area"],
                }
            )
    if mismatches:
        raise ValueError(f"Hay inconsistencias level/area frente al mapa oficial. Ejemplos: {mismatches[:20]}")


def build_paper_master(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Orden estable y reproducible.
    df = df.sort_values(
        by=["year", "congress", "dblp_key"],
        kind="mergesort",
    ).reset_index(drop=True)

    df.insert(0, "paper_id", [f"P{idx:07d}" for idx in range(1, len(df) + 1)])
    df["window"] = df["year"].apply(year_to_window)

    # Orden final de columnas. Conserva solo la tabla maestra estable y útil
    # para los siguientes pasos de afiliación y conteo país-artículo.
    columns = [
        "paper_id",
        "dblp_key",
        "congress",
        "level",
        "area",
        "year",
        "window",
        "title",
        "doi",
        "arxiv_id",
        "authors",
        "booktitle",
    ]
    return df[columns]


def _count(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    return (
        df.groupby(group_cols, dropna=False)
        .size()
        .reset_index(name="n_articles")
        .sort_values(group_cols, kind="mergesort")
        .reset_index(drop=True)
    )


def write_outputs(paper_master: pd.DataFrame, df_map: pd.DataFrame) -> dict:
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    paper_master.to_csv(OUTPUTS / "paper_master.csv", index=False)

    counts_by_year = _count(paper_master, ["year"])
    counts_by_congress = _count(paper_master, ["congress", "level", "area"])
    counts_by_congress_year = _count(paper_master, ["congress", "level", "area", "year"])
    counts_by_area = _count(paper_master, ["area"])
    counts_by_level = _count(paper_master, ["level"])
    counts_by_window = _count(paper_master, ["window"])
    counts_by_area_window = _count(paper_master, ["area", "window"])
    counts_by_level_window = _count(paper_master, ["level", "window"])

    counts_by_year.to_csv(OUTPUTS / "paper_counts_by_year.csv", index=False)
    counts_by_congress.to_csv(OUTPUTS / "paper_counts_by_congress.csv", index=False)
    counts_by_congress_year.to_csv(OUTPUTS / "paper_counts_by_congress_year.csv", index=False)
    counts_by_area.to_csv(OUTPUTS / "paper_counts_by_area.csv", index=False)
    counts_by_level.to_csv(OUTPUTS / "paper_counts_by_level.csv", index=False)
    counts_by_window.to_csv(OUTPUTS / "paper_counts_by_window.csv", index=False)
    counts_by_area_window.to_csv(OUTPUTS / "paper_counts_by_area_window.csv", index=False)
    counts_by_level_window.to_csv(OUTPUTS / "paper_counts_by_level_window.csv", index=False)

    # Summary compacto para trazabilidad del pipeline.
    summary_rows = [
        {"metric": "n_articles", "value": len(paper_master)},
        {"metric": "n_congresses_with_articles", "value": paper_master["congress"].nunique()},
        {"metric": "n_official_congresses", "value": len(df_map)},
        {"metric": "n_astar_congresses", "value": int((df_map["level"] == "A*").sum())},
        {"metric": "n_a_congresses", "value": int((df_map["level"] == "A").sum())},
        {"metric": "year_min", "value": int(paper_master["year"].min())},
        {"metric": "year_max", "value": int(paper_master["year"].max())},
        {"metric": "n_windows", "value": paper_master["window"].nunique()},
        {"metric": "n_areas", "value": paper_master["area"].nunique()},
        {"metric": "n_booktitles", "value": paper_master["booktitle"].nunique()},
        {"metric": "n_with_doi", "value": int((paper_master["doi"] != "").sum())},
        {"metric": "n_with_arxiv_id", "value": int((paper_master["arxiv_id"] != "").sum())},
    ]
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUTPUTS / "paper_master_summary.csv", index=False)

    report_lines = []
    report_lines.append("=== PASO 4 — TABLA MAESTRA DE ARTÍCULOS ===\n")
    report_lines.append(f"Rango temporal: {YEAR_MIN}-{YEAR_MAX}")
    report_lines.append(f"Artículos: {len(paper_master):,}")
    report_lines.append(f"Congresos con datos: {paper_master['congress'].nunique()} / {len(df_map)}")
    report_lines.append(f"Niveles: {dict(counts_by_level.set_index('level')['n_articles'])}")
    report_lines.append(f"Áreas: {paper_master['area'].nunique()}")
    report_lines.append(f"Booktitles distintos: {paper_master['booktitle'].nunique()}")
    report_lines.append(f"Con DOI: {int((paper_master['doi'] != '').sum()):,}")
    report_lines.append(f"Con ArXiv ID: {int((paper_master['arxiv_id'] != '').sum()):,}\n")

    report_lines.append("=== ARTÍCULOS POR VENTANA ===")
    for row in counts_by_window.itertuples(index=False):
        report_lines.append(f"  {row.window}: {row.n_articles:,}")

    report_lines.append("\n=== ARTÍCULOS POR NIVEL ===")
    for row in counts_by_level.itertuples(index=False):
        report_lines.append(f"  {row.level}: {row.n_articles:,}")

    report_lines.append("\n=== TOP 20 CONGRESOS POR VOLUMEN ===")
    top20 = counts_by_congress.sort_values("n_articles", ascending=False).head(20)
    for row in top20.itertuples(index=False):
        report_lines.append(f"  {row.congress:16s} {row.level:2s} {row.n_articles:8,}  {row.area}")

    report_lines.append("\n=== BOTTOM 20 CONGRESOS POR VOLUMEN ===")
    bottom20 = counts_by_congress.sort_values("n_articles", ascending=True).head(20)
    for row in bottom20.itertuples(index=False):
        report_lines.append(f"  {row.congress:16s} {row.level:2s} {row.n_articles:8,}  {row.area}")

    report_lines.append("\n=== SALIDAS GENERADAS ===")
    for name in [
        "paper_master.csv",
        "paper_master_summary.csv",
        "paper_counts_by_year.csv",
        "paper_counts_by_congress.csv",
        "paper_counts_by_congress_year.csv",
        "paper_counts_by_area.csv",
        "paper_counts_by_level.csv",
        "paper_counts_by_window.csv",
        "paper_counts_by_area_window.csv",
        "paper_counts_by_level_window.csv",
    ]:
        report_lines.append(f"  outputs/{name}")

    (OUTPUTS / "paper_master_report.txt").write_text("\n".join(report_lines), encoding="utf-8")

    return {
        "n_articles": len(paper_master),
        "n_congresses": int(paper_master["congress"].nunique()),
        "year_min": int(paper_master["year"].min()),
        "year_max": int(paper_master["year"].max()),
        "outputs": [
            "paper_master.csv",
            "paper_master_summary.csv",
            "paper_counts_by_year.csv",
            "paper_counts_by_congress.csv",
            "paper_counts_by_congress_year.csv",
            "paper_counts_by_area.csv",
            "paper_counts_by_level.csv",
            "paper_counts_by_window.csv",
            "paper_counts_by_area_window.csv",
            "paper_counts_by_level_window.csv",
            "paper_master_report.txt",
        ],
    }


def run(force: bool = False) -> None:
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭  Paso 4 ya completado (usa --force para repetir).")
        return

    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    print("  Cargando mapa oficial de congresos...")
    df_map = load_official_map()
    print(f"  Mapa oficial: {len(df_map)} congresos ({EXPECTED_ASTAR} A* + {EXPECTED_A} A)")

    print("  Cargando artículos DBLP extraídos...")
    df_articles = load_dblp_articles()
    print(f"  Artículos DBLP: {len(df_articles):,}")

    print("  Validando artículos contra el mapa oficial...")
    validate_against_map(df_articles, df_map)

    print("  Construyendo paper_master...")
    paper_master = build_paper_master(df_articles)

    print("  Generando tablas de control...")
    result = write_outputs(paper_master, df_map)

    checkpoint = {
        "step": 4,
        "status": "COMPLETE",
        **result,
    }
    CHECKPOINT_FILE.write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  ✅ paper_master.csv generado con {result['n_articles']:,} artículos")
    print("  ✅ Tablas de control generadas en outputs/")
    print("  ✅ Informe: outputs/paper_master_report.txt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Repetir aunque ya esté completado")
    args = parser.parse_args()

    print("=" * 60)
    print("PASO 4 — Crear tabla maestra de artículos")
    print("=" * 60)

    try:
        run(force=args.force)
    except Exception as exc:
        print(f"  ❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)
