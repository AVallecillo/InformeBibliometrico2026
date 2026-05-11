"""
PASO 12 — Semantic Scholar selectivo

Complementa la resolución de países para congresos con baja cobertura usando
Semantic Scholar, pero solo sobre artículos aún no resueltos y venues objetivo.

Estrategia:
  1) DOI batch: POST /paper/batch para artículos con DOI.
  2) Title search: GET /paper/search para artículos sin DOI o no resueltos por DOI.
  3) Validación estricta por título normalizado y año (+/-1).
  4) Extracción de países desde authors.affiliations.

Entradas:
  outputs/paper_master.csv
  outputs/affiliation_evidence_*.csv

Salidas:
  outputs/affiliation_evidence_semantic_scholar_selective.csv
  outputs/semantic_scholar_selective_cache.json
  outputs/semantic_scholar_selective_unresolved.csv
  outputs/semantic_scholar_selective_audit.csv
  outputs/semantic_scholar_selective_coverage_report.txt
  checkpoints/step12_semantic_scholar_selective.json

Uso:
  python scripts/12_resolve_affiliations_semantic_scholar_selective.py --api-key TU_S2_KEY --force
  python scripts/12_resolve_affiliations_semantic_scholar_selective.py --api-key TU_S2_KEY --only-doi --force
  python scripts/12_resolve_affiliations_semantic_scholar_selective.py --api-key TU_S2_KEY --limit 1000 --force
"""

from __future__ import annotations

import argparse
import json
import re
import time
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step12_semantic_scholar_selective.json"

PAPER_MASTER = OUTPUTS / "paper_master.csv"
CACHE_FILE = OUTPUTS / "semantic_scholar_selective_cache.json"
OUT_EVIDENCE = OUTPUTS / "affiliation_evidence_semantic_scholar_selective.csv"
OUT_AUDIT = OUTPUTS / "semantic_scholar_selective_audit.csv"
OUT_UNRESOLVED = OUTPUTS / "semantic_scholar_selective_unresolved.csv"
OUT_REPORT = OUTPUTS / "semantic_scholar_selective_coverage_report.txt"

EVIDENCE_FILES = [
    OUTPUTS / "affiliation_evidence_openalex_doi.csv",
    OUTPUTS / "affiliation_evidence_openalex_venue.csv",
    OUTPUTS / "affiliation_evidence_drops.csv",
    OUTPUTS / "affiliation_evidence_crossref.csv",
    OUTPUTS / "affiliation_evidence_openreview.csv",
    OUTPUTS / "affiliation_evidence_openreview_expanded.csv",
    OUTPUTS / "affiliation_evidence_official_sources.csv",
]

DEFAULT_TARGET_CONFS = {
    "AAMAS", "ICWSM", "BMVC", "Interspeech", "AISTATS",
    "NDSS", "USENIX", "USENIX-Security", "OSDI", "FAST",
    "ICAPS", "ICLR", "NeurIPS", "ICML", "COLT",
}

S2_BASE = "https://api.semanticscholar.org/graph/v1"
BATCH_SIZE = 500
RATE_LIMIT = 0.9  # req/s, conservador
DOI_WORKERS = 2
TITLE_WORKERS = 4
MAX_RETRIES = 5
INITIAL_WAIT = 5
SAVE_EVERY = 1000
TITLE_SAVE_EVERY = 1000
TITLE_THRESHOLD = 0.90

API_KEY = None
_rate_lock = threading.Lock()
_next_request_at = 0.0
_thread_local = threading.local()

