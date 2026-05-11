"""
PASO 8 — Resolución de afiliaciones mediante CrossRef

Objetivo:
  Complementar las evidencias de países usando metadatos de CrossRef para
  artículos que siguen sin país tras OpenAlex DOI, OpenAlex venue y DROPS.

Entrada:
  outputs/paper_master.csv
  outputs/affiliation_evidence_openalex_doi.csv
  outputs/affiliation_evidence_openalex_venue.csv   (opcional)
  outputs/affiliation_evidence_drops.csv            (opcional)

Salida:
  outputs/affiliation_evidence_crossref.csv
  outputs/crossref_cache.json
  outputs/crossref_unresolved.csv
  outputs/crossref_coverage_report.txt
  checkpoints/step8_crossref.json

Uso:
  python scripts/08_resolve_affiliations_crossref.py --mailto tu@email.com --force
  python scripts/08_resolve_affiliations_crossref.py --mailto tu@email.com --limit 1000 --force

Notas metodológicas:
  - Se genera una fila por paper_id + country_code + source.
  - Solo se usa afiliación explícita o inferida desde texto de afiliación de autores.
  - CrossRef suele aportar más en artículos recientes y cuando el registrador incluye
    afiliaciones en los metadatos DOI. En muchos DOIs antiguos devuelve autores sin afiliación.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from tqdm import tqdm

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step8_crossref.json"

PAPER_MASTER = OUTPUTS / "paper_master.csv"
CACHE_FILE = OUTPUTS / "crossref_cache.json"
OUT_EVIDENCE = OUTPUTS / "affiliation_evidence_crossref.csv"
OUT_UNRESOLVED = OUTPUTS / "crossref_unresolved.csv"
OUT_REPORT = OUTPUTS / "crossref_coverage_report.txt"

CROSSREF_BASE = "https://api.crossref.org/works"
BATCH_SIZE = 100
N_WORKERS = 8
RATE_LIMIT = 35.0
MAX_RETRIES = 5
INITIAL_WAIT = 5
SAVE_EVERY_BATCHES = 200

EVIDENCE_FILES = [
    OUTPUTS / "affiliation_evidence_openalex_doi.csv",
    OUTPUTS / "affiliation_evidence_openalex_venue.csv",
    OUTPUTS / "affiliation_evidence_drops.csv",
]

_cache_lock = threading.Lock()

# ISO alpha-2 codes and names/patterns. This is intentionally broad; it is used
# only to parse affiliation strings returned by CrossRef.
COUNTRY_MAP = {
    "spain": "ES", "españa": "ES", "espana": "ES",
    "italy": "IT", "italia": "IT",
    "france": "FR", "francia": "FR",
    "germany": "DE", "deutschland": "DE", "alemania": "DE",
    "netherlands": "NL", "holland": "NL", "nederland": "NL", "the netherlands": "NL",
    "united kingdom": "GB", "uk": "GB", "u.k.": "GB", "england": "GB", "scotland": "GB", "wales": "GB", "great britain": "GB",
    "portugal": "PT",
    "united states": "US", "united states of america": "US", "usa": "US", "u.s.a.": "US", "u.s.": "US", "america": "US",
    "china": "CN", "people's republic of china": "CN", "pr china": "CN", "p.r. china": "CN",
    "japan": "JP", "canada": "CA", "australia": "AU", "india": "IN",
    "south korea": "KR", "republic of korea": "KR", "korea": "KR",
    "switzerland": "CH", "sweden": "SE", "denmark": "DK", "norway": "NO", "finland": "FI",
    "austria": "AT", "belgium": "BE", "poland": "PL", "czech republic": "CZ", "czechia": "CZ",
    "slovakia": "SK", "slovenia": "SI", "croatia": "HR", "serbia": "RS", "bulgaria": "BG",
    "romania": "RO", "hungary": "HU", "greece": "GR", "ireland": "IE", "iceland": "IS",
    "luxembourg": "LU", "malta": "MT", "cyprus": "CY", "estonia": "EE", "latvia": "LV", "lithuania": "LT",
    "israel": "IL", "singapore": "SG", "taiwan": "TW", "hong kong": "HK", "russia": "RU",
    "turkey": "TR", "brazil": "BR", "mexico": "MX", "chile": "CL", "argentina": "AR",
    "colombia": "CO", "peru": "PE", "uruguay": "UY", "egypt": "EG", "saudi arabia": "SA",
    "united arab emirates": "AE", "iran": "IR", "new zealand": "NZ", "south africa": "ZA",
    "malaysia": "MY", "thailand": "TH", "vietnam": "VN", "indonesia": "ID", "pakistan": "PK",
    # Institution patterns, used only when country text is absent.
    "eth zurich": "CH", "epfl": "CH", "inria": "FR", "cnrs": "FR", "sorbonne": "FR",
    "max planck": "DE", "rwth": "DE", "kit": "DE", "tum": "DE", "lmu munich": "DE",
    "csic": "ES", "upm": "ES", "uam": "ES", "upc": "ES", "upv": "ES", "ugr": "ES", "uc3m": "ES", "bsc": "ES",
    "imdea": "ES", "universitat politecnica de catalunya": "ES", "universidad politecnica de madrid": "ES",
    "technion": "IL", "weizmann": "IL", "tel aviv university": "IL",
    "nus": "SG", "national university of singapore": "SG", "ntu singapore": "SG",
    "kaist": "KR", "postech": "KR", "seoul national university": "KR",
    "tsinghua": "CN", "peking university": "CN", "pku": "CN", "zhejiang university": "CN",
    "iit ": "IN", "indian institute of technology": "IN", "iisc": "IN",
    "mit": "US", "stanford": "US", "berkeley": "US", "carnegie mellon": "US", "cmu": "US",
    "oxford": "GB", "cambridge": "GB", "imperial college": "GB", "ucl": "GB",
}
ISO2 = set(COUNTRY_MAP.values())


def is_missing(value: Any) -> bool:
    """True for None, pandas.NA/NaN/NaT, and empty strings."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def normalize_doi(doi: str | None) -> str:
    if is_missing(doi):
        return ""
    d = str(doi).strip()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d, flags=re.I)
    return d.strip().rstrip(".")


