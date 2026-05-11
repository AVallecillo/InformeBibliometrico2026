"""
PASO 11 — Afiliaciones desde fuentes oficiales/PDFs selectivos

Objetivo: recuperar países para congresos con baja cobertura usando solo fuentes
oficiales o muy próximas a los proceedings: USENIX, NDSS y PMLR/JMLR.

Diseño conservador:
  - Procesa solo artículos que sigan sin país tras las evidencias existentes.
  - Usa enlaces DBLP (ee/url) cuando estén disponibles.
  - Solo descarga PDFs o páginas HTML desde dominios permitidos.
  - Extrae texto nativo de las primeras páginas del PDF; NO usa OCR.
  - Devuelve evidencias paper_id + country_code, nunca sobreescribe fuentes previas.

Entradas:
  outputs/paper_master.csv
  outputs/dblp_inproceedings.csv                      (opcional, para ee/url)
  outputs/affiliation_evidence_*.csv                  (opcional)

Salidas:
  outputs/affiliation_evidence_official_sources.csv
  outputs/official_sources_cache.json
  outputs/official_sources_pdf_audit.csv
  outputs/official_sources_unresolved.csv
  outputs/official_sources_coverage_report.txt
  checkpoints/step11_official_sources.json

Uso:
  python scripts/11_resolve_affiliations_official_sources.py --force
  python scripts/11_resolve_affiliations_official_sources.py --limit 500 --force
  python scripts/11_resolve_affiliations_official_sources.py --target-confs USENIX USENIX-Security NDSS AISTATS COLT UAI --force
"""

from __future__ import annotations

import argparse
import io
import json
import re
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse, urljoin

import pandas as pd
import requests
from tqdm import tqdm

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step11_official_sources.json"

PAPER_MASTER = OUTPUTS / "paper_master.csv"
DBLP_CSV = OUTPUTS / "dblp_inproceedings.csv"
CACHE_FILE = OUTPUTS / "official_sources_cache.json"
OUT_EVIDENCE = OUTPUTS / "affiliation_evidence_official_sources.csv"
OUT_AUDIT = OUTPUTS / "official_sources_pdf_audit.csv"
OUT_UNRESOLVED = OUTPUTS / "official_sources_unresolved.csv"
OUT_REPORT = OUTPUTS / "official_sources_coverage_report.txt"

EVIDENCE_FILES = [
    OUTPUTS / "affiliation_evidence_openalex_doi.csv",
    OUTPUTS / "affiliation_evidence_openalex_venue.csv",
    OUTPUTS / "affiliation_evidence_drops.csv",
    OUTPUTS / "affiliation_evidence_crossref.csv",
    OUTPUTS / "affiliation_evidence_openreview.csv",
    OUTPUTS / "affiliation_evidence_openreview_expanded.csv",
]

DEFAULT_TARGET_CONFS = {
    "USENIX", "USENIX-Security", "OSDI", "FAST", "HotOS",
    "NDSS",
    "AISTATS", "COLT", "UAI",
}

# Solo dominios oficiales o proceedings muy directos.
ALLOWED_DOMAINS = {
    "usenix.org", "www.usenix.org",
    "ndss-symposium.org", "www.ndss-symposium.org",
    "proceedings.mlr.press", "proceedings.mlr.press",
    "jmlr.org", "www.jmlr.org",
}

# Patrones país → ISO. Incluye nombres y variantes habituales en afiliaciones.
COUNTRY_PATTERNS = {
    "ES": [r"\bSpain\b", r"\bEspaña\b", r"\bEspana\b"],
    "US": [r"\bUnited States\b", r"\bUSA\b", r"\bU\.S\.A\.\b", r"\bUnited States of America\b"],
    "GB": [r"\bUnited Kingdom\b", r"\bUK\b", r"\bEngland\b", r"\bScotland\b", r"\bWales\b"],
    "DE": [r"\bGermany\b", r"\bDeutschland\b"],
    "FR": [r"\bFrance\b"],
    "IT": [r"\bItaly\b"],
    "NL": [r"\bNetherlands\b", r"\bThe Netherlands\b"],
    "PT": [r"\bPortugal\b"],
    "CN": [r"\bChina\b", r"\bP\.R\. China\b", r"\bPR China\b"],
    "JP": [r"\bJapan\b"],
    "CA": [r"\bCanada\b"],
    "AU": [r"\bAustralia\b"],
    "IN": [r"\bIndia\b"],
    "KR": [r"\bSouth Korea\b", r"\bRepublic of Korea\b", r"\bKorea\b"],
    "CH": [r"\bSwitzerland\b"],
    "SE": [r"\bSweden\b"],
    "DK": [r"\bDenmark\b"],
    "NO": [r"\bNorway\b"],
    "FI": [r"\bFinland\b"],
    "AT": [r"\bAustria\b"],
    "BE": [r"\bBelgium\b"],
    "PL": [r"\bPoland\b"],
    "CZ": [r"\bCzech Republic\b", r"\bCzechia\b"],
    "IL": [r"\bIsrael\b"],
    "SG": [r"\bSingapore\b"],
    "TW": [r"\bTaiwan\b"],
    "HK": [r"\bHong Kong\b"],
    "BR": [r"\bBrazil\b"],
    "MX": [r"\bMexico\b"],
    "GR": [r"\bGreece\b"],
    "IE": [r"\bIreland\b"],
    "RU": [r"\bRussia\b", r"\bRussian Federation\b"],
    "TR": [r"\bTurkey\b", r"\bTürkiye\b"],
    "AE": [r"\bUnited Arab Emirates\b", r"\bUAE\b"],
    "SA": [r"\bSaudi Arabia\b"],
    "NZ": [r"\bNew Zealand\b"],
    "CL": [r"\bChile\b"],
    "AR": [r"\bArgentina\b"],
}