COUNTRY_MAP = {
    "spain":"ES", "españa":"ES", "espana":"ES",
    "italy":"IT", "italia":"IT", "france":"FR", "germany":"DE", "deutschland":"DE",
    "netherlands":"NL", "the netherlands":"NL", "united kingdom":"GB", "uk":"GB", "england":"GB", "scotland":"GB",
    "portugal":"PT", "united states":"US", "usa":"US", "u.s.a.":"US", "u.s.":"US", "united states of america":"US",
    "china":"CN", "p.r. china":"CN", "pr china":"CN", "japan":"JP", "canada":"CA", "australia":"AU", "india":"IN",
    "south korea":"KR", "republic of korea":"KR", "korea":"KR", "switzerland":"CH", "sweden":"SE", "denmark":"DK",
    "norway":"NO", "finland":"FI", "austria":"AT", "belgium":"BE", "poland":"PL", "czech republic":"CZ", "czechia":"CZ",
    "israel":"IL", "singapore":"SG", "taiwan":"TW", "hong kong":"HK", "russia":"RU", "russian federation":"RU",
    "turkey":"TR", "türkiye":"TR", "greece":"GR", "hungary":"HU", "romania":"RO", "brazil":"BR", "mexico":"MX",
    "chile":"CL", "argentina":"AR", "ireland":"IE", "new zealand":"NZ", "united arab emirates":"AE", "uae":"AE", "saudi arabia":"SA",
    "luxembourg":"LU", "slovenia":"SI", "slovakia":"SK", "vietnam":"VN", "macao":"MO", "macau":"MO",
    # instituciones frecuentes
    "eth zurich":"CH", "epfl":"CH", "inria":"FR", "cnrs":"FR", "max planck":"DE", "mpi":"DE", "rwth":"DE", "tum":"DE",
    "csic":"ES", "upm":"ES", "uam":"ES", "upc":"ES", "upv":"ES", "ugr":"ES", "uc3m":"ES", "bsc":"ES", "imdea":"ES",
    "technion":"IL", "weizmann":"IL", "nus":"SG", "ntu singapore":"SG", "kaist":"KR", "postech":"KR",
    "tsinghua":"CN", "peking university":"CN", "zhejiang university":"CN", "fudan":"CN", "shanghai jiao tong":"CN",
    "mit":"US", "stanford":"US", "berkeley":"US", "carnegie mellon":"US", "princeton":"US", "cornell":"US",
    "oxford":"GB", "cambridge":"GB", "imperial college":"GB", "university college london":"GB",
    "waterloo":"CA", "university of toronto":"CA", "mcgill":"CA", "ubc":"CA", "mila":"CA",
}
ISO2 = set(COUNTRY_MAP.values())


def s2_headers() -> dict:
    h = {"User-Agent": "bibliometric-affiliation-audit/1.0"}
    if API_KEY:
        h["x-api-key"] = API_KEY
    return h


