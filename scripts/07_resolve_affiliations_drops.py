"""
PASO 7 — Afiliaciones desde DROPS/LIPIcs

Lee outputs/paper_master.csv y las evidencias ya generadas por pasos anteriores
(OpenAlex DOI / OpenAlex venue), identifica artículos aún sin país en congresos
cubiertos por DROPS/LIPIcs, descarga metadatos XML de volúmenes DROPS y cruza
por título para extraer países de afiliación.

Produce:
  outputs/affiliation_evidence_drops.csv
  outputs/drops_cache.json
  outputs/drops_unresolved.csv
  outputs/drops_coverage_report.txt
  checkpoints/step7_drops.json

Uso:
  python scripts/07_resolve_affiliations_drops.py --force
  python scripts/07_resolve_affiliations_drops.py --limit-volumes 10 --force

Notas metodológicas:
  - Granularidad de salida: paper_id + country_code + source.
  - Un artículo con afiliaciones en varios países produce varias filas.
  - Solo se procesan artículos sin evidencia previa de país.
  - El matching usa título normalizado, primero exacto y luego fuzzy acotado.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests
from tqdm import tqdm

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step7_drops.json"

PAPER_MASTER = OUTPUTS / "paper_master.csv"
OUT_EVIDENCE = OUTPUTS / "affiliation_evidence_drops.csv"
OUT_UNRESOLVED = OUTPUTS / "drops_unresolved.csv"
OUT_REPORT = OUTPUTS / "drops_coverage_report.txt"
CACHE_FILE = OUTPUTS / "drops_cache.json"

DROPS_BASE = "https://drops.dagstuhl.de"
YEAR_MIN, YEAR_MAX = 2001, 2025
RATE_LIMIT = 1.5  # req/s, conservative
MAX_RETRIES = 5
INITIAL_WAIT = 5
TITLE_SIM_THRESHOLD = 0.86
SAVE_EVERY = 20

# Congresos del corpus actual con cobertura probable en DROPS/LIPIcs.
# La lista se mantiene amplia pero el script solo procesa congresos presentes
# en paper_master y aún sin país.
DROPS_CONF_MAP: dict[str, list[str]] = {
    "ICALP": ["ICALP"],
    "STACS": ["STACS"],
    "ESA": ["ESA"],
    "SoCG": ["SoCG"],
    "DISC": ["DISC"],
    "ITCS": ["ITCS"],
    "CCC": ["CCC"],
    "GD": ["GD"],
    "COLT": ["COLT"],
    "EC": ["EC"],
    "SODA": ["SODA"],
    "FOCS": ["FOCS"],
    "STOC": ["STOC"],
    "PODC": ["PODC"],
    "LICS": ["LICS"],
    "TACAS": ["TACAS"],
    "CAV": ["CAV"],
    "ESOP": ["ESOP"],
    "ECOOP": ["ECOOP"],
    "CSF": ["CSF"],
    "KR": ["KR"],
    "CP": ["CP"],
    "SAT": ["SAT"],
    "ICDT": ["ICDT"],
    "PODS": ["PODS"],
    # Caso combinado en CORE/DBLP: DBLP usa APPROX/RANDOM, DROPS puede listar
    # APPROX y RANDOM por separado o en volúmenes conjuntos.
    "APPROX/RANDOM": ["APPROX", "RANDOM", "APPROX-RANDOM", "APPROX/RANDOM"],
    # Algunos años de IJCAR/CADE pueden aparecer en series LNCS, no DROPS;
    # se incluyen solo si DROPS publica metadatos disponibles.
    "IJCAR": ["IJCAR"],
    "CADE": ["CADE"],
    "ALENEX": ["ALENEX"],
}

COUNTRY_MAP = {
    # Países directos
    "spain": "ES", "españa": "ES", "espana": "ES",
    "italy": "IT", "italia": "IT",
    "france": "FR", "francia": "FR",
    "germany": "DE", "deutschland": "DE", "alemania": "DE",
    "netherlands": "NL", "holland": "NL", "nederland": "NL",
    "united kingdom": "GB", "uk": "GB", "england": "GB", "scotland": "GB", "great britain": "GB",
    "portugal": "PT",
    "united states": "US", "usa": "US", "u.s.a.": "US", "u.s.": "US",
    "china": "CN", "japan": "JP", "canada": "CA", "australia": "AU", "india": "IN",
    "south korea": "KR", "korea": "KR", "republic of korea": "KR",
    "switzerland": "CH", "sweden": "SE", "denmark": "DK", "norway": "NO", "finland": "FI",
    "austria": "AT", "belgium": "BE", "poland": "PL", "czech republic": "CZ", "czechia": "CZ",
    "israel": "IL", "singapore": "SG", "taiwan": "TW", "hong kong": "HK", "russia": "RU",
    "turkey": "TR", "brazil": "BR", "mexico": "MX", "greece": "GR", "hungary": "HU",
    "romania": "RO", "iran": "IR", "new zealand": "NZ", "south africa": "ZA", "chile": "CL",
    "argentina": "AR", "ireland": "IE", "luxembourg": "LU", "slovenia": "SI", "slovakia": "SK",
    "croatia": "HR", "estonia": "EE", "latvia": "LV", "lithuania": "LT",
    # Instituciones frecuentes
    "eth zurich": "CH", "eth zürich": "CH", "epfl": "CH",
    "weizmann": "IL", "technion": "IL", "tel aviv": "IL", "haifa": "IL",
    "inria": "FR", "cnrs": "FR", "irif": "FR", "ens paris": "FR", "ens lyon": "FR",
    "kit": "DE", "rwth": "DE", "max planck": "DE", "mpi": "DE", "tum": "DE", "tu berlin": "DE",
    "lmu munich": "DE", "saarland": "DE",
    "csic": "ES", "upm": "ES", "uam": "ES", "ugr": "ES", "upc": "ES", "upv": "ES",
    "universidad": "ES", "universitat": "ES", "bsc": "ES", "uc3m": "ES",
    "nus": "SG", "ntu singapore": "SG",
    "kaist": "KR", "postech": "KR", "snu": "KR",
    "tsinghua": "CN", "peking": "CN", "pku": "CN", "fudan": "CN",
    "tifr": "IN", "iit": "IN", "iisc": "IN",
    "chalmers": "SE", "kth": "SE", "stockholm": "SE", "lund": "SE",
    "cmu": "US", "carnegie mellon": "US", "mit": "US", "stanford": "US", "berkeley": "US",
    "princeton": "US", "columbia": "US", "cornell": "US", "yale": "US", "harvard": "US",
    "oxford": "GB", "cambridge": "GB", "imperial": "GB", "edinburgh": "GB", "warwick": "GB",
    "toronto": "CA", "waterloo": "CA", "mcgill": "CA", "montreal": "CA",
    "aarhus": "DK", "copenhagen": "DK",
    "amsterdam": "NL", "utrecht": "NL", "delft": "NL", "eindhoven": "NL", "cwi": "NL",
    "vienna": "AT", "graz": "AT", "ista": "AT",
    "warsaw": "PL", "wroclaw": "PL", "jagiellonian": "PL",
}
ISO2 = {v for v in COUNTRY_MAP.values()}


@dataclass
class Paper:
    paper_id: str
    dblp_key: str
    congress: str
    level: str
    area: str
    year: int
    window: str
    title: str
    doi: str


def normalize_title(t: str) -> str:
    if not t:
        return ""
    t = t.lower().strip()
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


def infer_country(text: str) -> str | None:
    if not text:
        return None
    t = text.lower().strip()
    t = re.sub(r"\s+", " ", t)

    if len(t) == 2 and t.upper() in ISO2:
        return t.upper()

    # País explícito al final de afiliación: "..., Germany".
    tokens = [tok.strip(" .,;:()[]") for tok in re.split(r"[,;|]", t) if tok.strip()]
    for tok in reversed(tokens):
        if tok in COUNTRY_MAP:
            return COUNTRY_MAP[tok]

    if t in COUNTRY_MAP:
        return COUNTRY_MAP[t]

    # Patrones institucionales dentro del texto.
    for pattern, iso in COUNTRY_MAP.items():
        if len(pattern) > 4 and pattern in t:
            return iso
    return None


def drops_get(url: str) -> requests.Response | None:
    wait = INITIAL_WAIT
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers={"User-Agent": "bibliometric-replication/1.0"}, timeout=40)
            if r.status_code == 429:
                time.sleep(wait)
                wait = min(wait * 2, 90)
                continue
            if r.status_code in (500, 502, 503, 504):
                time.sleep(wait)
                wait = min(wait * 2, 60)
                continue
            time.sleep(1.0 / RATE_LIMIT)
            return r
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(wait)
            wait = min(wait * 2, 60)
    return None


def load_json(path: Path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data) -> None:
    """Guarda JSON de forma tolerante a bloqueos temporales de Windows/Dropbox.

    En carpetas sincronizadas, os.replace/tmp.replace puede fallar con
    WinError 5 si Dropbox, antivirus o un editor bloquean el destino.
    Reintentamos varias veces y, si el bloqueo persiste, dejamos una copia
    con timestamp para no perder progreso.
    """
    import os
    import time

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())

    last_exc = None
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError as exc:
            last_exc = exc
            time.sleep(0.5 * (attempt + 1))

    # Fallback: guardar backup para no perder progreso, y dejar el .part.
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(path.suffix + f".{stamp}.backup")
    try:
        os.replace(tmp, backup)
        print(f"  ⚠️  No se pudo reemplazar {path.name} por bloqueo de Windows/Dropbox.")
        print(f"      Progreso guardado en backup: {backup.name}")
    except Exception:
        print(f"  ⚠️  No se pudo guardar {path.name}; queda fichero temporal: {tmp.name}")
    if last_exc:
        print(f"      Último error: {last_exc}")


def load_papers() -> dict[str, Paper]:
    if not PAPER_MASTER.exists():
        raise FileNotFoundError(f"No se encuentra {PAPER_MASTER}. Ejecuta antes el paso 4.")
    papers: dict[str, Paper] = {}
    with open(PAPER_MASTER, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                year = int(row["year"])
            except Exception:
                continue
            papers[row["paper_id"]] = Paper(
                paper_id=row["paper_id"],
                dblp_key=row.get("dblp_key", ""),
                congress=row.get("congress", ""),
                level=row.get("level", ""),
                area=row.get("area", ""),
                year=year,
                window=row.get("window", ""),
                title=row.get("title", ""),
                doi=row.get("doi", ""),
            )
    return papers


def load_resolved_paper_ids() -> set[str]:
    evidence_files = [
        OUTPUTS / "affiliation_evidence_openalex_doi.csv",
        OUTPUTS / "affiliation_evidence_openalex_venue.csv",
        OUTPUTS / "affiliation_evidence_crossref.csv",
        OUTPUTS / "affiliation_evidence_drops.csv",
    ]
    resolved = set()
    for path in evidence_files:
        if not path.exists():
            continue
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if "paper_id" not in (reader.fieldnames or []):
                continue
            for row in reader:
                pid = row.get("paper_id")
                cc = row.get("country_code")
                if pid and cc:
                    resolved.add(pid)
    return resolved


def get_volume_ids_for_conf(drops_acronym: str) -> list[dict]:
    """Devuelve volúmenes posibles: {year, vol_id, url, label}."""
    if BeautifulSoup is None:
        raise ImportError("Falta beautifulsoup4. Instala con: pip install beautifulsoup4")

    url = f"{DROPS_BASE}/entities/conference/{drops_acronym}"
    r = drops_get(url)
    if not r or r.status_code != 200:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    vols = []
    seen = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = " ".join(link.get_text(" ").split())
        if "entities/volume/" not in href:
            continue
        if "LIPIcs-volume-" not in href and "OASIcs-volume-" not in href:
            continue

        year_match = re.search(r"\b(20\d{2}|19\d{2})\b", text)
        if not year_match:
            # sometimes year appears in surrounding href/text
            year_match = re.search(r"\b(20\d{2}|19\d{2})\b", href)
        if not year_match:
            continue
        year = int(year_match.group(1))
        if not (YEAR_MIN <= year <= YEAR_MAX):
            continue

        # extract canonical volume entity path.
        m = re.search(r"entities/volume/([^/?#]+)", href)
        if not m:
            continue
        vol_entity = m.group(1)
        key = (year, vol_entity)
        if key in seen:
            continue
        seen.add(key)
        vols.append({"year": year, "vol_id": vol_entity, "label": text, "href": href})

    return vols


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _element_text(elem: ET.Element | None) -> str:
    if elem is None:
        return ""
    return " ".join("".join(elem.itertext()).split())


def parse_drops_xml(xml_text: str) -> list[dict]:
    """Parsea XML DROPS y devuelve papers con título y países."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    papers = []
    for article in root.iter():
        if _strip_ns(article.tag).lower() not in {"article", "paper", "entry"}:
            continue

        title = ""
        countries = set()
        affiliations = []

        for child in article.iter():
            tag = _strip_ns(child.tag).lower()
            if tag == "title" and not title:
                title = _element_text(child)
            elif tag in {"affiliation", "affiliations", "institution", "organization"}:
                txt = _element_text(child)
                if txt:
                    affiliations.append(txt)
            elif tag in {"country", "country_code", "country-code"}:
                txt = _element_text(child)
                cc = infer_country(txt)
                if cc:
                    countries.add(cc)

        if not title:
            continue
        low = title.lower()
        if any(skip in low for skip in [
            "front matter", "table of contents", "preface", "invited paper",
            "invited lecture", "invited talk", "keynote", "abstracts",
        ]):
            continue

        for aff in affiliations:
            cc = infer_country(aff)
            if cc:
                countries.add(cc)

        papers.append({
            "title": title,
            "title_norm": normalize_title(title),
            "countries": sorted(countries),
            "n_affiliations_raw": len(affiliations),
        })
    return papers


