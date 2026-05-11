#!/usr/bin/env python3
"""
PASO 5 — Resolución de afiliaciones por DOI con OpenAlex

Entrada:
  outputs/paper_master.csv

Salida principal:
  outputs/affiliation_evidence_openalex_doi.csv

Salidas auxiliares:
  outputs/openalex_doi_cache.json
  outputs/openalex_doi_coverage_report.txt
  outputs/openalex_doi_unresolved.csv
  checkpoints/step5_openalex_doi.json

Objetivo metodológico:
  Obtener países de afiliación a partir de OpenAlex para artículos con DOI,
  generando una tabla de evidencias trazable. La granularidad de salida es
  una fila por paper_id + country_code + source.

Notas:
  - No consolida países finales. Ese paso se hará después combinando fuentes.
  - No genera columnas has_ES/has_FR/etc.; evita el patrón de CSVs versionados.
  - La caché guarda respuestas por DOI normalizado para reanudación.

Uso:
  python scripts/05_resolve_affiliations_openalex_doi.py --api-key TU_OA_KEY --force
  python scripts/05_resolve_affiliations_openalex_doi.py --api-key TU_OA_KEY --limit 1000
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from tqdm import tqdm

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step5_openalex_doi.json"

PAPER_MASTER = OUTPUTS / "paper_master.csv"
EVIDENCE_CSV = OUTPUTS / "affiliation_evidence_openalex_doi.csv"
CACHE_FILE = OUTPUTS / "openalex_doi_cache.json"
UNRESOLVED_CSV = OUTPUTS / "openalex_doi_unresolved.csv"
REPORT_FILE = OUTPUTS / "openalex_doi_coverage_report.txt"

OPENALEX_BASE = "https://api.openalex.org"
BATCH_SIZE = 100            # OpenAlex list filter supports up to ~100 values cleanly
N_WORKERS_WITH_KEY = 8
N_WORKERS_NO_KEY = 2
RATE_LIMIT_WITH_KEY = 75.0  # conservative margin
RATE_LIMIT_NO_KEY = 5.0
MAX_RETRIES = 6
INITIAL_WAIT = 5
SAVE_EVERY_BATCHES = 50

EXPECTED_TOTAL = 535_144
YEAR_MIN, YEAR_MAX = 2001, 2025

_cache_lock = threading.Lock()
_rate_lock = threading.Lock()
_last_request_ts = 0.0


def normalize_doi(raw: Any) -> str:
    """Normalize DOI values from DBLP/OpenAlex/CrossRef forms."""
    if raw is None:
        return ""
    if isinstance(raw, float) and math.isnan(raw):
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    s = s.replace("https://doi.org/", "").replace("http://doi.org/", "")
    s = s.replace("doi:", "").replace("DOI:", "")
    return s.strip().strip(".").lower()


def openalex_headers(api_key: str | None) -> dict[str, str]:
    headers = {"User-Agent": "bibliometric-replication/1.0"}
    if api_key:
        # Works with the OpenAlex API-key setup used in the earlier pipeline.
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def rate_limit_sleep(rate_limit: float) -> None:
    """Global throttling across threads."""
    global _last_request_ts
    delay = 1.0 / max(rate_limit, 0.1)
    with _rate_lock:
        now = time.time()
        wait = _last_request_ts + delay - now
        if wait > 0:
            time.sleep(wait)
        _last_request_ts = time.time()


def load_cache() -> dict[str, dict[str, Any]]:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        # Backward compatible: old caches may map DOI directly to list[country]
        fixed: dict[str, dict[str, Any]] = {}
        for doi, value in data.items():
            if isinstance(value, dict):
                fixed[normalize_doi(doi)] = value
            else:
                fixed[normalize_doi(doi)] = {
                    "status": "ok" if value else "not_found_or_no_affiliation",
                    "openalex_id": "",
                    "countries": sorted(set(value or [])),
                    "raw_country_occurrences": value or [],
                }
        return fixed
    return {}


def save_cache(cache: dict[str, dict[str, Any]]) -> None:
    tmp = CACHE_FILE.with_suffix(".json.part")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    tmp.replace(CACHE_FILE)


def extract_work_countries(work: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Extract countries and lightweight institution evidence from an OpenAlex work.
    Returns:
      country_codes, institution_rows
    """
    countries: set[str] = set()
    inst_rows: list[dict[str, Any]] = []

    for author_position, authorship in enumerate(work.get("authorships", []) or [], start=1):
        author = authorship.get("author") or {}
        author_id = author.get("id", "") or ""
        author_name = author.get("display_name", "") or ""

        for inst in authorship.get("institutions", []) or []:
            cc = inst.get("country_code") or ""
            if not cc:
                continue
            cc = str(cc).strip().upper()
            if len(cc) != 2:
                continue
            countries.add(cc)
            inst_rows.append({
                "author_position": author_position,
                "author_id": author_id,
                "author_name": author_name,
                "institution_id": inst.get("id", "") or "",
                "institution_name": inst.get("display_name", "") or "",
                "country_code": cc,
            })

    return sorted(countries), inst_rows


