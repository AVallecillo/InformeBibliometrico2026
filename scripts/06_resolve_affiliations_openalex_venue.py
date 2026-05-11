#!/usr/bin/env python3
"""
PASO 6 — Resolución de afiliaciones con OpenAlex por source_id + venue/año.

Versión optimizada para evitar combos lentos:
  - resuelve y cachea source_id exacto en OpenAlex /sources;
  - consulta /works por primary_location.source.id cuando puede;
  - limita páginas por combo;
  - registra auditoría de rendimiento por combo;
  - hace fuzzy matching acotado por tokens.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step6_openalex_venue.json"
CACHE_FILE = OUTPUTS / "openalex_venue_cache_v2.json"
SOURCE_CACHE_FILE = OUTPUTS / "openalex_source_cache.json"

OA_WORKS_BASE = "https://api.openalex.org/works"
OA_SOURCES_BASE = "https://api.openalex.org/sources"
OPENALEX_API_KEY: str | None = None

YEAR_MIN, YEAR_MAX = 2001, 2025
RESULTS_PER_PAGE = 200
DEFAULT_MAX_PAGES_PER_COMBO = 8
RATE_LIMIT = 50.0
MAX_RETRIES = 6
INITIAL_WAIT = 5
SAVE_EVERY_COMBOS = 20
TITLE_EXACT_CONFIDENCE = 1.0
TITLE_SIM_THRESHOLD = 0.90
FUZZY_MAX_CANDIDATES_PER_PAPER = 600
FUZZY_MAX_WORKS_PER_COMBO = 3500

OA_VENUE_MAP = {
    "NeurIPS": "Neural Information Processing Systems", "CVPR": "Computer Vision and Pattern Recognition",
    "ICML": "International Conference on Machine Learning", "IJCAI": "International Joint Conference on Artificial Intelligence",
    "AAAI": "AAAI Conference on Artificial Intelligence", "ICCV": "International Conference on Computer Vision",
    "ICLR": "International Conference on Learning Representations", "ECCV": "European Conference on Computer Vision",
    "EMNLP": "Empirical Methods in Natural Language Processing", "ACL": "Annual Meeting of the Association for Computational Linguistics",
    "ICRA": "International Conference on Robotics and Automation", "ACMMM": "ACM Multimedia",
    "ICAPS": "International Conference on Automated Planning and Scheduling", "KR": "Principles of Knowledge Representation and Reasoning",
    "AISTATS": "Artificial Intelligence and Statistics", "Interspeech": "Interspeech", "IROS": "Intelligent Robots and Systems",
    "ECML PKDD": "European Conference on Machine Learning and Principles and Practice of Knowledge Discovery",
    "MICCAI": "Medical Image Computing and Computer Assisted Intervention", "WACV": "Winter Conference on Applications of Computer Vision",
    "ICDAR": "Document Analysis and Recognition", "ICME": "IEEE International Conference on Multimedia and Expo",
    "AAMAS": "Autonomous Agents and Multi-Agent Systems", "UAI": "Uncertainty in Artificial Intelligence",
    "GECCO": "Genetic and Evolutionary Computation", "FOGA": "Foundations of Genetic Algorithms",
    "PPSN": "Parallel Problem Solving from Nature", "NAACL": "North American Chapter of the Association for Computational Linguistics",
    "EACL": "European Chapter of the Association for Computational Linguistics", "RecSys": "ACM Conference on Recommender Systems",
    "ICWSM": "International AAAI Conference on Web and Social Media", "ECAI": "European Conference on Artificial Intelligence",
    "BMVC": "British Machine Vision Conference", "SDM": "SIAM International Conference on Data Mining",
    "AIED": "Artificial Intelligence in Education", "LAK": "Learning Analytics and Knowledge", "ISMB": "Intelligent Systems for Molecular Biology",

    "ICSE": "International Conference on Software Engineering", "FSE": "Foundations of Software Engineering",
    "ASE": "Automated Software Engineering", "PLDI": "Programming Language Design and Implementation",
    "POPL": "Principles of Programming Languages", "CAV": "Computer Aided Verification",
    "ICSME": "Software Maintenance and Evolution", "ESEM": "Empirical Software Engineering and Measurement",
    "BPM": "Business Process Management", "MODELS": "Model Driven Engineering Languages and Systems",
    "EASE": "Evaluation and Assessment in Software Engineering", "ICSA": "Software Architecture",
    "ICST": "Software Testing Verification and Validation", "ISSRE": "Software Reliability Engineering",
    "SEAMS": "Software Engineering for Adaptive and Self-Managing Systems", "ESOP": "European Symposium on Programming",
    "ICFP": "International Conference on Functional Programming", "OOPSLA": "Object-Oriented Programming Systems Languages and Applications",
    "ECOOP": "European Conference on Object-Oriented Programming", "CGO": "Code Generation and Optimization",
    "MSR": "Mining Software Repositories", "SANER": "Software Analysis Evolution and Reengineering",
    "ISSTA": "Software Testing and Analysis", "ICPC": "Program Comprehension", "RE": "Requirements Engineering",
    "TACAS": "Tools and Algorithms for the Construction and Analysis of Systems", "ICSOC": "Service-Oriented Computing",
    "CaiSE": "Advanced Information Systems Engineering",

    "MICRO": "International Symposium on Microarchitecture", "DAC": "Design Automation Conference",
    "ISCA": "International Symposium on Computer Architecture", "ASPLOS": "Architectural Support for Programming Languages and Operating Systems",
    "SIGMETRICS": "International Conference on Measurement and Modeling of Computer Systems",
    "OSDI": "Operating Systems Design and Implementation", "SOSP": "Symposium on Operating Systems Principles",
    "PODC": "Principles of Distributed Computing", "HPCA": "High Performance Computer Architecture",
    "ICDCS": "Distributed Computing Systems", "EuroSys": "European Conference on Computer Systems",
    "HotOS": "Hot Topics in Operating Systems", "Middleware": "Middleware", "FAST": "File and Storage Technologies",
    "SC": "High Performance Computing Networking Storage and Analysis", "HPDC": "High-Performance Parallel and Distributed Computing",
    "IPDPS": "Parallel and Distributed Processing Symposium", "ICS": "International Conference on Supercomputing",
    "ICCAD": "Computer-Aided Design", "ISLPED": "Low Power Electronics and Design", "ITC": "International Test Conference",
    "FPGA": "Field-Programmable Gate Arrays", "DATE": "Design Automation and Test in Europe",
    "RTAS": "Real-Time and Embedded Technology and Applications", "RTSS": "Real-Time Systems Symposium",
    "DSN": "Dependable Systems and Networks", "DISC": "International Symposium on Distributed Computing",

    "INFOCOM": "IEEE INFOCOM", "SIGCOMM": "Special Interest Group on Data Communication",
    "MOBICOM": "Mobile Computing and Networking", "IMC": "Internet Measurement Conference",
    "CoNEXT": "Emerging Networking Experiments and Technologies", "Mobisys": "Mobile Systems Applications and Services",
    "ICWS": "International Conference on Web Services", "MMSys": "Multimedia Systems",
    "MSWIM": "Modeling Analysis and Simulation of Wireless and Mobile Systems",

    "SP": "IEEE Symposium on Security and Privacy", "CCS": "Computer and Communications Security",
    "USENIX-Security": "USENIX Security Symposium", "NDSS": "Network and Distributed System Security",
    "EuroCrypt": "Theory and Applications of Cryptographic Techniques", "CRYPTO": "Advances in Cryptology",
    "ESORICS": "Research in Computer Security", "ASIACRYPT": "Theory and Application of Cryptology and Information Security",
    "FC": "Financial Cryptography and Data Security", "RAID": "Research in Attacks Intrusions and Defenses",
    "ACSAC": "Computer Security Applications Conference", "AsiaCCS": "Asia Conference on Computer and Communications Security",
    "PETS": "Privacy Enhancing Technologies", "CHES": "Cryptographic Hardware and Embedded Systems",
    "EuroS&P": "IEEE European Symposium on Security and Privacy", "CSF": "Computer Security Foundations",
    "SOUPS": "Usable Privacy and Security",

    "WWW": "The Web Conference", "VLDB": "Very Large Data Bases", "KDD": "Knowledge Discovery and Data Mining",
    "ICDE": "Data Engineering", "SIGMOD": "SIGMOD International Conference on Management of Data",
    "SIGIR": "Research and Development in Information Retrieval", "ICDM": "IEEE International Conference on Data Mining",
    "PODS": "Principles of Database Systems", "WSDM": "Web Search and Data Mining", "CIKM": "Information and Knowledge Management",
    "ECIR": "European Conference on Information Retrieval", "ISWC": "International Semantic Web Conference",
    "SIGSPATIAL": "Advances in Geographic Information Systems", "ICDT": "International Conference on Database Theory",
    "CIDR": "Innovative Data Systems Research", "ER": "Conceptual Modeling",

    "ICALP": "Automata Languages and Programming", "SODA": "ACM-SIAM Symposium on Discrete Algorithms",
    "STOC": "Symposium on Theory of Computing", "FOCS": "Symposium on Foundations of Computer Science",
    "LICS": "Logic in Computer Science", "SoCG": "Symposium on Computational Geometry", "EC": "Economics and Computation",
    "COLT": "Conference on Learning Theory", "STACS": "Theoretical Aspects of Computer Science", "ESA": "European Symposium on Algorithms",
    "ALENEX": "Algorithm Engineering and Experiments", "APPROX/RANDOM": "Approximation Randomization and Combinatorial Optimization",
    "IJCAR": "Automated Reasoning", "CADE": "Automated Deduction", "GD": "Graph Drawing",
    "CCC": "Computational Complexity Conference", "ITCS": "Innovations in Theoretical Computer Science",
    "SAT": "Theory and Applications of Satisfiability Testing", "CP": "Principles and Practice of Constraint Programming",

    "CHI": "CHI Conference on Human Factors in Computing Systems", "UIST": "User Interface Software and Technology",
    "VR": "Virtual Reality and 3D User Interfaces", "HRI": "Human-Robot Interaction",
    "PERCOM": "Pervasive Computing and Communications", "ISMAR": "Mixed and Augmented Reality",
    "SIGGRAPH": "Special Interest Group on Computer Graphics", "SiggraphA": "SIGGRAPH Asia",
    "CSCW": "Computer-Supported Cooperative Work", "DIS": "Designing Interactive Systems", "IUI": "Intelligent User Interfaces",
    "ASSETS": "Computers and Accessibility", "UMAP": "User Modeling Adaptation and Personalization",
    "SIGCSE": "Computer Science Education", "ICER": "International Computing Education Research", "IEEE VIS": "IEEE Visualization",
}

OA_SOURCE_ID_OVERRIDES = {
    # Rellena manualmente si la resolución automática elige una fuente mala:
    # "NeurIPS": "S4306402512",
}


def normalize_title(text: str) -> str:
    if not text:
        return ""
    text = text.casefold().strip()
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def title_similarity_norm(na: str, nb: str) -> float:
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    wa, wb = set(na.split()), set(nb.split())
    return len(wa & wb) / max(len(wa), len(wb)) if wa and wb else 0.0


def useful_tokens(norm: str) -> list[str]:
    stop = {"the", "and", "for", "with", "from", "into", "over", "under", "using", "based", "towards", "toward", "via", "its", "your", "our", "this", "that", "what", "when", "where", "which", "that", "a", "an", "of", "on", "in", "to", "by", "is", "are"}
    return [t for t in norm.split() if len(t) >= 4 and t not in stop]


def oa_headers() -> dict[str, str]:
    h = {"User-Agent": "bibliometric-replication/1.0"}
    if OPENALEX_API_KEY:
        h["Authorization"] = f"Bearer {OPENALEX_API_KEY}"
    return h


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(path)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def request_json(url: str, params: dict[str, Any], *, timeout: int = 45) -> dict[str, Any] | None:
    wait = INITIAL_WAIT
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, headers=oa_headers(), timeout=timeout)
            if r.status_code == 429:
                print(f"\n  ⏳ OpenAlex 429; esperando {wait}s...")
                time.sleep(wait)
                wait = min(wait * 2, 180)
                continue
            if r.status_code in (500, 502, 503, 504):
                time.sleep(wait)
                wait = min(wait * 2, 120)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(wait)
            wait = min(wait * 2, 120)
    return None


def load_papers(limit_articles: int | None = None) -> list[dict[str, str]]:
    path = OUTPUTS / "paper_master.csv"
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra {path}. Ejecuta antes el paso 4.")
    papers = read_csv_rows(path)
    if limit_articles is not None:
        papers = papers[:limit_articles]
    required = {"paper_id", "dblp_key", "congress", "level", "area", "year", "window", "title"}
    if papers:
        missing = required - set(papers[0])
        if missing:
            raise ValueError(f"Faltan columnas en paper_master.csv: {sorted(missing)}")
    return papers


def load_existing_resolved_paper_ids() -> set[str]:
    path = OUTPUTS / "affiliation_evidence_openalex_doi.csv"
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra {path}. Ejecuta antes el paso 5 OpenAlex DOI.")
    resolved = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = (row.get("paper_id") or "").strip()
            cc = (row.get("country_code") or "").strip()
            if pid and cc:
                resolved.add(pid)
    return resolved


def countries_from_authorships(work: dict[str, Any]) -> dict[str, int]:
    c = Counter()
    for authorship in work.get("authorships") or []:
        for inst in authorship.get("institutions") or []:
            cc = inst.get("country_code")
            if cc:
                c[str(cc).upper()] += 1
    return dict(c)


def source_id_short(source_id: str) -> str:
    if not source_id:
        return ""
    return source_id.rstrip("/").split("/")[-1]


def resolve_openalex_source(congress: str, venue_query: str, source_cache: dict[str, Any]) -> dict[str, Any]:
    if congress in OA_SOURCE_ID_OVERRIDES:
        sid = source_id_short(OA_SOURCE_ID_OVERRIDES[congress])
        return {"status": "manual_override", "source_id": sid, "display_name": "", "query": venue_query}
    if congress in source_cache:
        return source_cache[congress]

    params = {"search": venue_query, "per-page": 10, "select": "id,display_name,type,works_count"}
    data = request_json(OA_SOURCES_BASE, params, timeout=30)
    candidates = (data or {}).get("results") or []
    qn = normalize_title(venue_query)
    best = None
    best_score = -1.0
    for src in candidates:
        name = src.get("display_name") or ""
        nn = normalize_title(name)
        score = title_similarity_norm(qn, nn)
        stype = (src.get("type") or "").casefold()
        if "conference" in stype or "proceedings" in stype:
            score += 0.05
        if "journal" in stype:
            score -= 0.02
        if score > best_score:
            best_score = score
            best = src

    if best and best_score >= 0.35:
        resolved = {
            "status": "resolved",
            "source_id": source_id_short(best.get("id") or ""),
            "display_name": best.get("display_name") or "",
            "type": best.get("type") or "",
            "works_count": best.get("works_count") or 0,
            "query": venue_query,
            "score": round(best_score, 4),
            "candidate_count": len(candidates),
        }
    else:
        resolved = {
            "status": "unresolved",
            "source_id": "",
            "display_name": "",
            "type": "",
            "works_count": 0,
            "query": venue_query,
            "score": round(best_score, 4),
            "candidate_count": len(candidates),
        }
    source_cache[congress] = resolved
    return resolved


def fetch_openalex_venue_year(congress: str, venue_query: str, year: int, *, source_id: str = "", max_pages: int = DEFAULT_MAX_PAGES_PER_COMBO) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cursor = "*"
    page = 0
    t0 = time.perf_counter()
    while page < max_pages:
        if source_id:
            filter_expr = f"primary_location.source.id:{source_id},publication_year:{year}"
        else:
            filter_expr = f"primary_location.source.display_name.search:{venue_query},publication_year:{year}"
        params = {
            "filter": filter_expr,
            "select": "id,doi,title,display_name,publication_year,authorships,primary_location",
            "per-page": RESULTS_PER_PAGE,
            "cursor": cursor,
        }
        data = request_json(OA_WORKS_BASE, params, timeout=45)
        if not data:
            break
        batch = data.get("results") or []
        if not batch:
            break
        results.extend(batch)
        page += 1
        next_cursor = (data.get("meta") or {}).get("next_cursor")
        if not next_cursor or len(batch) < RESULTS_PER_PAGE:
            break
        cursor = next_cursor
        time.sleep(1.0 / RATE_LIMIT)
    time.sleep(1.0 / RATE_LIMIT)
    meta = {
        "n_pages": page,
        "n_raw_results": len(results),
        "seconds_fetch": round(time.perf_counter() - t0, 3),
        "used_source_id": source_id,
        "query_mode": "source_id" if source_id else "source_search",
        "max_pages": max_pages,
    }
    return results, meta


def build_work_index(works: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, set[str]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    token_index: dict[str, set[str]] = defaultdict(set)
    for w in works:
        title = w.get("title", "")
        norm = normalize_title(title)
        if not norm:
            continue
        item = {"title": title, "countries": w.get("countries", {}), "openalex_id": w.get("openalex_id", ""), "doi": w.get("doi", "")}
        index[norm].append(item)
        for tok in useful_tokens(norm):
            token_index[tok].add(norm)
    return dict(index), token_index


def match_paper_to_work(title: str, index: dict[str, list[dict[str, Any]]], token_index: dict[str, set[str]], *, allow_fuzzy: bool = True) -> tuple[dict[str, Any] | None, str, float, int]:
    norm = normalize_title(title)
    if not norm:
        return None, "no_title", 0.0, 0
    if norm in index:
        return index[norm][0], "title_exact", TITLE_EXACT_CONFIDENCE, 1
    if not allow_fuzzy or len(index) > FUZZY_MAX_WORKS_PER_COMBO:
        return None, "unmatched_no_fuzzy", 0.0, 0
    candidate_keys: set[str] = set()
    toks = useful_tokens(norm)
    token_freqs = sorted(((len(token_index.get(t, set())), t) for t in toks if t in token_index))
    for _, tok in token_freqs[:8]:
        candidate_keys.update(token_index[tok])
        if len(candidate_keys) >= FUZZY_MAX_CANDIDATES_PER_PAPER:
            break
    if not candidate_keys:
        candidate_keys = set(index.keys()) if len(index) <= 250 else set()
    best = None
    best_score = 0.0
    checked = 0
    for key in candidate_keys:
        checked += 1
        score = title_similarity_norm(norm, key)
        if score > best_score:
            best_score = score
            best = index[key][0]
    if best is not None and best_score >= TITLE_SIM_THRESHOLD:
        return best, "title_fuzzy", round(best_score, 4), checked
    return None, "unmatched", round(best_score, 4), checked


def build_target_groups(papers: list[dict[str, str]], resolved_ids: set[str]) -> dict[tuple[str, int], list[dict[str, str]]]:
    groups = defaultdict(list)
    skipped = Counter()
    for p in papers:
        if p["paper_id"] in resolved_ids:
            continue
        congress = p["congress"]
        if congress not in OA_VENUE_MAP:
            skipped[congress] += 1
            continue
        year = int(float(p["year"]))
        if YEAR_MIN <= year <= YEAR_MAX:
            groups[(congress, year)].append(p)
    if skipped:
        print(f"  ⚠️  Congresos sin mapeo OA venue: {len(skipped)}")
        for c, n in skipped.most_common(20):
            print(f"     {c}: {n:,} artículos sin país")
    return dict(groups)


def report_text(papers, target_papers, evidence_rows, unresolved_rows, venue_cache, combo_audit) -> str:
    resolved_ids = {r["paper_id"] for r in evidence_rows}
    lines = ["=== PASO 6 — OPENALEX POR SOURCE/VENUE-AÑO ===\n"]
    lines.append(f"Artículos totales en paper_master: {len(papers):,}")
    lines.append(f"Artículos objetivo sin país previo: {len(target_papers):,}")
    lines.append(f"Artículos resueltos vía OpenAlex venue: {len(resolved_ids):,}")
    pct = len(resolved_ids) / len(target_papers) * 100 if target_papers else 0
    lines.append(f"Cobertura sobre objetivo: {pct:.2f}%")
    lines.append(f"Filas de evidencia paper-país: {len(evidence_rows):,}")
    lines.append(f"Combos venue+año en caché: {len(venue_cache):,}")
    if combo_audit:
        total_fetch = sum(float(r.get("seconds_fetch", 0) or 0) for r in combo_audit)
        total_match = sum(float(r.get("seconds_match", 0) or 0) for r in combo_audit)
        lines.append(f"Tiempo fetch total combos ejecutados: {total_fetch:.1f}s")
        lines.append(f"Tiempo matching total combos ejecutados: {total_match:.1f}s")
    status_counts = Counter(r.get("status", "unknown") for r in unresolved_rows)
    if status_counts:
        lines.append("\n=== NO RESUELTOS / DIAGNÓSTICO ===")
        for status, n in status_counts.most_common():
            lines.append(f"  {status}: {n:,}")
    for field, title in [("window", "VENTANA"), ("level", "NIVEL"), ("area", "ÁREA")]:
        totals = Counter(p[field] for p in target_papers)
        resolved = Counter(r[field] for r in evidence_rows)
        lines.append(f"\n=== COBERTURA POR {title} ===")
        for key in sorted(totals):
            t = totals[key]
            r = resolved[key]
            lines.append(f"  {key}: objetivo={t:,} resueltos={r:,} cobertura={r/t*100 if t else 0:.2f}%")
    countries = Counter(r["country_code"] for r in evidence_rows)
    lines.append("\n=== TOP 30 PAÍSES RESUELTOS VIA VENUE ===")
    if countries:
        for cc, n in countries.most_common(30):
            lines.append(f"  {cc}: {n:,}")
    else:
        lines.append("  Ninguno")
    by_conf_t = Counter(p["congress"] for p in target_papers)
    by_conf_r = Counter(r["congress"] for r in evidence_rows)
    lines.append("\n=== TOP 30 CONGRESOS POR ARTÍCULOS RESUELTOS VIA VENUE ===")
    rows = [(by_conf_r[c], t, c) for c, t in by_conf_t.items() if by_conf_r[c]]
    for r, t, c in sorted(rows, reverse=True)[:30]:
        lines.append(f"  {c:18s} resueltos={r:7,d} objetivo={t:7,d} cobertura={r/t*100:.2f}%")
    lines.append("\n=== COMBOS MÁS LENTOS ===")
    for row in sorted(combo_audit, key=lambda x: float(x.get("seconds_total", 0) or 0), reverse=True)[:20]:
        lines.append(
            f"  {row['congress']:18s} {row['year']} total={float(row['seconds_total']):7.2f}s "
            f"fetch={float(row['seconds_fetch']):7.2f}s match={float(row['seconds_match']):7.2f}s "
            f"targets={row['n_targets']} results={row['n_raw_results']} pages={row['n_pages']} mode={row['query_mode']}"
        )
    return "\n".join(lines) + "\n"


def run(*, force: bool = False, limit_combos: int | None = None, limit_articles: int | None = None, max_pages: int = DEFAULT_MAX_PAGES_PER_COMBO, no_fuzzy: bool = False):
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭  Paso 6 ya completado (usa --force para repetir).")
        return
    if not OPENALEX_API_KEY:
        raise ValueError("Falta --api-key TU_OA_KEY")
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    papers = load_papers(limit_articles)
    resolved_ids = load_existing_resolved_paper_ids()
    groups = build_target_groups(papers, resolved_ids)
    combos = sorted(groups)
    if limit_combos is not None:
        combos = combos[:limit_combos]
        print(f"  ⚠️  Modo test: {limit_combos} combos")
    target_papers = [p for combo in combos for p in groups[combo]]
    print(f"  Artículos totales: {len(papers):,}")
    print(f"  Ya resueltos por OpenAlex DOI: {len(resolved_ids):,}")
    print(f"  Combos venue+año objetivo: {len(combos):,}")
    print(f"  Artículos objetivo en combos seleccionados: {len(target_papers):,}")
    print(f"  Max pages por combo: {max_pages} | fuzzy: {'no' if no_fuzzy else 'sí, acotado'}")
    venue_cache = load_json(CACHE_FILE, {})
    source_cache = load_json(SOURCE_CACHE_FILE, {})
    evidence_rows: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []
    combo_audit: list[dict[str, Any]] = []
    n_cache_hits = 0
    n_api_fetches = 0
    for idx, (congress, year) in enumerate(tqdm(combos, desc="  OpenAlex source/venue-año", unit=" combo"), start=1):
        combo_t0 = time.perf_counter()
        ck = f"{congress}|{year}|pages={max_pages}"
        venue_query = OA_VENUE_MAP[congress]
        targets = groups[(congress, year)]
        source_info = resolve_openalex_source(congress, venue_query, source_cache)
        source_id = source_info.get("source_id") or ""
        cache_hit = ck in venue_cache
        if cache_hit:
            works = venue_cache[ck].get("works", [])
            fetch_meta = venue_cache[ck].get("fetch_meta", {})
            n_cache_hits += 1
        else:
            raw_works, fetch_meta = fetch_openalex_venue_year(congress, venue_query, year, source_id=source_id, max_pages=max_pages)
            works = []
            for w in raw_works:
                title = w.get("display_name") or w.get("title") or ""
                countries = countries_from_authorships(w)
                if title and countries:
                    works.append({"openalex_id": w.get("id") or "", "doi": w.get("doi") or "", "title": title, "countries": countries})
            venue_cache[ck] = {"congress": congress, "year": year, "venue_query": venue_query, "source_info": source_info, "n_works_with_countries": len(works), "fetch_meta": fetch_meta, "works": works}
            n_api_fetches += 1
        match_t0 = time.perf_counter()
        index, token_index = build_work_index(works)
        n_resolved_papers_combo = 0
        n_evidence_combo = 0
        n_fuzzy_checked = 0
        for p in targets:
            match, matched_by, confidence, n_checked = match_paper_to_work(p.get("title", ""), index, token_index, allow_fuzzy=not no_fuzzy)
            n_fuzzy_checked += n_checked
            if not match:
                unresolved_rows.append({"paper_id": p["paper_id"], "dblp_key": p["dblp_key"], "congress": congress, "level": p["level"], "area": p["area"], "year": year, "window": p["window"], "title": p.get("title", ""), "status": matched_by, "best_title_similarity": confidence, "venue_query": venue_query, "source_id": source_id, "n_candidate_works": len(works)})
                continue
            countries = match.get("countries") or {}
            if not countries:
                unresolved_rows.append({"paper_id": p["paper_id"], "dblp_key": p["dblp_key"], "congress": congress, "level": p["level"], "area": p["area"], "year": year, "window": p["window"], "title": p.get("title", ""), "status": "matched_no_country", "best_title_similarity": confidence, "venue_query": venue_query, "source_id": source_id, "n_candidate_works": len(works)})
                continue
            n_resolved_papers_combo += 1
            for cc, inst_count in sorted(countries.items()):
                evidence_rows.append({"paper_id": p["paper_id"], "dblp_key": p["dblp_key"], "congress": congress, "level": p["level"], "area": p["area"], "year": year, "window": p["window"], "country_code": cc, "source": "openalex", "method": "source_or_venue_year_title_match", "confidence": confidence, "matched_by": matched_by, "source_work_id": match.get("openalex_id", ""), "source_doi": match.get("doi", ""), "venue_query": venue_query, "source_id": source_id, "matched_title": match.get("title", ""), "n_institutions_for_country": inst_count})
                n_evidence_combo += 1
        seconds_match = time.perf_counter() - match_t0
        seconds_total = time.perf_counter() - combo_t0
        combo_audit.append({"congress": congress, "year": year, "n_targets": len(targets), "n_resolved_papers": n_resolved_papers_combo, "n_evidence_rows": n_evidence_combo, "n_candidate_works_with_countries": len(works), "n_index_titles": len(index), "n_fuzzy_candidates_checked": n_fuzzy_checked, "venue_query": venue_query, "source_id": source_id, "source_status": source_info.get("status", ""), "source_display_name": source_info.get("display_name", ""), "query_mode": fetch_meta.get("query_mode", "cache"), "n_pages": fetch_meta.get("n_pages", 0), "n_raw_results": fetch_meta.get("n_raw_results", 0), "seconds_fetch": fetch_meta.get("seconds_fetch", 0), "seconds_match": round(seconds_match, 3), "seconds_total": round(seconds_total, 3), "cache_hit": cache_hit})
        if idx % SAVE_EVERY_COMBOS == 0:
            save_json(CACHE_FILE, venue_cache)
            save_json(SOURCE_CACHE_FILE, source_cache)
            write_csv_rows(OUTPUTS / "openalex_venue_combo_audit.csv", combo_audit, list(combo_audit[0].keys()) if combo_audit else [])
    save_json(CACHE_FILE, venue_cache)
    save_json(SOURCE_CACHE_FILE, source_cache)
    evidence_fields = ["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "country_code", "source", "method", "confidence", "matched_by", "source_work_id", "source_doi", "venue_query", "source_id", "matched_title", "n_institutions_for_country"]
    unresolved_fields = ["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "title", "status", "best_title_similarity", "venue_query", "source_id", "n_candidate_works"]
    audit_fields = list(combo_audit[0].keys()) if combo_audit else ["congress", "year", "n_targets", "n_resolved_papers", "n_evidence_rows", "n_candidate_works_with_countries", "n_index_titles", "n_fuzzy_candidates_checked", "venue_query", "source_id", "source_status", "source_display_name", "query_mode", "n_pages", "n_raw_results", "seconds_fetch", "seconds_match", "seconds_total", "cache_hit"]
    write_csv_rows(OUTPUTS / "affiliation_evidence_openalex_venue.csv", evidence_rows, evidence_fields)
    write_csv_rows(OUTPUTS / "openalex_venue_unresolved.csv", unresolved_rows, unresolved_fields)
    write_csv_rows(OUTPUTS / "openalex_venue_combo_audit.csv", combo_audit, audit_fields)
    report = report_text(papers, target_papers, evidence_rows, unresolved_rows, venue_cache, combo_audit)
    (OUTPUTS / "openalex_venue_coverage_report.txt").write_text(report, encoding="utf-8")
    result = {"step": 6, "status": "COMPLETE", "total_papers": len(papers), "already_resolved_doi": len(resolved_ids), "target_papers": len(target_papers), "resolved_papers_venue": len({r["paper_id"] for r in evidence_rows}), "evidence_rows": len(evidence_rows), "unresolved_rows": len(unresolved_rows), "venue_cache_entries": len(venue_cache), "source_cache_entries": len(source_cache), "cache_hits": n_cache_hits, "api_fetches": n_api_fetches, "max_pages_per_combo": max_pages, "fuzzy_enabled": not no_fuzzy}
    CHECKPOINT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + report)
    print("  ✅ Paso 6 completado → outputs/affiliation_evidence_openalex_venue.csv")


def main():
    global OPENALEX_API_KEY
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit-combos", type=int, default=None)
    parser.add_argument("--limit-articles", type=int, default=None)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES_PER_COMBO)
    parser.add_argument("--no-fuzzy", action="store_true", help="Solo match exacto por título; útil para test de rendimiento")
    args = parser.parse_args()
    OPENALEX_API_KEY = args.api_key
    print("=" * 70)
    print("PASO 6 — OpenAlex por source_id/venue-año")
    print("=" * 70)
    try:
        run(force=args.force, limit_combos=args.limit_combos, limit_articles=args.limit_articles, max_pages=args.max_pages, no_fuzzy=args.no_fuzzy)
    except Exception as exc:
        print(f"  ❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