def get_volume_papers(vol_entity: str) -> list[dict]:
    # vol_entity usually includes LIPIcs-volume-123. Build XML endpoint.
    url = f"{DROPS_BASE}/entities/volume/{vol_entity}/metadata/xml"
    r = drops_get(url)
    if not r or r.status_code != 200 or not r.text.strip():
        return []
    return parse_drops_xml(r.text)


def build_target_index(papers: Iterable[Paper]) -> dict[tuple[str, int], dict[str, Paper]]:
    idx: dict[tuple[str, int], dict[str, Paper]] = defaultdict(dict)
    for p in papers:
        norm = normalize_title(p.title)
        if norm:
            idx[(p.congress, p.year)][norm] = p
    return idx


def find_match(title_norm: str, candidates: dict[str, Paper]) -> tuple[Paper | None, float, str]:
    if not title_norm or not candidates:
        return None, 0.0, "none"
    if title_norm in candidates:
        return candidates[title_norm], 1.0, "title_exact"

    words = set(title_norm.split())
    if not words:
        return None, 0.0, "none"
    best_paper, best_score = None, 0.0
    # Candidate pruning: require at least one rare-ish token match, avoid O(N) cost being too harmful.
    for cand_norm, paper in candidates.items():
        cwords = set(cand_norm.split())
        if not cwords:
            continue
        overlap_count = len(words & cwords)
        if overlap_count < max(2, min(4, len(words) // 4)):
            continue
        score = overlap_count / max(len(words), len(cwords))
        if score > best_score:
            best_score, best_paper = score, paper

    if best_paper is not None and best_score >= TITLE_SIM_THRESHOLD:
        return best_paper, best_score, "title_fuzzy"
    return None, best_score, "unmatched"


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run(force: bool = False, limit_volumes: int | None = None) -> None:
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭  Paso 7 ya completado (usa --force para repetir).")
        return

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    papers = load_papers()
    resolved = load_resolved_paper_ids()
    targets = [p for p in papers.values() if p.paper_id not in resolved and p.congress in DROPS_CONF_MAP]
    target_idx = build_target_index(targets)

    print(f"  Artículos en paper_master: {len(papers):,}")
    print(f"  Ya resueltos por evidencias previas: {len(resolved):,}")
    print(f"  Objetivo DROPS sin país previo: {len(targets):,}")
    print(f"  Ediciones objetivo (congress, year): {len(target_idx):,}")

    if not targets:
        write_csv(OUT_EVIDENCE, [], [
            "paper_id", "dblp_key", "congress", "level", "area", "year", "window",
            "country_code", "source", "method", "confidence", "matched_by", "source_work_id",
            "source_url", "matched_title", "title_similarity", "n_affiliations_raw",
        ])
        OUT_REPORT.write_text("No hay artículos objetivo para DROPS.\n", encoding="utf-8")
        return

    cache = load_json(CACHE_FILE, {"volumes": {}, "conf_volumes": {}})
    evidence_rows = []
    unresolved_rows = []
    volume_audit = []

    # Discover volumes for needed conferences.
    needed_confs = sorted({p.congress for p in targets})
    volume_tasks = []  # (congress, year, vol_entity, label)

    print("\n  [Fase 1] Buscando volúmenes DROPS...")
    for congress in tqdm(needed_confs, desc="  congresos"):
        for drops_acronym in DROPS_CONF_MAP.get(congress, []):
            conf_key = f"{congress}|{drops_acronym}"
            if conf_key not in cache["conf_volumes"]:
                cache["conf_volumes"][conf_key] = get_volume_ids_for_conf(drops_acronym)
                save_json(CACHE_FILE, cache)
            for vol in cache["conf_volumes"].get(conf_key, []):
                year = int(vol.get("year", 0))
                if (congress, year) in target_idx:
                    volume_tasks.append((congress, year, vol["vol_id"], vol.get("label", "")))

    # Deduplicate tasks.
    seen_tasks = set()
    unique_tasks = []
    for task in volume_tasks:
        key = (task[0], task[1], task[2])
        if key not in seen_tasks:
            seen_tasks.add(key)
            unique_tasks.append(task)
    volume_tasks = unique_tasks
    if limit_volumes:
        volume_tasks = volume_tasks[:limit_volumes]
        print(f"  ⚠️  Modo test: {limit_volumes} volúmenes")

    print(f"  Volúmenes DROPS candidatos: {len(volume_tasks):,}")

    matched_papers: set[str] = set()
    save_counter = 0

    print("\n  [Fase 2] Descargando XML y cruzando títulos...")
    for congress, year, vol_entity, label in tqdm(volume_tasks, desc="  volúmenes"):
        vol_key = f"{vol_entity}"
        t0 = time.time()
        if vol_key not in cache["volumes"]:
            papers_xml = get_volume_papers(vol_entity)
            cache["volumes"][vol_key] = papers_xml
            save_counter += 1
            if save_counter >= SAVE_EVERY:
                save_json(CACHE_FILE, cache)
                save_counter = 0
        else:
            papers_xml = cache["volumes"][vol_key]

        candidates = target_idx.get((congress, year), {})
        n_seen = len(papers_xml)
        n_matched = 0
        n_country_rows = 0
        for src_paper in papers_xml:
            p, score, matched_by = find_match(src_paper.get("title_norm", ""), candidates)
            if p is None:
                continue
            n_matched += 1
            matched_papers.add(p.paper_id)
            countries = sorted(set(src_paper.get("countries") or []))
            if not countries:
                continue
            for cc in countries:
                evidence_rows.append({
                    "paper_id": p.paper_id,
                    "dblp_key": p.dblp_key,
                    "congress": p.congress,
                    "level": p.level,
                    "area": p.area,
                    "year": p.year,
                    "window": p.window,
                    "country_code": cc,
                    "source": "drops",
                    "method": "volume_xml_title_match",
                    "confidence": round(float(score), 4),
                    "matched_by": matched_by,
                    "source_work_id": vol_entity,
                    "source_url": f"{DROPS_BASE}/entities/volume/{vol_entity}",
                    "matched_title": src_paper.get("title", ""),
                    "title_similarity": round(float(score), 4),
                    "n_affiliations_raw": src_paper.get("n_affiliations_raw", 0),
                })
                n_country_rows += 1

        volume_audit.append({
            "congress": congress,
            "year": year,
            "volume": vol_entity,
            "label": label,
            "target_papers": len(candidates),
            "drops_papers": n_seen,
            "matched_papers": n_matched,
            "country_evidence_rows": n_country_rows,
            "seconds": round(time.time() - t0, 2),
        })

    save_json(CACHE_FILE, cache)

    # Remove duplicate evidence rows.
    dedup = {}
    for row in evidence_rows:
        key = (row["paper_id"], row["country_code"], row["source"], row["source_work_id"])
        old = dedup.get(key)
        if old is None or float(row["confidence"]) > float(old["confidence"]):
            dedup[key] = row
    evidence_rows = list(dedup.values())

    # Unresolved among targets processed by available volumes.
    for p in targets:
        if p.paper_id not in matched_papers:
            unresolved_rows.append({
                "paper_id": p.paper_id,
                "dblp_key": p.dblp_key,
                "congress": p.congress,
                "level": p.level,
                "area": p.area,
                "year": p.year,
                "window": p.window,
                "title": p.title,
                "reason": "no_drops_title_match_or_no_volume",
            })

    evidence_fields = [
        "paper_id", "dblp_key", "congress", "level", "area", "year", "window",
        "country_code", "source", "method", "confidence", "matched_by", "source_work_id",
        "source_url", "matched_title", "title_similarity", "n_affiliations_raw",
    ]
    unresolved_fields = ["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "title", "reason"]
    audit_fields = ["congress", "year", "volume", "label", "target_papers", "drops_papers", "matched_papers", "country_evidence_rows", "seconds"]

    write_csv(OUT_EVIDENCE, evidence_rows, evidence_fields)
    write_csv(OUT_UNRESOLVED, unresolved_rows, unresolved_fields)
    write_csv(OUTPUTS / "drops_volume_audit.csv", volume_audit, audit_fields)

    resolved_papers_drops = {r["paper_id"] for r in evidence_rows}
    countries_count = defaultdict(int)
    congress_count = defaultdict(int)
    for row in evidence_rows:
        countries_count[row["country_code"]] += 1
        congress_count[row["congress"]] += 1

    lines = []
    lines.append("=== PASO 7 — DROPS/LIPIcs ===\n")
    lines.append(f"Artículos en paper_master: {len(papers):,}")
    lines.append(f"Artículos ya resueltos por fuentes previas: {len(resolved):,}")
    lines.append(f"Artículos objetivo DROPS sin país previo: {len(targets):,}")
    lines.append(f"Ediciones objetivo (congress, year): {len(target_idx):,}")
    lines.append(f"Volúmenes DROPS procesados: {len(volume_tasks):,}")
    lines.append(f"Artículos con ≥1 país vía DROPS: {len(resolved_papers_drops):,}")
    cov = len(resolved_papers_drops) / len(targets) * 100 if targets else 0.0
    lines.append(f"Cobertura sobre objetivo DROPS: {cov:.2f}%")
    lines.append(f"Filas de evidencia paper-país: {len(evidence_rows):,}")

    lines.append("\n=== TOP 30 PAÍSES VIA DROPS ===")
    if countries_count:
        for cc, n in sorted(countries_count.items(), key=lambda kv: kv[1], reverse=True)[:30]:
            lines.append(f"  {cc}: {n:,}")
    else:
        lines.append("  Ninguno")

    lines.append("\n=== TOP 30 CONGRESOS VIA DROPS ===")
    if congress_count:
        for conf, n in sorted(congress_count.items(), key=lambda kv: kv[1], reverse=True)[:30]:
            target_n = sum(1 for p in targets if p.congress == conf)
            lines.append(f"  {conf:18s} evidencia={n:6,d} objetivo={target_n:6,d}")
    else:
        lines.append("  Ninguno")

    lines.append("\n=== VOLÚMENES CON MÁS MATCHES ===")
    for row in sorted(volume_audit, key=lambda r: int(r["matched_papers"]), reverse=True)[:30]:
        lines.append(
            f"  {row['congress']:18s} {row['year']} matched={int(row['matched_papers']):4d} "
            f"countries={int(row['country_evidence_rows']):4d} drops={int(row['drops_papers']):4d} "
            f"target={int(row['target_papers']):4d} sec={float(row['seconds']):5.1f} {row['volume']}"
        )

    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")

    result = {
        "step": 7,
        "status": "COMPLETE",
        "target_articles": len(targets),
        "volumes_processed": len(volume_tasks),
        "resolved_articles": len(resolved_papers_drops),
        "evidence_rows": len(evidence_rows),
        "coverage_pct": round(cov, 4),
    }
    CHECKPOINT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n  ✅ Evidencias guardadas: {OUT_EVIDENCE}")
    print(f"  ✅ Informe: {OUT_REPORT}")
    print(f"  Artículos resueltos vía DROPS: {len(resolved_papers_drops):,}/{len(targets):,} ({cov:.2f}%)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Repetir aunque exista checkpoint")
    parser.add_argument("--limit-volumes", type=int, default=None, help="Modo test: procesa solo N volúmenes")
    args = parser.parse_args()

    print("=" * 60)
    print("PASO 7 — Afiliaciones desde DROPS/LIPIcs")
    print("=" * 60)
    try:
        run(force=args.force, limit_volumes=args.limit_volumes)
    except Exception as exc:
        print(f"❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
