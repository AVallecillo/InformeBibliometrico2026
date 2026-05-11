"""
PASO 3c — Auditoría del corpus DBLP extraído

Objetivo:
  Revisar la extracción DBLP del paso 3 antes de pasar a afiliaciones.
  Produce tablas de control por congreso, año y booktitle para detectar:
    - cobertura anual anómala,
    - congresos con pocos artículos,
    - booktitles inesperados,
    - posibles falsos positivos por filtros demasiado amplios,
    - registros duplicados por clave DBLP.

Entradas:
  outputs/conf_dblp_map.csv
  outputs/dblp_inproceedings.csv

Salidas:
  outputs/corpus_congress_audit.csv
  outputs/corpus_booktitle_audit.csv
  outputs/corpus_year_coverage.csv
  outputs/corpus_dblp_duplicates.csv
  outputs/corpus_audit_report.txt

Uso:
  python scripts/03c_audit_dblp_corpus.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"

YEAR_MIN, YEAR_MAX = 2001, 2025
EXPECTED_ASTAR = 62
EXPECTED_A = 108
EXPECTED_TOTAL = 170

# Umbrales conservadores. No detienen el pipeline; solo generan avisos.
# Se pueden ajustar tras revisar resultados reales.
LOW_TOTAL_THRESHOLD_ASTAR = 100
LOW_TOTAL_THRESHOLD_A = 25
LOW_YEAR_SPAN_THRESHOLD = 3

# Congresos cuyo comportamiento DBLP merece atención explícita.
SPECIAL_WATCHLIST = {
    "VLDB": "Incluye journals/pvldb/PVLDB; revisar que no se estén capturando artículos ajenos a actas VLDB.",
    "IJCAR": "Comparte históricamente parte del stream conf/cade; revisar routing CADE/IJCAR.",
    "CADE": "Comparte históricamente parte del stream conf/cade; revisar routing CADE/IJCAR.",
    "SIGSPATIAL": "Clave DBLP gis; revisar que no entren workshops tipo HealthGIS/MobiGIS.",
    "ITCS": "Debe usar conf/innovations, no conf/itcs.",
    "PETS": "Desde 2015 debe incluir journals/popets / PoPETs.",
    "APPROX/RANDOM": "DBLP puede separar APPROX y RANDOM; revisar booktitles capturados.",
}

# Patrones típicos de proceedings secundarios. Si aparecen, no siempre implican error,
# pero son buenos candidatos para inspección manual.
SECONDARY_BOOKTITLE_TOKENS = [
    "workshop", "workshops", "companion", "poster", "posters", "demo", "demos",
    "doctoral", "tutorial", "tutorials", "extended abstracts", "adjunct",
    "satellite", "challenge", "proceedings of the workshops", "symposium workshops",
]

REQUIRED_MAP_COLS = {"acronym", "title", "level", "area", "dblp_key"}
REQUIRED_DBLP_COLS = {
    "dblp_key", "congress", "level", "area", "year", "title", "doi", "arxiv_id", "authors", "booktitle"
}


def _fail(message: str) -> None:
    print(f"❌ {message}", file=sys.stderr)
    sys.exit(1)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    map_csv = OUTPUTS / "conf_dblp_map.csv"
    dblp_csv = OUTPUTS / "dblp_inproceedings.csv"

    if not map_csv.exists():
        _fail(f"No se encuentra {map_csv}. Ejecuta primero el paso 2.")
    if not dblp_csv.exists():
        _fail(f"No se encuentra {dblp_csv}. Ejecuta primero el paso 3.")

    conf_df = pd.read_csv(map_csv)
    missing_map = REQUIRED_MAP_COLS - set(conf_df.columns)
    if missing_map:
        _fail(f"Faltan columnas en conf_dblp_map.csv: {sorted(missing_map)}")

    n_astar = int((conf_df["level"] == "A*").sum())
    n_a = int((conf_df["level"] == "A").sum())
    if len(conf_df) != EXPECTED_TOTAL or n_astar != EXPECTED_ASTAR or n_a != EXPECTED_A:
        _fail(
            "conf_dblp_map.csv no parece ser el corpus oficial: "
            f"{n_astar} A* + {n_a} A = {len(conf_df)}"
        )

    df = pd.read_csv(dblp_csv)
    missing_dblp = REQUIRED_DBLP_COLS - set(df.columns)
    if missing_dblp:
        _fail(f"Faltan columnas en dblp_inproceedings.csv: {sorted(missing_dblp)}")

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    if df["year"].isna().any():
        bad = df[df["year"].isna()].head(5).to_dict("records")
        _fail(f"Hay años no numéricos en dblp_inproceedings.csv. Ejemplos: {bad}")

    outside_year = df[(df["year"] < YEAR_MIN) | (df["year"] > YEAR_MAX)]
    if not outside_year.empty:
        examples = outside_year[["congress", "year", "title"]].head(5).to_dict("records")
        _fail(f"Hay registros fuera de {YEAR_MIN}-{YEAR_MAX}. Ejemplos: {examples}")

    official = set(conf_df["acronym"])
    extracted = set(df["congress"])
    outside = sorted(extracted - official)
    if outside:
        _fail(f"El CSV extraído contiene congresos fuera del corpus oficial: {outside}")

    missing_confs = sorted(official - extracted)
    if missing_confs:
        _fail(f"Hay congresos oficiales sin artículos extraídos: {missing_confs}")

    return conf_df, df


def make_congress_audit(conf_df: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("congress", dropna=False)

    audit = grouped.agg(
        n_articles=("title", "size"),
        first_year=("year", "min"),
        last_year=("year", "max"),
        n_years=("year", "nunique"),
        n_booktitles=("booktitle", "nunique"),
        n_dblp_records=("dblp_key", "nunique"),
        n_with_doi=("doi", lambda s: s.fillna("").astype(str).str.strip().ne("").sum()),
        n_with_arxiv=("arxiv_id", lambda s: s.fillna("").astype(str).str.strip().ne("").sum()),
    ).reset_index()

    audit = conf_df[["acronym", "title", "level", "area", "dblp_key"]].merge(
        audit,
        left_on="acronym",
        right_on="congress",
        how="left",
    )

    audit.drop(columns=["congress"], inplace=True)
    audit["n_articles"] = audit["n_articles"].fillna(0).astype(int)
    audit["n_years"] = audit["n_years"].fillna(0).astype(int)
    audit["n_booktitles"] = audit["n_booktitles"].fillna(0).astype(int)
    audit["n_dblp_records"] = audit["n_dblp_records"].fillna(0).astype(int)
    audit["n_with_doi"] = audit["n_with_doi"].fillna(0).astype(int)
    audit["n_with_arxiv"] = audit["n_with_arxiv"].fillna(0).astype(int)

    audit["doi_coverage_pct"] = (audit["n_with_doi"] / audit["n_articles"].replace(0, pd.NA) * 100).round(2)
    audit["arxiv_coverage_pct"] = (audit["n_with_arxiv"] / audit["n_articles"].replace(0, pd.NA) * 100).round(2)

    def flags(row: pd.Series) -> str:
        out = []
        if row["n_articles"] == 0:
            out.append("ZERO_ARTICLES")
        elif row["level"] == "A*" and row["n_articles"] < LOW_TOTAL_THRESHOLD_ASTAR:
            out.append(f"LOW_TOTAL_ASTAR_LT_{LOW_TOTAL_THRESHOLD_ASTAR}")
        elif row["level"] == "A" and row["n_articles"] < LOW_TOTAL_THRESHOLD_A:
            out.append(f"LOW_TOTAL_A_LT_{LOW_TOTAL_THRESHOLD_A}")

        if row["n_years"] and row["n_years"] < LOW_YEAR_SPAN_THRESHOLD:
            out.append(f"LOW_YEAR_SPAN_LT_{LOW_YEAR_SPAN_THRESHOLD}")

        if row["acronym"] in SPECIAL_WATCHLIST:
            out.append("WATCHLIST")

        return ";".join(out)

    audit["flags"] = audit.apply(flags, axis=1)
    return audit.sort_values(["level", "area", "acronym"]).reset_index(drop=True)


def make_booktitle_audit(df: pd.DataFrame) -> pd.DataFrame:
    bt = df.copy()
    bt["booktitle"] = bt["booktitle"].fillna("").astype(str)
    bt["booktitle_norm"] = bt["booktitle"].str.casefold()

    audit = bt.groupby(["congress", "level", "area", "booktitle"], dropna=False).agg(
        n_articles=("title", "size"),
        first_year=("year", "min"),
        last_year=("year", "max"),
        n_years=("year", "nunique"),
    ).reset_index()

    def secondary_flag(booktitle: str) -> str:
        bt_norm = str(booktitle).casefold()
        hits = [tok for tok in SECONDARY_BOOKTITLE_TOKENS if tok in bt_norm]
        return ";".join(hits)

    audit["secondary_tokens"] = audit["booktitle"].apply(secondary_flag)
    audit["flag_secondary_candidate"] = audit["secondary_tokens"].astype(str).str.len() > 0
    return audit.sort_values(["flag_secondary_candidate", "congress", "n_articles"], ascending=[False, True, False])


def make_year_coverage(df: pd.DataFrame) -> pd.DataFrame:
    year_counts = df.groupby(["congress", "level", "area", "year"]).size().reset_index(name="n_articles")
    return year_counts.sort_values(["congress", "year"]).reset_index(drop=True)


def make_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    # En DBLP, el atributo key debería ser único. Si aparece repetido, puede indicar
    # duplicación accidental en el parseo o mezcla de entradas.
    dup_counts = df.groupby("dblp_key").size().reset_index(name="n")
    dup_keys = dup_counts[dup_counts["n"] > 1]["dblp_key"]
    if dup_keys.empty:
        return pd.DataFrame(columns=df.columns)
    return df[df["dblp_key"].isin(set(dup_keys))].sort_values(["dblp_key", "congress", "year"])


def write_report(
    conf_df: pd.DataFrame,
    df: pd.DataFrame,
    congress_audit: pd.DataFrame,
    booktitle_audit: pd.DataFrame,
    duplicates: pd.DataFrame,
) -> None:
    lines = []
    lines.append("=== AUDITORÍA DEL CORPUS DBLP EXTRAÍDO ===\n")
    lines.append(f"Rango temporal esperado: {YEAR_MIN}-{YEAR_MAX}")
    lines.append(f"Congresos oficiales: {len(conf_df)} ({EXPECTED_ASTAR} A* + {EXPECTED_A} A)")
    lines.append(f"Artículos extraídos: {len(df):,}")
    lines.append(f"Congresos con datos: {df['congress'].nunique()}")
    lines.append(f"Booktitles distintos: {df['booktitle'].nunique()}\n")

    by_level = congress_audit.groupby("level")["n_articles"].agg(["count", "sum", "min", "median", "max"]).reset_index()
    lines.append("=== RESUMEN POR NIVEL ===")
    for _, row in by_level.iterrows():
        lines.append(
            f"  {row['level']}: congresos={int(row['count'])}, artículos={int(row['sum']):,}, "
            f"min={int(row['min'])}, mediana={row['median']:.1f}, max={int(row['max'])}"
        )

    flagged = congress_audit[congress_audit["flags"].fillna("").astype(str).str.len() > 0]
    lines.append("\n=== CONGRESOS CON AVISOS ===")
    if flagged.empty:
        lines.append("  Ninguno")
    else:
        for _, row in flagged.sort_values(["level", "n_articles", "acronym"]).iterrows():
            note = SPECIAL_WATCHLIST.get(row["acronym"], "")
            lines.append(
                f"  {row['acronym']:16s} nivel={row['level']:2s} artículos={row['n_articles']:6,d} "
                f"años={row['first_year']}-{row['last_year']} n_years={row['n_years']:2d} flags={row['flags']}"
            )
            if note:
                lines.append(f"      Nota: {note}")

    secondary = booktitle_audit[booktitle_audit["flag_secondary_candidate"]]
    lines.append("\n=== BOOKTITLES CON TOKENS DE PROCEEDINGS SECUNDARIOS ===")
    if secondary.empty:
        lines.append("  Ninguno")
    else:
        lines.append("  Revisar manualmente. No todos son necesariamente errores.")
        for _, row in secondary.head(80).iterrows():
            lines.append(
                f"  {row['congress']:16s} n={row['n_articles']:5,d} años={int(row['first_year'])}-{int(row['last_year'])} "
                f"tokens={row['secondary_tokens']} | {row['booktitle']}"
            )
        if len(secondary) > 80:
            lines.append(f"  ... {len(secondary) - 80} booktitles adicionales en corpus_booktitle_audit.csv")

    lines.append("\n=== DUPLICADOS POR DBLP KEY ===")
    if duplicates.empty:
        lines.append("  Ninguno")
    else:
        lines.append(f"  Hay {duplicates['dblp_key'].nunique()} claves DBLP duplicadas; ver corpus_dblp_duplicates.csv")

    lines.append("\n=== TOP 20 CONGRESOS POR VOLUMEN ===")
    top20 = congress_audit.sort_values("n_articles", ascending=False).head(20)
    for _, row in top20.iterrows():
        lines.append(f"  {row['acronym']:16s} {row['level']:2s} {row['n_articles']:7,d} artículos")

    lines.append("\n=== BOTTOM 20 CONGRESOS POR VOLUMEN ===")
    bottom20 = congress_audit.sort_values("n_articles", ascending=True).head(20)
    for _, row in bottom20.iterrows():
        lines.append(f"  {row['acronym']:16s} {row['level']:2s} {row['n_articles']:7,d} artículos")

    (OUTPUTS / "corpus_audit_report.txt").write_text("\n".join(lines), encoding="utf-8")


def run() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    conf_df, df = load_inputs()

    congress_audit = make_congress_audit(conf_df, df)
    booktitle_audit = make_booktitle_audit(df)
    year_coverage = make_year_coverage(df)
    duplicates = make_duplicates(df)

    congress_audit.to_csv(OUTPUTS / "corpus_congress_audit.csv", index=False)
    booktitle_audit.to_csv(OUTPUTS / "corpus_booktitle_audit.csv", index=False)
    year_coverage.to_csv(OUTPUTS / "corpus_year_coverage.csv", index=False)
    duplicates.to_csv(OUTPUTS / "corpus_dblp_duplicates.csv", index=False)

    write_report(conf_df, df, congress_audit, booktitle_audit, duplicates)

    flagged = congress_audit[congress_audit["flags"].fillna("").astype(str).str.len() > 0]
    secondary = booktitle_audit[booktitle_audit["flag_secondary_candidate"]]

    print("=" * 60)
    print("PASO 3c — Auditoría del corpus DBLP extraído")
    print("=" * 60)
    print(f"  Artículos extraídos: {len(df):,}")
    print(f"  Congresos auditados: {len(congress_audit)}")
    print(f"  Congresos con avisos: {len(flagged)}")
    print(f"  Booktitles secundarios candidatos: {len(secondary)}")
    print(f"  DBLP keys duplicadas: {duplicates['dblp_key'].nunique() if not duplicates.empty else 0}")
    print("\n  Archivos generados:")
    print("    outputs/corpus_congress_audit.csv")
    print("    outputs/corpus_booktitle_audit.csv")
    print("    outputs/corpus_year_coverage.csv")
    print("    outputs/corpus_dblp_duplicates.csv")
    print("    outputs/corpus_audit_report.txt")


if __name__ == "__main__":
    run()