# Instituciones conocidas como respaldo cuando no aparece el país explícito.
INSTITUTION_HINTS = {
    "ES": ["csic", "upm", "uam", "upc", "upv", "ugr", "uc3m", "bsc", "imdea", "universidad", "universitat"],
    "FR": ["inria", "cnrs", "sorbonne", "polytechnique"],
    "DE": ["max planck", "mpi", "rwth", "tum", "kit", "lmu"],
    "CH": ["eth zurich", "epfl"],
    "IL": ["technion", "weizmann", "hebrew university", "tel aviv university"],
    "SG": ["national university of singapore", "ntu singapore", "a*star"],
    "KR": ["kaist", "postech", "seoul national university"],
    "CN": ["tsinghua", "peking university", "zhejiang university", "fudan", "shanghai jiao tong"],
    "US": ["mit", "stanford", "berkeley", "carnegie mellon", "princeton", "cornell", "harvard"],
    "GB": ["oxford", "cambridge", "imperial college", "university college london", "edinburgh"],
    "CA": ["university of toronto", "waterloo", "mcgill", "ubc", "mila"],
}

HEADERS = {"User-Agent": "bibliometric-affiliation-audit/1.0"}
REQUEST_TIMEOUT = 30
RATE_SLEEP = 0.2
MAX_PDF_BYTES = 30 * 1024 * 1024


def load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    tmp = CACHE_FILE.with_suffix(CACHE_FILE.suffix + ".part")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    tmp.replace(CACHE_FILE)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def load_resolved_papers() -> set[str]:
    resolved: set[str] = set()
    for path in EVIDENCE_FILES:
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path, usecols=["paper_id"], dtype={"paper_id": "string"})
            resolved.update(df["paper_id"].dropna().astype(str).tolist())
        except Exception:
            continue
    return resolved


def merge_dblp_links(papers: pd.DataFrame) -> pd.DataFrame:
    if not DBLP_CSV.exists():
        papers["ee"] = ""
        papers["url"] = ""
        return papers
    dblp = read_csv(DBLP_CSV)
    cols = [c for c in ["dblp_key", "ee", "url"] if c in dblp.columns]
    if "dblp_key" not in cols:
        papers["ee"] = ""
        papers["url"] = ""
        return papers
    links = dblp[cols].copy()
    links["dblp_key"] = links["dblp_key"].astype(str)
    papers["dblp_key"] = papers["dblp_key"].astype(str)
    out = papers.merge(links, on="dblp_key", how="left")
    for c in ["ee", "url"]:
        if c not in out.columns:
            out[c] = ""
        out[c] = out[c].fillna("").astype(str)
    return out


def split_links(value: str) -> list[str]:
    if not value or value.lower() in {"nan", "none", "<na>"}:
        return []
    # DBLP a veces separa múltiples enlaces por | o espacios.
    parts = re.split(r"[|;\s]+", value.strip())
    return [p for p in parts if p.startswith("http")]