def get_session() -> requests.Session:
    """One session per worker thread for connection reuse."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(s2_headers())
        _thread_local.session = session
    return session


def rate_limit_wait(rate_limit: float) -> None:
    """Throttle request starts globally across workers."""
    global _next_request_at
    delay = 1.0 / max(rate_limit, 0.1)
    with _rate_lock:
        now = time.monotonic()
        wait = max(0.0, _next_request_at - now)
        _next_request_at = max(now, _next_request_at) + delay
    if wait > 0:
        time.sleep(wait)


def retry_delay(response: requests.Response | None, current_wait: float) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 180.0)
            except ValueError:
                pass
    return current_wait


def load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"doi": {}, "title": {}}


def save_cache(cache: dict) -> None:
    tmp = CACHE_FILE.with_suffix(CACHE_FILE.suffix + ".part")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    tmp.replace(CACHE_FILE)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def load_resolved_papers() -> set[str]:
    resolved = set()
    for p in EVIDENCE_FILES:
        if not p.exists():
            continue
        try:
            df = pd.read_csv(p, usecols=["paper_id"], dtype={"paper_id": "string"})
            resolved.update(df["paper_id"].dropna().astype(str).tolist())
        except Exception:
            pass
    return resolved


def normalize_doi(value) -> str:
    if value is None or pd.isna(value):
        return ""
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "<na>"}:
        return ""
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s, flags=re.I)
    return s.lower()


def normalize_title(t: str) -> str:
    if t is None or pd.isna(t):
        return ""
    t = str(t).lower().strip()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def title_similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    wa, wb = set(na.split()), set(nb.split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def infer_country(text) -> str | None:
    if text is None or pd.isna(text):
        return None
    t = str(text).lower().strip()
    if not t:
        return None
    if len(t) == 2 and t.upper() in ISO2:
        return t.upper()
    if t in COUNTRY_MAP:
        return COUNTRY_MAP[t]
    tokens = [x.strip(" .;,()[]") for x in re.split(r"[,;|]", t)]
    for tok in reversed(tokens):
        if tok in COUNTRY_MAP:
            return COUNTRY_MAP[tok]
    for pattern, iso in COUNTRY_MAP.items():
        if len(pattern) > 3 and pattern in t:
            return iso
    return None


def extract_countries(paper: dict | None) -> list[str]:
    if not paper:
        return []
    countries = set()
    for author in paper.get("authors") or []:
        if not isinstance(author, dict):
            continue
        affs = author.get("affiliations") or []
        if isinstance(affs, str):
            affs = [affs]
        if not isinstance(affs, list):
            continue
        for aff in affs:
            if isinstance(aff, dict):
                for key in ["country", "countryCode", "name"]:
                    cc = infer_country(aff.get(key))
                    if cc:
                        countries.add(cc)
                        break
            else:
                cc = infer_country(aff)
                if cc:
                    countries.add(cc)
    return sorted(countries)


def fetch_doi_batch(dois: list[str]) -> dict[str, dict]:
    url = f"{S2_BASE}/paper/batch"
    payload = {"ids": [f"DOI:{d}" for d in dois], "fields": "paperId,title,year,authors.affiliations,externalIds"}
    wait = INITIAL_WAIT
    for attempt in range(MAX_RETRIES):
        try:
            rate_limit_wait(RATE_LIMIT)
            r = get_session().post(url, json=payload, timeout=60)
            if r.status_code == 429:
                time.sleep(retry_delay(r, wait)); wait = min(wait * 2, 120); continue
            if r.status_code in {500, 503}:
                time.sleep(retry_delay(r, wait)); wait = min(wait * 2, 60); continue
            r.raise_for_status()
            data = r.json()
            return {doi: (paper or {}) for doi, paper in zip(dois, data)}
        except (requests.RequestException, ValueError):
            if attempt == MAX_RETRIES - 1:
                break
            time.sleep(wait); wait = min(wait * 2, 60)
    return {doi: {} for doi in dois}


def fetch_title(title: str, year: int) -> dict:
    url = f"{S2_BASE}/paper/search"
    params = {"query": title[:220], "fields": "paperId,title,year,authors.affiliations,externalIds", "limit": 5}
    wait = INITIAL_WAIT
    for attempt in range(MAX_RETRIES):
        try:
            rate_limit_wait(RATE_LIMIT)
            r = get_session().get(url, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(retry_delay(r, wait)); wait = min(wait * 2, 120); continue
            if r.status_code in {500, 503}:
                time.sleep(retry_delay(r, wait)); wait = min(wait * 2, 60); continue
            r.raise_for_status()
            data = r.json()
            best, best_sim = {}, 0.0
            for p in data.get("data", []) or []:
                py = p.get("year") or 0
                if year and py and abs(int(py) - int(year)) > 1:
                    continue
                sim = title_similarity(title, p.get("title") or "")
                if sim > best_sim:
                    best, best_sim = p, sim
            if best and best_sim >= TITLE_THRESHOLD:
                best["_title_similarity"] = best_sim
                return best
            return {"_title_similarity": best_sim}
        except (requests.RequestException, ValueError):
            if attempt == MAX_RETRIES - 1:
                break
            time.sleep(wait); wait = min(wait * 2, 60)
    return {}


def build_report(targets: pd.DataFrame, evid: pd.DataFrame, audit: pd.DataFrame) -> str:
    n_targets = len(targets)
    n_resolved = evid["paper_id"].nunique() if not evid.empty else 0
    lines = [
        "=== PASO 12 — SEMANTIC SCHOLAR SELECTIVO ===", "",
        f"Artículos objetivo sin país previo: {n_targets:,}",
        f"Artículos con >=1 país vía Semantic Scholar: {n_resolved:,}",
        f"Cobertura sobre objetivo: {n_resolved/max(n_targets,1)*100:.2f}%",
        f"Filas de evidencia paper-país: {len(evid):,}", "",
        "=== ESTADO ===",
    ]
    if not audit.empty:
        for status, n in audit["status"].value_counts().head(30).items():
            lines.append(f"  {status}: {n:,}")
    if not evid.empty:
        lines += ["", "=== TOP PAÍSES VIA SEMANTIC SCHOLAR ==="]
        for cc, n in evid.groupby("country_code")["paper_id"].nunique().sort_values(ascending=False).head(30).items():
            lines.append(f"  {cc}: {int(n):,}")
        lines += ["", "=== TOP CONGRESOS VIA SEMANTIC SCHOLAR ==="]
        for conf, n in evid.groupby("congress")["paper_id"].nunique().sort_values(ascending=False).head(30).items():
            obj = int((targets["congress"] == conf).sum())
            lines.append(f"  {conf:18s} resueltos={int(n):6d} objetivo={obj:6d} cobertura={int(n)/max(obj,1)*100:5.2f}%")
    return "\n".join(lines) + "\n"


def run(
    api_key: str | None = None,
    force: bool = False,
    limit: int | None = None,
    only_doi: bool = False,
    target_confs: list[str] | None = None,
    rate_limit: float | None = None,
    doi_workers: int = DOI_WORKERS,
    title_workers: int = TITLE_WORKERS,
    save_every: int = SAVE_EVERY,
) -> None:
    global API_KEY, RATE_LIMIT, _next_request_at
    API_KEY = api_key
    if rate_limit is not None:
        RATE_LIMIT = rate_limit
    doi_workers = max(1, int(doi_workers))
    title_workers = max(1, int(title_workers))
    save_every = max(1, int(save_every))
    _next_request_at = 0.0

    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭ Paso 12 ya completado (usa --force para repetir).")
        return
    if not PAPER_MASTER.exists():
        raise FileNotFoundError("No se encuentra outputs/paper_master.csv")
    CHECKPOINTS.mkdir(exist_ok=True)
    OUTPUTS.mkdir(exist_ok=True)

    paper_cols = ["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "title", "doi"]
    papers = pd.read_csv(PAPER_MASTER, usecols=lambda col: col in paper_cols, low_memory=False)
    papers["paper_id"] = papers["paper_id"].astype(str)
    papers["doi_norm"] = papers["doi"].apply(normalize_doi) if "doi" in papers.columns else ""
    resolved = load_resolved_papers()
    targets_set = set(target_confs) if target_confs else DEFAULT_TARGET_CONFS
    targets = papers[(~papers["paper_id"].isin(resolved)) & (papers["congress"].isin(targets_set))].copy()
    if limit:
        targets = targets.head(limit).copy()
        print(f"  ⚠️ Modo test: {limit} artículos")

    print("=" * 70)
    print("PASO 12 — Semantic Scholar selectivo")
    print("=" * 70)
    print(f"  Artículos objetivo: {len(targets):,}")
    print(f"  Con DOI: {(targets['doi_norm'].astype(str).str.len() > 0).sum():,}")
    print(f"  Congresos: {sorted(targets_set)}")
    print(f"  S2 rate_limit≈{RATE_LIMIT}/s | DOI workers={doi_workers} | title workers={title_workers} | save_every={save_every}")

    cache = load_cache()
    doi_cache = cache.setdefault("doi", {})
    title_cache = cache.setdefault("title", {})
    evidence_rows = []
    audit_rows = []

    # Fase 1: DOI batch.
    doi_targets = targets[targets["doi_norm"].astype(str).str.len() > 0].copy()
    pending_dois = [d for d in doi_targets["doi_norm"].dropna().astype(str).unique().tolist() if d not in doi_cache]
    batches = [pending_dois[i:i+BATCH_SIZE] for i in range(0, len(pending_dois), BATCH_SIZE)]
    if batches:
        print(f"  [Fase DOI] {len(pending_dois):,} DOIs → {len(batches):,} batches")
        fetched_since_save = 0
        with tqdm(total=len(pending_dois), desc="  DOI→S2", unit="doi") as pbar:
            with ThreadPoolExecutor(max_workers=doi_workers) as executor:
                futures = {executor.submit(fetch_doi_batch, batch): batch for batch in batches}
                for future in as_completed(futures):
                    batch = futures[future]
                    try:
                        res = future.result()
                    except Exception:
                        res = {doi: {} for doi in batch}
                    doi_cache.update(res)
                    fetched_since_save += len(batch)
                    pbar.update(len(batch))
                    if fetched_since_save >= save_every:
                        save_cache(cache)
                        fetched_since_save = 0
    save_cache(cache)

    unresolved_for_title = []
    for row in tqdm(targets.to_dict("records"), total=len(targets), desc="  parse DOI"):
        doi = row.get("doi_norm", "")
        paper = doi_cache.get(doi) if doi else None
        countries = extract_countries(paper)
        status = "no_doi" if not doi else "doi_no_country"
        method = "doi_batch"
        sim = ""
        if countries:
            status = "ok_doi"
        else:
            unresolved_for_title.append(row)
        audit_rows.append({"paper_id": row["paper_id"], "congress": row["congress"], "year": row["year"], "method": method, "status": status, "title_similarity": sim, "countries": "|".join(countries)})
        for cc in countries:
            evidence_rows.append({
                "paper_id": row["paper_id"], "dblp_key": row.get("dblp_key", ""), "congress": row.get("congress", ""), "level": row.get("level", ""),
                "area": row.get("area", ""), "year": row.get("year", ""), "window": row.get("window", ""), "country_code": cc,
                "source": "semantic_scholar", "method": "doi_batch", "confidence": 0.70, "matched_by": "doi", "source_work_id": (paper or {}).get("paperId", "") or doi,
                "doi": row.get("doi", ""), "matched_title": (paper or {}).get("title", ""),
            })

    # Fase 2: título solo para los que no resolvió DOI.
    if not only_doi:
        title_jobs: dict[str, tuple[str, int]] = {}
        for row in unresolved_for_title:
            title = str(row.get("title", ""))
            year = int(row.get("year", 0)) if not pd.isna(row.get("year", 0)) else 0
            title_key = normalize_title(title)
            key = title_key + f"|{year}"
            row["_s2_title_key"] = key
            if title_key and key not in title_cache and key not in title_jobs:
                title_jobs[key] = (title, year)

        print(f"  [Fase título] {len(unresolved_for_title):,} artículos | {len(title_jobs):,} búsquedas S2 pendientes")
        if title_jobs:
            fetched_since_save = 0
            with tqdm(total=len(title_jobs), desc="  title→S2", unit="query") as pbar:
                with ThreadPoolExecutor(max_workers=title_workers) as executor:
                    futures = {
                        executor.submit(fetch_title, title, year): key
                        for key, (title, year) in title_jobs.items()
                    }
                    for future in as_completed(futures):
                        key = futures[future]
                        try:
                            paper = future.result()
                        except Exception:
                            paper = {}
                        title_cache[key] = paper
                        fetched_since_save += 1
                        pbar.update(1)
                        if fetched_since_save >= save_every:
                            save_cache(cache)
                            fetched_since_save = 0

        for row in tqdm(unresolved_for_title, desc="  parse title"):
            key = row.get("_s2_title_key", "")
            paper = title_cache.get(key, {}) if key else {}
            countries = extract_countries(paper)
            sim = paper.get("_title_similarity", "") if isinstance(paper, dict) else ""
            status = "ok_title" if countries else "title_no_country_or_no_match"
            audit_rows.append({"paper_id": row["paper_id"], "congress": row["congress"], "year": row["year"], "method": "title_search", "status": status, "title_similarity": sim, "countries": "|".join(countries)})
            for cc in countries:
                evidence_rows.append({
                    "paper_id": row["paper_id"], "dblp_key": row.get("dblp_key", ""), "congress": row.get("congress", ""), "level": row.get("level", ""),
                    "area": row.get("area", ""), "year": row.get("year", ""), "window": row.get("window", ""), "country_code": cc,
                    "source": "semantic_scholar", "method": "title_search", "confidence": 0.58, "matched_by": "title_year", "source_work_id": paper.get("paperId", "") if isinstance(paper, dict) else "",
                    "doi": row.get("doi", ""), "matched_title": paper.get("title", "") if isinstance(paper, dict) else "",
                })
        save_cache(cache)

    evid = pd.DataFrame(evidence_rows)
    if evid.empty:
        evid = pd.DataFrame(columns=["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "country_code", "source", "method", "confidence", "matched_by", "source_work_id", "doi", "matched_title"])
    evid.drop_duplicates(["paper_id", "country_code", "source"], inplace=True)
    audit = pd.DataFrame(audit_rows)
    evid.to_csv(OUT_EVIDENCE, index=False)
    audit.to_csv(OUT_AUDIT, index=False)
    unresolved = targets[~targets["paper_id"].isin(set(evid["paper_id"].astype(str)))].copy()
    unresolved.to_csv(OUT_UNRESOLVED, index=False)
    report = build_report(targets, evid, audit)
    OUT_REPORT.write_text(report, encoding="utf-8")
    CHECKPOINT_FILE.write_text(json.dumps({"step": 12, "status": "COMPLETE", "n_evidence": len(evid), "n_resolved": evid["paper_id"].nunique() if not evid.empty else 0}, indent=2), encoding="utf-8")
    print("\n" + report)
    print(f"  ✅ Paso 12 completado → {OUT_EVIDENCE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only-doi", action="store_true")
    parser.add_argument("--target-confs", nargs="*", default=None)
    parser.add_argument("--rate-limit", type=float, default=None, help="Peticiones S2 por segundo; por defecto 0.9")
    parser.add_argument("--doi-workers", type=int, default=DOI_WORKERS)
    parser.add_argument("--title-workers", type=int, default=TITLE_WORKERS)
    parser.add_argument("--save-every", type=int, default=SAVE_EVERY, help="Guardar caché cada N consultas nuevas")
    args = parser.parse_args()
    try:
        run(
            api_key=args.api_key,
            force=args.force,
            limit=args.limit,
            only_doi=args.only_doi,
            target_confs=args.target_confs,
            rate_limit=args.rate_limit,
            doi_workers=args.doi_workers,
            title_workers=args.title_workers,
            save_every=args.save_every,
        )
    except Exception as exc:
        print(f"❌ Error: {exc}")
        raise