def infer_country(text: str | None) -> str | None:
    if is_missing(text):
        return None
    t = str(text).lower().strip()
    if not t:
        return None
    if len(t) == 2 and t.upper() in ISO2:
        return t.upper()
    # Split on common separators; country often appears at the end.
    tokens = [tok.strip(" .;:()[]{}") for tok in re.split(r"[,|/]", t) if tok.strip()]
    for tok in reversed(tokens):
        if tok in COUNTRY_MAP:
            return COUNTRY_MAP[tok]
    if t in COUNTRY_MAP:
        return COUNTRY_MAP[t]
    for pattern, iso in COUNTRY_MAP.items():
        if len(pattern) > 4 and pattern in t:
            return iso
    return None


def load_cache() -> dict[str, dict[str, Any]]:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict[str, dict[str, Any]]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(CACHE_FILE.suffix + ".part")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    # Windows/Dropbox tolerant replace.
    for i in range(8):
        try:
            tmp.replace(CACHE_FILE)
            return
        except PermissionError:
            time.sleep(0.5 * (i + 1))
    backup = CACHE_FILE.with_name(f"{CACHE_FILE.stem}.backup_{int(time.time())}.json")
    tmp.replace(backup)
    print(f"  ⚠️  No se pudo reemplazar {CACHE_FILE.name}; caché guardada como {backup.name}")


def headers(mailto: str) -> dict[str, str]:
    return {"User-Agent": f"bibliometric-replication/1.0 (mailto:{mailto})"}


def parse_crossref_item(item: dict[str, Any]) -> list[str]:
    countries: set[str] = set()
    for author in item.get("author", []) or []:
        affs = author.get("affiliation", []) or []
        if isinstance(affs, dict):
            affs = [affs]
        for aff in affs:
            if isinstance(aff, dict):
                name = aff.get("name", "")
            else:
                name = str(aff)
            cc = infer_country(name)
            if cc:
                countries.add(cc)
    return sorted(countries)