def domain_allowed(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return host in ALLOWED_DOMAINS or any(host.endswith("." + d) for d in ALLOWED_DOMAINS)


def candidate_urls(row: pd.Series) -> list[str]:
    urls: list[str] = []
    for col in ["ee", "url"]:
        urls.extend(split_links(str(row.get(col, ""))))
    # Derivar PDF de PMLR HTML si DBLP enlaza a la página del paper.
    derived = []
    for u in urls:
        if "proceedings.mlr.press" in u and u.endswith(".html"):
            derived.append(u[:-5] + ".pdf")
        if "jmlr.org" in u and u.endswith(".html"):
            derived.append(u[:-5] + ".pdf")
    urls.extend(derived)
    # Solo oficiales y sin duplicados.
    seen, clean = set(), []
    for u in urls:
        u = u.strip()
        if not u or u in seen or not domain_allowed(u):
            continue
        seen.add(u)
        clean.append(u)
    return clean


def http_get(url: str) -> tuple[int, bytes, str]:
    r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    time.sleep(RATE_SLEEP)
    ctype = r.headers.get("content-type", "")
    data = r.content[:MAX_PDF_BYTES + 1]
    return r.status_code, data, ctype


def find_pdf_from_html(base_url: str, html_bytes: bytes) -> str | None:
    html = html_bytes.decode("utf-8", errors="ignore")
    # Preferir enlaces .pdf, especialmente los que contengan el mismo slug.
    links = re.findall(r"href=[\'\"]([^\'\"]+\.pdf(?:\?[^\'\"]*)?)[\'\"]", html, flags=re.I)
    for href in links:
        pdf_url = urljoin(base_url, href)
        if domain_allowed(pdf_url):
            return pdf_url
    return None


def extract_pdf_text(pdf_bytes: bytes, max_pages: int = 2) -> str:
    # No OCR. Primero pypdf, luego PyPDF2 si está instalado.
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception as exc:
            raise RuntimeError("Falta pypdf o PyPDF2. Instala: pip install pypdf") from exc
    reader = PdfReader(io.BytesIO(pdf_bytes))
    texts = []
    for page in list(reader.pages)[:max_pages]:
        try:
            texts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(texts)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or " ").strip()


def infer_countries_from_text(text: str) -> list[str]:
    text_norm = normalize_text(text)
    countries = set()
    for cc, pats in COUNTRY_PATTERNS.items():
        for pat in pats:
            if re.search(pat, text_norm, flags=re.I):
                countries.add(cc)
                break
    low = text_norm.lower()
    for cc, hints in INSTITUTION_HINTS.items():
        if any(h in low for h in hints):
            countries.add(cc)
    return sorted(countries)


def process_article(row: pd.Series, cache: dict) -> dict:
    paper_id = str(row["paper_id"])
    if paper_id in cache:
        return cache[paper_id]

    urls = candidate_urls(row)
    audit = {
        "paper_id": paper_id,
        "dblp_key": str(row.get("dblp_key", "")),
        "congress": str(row.get("congress", "")),
        "year": int(row.get("year", 0)),
        "status": "no_official_url",
        "url": "",
        "pdf_url": "",
        "text_chars": 0,
        "countries": [],
        "error": "",
    }
    for url in urls:
        audit["url"] = url
        try:
            status, data, ctype = http_get(url)
            if status != 200:
                audit.update({"status": f"http_{status}"})
                continue
            if len(data) > MAX_PDF_BYTES:
                audit.update({"status": "pdf_too_large"})
                continue
            pdf_url = url
            if ("pdf" not in ctype.lower()) and not url.lower().split("?")[0].endswith(".pdf"):
                found = find_pdf_from_html(url, data)
                if not found:
                    audit.update({"status": "html_no_pdf"})
                    continue
                pdf_url = found
                status2, data2, ctype2 = http_get(pdf_url)
                if status2 != 200:
                    audit.update({"status": f"pdf_http_{status2}", "pdf_url": pdf_url})
                    continue
                data = data2
                ctype = ctype2
            audit["pdf_url"] = pdf_url
            text = extract_pdf_text(data, max_pages=2)
            audit["text_chars"] = len(text)
            if len(text.strip()) < 100:
                audit.update({"status": "no_pdf_text"})
                continue
            countries = infer_countries_from_text(text)
            audit["countries"] = countries
            audit["status"] = "ok" if countries else "no_country_detected"
            break
        except Exception as exc:
            audit.update({"status": "error", "error": str(exc)[:300]})
            continue

    cache[paper_id] = audit
    return audit


def build_report(papers: pd.DataFrame, evid: pd.DataFrame, audit: pd.DataFrame) -> str:
    n_targets = len(papers)
    n_resolved = evid["paper_id"].nunique() if not evid.empty else 0
    lines = [
        "=== PASO 11 — FUENTES OFICIALES/PDFs ===",
        "",
        f"Artículos objetivo sin país previo: {n_targets:,}",
        f"Artículos con >=1 país vía fuentes oficiales/PDF: {n_resolved:,}",
        f"Cobertura sobre objetivo: {n_resolved/max(n_targets,1)*100:.2f}%",
        f"Filas de evidencia paper-país: {len(evid):,}",
        f"PDFs/URLs auditados: {len(audit):,}",
        "",
        "=== ESTADO ===",
    ]
    if not audit.empty:
        for status, n in audit["status"].value_counts().head(30).items():
            lines.append(f"  {status}: {n:,}")
    if not evid.empty:
        lines += ["", "=== TOP PAÍSES VIA FUENTES OFICIALES/PDF ==="]
        for cc, n in evid.groupby("country_code")["paper_id"].nunique().sort_values(ascending=False).head(30).items():
            lines.append(f"  {cc}: {int(n):,}")
        lines += ["", "=== TOP CONGRESOS VIA FUENTES OFICIALES/PDF ==="]
        for conf, n in evid.groupby("congress")["paper_id"].nunique().sort_values(ascending=False).head(30).items():
            obj = int((papers["congress"] == conf).sum())
            lines.append(f"  {conf:18s} resueltos={int(n):6d} objetivo={obj:6d} cobertura={int(n)/max(obj,1)*100:5.2f}%")
    return "\n".join(lines) + "\n"