def fetch_openalex_batch(
    dois: list[str],
    api_key: str | None,
    rate_limit: float,
    mailto: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch one DOI batch from OpenAlex. Returns cache records keyed by normalized DOI."""
    # OpenAlex filter value is pipe-separated. Use normalized DOI values.
    dois_norm = [normalize_doi(d) for d in dois if normalize_doi(d)]
    if not dois_norm:
        return {}

    filter_str = "|".join(dois_norm)
    params = {
        "filter": f"doi:{filter_str}",
        "select": "id,doi,authorships",
        "per-page": str(min(BATCH_SIZE, len(dois_norm))),
    }
    if mailto:
        params["mailto"] = mailto

    url = f"{OPENALEX_BASE}/works"
    wait = INITIAL_WAIT

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            rate_limit_sleep(rate_limit)
            r = requests.get(
                url,
                params=params,
                headers=openalex_headers(api_key),
                timeout=60,
            )
            if r.status_code in {429, 500, 502, 503, 504}:
                time.sleep(wait)
                wait = min(wait * 2, 180)
                continue
            r.raise_for_status()
            data = r.json()
            break
        except (requests.RequestException, ValueError):
            if attempt == MAX_RETRIES:
                return {
                    doi: {
                        "status": "request_failed",
                        "openalex_id": "",
                        "countries": [],
                        "raw_country_occurrences": [],
                        "institutions": [],
                    }
                    for doi in dois_norm
                }
            time.sleep(wait)
            wait = min(wait * 2, 180)
    else:
        return {}

    by_doi: dict[str, dict[str, Any]] = {}
    for work in data.get("results", []) or []:
        doi_raw = normalize_doi(work.get("doi", ""))
        if not doi_raw:
            continue
        countries, inst_rows = extract_work_countries(work)
        by_doi[doi_raw] = {
            "status": "ok" if countries else "found_no_affiliation_country",
            "openalex_id": work.get("id", "") or "",
            "countries": countries,
            "raw_country_occurrences": [r["country_code"] for r in inst_rows],
            "institutions": inst_rows,
        }

    # Cache explicit empty result for missing DOIs to avoid repeated calls.
    for doi in dois_norm:
        if doi not in by_doi:
            by_doi[doi] = {
                "status": "not_found",
                "openalex_id": "",
                "countries": [],
                "raw_country_occurrences": [],
                "institutions": [],
            }

    return by_doi


def validate_paper_master(df: pd.DataFrame) -> None:
    required = {
        "paper_id", "dblp_key", "congress", "level", "area", "year",
        "window", "title", "doi", "authors", "booktitle",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"paper_master.csv no tiene columnas obligatorias: {missing}")

    if df["paper_id"].duplicated().any():
        dup = df.loc[df["paper_id"].duplicated(), "paper_id"].head().tolist()
        raise ValueError(f"paper_id duplicados. Ejemplos: {dup}")
    if df["dblp_key"].duplicated().any():
        dup = df.loc[df["dblp_key"].duplicated(), "dblp_key"].head().tolist()
        raise ValueError(f"dblp_key duplicados. Ejemplos: {dup}")

    years = pd.to_numeric(df["year"], errors="coerce")
    if years.isna().any():
        raise ValueError("Hay años no numéricos en paper_master.csv")
    bad_years = df[(years < YEAR_MIN) | (years > YEAR_MAX)]
    if not bad_years.empty:
        raise ValueError(f"Hay {len(bad_years)} artículos fuera de {YEAR_MIN}-{YEAR_MAX}")

    levels = set(df["level"].astype(str).unique())
    if not levels <= {"A", "A*"}:
        raise ValueError(f"Niveles no oficiales detectados: {sorted(levels)}")


def write_evidence(df: pd.DataFrame, cache: dict[str, dict[str, Any]], limit: int | None = None) -> tuple[int, int, int]:
    """
    Write evidence rows from cache.
    Returns n_papers_with_country, n_evidence_rows, n_unique_paper_country.
    """
    fieldnames = [
        "paper_id", "dblp_key", "congress", "level", "area", "year", "window",
        "country_code", "source", "method", "confidence", "matched_by",
        "source_work_id", "doi", "n_institutions_for_country",
    ]

    df_work = df.head(limit).copy() if limit else df.copy()
    rows_seen: set[tuple[str, str]] = set()
    papers_with_country: set[str] = set()
    n_rows = 0

    with open(EVIDENCE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for rec in df_work.to_dict("records"):
            doi = normalize_doi(rec.get("doi"))
            if not doi:
                continue
            cache_rec = cache.get(doi, {})
            countries = sorted(set(cache_rec.get("countries", []) or []))
            if not countries:
                continue

            occurrences = Counter(cache_rec.get("raw_country_occurrences", []) or [])
            for cc in countries:
                key = (str(rec["paper_id"]), cc)
                if key in rows_seen:
                    continue
                rows_seen.add(key)
                papers_with_country.add(str(rec["paper_id"]))
                writer.writerow({
                    "paper_id": rec["paper_id"],
                    "dblp_key": rec["dblp_key"],
                    "congress": rec["congress"],
                    "level": rec["level"],
                    "area": rec["area"],
                    "year": int(rec["year"]),
                    "window": rec["window"],
                    "country_code": cc,
                    "source": "OpenAlex",
                    "method": "doi_batch",
                    "confidence": "high",
                    "matched_by": "doi",
                    "source_work_id": cache_rec.get("openalex_id", ""),
                    "doi": doi,
                    "n_institutions_for_country": int(occurrences.get(cc, 0)),
                })
                n_rows += 1

    return len(papers_with_country), n_rows, len(rows_seen)


def write_unresolved(df: pd.DataFrame, cache: dict[str, dict[str, Any]], limit: int | None = None) -> None:
    df_work = df.head(limit).copy() if limit else df.copy()
    fieldnames = [
        "paper_id", "dblp_key", "congress", "level", "area", "year", "window",
        "title", "doi", "status",
    ]
    with open(UNRESOLVED_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in df_work.to_dict("records"):
            doi = normalize_doi(rec.get("doi"))
            if not doi:
                status = "no_doi"
            else:
                status = cache.get(doi, {}).get("status", "not_queried")
            countries = cache.get(doi, {}).get("countries", []) if doi else []
            if countries:
                continue
            writer.writerow({
                "paper_id": rec["paper_id"],
                "dblp_key": rec["dblp_key"],
                "congress": rec["congress"],
                "level": rec["level"],
                "area": rec["area"],
                "year": int(rec["year"]),
                "window": rec["window"],
                "title": rec.get("title", ""),
                "doi": doi,
                "status": status,
            })


def write_report(
    df: pd.DataFrame,
    cache: dict[str, dict[str, Any]],
    n_papers_with_country: int,
    n_evidence_rows: int,
    limit: int | None = None,
) -> None:
    df_work = df.head(limit).copy() if limit else df.copy()
    df_work["doi_norm"] = df_work["doi"].apply(normalize_doi)
    df_work["has_doi"] = df_work["doi_norm"] != ""
    df_work["oa_status"] = df_work["doi_norm"].map(lambda d: cache.get(d, {}).get("status", "no_doi" if not d else "not_queried"))
    df_work["oa_has_country"] = df_work["doi_norm"].map(lambda d: bool(cache.get(d, {}).get("countries", [])) if d else False)

    lines: list[str] = []
    lines.append("=== PASO 5 — OPENALEX POR DOI ===\n")
    lines.append(f"Artículos considerados: {len(df_work):,}")
    lines.append(f"Con DOI: {int(df_work['has_doi'].sum()):,}")
    lines.append(f"Sin DOI: {int((~df_work['has_doi']).sum()):,}")
    lines.append(f"Artículos con ≥1 país vía OpenAlex DOI: {n_papers_with_country:,}")
    denom = max(int(df_work['has_doi'].sum()), 1)
    lines.append(f"Cobertura sobre artículos con DOI: {n_papers_with_country / denom * 100:.2f}%")
    lines.append(f"Cobertura sobre total considerado: {n_papers_with_country / max(len(df_work), 1) * 100:.2f}%")
    lines.append(f"Filas de evidencia paper-país: {n_evidence_rows:,}")
    lines.append("")

    lines.append("=== ESTADO OPENALEX ===")
    for status, n in df_work["oa_status"].value_counts(dropna=False).sort_index().items():
        lines.append(f"  {status}: {int(n):,}")
    lines.append("")

    lines.append("=== COBERTURA POR VENTANA ===")
    for window, grp in df_work.groupby("window", sort=True):
        total = len(grp)
        doi_n = int(grp["has_doi"].sum())
        cov = int(grp["oa_has_country"].sum())
        lines.append(f"  {window}: total={total:,} doi={doi_n:,} con_pais={cov:,} cobertura_total={cov/max(total,1)*100:.2f}%")
    lines.append("")

    lines.append("=== COBERTURA POR NIVEL ===")
    for level, grp in df_work.groupby("level", sort=True):
        total = len(grp)
        cov = int(grp["oa_has_country"].sum())
        lines.append(f"  {level}: total={total:,} con_pais={cov:,} cobertura={cov/max(total,1)*100:.2f}%")
    lines.append("")

    lines.append("=== COBERTURA POR ÁREA ===")
    for area, grp in df_work.groupby("area", sort=True):
        total = len(grp)
        cov = int(grp["oa_has_country"].sum())
        lines.append(f"  {area}: total={total:,} con_pais={cov:,} cobertura={cov/max(total,1)*100:.2f}%")
    lines.append("")

    # Country counts from evidence rows implied by cache
    country_counter: Counter[str] = Counter()
    for doi in df_work.loc[df_work["has_doi"], "doi_norm"]:
        for cc in set(cache.get(doi, {}).get("countries", []) or []):
            country_counter[cc] += 1
    lines.append("=== TOP 30 PAÍSES POR ARTÍCULOS RESUELTOS VIA DOI ===")
    for cc, n in country_counter.most_common(30):
        lines.append(f"  {cc}: {n:,}")

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def run(api_key: str | None, mailto: str | None, force: bool = False, limit: int | None = None) -> None:
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭  Paso 5 OpenAlex DOI ya completado (usa --force para repetir).")
        return

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    if not PAPER_MASTER.exists():
        raise FileNotFoundError(f"No se encuentra {PAPER_MASTER}. Ejecuta antes 04_prepare_paper_master.py")

    print(f"  Cargando {PAPER_MASTER.name}...")
    df = pd.read_csv(PAPER_MASTER, low_memory=False)
    validate_paper_master(df)
    if limit:
        print(f"  ⚠️  Modo test: limit={limit:,} artículos")
        df_proc = df.head(limit).copy()
    else:
        df_proc = df

    print(f"  Artículos en tabla maestra: {len(df):,}")
    if len(df) != EXPECTED_TOTAL and not limit:
        print(f"  ⚠️  Aviso: total esperado {EXPECTED_TOTAL:,}; encontrado {len(df):,}")

    df_proc["doi_norm"] = df_proc["doi"].apply(normalize_doi)
    dois = sorted({d for d in df_proc["doi_norm"] if d})
    print(f"  DOIs únicos a considerar: {len(dois):,}")

    cache = load_cache()
    before_cache = len(cache)
    pending = [d for d in dois if d not in cache]
    print(f"  Caché existente: {before_cache:,} DOI")
    print(f"  Pendientes OpenAlex: {len(pending):,}")

    if api_key:
        n_workers = N_WORKERS_WITH_KEY
        rate_limit = RATE_LIMIT_WITH_KEY
        print(f"  API key: sí | workers={n_workers} | rate_limit≈{rate_limit}/s")
    else:
        n_workers = N_WORKERS_NO_KEY
        rate_limit = RATE_LIMIT_NO_KEY
        print(f"  API key: no | workers={n_workers} | rate_limit≈{rate_limit}/s")

    batches = [pending[i:i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    print(f"  Batches a enviar: {len(batches):,} ({BATCH_SIZE} DOI/batch)")

    save_counter = 0
    if batches:
        with tqdm(total=len(pending), desc="  OpenAlex DOI", unit="doi") as pbar:
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = {
                    executor.submit(fetch_openalex_batch, batch, api_key, rate_limit, mailto): batch
                    for batch in batches
                }
                for future in as_completed(futures):
                    batch = futures[future]
                    try:
                        result = future.result()
                    except Exception:
                        result = {
                            doi: {
                                "status": "worker_exception",
                                "openalex_id": "",
                                "countries": [],
                                "raw_country_occurrences": [],
                                "institutions": [],
                            }
                            for doi in batch
                        }
                    with _cache_lock:
                        cache.update(result)
                    save_counter += 1
                    pbar.update(len(batch))
                    if save_counter >= SAVE_EVERY_BATCHES:
                        with _cache_lock:
                            save_cache(cache)
                        save_counter = 0

    save_cache(cache)
    print(f"  Caché guardada: {len(cache):,} DOI (+{len(cache) - before_cache:,})")

    print("  Escribiendo evidencias...")
    n_papers_with_country, n_evidence_rows, _ = write_evidence(df, cache, limit=limit)
    write_unresolved(df, cache, limit=limit)
    write_report(df, cache, n_papers_with_country, n_evidence_rows, limit=limit)

    result = {
        "step": "5_openalex_doi",
        "status": "COMPLETE",
        "input": str(PAPER_MASTER),
        "articles_total": int(len(df_proc)),
        "unique_dois": int(len(dois)),
        "cache_size": int(len(cache)),
        "papers_with_country": int(n_papers_with_country),
        "evidence_rows": int(n_evidence_rows),
        "evidence_csv": str(EVIDENCE_CSV),
        "unresolved_csv": str(UNRESOLVED_CSV),
        "report": str(REPORT_FILE),
    }
    CHECKPOINT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  ✅ Evidencias: {EVIDENCE_CSV}")
    print(f"  ✅ No resueltos: {UNRESOLVED_CSV}")
    print(f"  ✅ Informe: {REPORT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default=None, help="API key de OpenAlex")
    parser.add_argument("--mailto", default=None, help="Email para polite pool/metadatos OpenAlex")
    parser.add_argument("--force", action="store_true", help="Repetir aunque exista checkpoint")
    parser.add_argument("--limit", type=int, default=None, help="Procesar solo los primeros N artículos")
    args = parser.parse_args()

    print("=" * 70)
    print("PASO 5 — OpenAlex DOI → evidencias país")
    print("=" * 70)
    try:
        run(api_key=args.api_key, mailto=args.mailto, force=args.force, limit=args.limit)
    except Exception as exc:
        print(f"  ❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)