def fetch_batch(dois: list[str], mailto: str) -> dict[str, dict[str, Any]]:
    """Fetch a DOI batch from CrossRef. Returns DOI -> metadata dict."""
    # CrossRef filter=doi supports comma-separated filter values in practice, but
    # some responses are incomplete. Keep rows == len(dois) and map by DOI.
    filter_str = ",".join(f"doi:{d}" for d in dois)
    params = {"filter": filter_str, "rows": len(dois), "select": "DOI,author"}
    wait = INITIAL_WAIT

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(CROSSREF_BASE, params=params, headers=headers(mailto), timeout=45)
            if r.status_code == 429:
                time.sleep(wait)
                wait = min(wait * 2, 120)
                continue
            if r.status_code in (500, 502, 503, 504):
                time.sleep(wait)
                wait = min(wait * 2, 90)
                continue
            r.raise_for_status()
            if not r.text.strip():
                return {d: {"status": "not_found", "countries": []} for d in dois}
            data = r.json()
            break
        except (requests.RequestException, ValueError):
            if attempt == MAX_RETRIES - 1:
                return {d: {"status": "request_failed", "countries": []} for d in dois}
            time.sleep(wait)
            wait = min(wait * 2, 90)
    else:
        return {d: {"status": "request_failed", "countries": []} for d in dois}

    doi_map = {d.lower(): d for d in dois}
    out = {d: {"status": "not_found", "countries": []} for d in dois}
    for item in data.get("message", {}).get("items", []) or []:
        raw = normalize_doi(item.get("DOI", "")).lower()
        if raw not in doi_map:
            continue
        original = doi_map[raw]
        countries = parse_crossref_item(item)
        status = "ok" if countries else "found_no_affiliation_country"
        out[original] = {"status": status, "countries": countries}
    time.sleep(1.0 / RATE_LIMIT)
    return out


def batch_worker(batch: list[str], cache: dict[str, dict[str, Any]], mailto: str) -> dict[str, dict[str, Any]]:
    to_fetch = [d for d in batch if d not in cache]
    results = {d: cache[d] for d in batch if d in cache}
    if to_fetch:
        fetched = fetch_batch(to_fetch, mailto)
        with _cache_lock:
            cache.update(fetched)
        results.update(fetched)
    return results


def load_previous_resolved_paper_ids() -> set[str]:
    resolved: set[str] = set()
    for path in EVIDENCE_FILES:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, usecols=["paper_id"], dtype={"paper_id": "string"})
        except Exception:
            continue
        resolved.update(df["paper_id"].dropna().astype(str).unique())
    return resolved