def run(force: bool = False, limit: int | None = None, target_confs: list[str] | None = None) -> None:
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭ Paso 11 ya completado (usa --force para repetir).")
        return
    if not PAPER_MASTER.exists():
        raise FileNotFoundError("No se encuentra outputs/paper_master.csv")

    CHECKPOINTS.mkdir(exist_ok=True)
    OUTPUTS.mkdir(exist_ok=True)

    papers = read_csv(PAPER_MASTER)
    papers["paper_id"] = papers["paper_id"].astype(str)
    resolved = load_resolved_papers()

    targets = set(target_confs) if target_confs else DEFAULT_TARGET_CONFS
    target_df = papers[(~papers["paper_id"].isin(resolved)) & (papers["congress"].isin(targets))].copy()
    target_df = merge_dblp_links(target_df)
    # Solo tiene sentido si hay al menos un enlace oficial candidate.
    target_df["n_candidate_urls"] = target_df.apply(lambda r: len(candidate_urls(r)), axis=1)
    target_df = target_df[target_df["n_candidate_urls"] > 0].copy()
    if limit:
        target_df = target_df.head(limit).copy()
        print(f"  ⚠️ Modo test: {limit} artículos")

    print("=" * 70)
    print("PASO 11 — Fuentes oficiales/PDFs")
    print("=" * 70)
    print(f"  Artículos objetivo con enlace oficial: {len(target_df):,}")
    print(f"  Congresos: {sorted(targets)}")

    cache = load_cache()
    audit_rows = []
    evidence_rows = []
    for _, row in tqdm(target_df.iterrows(), total=len(target_df), desc="  official PDFs"):
        item = process_article(row, cache)
        audit_rows.append({**item, "countries": "|".join(item.get("countries", []))})
        countries = item.get("countries") or []
        if countries:
            for cc in countries:
                evidence_rows.append({
                    "paper_id": row["paper_id"],
                    "dblp_key": row.get("dblp_key", ""),
                    "congress": row.get("congress", ""),
                    "level": row.get("level", ""),
                    "area": row.get("area", ""),
                    "year": row.get("year", ""),
                    "window": row.get("window", ""),
                    "country_code": cc,
                    "source": "official_sources",
                    "method": "official_pdf_first_pages",
                    "confidence": 0.72,
                    "matched_by": "official_url_pdf_text",
                    "source_work_id": item.get("pdf_url") or item.get("url"),
                    "doi": row.get("doi", ""),
                    "matched_title": row.get("title", ""),
                })
        if len(audit_rows) % 100 == 0:
            save_cache(cache)
    save_cache(cache)

    evid = pd.DataFrame(evidence_rows)
    audit = pd.DataFrame(audit_rows)
    if evid.empty:
        evid = pd.DataFrame(columns=["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "country_code", "source", "method", "confidence", "matched_by", "source_work_id", "doi", "matched_title"])
    evid.drop_duplicates(["paper_id", "country_code", "source"], inplace=True)
    evid.to_csv(OUT_EVIDENCE, index=False)
    audit.to_csv(OUT_AUDIT, index=False)

    unresolved = target_df[~target_df["paper_id"].isin(set(evid["paper_id"].astype(str)))].copy()
    unresolved.to_csv(OUT_UNRESOLVED, index=False)

    report = build_report(target_df, evid, audit)
    OUT_REPORT.write_text(report, encoding="utf-8")
    CHECKPOINT_FILE.write_text(json.dumps({"step": 11, "status": "COMPLETE", "n_evidence": len(evid), "n_resolved": evid["paper_id"].nunique() if not evid.empty else 0}, indent=2), encoding="utf-8")
    print("\n" + report)
    print(f"  ✅ Paso 11 completado → {OUT_EVIDENCE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--target-confs", nargs="*", default=None)
    args = parser.parse_args()
    try:
        run(force=args.force, limit=args.limit, target_confs=args.target_confs)
    except Exception as exc:
        print(f"❌ Error: {exc}")
        raise