def load_papers(limit: int | None = None) -> pd.DataFrame:
    if not PAPER_MASTER.exists():
        raise FileNotFoundError(f"No se encuentra {PAPER_MASTER}. Ejecuta antes el paso 4.")
    cols = ["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "title", "doi"]
    df = pd.read_csv(PAPER_MASTER, usecols=lambda c: c in cols, dtype={"paper_id": "string", "doi": "string"})
    missing = set(cols) - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en paper_master.csv: {sorted(missing)}")
    df["doi_norm"] = df["doi"].map(normalize_doi)
    if limit:
        df = df.head(limit).copy()
    return df


def write_outputs(target_df: pd.DataFrame, cache: dict[str, dict[str, Any]]) -> tuple[int, int, dict[str, int]]:
    evidence_rows: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    resolved_papers: set[str] = set()

    for row in target_df.itertuples(index=False):
        doi = row.doi_norm
        meta = cache.get(doi, {"status": "not_in_cache", "countries": []}) if doi else {"status": "no_doi", "countries": []}
        status = str(meta.get("status", "unknown"))
        countries = sorted(set(meta.get("countries", []) or []))
        status_counts[status] = status_counts.get(status, 0) + 1

        if countries:
            resolved_papers.add(str(row.paper_id))
            for cc in countries:
                evidence_rows.append({
                    "paper_id": row.paper_id,
                    "dblp_key": row.dblp_key,
                    "congress": row.congress,
                    "level": row.level,
                    "area": row.area,
                    "year": int(row.year),
                    "window": row.window,
                    "country_code": cc,
                    "source": "crossref",
                    "method": "doi_author_affiliation",
                    "confidence": 0.82,
                    "matched_by": "doi",
                    "source_work_id": f"doi:{doi}",
                    "doi": doi,
                    "n_institutions_for_country": "",
                })
        else:
            unresolved_rows.append({
                "paper_id": row.paper_id,
                "dblp_key": row.dblp_key,
                "congress": row.congress,
                "level": row.level,
                "area": row.area,
                "year": int(row.year),
                "window": row.window,
                "doi": doi,
                "status": status,
            })

    ev_cols = [
        "paper_id", "dblp_key", "congress", "level", "area", "year", "window",
        "country_code", "source", "method", "confidence", "matched_by",
        "source_work_id", "doi", "n_institutions_for_country",
    ]
    un_cols = ["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "doi", "status"]
    pd.DataFrame(evidence_rows, columns=ev_cols).to_csv(OUT_EVIDENCE, index=False)
    pd.DataFrame(unresolved_rows, columns=un_cols).to_csv(OUT_UNRESOLVED, index=False)
    return len(resolved_papers), len(evidence_rows), status_counts


def write_report(papers: pd.DataFrame, target_df: pd.DataFrame, resolved_ids: set[str], n_resolved: int, n_ev: int, status_counts: dict[str, int]) -> None:
    lines: list[str] = []
    lines.append("=== PASO 8 — CROSSREF DOI ===\n")
    lines.append(f"Artículos en paper_master: {len(papers):,}")
    lines.append(f"Artículos ya resueltos por fuentes previas: {len(resolved_ids):,}")
    lines.append(f"Artículos objetivo CrossRef sin país previo y con DOI: {len(target_df):,}")
    lines.append(f"Artículos con ≥1 país vía CrossRef: {n_resolved:,}")
    cov = n_resolved / len(target_df) * 100 if len(target_df) else 0
    lines.append(f"Cobertura sobre objetivo CrossRef: {cov:.2f}%")
    lines.append(f"Filas de evidencia paper-país: {n_ev:,}\n")

    lines.append("=== ESTADO CROSSREF ===")
    for k, v in sorted(status_counts.items()):
        lines.append(f"  {k}: {v:,}")

    if n_resolved:
        ev = pd.read_csv(OUT_EVIDENCE)
        lines.append("\n=== COBERTURA POR VENTANA ===")
        tmp = target_df.groupby("window").size().rename("objetivo").reset_index()
        res = ev.drop_duplicates("paper_id").groupby("window").size().rename("resueltos").reset_index()
        tmp = tmp.merge(res, on="window", how="left").fillna({"resueltos": 0})
        for r in tmp.itertuples(index=False):
            pct = r.resueltos / r.objetivo * 100 if r.objetivo else 0
            lines.append(f"  {r.window}: objetivo={int(r.objetivo):,} resueltos={int(r.resueltos):,} cobertura={pct:.2f}%")

        lines.append("\n=== COBERTURA POR ÁREA ===")
        tmp = target_df.groupby("area").size().rename("objetivo").reset_index()
        res = ev.drop_duplicates("paper_id").groupby("area").size().rename("resueltos").reset_index()
        tmp = tmp.merge(res, on="area", how="left").fillna({"resueltos": 0}).sort_values("area")
        for r in tmp.itertuples(index=False):
            pct = r.resueltos / r.objetivo * 100 if r.objetivo else 0
            lines.append(f"  {r.area}: objetivo={int(r.objetivo):,} resueltos={int(r.resueltos):,} cobertura={pct:.2f}%")

        lines.append("\n=== TOP 30 PAÍSES VIA CROSSREF ===")
        for cc, n in ev.groupby("country_code")["paper_id"].nunique().sort_values(ascending=False).head(30).items():
            lines.append(f"  {cc}: {int(n):,}")

        lines.append("\n=== TOP 30 CONGRESOS VIA CROSSREF ===")
        base = target_df.groupby("congress").size().rename("objetivo").reset_index()
        res = ev.drop_duplicates("paper_id").groupby("congress").size().rename("resueltos").reset_index()
        rank = base.merge(res, on="congress", how="left").fillna({"resueltos": 0})
        rank = rank[rank["resueltos"] > 0].sort_values("resueltos", ascending=False).head(30)
        for r in rank.itertuples(index=False):
            pct = r.resueltos / r.objetivo * 100 if r.objetivo else 0
            lines.append(f"  {r.congress:18s} resueltos={int(r.resueltos):7,d} objetivo={int(r.objetivo):7,d} cobertura={pct:.2f}%")

    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")


def run(mailto: str, force: bool = False, limit: int | None = None) -> None:
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭  Paso 8 ya completado (usa --force para repetir).")
        return
    if not mailto or "@" not in mailto:
        raise ValueError("Debes indicar --mailto con un email válido para el polite pool de CrossRef.")

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    papers = load_papers(limit=limit)
    resolved_ids = load_previous_resolved_paper_ids()
    doi_len = papers["doi_norm"].fillna("").astype(str).str.len()
    unresolved_mask = ~papers["paper_id"].astype(str).isin(resolved_ids)
    target = papers[unresolved_mask & (doi_len > 0)].copy()

    print(f"  Artículos en paper_master: {len(papers):,}")
    print(f"  Ya resueltos por evidencias previas: {len(resolved_ids):,}")
    print(f"  Objetivo CrossRef sin país previo y con DOI: {len(target):,}")

    cache = load_cache()
    n_cache_before = len(cache)
    dois = sorted(set(target["doi_norm"].dropna().astype(str)))
    pending = [d for d in dois if d not in cache]
    batches = [pending[i:i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    print(f"  DOIs únicos objetivo: {len(dois):,}")
    print(f"  En caché: {len(dois) - len(pending):,} | Pendientes: {len(pending):,}")
    print(f"  Batches CrossRef: {len(batches):,}\n")

    save_counter = 0
    if batches:
        with tqdm(total=len(batches), desc="  CrossRef DOI batches") as pbar:
            with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
                futures = {ex.submit(batch_worker, b, cache, mailto): b for b in batches}
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception:
                        pass
                    save_counter += 1
                    pbar.update(1)
                    if save_counter >= SAVE_EVERY_BATCHES:
                        with _cache_lock:
                            save_cache(cache)
                        save_counter = 0
    save_cache(cache)

    n_resolved, n_ev, status_counts = write_outputs(target, cache)
    write_report(papers, target, resolved_ids, n_resolved, n_ev, status_counts)

    result = {
        "step": 8,
        "status": "COMPLETE",
        "papers_total": int(len(papers)),
        "previously_resolved": int(len(resolved_ids)),
        "target_papers": int(len(target)),
        "target_unique_dois": int(len(dois)),
        "resolved_papers": int(n_resolved),
        "evidence_rows": int(n_ev),
        "cache_size": int(len(cache)),
        "cache_new": int(len(cache) - n_cache_before),
    }
    CHECKPOINT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n  Caché CrossRef: {len(cache):,} (+{len(cache) - n_cache_before:,})")
    print(f"  Artículos resueltos vía CrossRef: {n_resolved:,}")
    print(f"  Evidencias paper-país: {n_ev:,}")
    print(f"  ✅ Paso 8 completado → {OUT_EVIDENCE}")
    print(f"  Informe → {OUT_REPORT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mailto", required=True, help="Email para CrossRef polite pool")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Procesar solo los primeros N papers de paper_master para test")
    args = parser.parse_args()

    print("=" * 70)
    print("PASO 8 — CrossRef DOI → evidencias de país")
    print("=" * 70)
    try:
        run(mailto=args.mailto, force=args.force, limit=args.limit)
    except Exception as exc:
        print(f"❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)
