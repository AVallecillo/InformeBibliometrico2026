#!/usr/bin/env python3
"""
PASO 10 — Afiliaciones mediante OpenReview, con salida como evidencias.

Objetivo:
  Mejorar cobertura en congresos IA/ML recientes con baja cobertura en
  OpenAlex/CrossRef/DROPS, especialmente ICLR, NeurIPS, ICML y AISTATS.

Entrada:
  outputs/paper_master.csv
  outputs/affiliation_evidence_openalex_doi.csv
  outputs/affiliation_evidence_openalex_venue.csv
  outputs/affiliation_evidence_drops.csv
  outputs/affiliation_evidence_crossref.csv

Salida:
  outputs/affiliation_evidence_openreview.csv
  outputs/openreview_affiliations_cache.json
  outputs/openreview_venue_audit.csv
  outputs/openreview_unresolved.csv
  outputs/openreview_coverage_report.txt

Notas:
  - Usa OpenReview solo como fuente complementaria.
  - No reemplaza evidencias previas; solo intenta resolver papers aún sin país.
  - Produce una fila por paper_id + country_code.
  - Puede ejecutarse sin credenciales, pero algunas venues/perfiles pueden requerir auth.

Instalación:
  pip install openreview-py pandas tqdm

Uso:
  python scripts/10_resolve_affiliations_openreview.py --force
  python scripts/10_resolve_affiliations_openreview.py --username EMAIL --password PASS --force
  python scripts/10_resolve_affiliations_openreview.py --limit-venues 5 --force
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step10_openreview.json"

CACHE_FILE = OUTPUTS / "openreview_affiliations_cache.json"
EVIDENCE_FILE = OUTPUTS / "affiliation_evidence_openreview.csv"
AUDIT_FILE = OUTPUTS / "openreview_venue_audit.csv"
UNRESOLVED_FILE = OUTPUTS / "openreview_unresolved.csv"
REPORT_FILE = OUTPUTS / "openreview_coverage_report.txt"

YEAR_MIN, YEAR_MAX = 2001, 2025
TITLE_MATCH_THRESHOLD = 0.86
SAVE_EVERY_VENUES = 1
PROFILE_BATCH_SIZE = 50

# Solo venues donde OpenReview suele ser realmente útil.
# api_version: 1 legacy api.openreview.net, 2 api2.openreview.net
OPENREVIEW_VENUES: dict[str, list[tuple[str, int, int]]] = {
    "ICLR": [
        ("ICLR.cc/2013/conference", 2013, 1),
        ("ICLR.cc/2014/conference", 2014, 1),
        # 2015 no tuvo edición ICLR estándar en muchos listados; se omite salvo evidencia explícita.
        ("ICLR.cc/2016/conference", 2016, 1),
        ("ICLR.cc/2017/conference", 2017, 1),
        ("ICLR.cc/2018/Conference", 2018, 1),
        ("ICLR.cc/2019/Conference", 2019, 1),
        ("ICLR.cc/2020/Conference", 2020, 1),
        ("ICLR.cc/2021/Conference", 2021, 1),
        ("ICLR.cc/2022/Conference", 2022, 1),
        ("ICLR.cc/2023/Conference", 2023, 1),
        ("ICLR.cc/2024/Conference", 2024, 2),
        ("ICLR.cc/2025/Conference", 2025, 2),
    ],
    "NeurIPS": [
        ("NeurIPS.cc/2021/Conference", 2021, 1),
        ("NeurIPS.cc/2022/Conference", 2022, 1),
        ("NeurIPS.cc/2023/Conference", 2023, 2),
        ("NeurIPS.cc/2024/Conference", 2024, 2),
        ("NeurIPS.cc/2025/Conference", 2025, 2),
    ],
    "ICML": [
        # ICML 2022 no es fiable públicamente en OpenReview; 2023+ sí.
        ("ICML.cc/2023/Conference", 2023, 2),
        ("ICML.cc/2024/Conference", 2024, 2),
        ("ICML.cc/2025/Conference", 2025, 2),
    ],
    "AISTATS": [
        ("AISTATS.cc/2022/Conference", 2022, 2),
        ("AISTATS.cc/2023/Conference", 2023, 2),
        ("AISTATS.cc/2024/Conference", 2024, 2),
        ("AISTATS.cc/2025/Conference", 2025, 2),
    ],
    "UAI": [
        ("auai.org/UAI/2022/Conference", 2022, 2),
        ("auai.org/UAI/2023/Conference", 2023, 2),
        ("auai.org/UAI/2024/Conference", 2024, 2),
        ("auai.org/UAI/2025/Conference", 2025, 2),
    ],
    "ACMMM": [
        ("acmmm.org/MM/2023/Conference", 2023, 2),
        ("acmmm.org/MM/2024/Conference", 2024, 2),
    ],
    # CVF venues are included, but may require authentication / may expose limited data.
    "CVPR": [
        ("thecvf.com/CVPR/2023/Conference", 2023, 2),
        ("thecvf.com/CVPR/2024/Conference", 2024, 2),
        ("thecvf.com/CVPR/2025/Conference", 2025, 2),
    ],
    "ICCV": [
        ("thecvf.com/ICCV/2023/Conference", 2023, 2),
    ],
    "ECCV": [
        ("thecvf.com/ECCV/2024/Conference", 2024, 2),
    ],
}

# Dominios institucionales españoles como fallback cuando el perfil no incluye country.
ES_DOMAINS = {
    "upm.es", "ucm.es", "uam.es", "upc.edu", "upv.es", "us.es", "ugr.es",
    "uv.es", "unizar.es", "ub.edu", "usc.es", "uva.es", "uvigo.es", "uab.cat",
    "uab.es", "uc3m.es", "uned.es", "urjc.es", "uma.es", "ual.es", "uco.es",
    "uji.es", "uah.es", "bsc.es", "csic.es", "imdea.org", "telefonica.com",
    "iri.upc.edu", "cvc.uab.es", "vicomtech.org", "tecnalia.com", "tecnalia.es",
}

COUNTRY_NORMALIZATION = {
    "uk": "GB",
    "united kingdom": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "usa": "US",
    "u.s.a.": "US",
    "united states": "US",
    "united states of america": "US",
    "korea": "KR",
    "south korea": "KR",
    "republic of korea": "KR",
    "czech republic": "CZ",
    "czechia": "CZ",
    "russian federation": "RU",
    "iran": "IR",
    "hong kong": "HK",
    "taiwan": "TW",
}

VALID_ISO2_RE = re.compile(r"^[A-Z]{2}$")


def is_missing(x: Any) -> bool:
    if x is None:
        return True
    try:
        if pd.isna(x):
            return True
    except Exception:
        pass
    if isinstance(x, str) and not x.strip():
        return True
    return False


def normalize_title(t: Any) -> str:
    if is_missing(t):
        return ""
    s = str(t).lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def title_similarity_norm(a_norm: str, b_norm: str) -> float:
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    wa, wb = set(a_norm.split()), set(b_norm.split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def normalize_country(raw: Any) -> str | None:
    if is_missing(raw):
        return None
    s = str(raw).strip()
    if not s:
        return None
    up = s.upper()
    if VALID_ISO2_RE.match(up):
        return up
    low = s.lower().strip(" .")
    if low in COUNTRY_NORMALIZATION:
        return COUNTRY_NORMALIZATION[low]
    # OpenReview country fields are usually already ISO or names; use pycountry if present.
    try:
        import pycountry  # type: ignore
        obj = pycountry.countries.lookup(s)
        if obj and getattr(obj, "alpha_2", None):
            return obj.alpha_2
    except Exception:
        pass
    return None


def get_clients(username: str | None = None, password: str | None = None):
    try:
        import openreview  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Falta openreview-py. Instala con: pip install openreview-py") from exc

    kwargs = {}
    env_user = os.environ.get("OPENREVIEW_USERNAME") or None
    env_pass = os.environ.get("OPENREVIEW_PASSWORD") or None
    username = username or env_user
    password = password or env_pass
    if username and password:
        kwargs = {"username": username, "password": password}
        print(f"  OpenReview: autenticado como {username}")
    else:
        print("  OpenReview: API pública sin autenticación")

    client_v1 = openreview.Client(baseurl="https://api.openreview.net", **kwargs)
    client_v2 = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net", **kwargs)
    return openreview, client_v1, client_v2


def content_value(content: dict, key: str, default=None):
    val = content.get(key, default)
    if isinstance(val, dict) and "value" in val:
        return val.get("value", default)
    return val


def extract_title(note: Any, api_version: int) -> str:
    try:
        return str(content_value(note.content, "title", "") or "").strip()
    except Exception:
        return ""


def extract_authorids(note: Any, api_version: int) -> list[str]:
    try:
        ids = content_value(note.content, "authorids", [])
        if not ids:
            ids = content_value(note.content, "authors", [])
        if isinstance(ids, str):
            ids = [ids]
        return [str(x) for x in ids if x]
    except Exception:
        return []


def note_is_accepted(note: Any) -> bool:
    try:
        venue = str(content_value(note.content, "venue", "") or "")
        venueid = str(content_value(note.content, "venueid", "") or "")
        decision = str(content_value(note.content, "decision", "") or "")
        joined = " ".join([venue, venueid, decision]).lower()
        if any(bad in joined for bad in ["reject", "rejected", "withdraw", "withdrawn", "desk reject"]):
            return False
        if any(good in joined for good in ["accept", "accepted", "poster", "oral", "spotlight"]):
            return True
        # If venueid exists in OpenReview accepted notes, often enough.
        return bool(venueid)
    except Exception:
        return True


def get_accepted_papers_v2(openreview_mod, client_v2, venue_id: str) -> list[Any]:
    """Try several OpenReview v2 patterns for accepted papers."""
    notes: list[Any] = []
    domain_candidates = [venue_id]
    try:
        group = client_v2.get_group(venue_id)
        if getattr(group, "domain", None):
            domain_candidates.insert(0, group.domain)
    except Exception:
        pass

    # Most reliable: all notes whose venueid is the venue domain/id.
    for domain in domain_candidates:
        try:
            got = client_v2.get_all_notes(content={"venueid": domain})
            if got:
                notes = got
                break
        except Exception:
            pass

    # Fallback invitation patterns.
    if not notes:
        inv_suffixes = [
            "/-/Submission",
            "/-/Blind_Submission",
            "/-/Paper_Decision",
            "/-/Decision",
            "/-/Acceptance",
        ]
        for domain in domain_candidates:
            for suffix in inv_suffixes:
                try:
                    got = client_v2.get_all_notes(invitation=f"{domain}{suffix}")
                    if got:
                        notes = got
                        break
                except Exception:
                    pass
            if notes:
                break

    return [n for n in notes if note_is_accepted(n)]


def get_accepted_papers_v1(openreview_mod, client_v1, venue_id: str) -> list[Any]:
    """Try several OpenReview v1 patterns for accepted papers."""
    notes: list[Any] = []
    invitation_suffixes = ["/-/Blind_Submission", "/-/Submission", "/-/submission"]
    for suffix in invitation_suffixes:
        try:
            got = list(openreview_mod.tools.iterget_notes(client_v1, invitation=f"{venue_id}{suffix}"))
            if got:
                notes = got
                break
        except Exception:
            pass

    if not notes:
        return []

    # Try to collect explicit accept decisions.
    accepted_forums: set[str] = set()
    decision_invs = [
        f"{venue_id}/-/Decision",
        f"{venue_id}/-/Paper_Decision",
        f"{venue_id}/-/Acceptance",
    ]
    for inv in decision_invs:
        try:
            decisions = list(openreview_mod.tools.iterget_notes(client_v1, invitation=inv))
            for d in decisions:
                decision = str(content_value(d.content, "decision", "") or "")
                if "accept" in decision.lower():
                    accepted_forums.add(d.forum)
        except Exception:
            pass

    if accepted_forums:
        notes = [n for n in notes if getattr(n, "forum", None) in accepted_forums]

    return [n for n in notes if note_is_accepted(n)]


def country_from_profile(profile: Any, pub_year: int) -> str | None:
    """Resolve a profile country, preferring affiliation active in publication year."""
    try:
        content = getattr(profile, "content", {}) or {}
        history = content.get("history", []) or []
        if isinstance(history, dict):
            history = [history]

        def start_year(h: dict) -> int:
            try:
                return int(h.get("start") or 0)
            except Exception:
                return 0

        # Prefer active at pub_year, then latest before pub_year, then latest overall.
        candidates: list[dict] = []
        hist_sorted = sorted([h for h in history if isinstance(h, dict)], key=start_year, reverse=True)
        active = []
        before = []
        for h in hist_sorted:
            start = h.get("start")
            end = h.get("end")
            try:
                start_i = int(start) if start else None
            except Exception:
                start_i = None
            try:
                end_i = int(end) if end else None
            except Exception:
                end_i = None
            if start_i and start_i <= pub_year and (end_i is None or end_i >= pub_year):
                active.append(h)
            elif start_i and start_i <= pub_year:
                before.append(h)
        candidates = active + before + hist_sorted

        for h in candidates:
            inst = h.get("institution", {}) or {}
            if not isinstance(inst, dict):
                continue
            cc = normalize_country(inst.get("country"))
            if cc:
                return cc
            domain = str(inst.get("domain") or "").lower().strip()
            if domain in ES_DOMAINS:
                return "ES"
            # Some profiles store institution name only.
            name = str(inst.get("name") or "").lower()
            if any(tok in name for tok in ["spain", "españa", "espana"]):
                return "ES"
        return None
    except Exception:
        return None


def load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"venues": {}, "profiles": {}}


def safe_save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    # Windows/Dropbox tolerant replace.
    for attempt in range(10):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(0.5 * (attempt + 1))
    backup = path.with_suffix(path.suffix + f".{int(time.time())}.bak")
    tmp.replace(backup)
    print(f"  ⚠️ No se pudo reemplazar {path.name}; progreso guardado en {backup.name}")


def load_paper_master() -> pd.DataFrame:
    path = OUTPUTS / "paper_master.csv"
    if not path.exists():
        raise FileNotFoundError("No existe outputs/paper_master.csv. Ejecuta el paso 4.")
    df = pd.read_csv(path, dtype={"paper_id": "string", "dblp_key": "string", "congress": "string"}, low_memory=False)
    required = {"paper_id", "dblp_key", "congress", "level", "area", "year", "window", "title", "doi", "booktitle"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en paper_master.csv: {sorted(missing)}")
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    return df


def load_resolved_paper_ids() -> set[str]:
    files = [
        OUTPUTS / "affiliation_evidence_openalex_doi.csv",
        OUTPUTS / "affiliation_evidence_openalex_venue.csv",
        OUTPUTS / "affiliation_evidence_drops.csv",
        OUTPUTS / "affiliation_evidence_crossref.csv",
    ]
    resolved: set[str] = set()
    for path in files:
        if not path.exists():
            continue
        try:
            # Only need paper_id.
            for chunk in pd.read_csv(path, usecols=["paper_id"], dtype={"paper_id": "string"}, chunksize=200_000):
                resolved.update(str(x) for x in chunk["paper_id"].dropna().tolist())
        except Exception:
            pass
    return resolved


def build_target_index(papers: pd.DataFrame, resolved: set[str]) -> tuple[dict[tuple[str, int], dict[str, list[dict]]], int]:
    target_confs = set(OPENREVIEW_VENUES)
    targets = papers[
        (~papers["paper_id"].astype(str).isin(resolved))
        & (papers["congress"].astype(str).isin(target_confs))
        & (papers["year"].notna())
    ].copy()

    idx: dict[tuple[str, int], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in targets.to_dict("records"):
        year = int(row["year"])
        key = (str(row["congress"]), year)
        norm = normalize_title(row.get("title"))
        if norm:
            idx[key][norm].append(row)
    return idx, len(targets)


def best_match(title_norm: str, target_titles: dict[str, list[dict]]) -> tuple[dict | None, float, str]:
    if title_norm in target_titles:
        # If duplicate titles in DBLP, take the first; rare and later dedup handles country.
        return target_titles[title_norm][0], 1.0, "title_exact"
    # Token-gated fuzzy matching.
    words = set(title_norm.split())
    if not words:
        return None, 0.0, "none"
    best_row = None
    best_sim = 0.0
    for cand_norm, rows in target_titles.items():
        cand_words = set(cand_norm.split())
        if not cand_words:
            continue
        # Gate: at least 3 shared words or high overlap in short titles.
        shared = len(words & cand_words)
        if shared < 3 and shared / max(len(words), len(cand_words)) < 0.75:
            continue
        sim = shared / max(len(words), len(cand_words))
        if sim > best_sim:
            best_sim = sim
            best_row = rows[0]
    if best_row is not None and best_sim >= TITLE_MATCH_THRESHOLD:
        return best_row, best_sim, "title_fuzzy"
    return None, best_sim, "none"


def get_profiles_cached(openreview_mod, client, author_ids: list[str], cache: dict) -> dict[str, Any]:
    profiles_cache = cache.setdefault("profiles", {})
    out: dict[str, Any] = {}
    missing = [aid for aid in sorted(set(author_ids)) if aid.startswith("~") and aid not in profiles_cache]

    # Batch where possible.
    for i in range(0, len(missing), PROFILE_BATCH_SIZE):
        batch = missing[i:i + PROFILE_BATCH_SIZE]
        try:
            profs = openreview_mod.tools.get_profiles(client, batch, as_dict=True)
            if profs:
                for aid in batch:
                    p = profs.get(aid)
                    if p:
                        # Store only content; objects are not JSON serializable.
                        profiles_cache[aid] = getattr(p, "content", {}) or {}
                    else:
                        profiles_cache[aid] = None
            else:
                for aid in batch:
                    profiles_cache[aid] = None
        except Exception:
            for aid in batch:
                try:
                    p = client.get_profile(aid)
                    profiles_cache[aid] = getattr(p, "content", {}) if p else None
                except Exception:
                    profiles_cache[aid] = None
        time.sleep(0.2)

    # Convert cached dict content to lightweight object with .content for reuse.
    class ProfileLite:
        def __init__(self, content):
            self.content = content or {}

    for aid in sorted(set(author_ids)):
        val = profiles_cache.get(aid)
        if val:
            out[aid] = ProfileLite(val)
    return out


def process_venue(openreview_mod, client_v1, client_v2, congress: str, venue_id: str, year: int, api_version: int,
                  targets: dict[str, list[dict]], cache: dict, limit_papers: int | None = None) -> tuple[list[dict], dict]:
    venue_key = f"{congress}|{year}|{venue_id}|v{api_version}"
    venues_cache = cache.setdefault("venues", {})
    audit = {
        "congress": congress,
        "year": year,
        "venue_id": venue_id,
        "api_version": api_version,
        "n_targets": sum(len(v) for v in targets.values()),
        "n_notes": 0,
        "n_matched_papers": 0,
        "n_evidence_rows": 0,
        "n_profiles": 0,
        "seconds": 0.0,
        "status": "ok",
    }
    t0 = time.time()

    if venue_key in venues_cache:
        cached = venues_cache[venue_key]
        audit.update(cached.get("audit", {}))
        audit["status"] = "cached"
        return cached.get("evidence", []), audit

    try:
        if api_version == 2:
            notes = get_accepted_papers_v2(openreview_mod, client_v2, venue_id)
            profile_client = client_v2
        else:
            notes = get_accepted_papers_v1(openreview_mod, client_v1, venue_id)
            profile_client = client_v1
    except Exception as exc:
        audit["status"] = f"venue_error:{type(exc).__name__}"
        audit["seconds"] = round(time.time() - t0, 3)
        venues_cache[venue_key] = {"evidence": [], "audit": audit}
        return [], audit

    if limit_papers:
        notes = notes[:limit_papers]
    audit["n_notes"] = len(notes)

    matched_items = []
    all_author_ids: list[str] = []
    for note in notes:
        title = extract_title(note, api_version)
        norm = normalize_title(title)
        row, sim, matched_by = best_match(norm, targets)
        if not row:
            continue
        author_ids = extract_authorids(note, api_version)
        if not author_ids:
            continue
        matched_items.append((row, title, sim, matched_by, author_ids))
        all_author_ids.extend([a for a in author_ids if a.startswith("~")])

    audit["n_matched_papers"] = len({str(x[0]["paper_id"]) for x in matched_items})
    profiles = get_profiles_cached(openreview_mod, profile_client, all_author_ids, cache)
    audit["n_profiles"] = len(profiles)

    evidence_rows: list[dict] = []
    seen = set()
    for row, matched_title, sim, matched_by, author_ids in matched_items:
        countries = set()
        for aid in author_ids:
            prof = profiles.get(aid)
            if not prof:
                continue
            cc = country_from_profile(prof, int(year))
            if cc:
                countries.add(cc)
        for cc in sorted(countries):
            key = (str(row["paper_id"]), cc)
            if key in seen:
                continue
            seen.add(key)
            evidence_rows.append({
                "paper_id": row["paper_id"],
                "dblp_key": row["dblp_key"],
                "congress": row["congress"],
                "level": row["level"],
                "area": row["area"],
                "year": int(row["year"]),
                "window": row["window"],
                "country_code": cc,
                "source": "openreview",
                "method": "venue_profile_title_match",
                "confidence": round(float(sim), 4),
                "matched_by": matched_by,
                "source_work_id": venue_id,
                "doi": "" if is_missing(row.get("doi")) else str(row.get("doi")),
                "matched_title": matched_title,
                "n_authors_with_profiles": len([a for a in author_ids if a in profiles]),
            })

    audit["n_evidence_rows"] = len(evidence_rows)
    audit["seconds"] = round(time.time() - t0, 3)
    venues_cache[venue_key] = {"evidence": evidence_rows, "audit": audit}
    return evidence_rows, audit


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def build_report(papers: pd.DataFrame, target_total: int, evidence: list[dict], audits: list[dict]) -> str:
    ev_df = pd.DataFrame(evidence)
    lines = []
    lines.append("=== PASO 10 — OPENREVIEW ===\n")
    lines.append(f"Artículos en paper_master: {len(papers):,}")
    lines.append(f"Artículos objetivo OpenReview sin país previo: {target_total:,}")
    n_papers = ev_df["paper_id"].nunique() if not ev_df.empty else 0
    lines.append(f"Artículos con >=1 país vía OpenReview: {n_papers:,}")
    lines.append(f"Cobertura sobre objetivo OpenReview: {n_papers / max(target_total, 1) * 100:.2f}%")
    lines.append(f"Filas de evidencia paper-país: {len(evidence):,}")
    lines.append(f"Venues/años auditados: {len(audits):,}\n")

    if not ev_df.empty:
        lines.append("=== TOP PAÍSES VIA OPENREVIEW ===")
        for cc, n in ev_df.groupby("country_code")["paper_id"].nunique().sort_values(ascending=False).head(30).items():
            lines.append(f"  {cc}: {int(n):,}")
        lines.append("")

        lines.append("=== TOP CONGRESOS VIA OPENREVIEW ===")
        by_conf = ev_df.groupby("congress")["paper_id"].nunique().sort_values(ascending=False).head(30)
        for conf, n in by_conf.items():
            lines.append(f"  {conf:16s} {int(n):7,d}")
        lines.append("")

        lines.append("=== COBERTURA POR VENTANA ===")
        target_rows = []
        # target denominator for OR venues only by window
        # Use audit n_targets by venue-year as approximate unique target per year; safer derive from papers in target confs unresolved not available here.
        for window, n in ev_df.groupby("window")["paper_id"].nunique().sort_index().items():
            lines.append(f"  {window}: resueltos={int(n):,}")
        lines.append("")

    lines.append("=== AUDITORÍA VENUES/AÑOS ===")
    if audits:
        aud_df = pd.DataFrame(audits)
        aud_df = aud_df.sort_values(["n_evidence_rows", "n_matched_papers"], ascending=False)
        for r in aud_df.head(40).to_dict("records"):
            lines.append(
                f"  {str(r.get('congress')):10s} {int(r.get('year')):4d} "
                f"targets={int(r.get('n_targets', 0)):5d} notes={int(r.get('n_notes', 0)):5d} "
                f"matched={int(r.get('n_matched_papers', 0)):5d} evidence={int(r.get('n_evidence_rows', 0)):5d} "
                f"profiles={int(r.get('n_profiles', 0)):5d} sec={float(r.get('seconds', 0)):.1f} "
                f"status={r.get('status')}"
            )
    else:
        lines.append("  Ninguna auditoría generada")

    lines.append("\n=== SALIDAS GENERADAS ===")
    lines.append(f"  {EVIDENCE_FILE}")
    lines.append(f"  {AUDIT_FILE}")
    lines.append(f"  {UNRESOLVED_FILE}")
    lines.append(f"  {REPORT_FILE}")
    return "\n".join(lines)


def run(username=None, password=None, force=False, limit_venues: int | None = None, limit_papers: int | None = None):
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭  Paso 10 ya completado (usa --force para repetir).")
        return

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    papers = load_paper_master()
    resolved = load_resolved_paper_ids()
    target_index, target_total = build_target_index(papers, resolved)

    print(f"  Artículos en paper_master: {len(papers):,}")
    print(f"  Ya resueltos por fuentes previas: {len(resolved):,}")
    print(f"  Objetivo OpenReview sin país previo: {target_total:,}")
    print(f"  Ediciones objetivo (congress, year): {len(target_index):,}")

    if target_total == 0:
        write_csv(EVIDENCE_FILE, [], [
            "paper_id", "dblp_key", "congress", "level", "area", "year", "window", "country_code",
            "source", "method", "confidence", "matched_by", "source_work_id", "doi", "matched_title",
            "n_authors_with_profiles",
        ])
        REPORT_FILE.write_text(build_report(papers, target_total, [], []), encoding="utf-8")
        return

    openreview_mod, client_v1, client_v2 = get_clients(username, password)
    cache = load_cache()

    jobs = []
    for congress, venues in OPENREVIEW_VENUES.items():
        for venue_id, year, api_ver in venues:
            if (congress, year) in target_index:
                jobs.append((congress, venue_id, year, api_ver))
    jobs = sorted(jobs, key=lambda x: (x[0], x[2], x[1]))
    if limit_venues:
        jobs = jobs[:limit_venues]
        print(f"  ⚠️ Modo test: {limit_venues} venues/años")

    print(f"  Venues/años OpenReview a procesar: {len(jobs):,}")

    evidence: list[dict] = []
    audits: list[dict] = []
    for i, (congress, venue_id, year, api_ver) in enumerate(tqdm(jobs, desc="  OpenReview venues")):
        targets = target_index.get((congress, year), {})
        ev, audit = process_venue(
            openreview_mod, client_v1, client_v2,
            congress, venue_id, year, api_ver,
            targets, cache, limit_papers=limit_papers,
        )
        evidence.extend(ev)
        audits.append(audit)
        if (i + 1) % SAVE_EVERY_VENUES == 0:
            safe_save_json(CACHE_FILE, cache)

    safe_save_json(CACHE_FILE, cache)

    # Deduplicate evidence paper-country.
    dedup = {}
    for r in evidence:
        key = (str(r.get("paper_id")), str(r.get("country_code")))
        if key not in dedup or float(r.get("confidence", 0) or 0) > float(dedup[key].get("confidence", 0) or 0):
            dedup[key] = r
    evidence = list(dedup.values())

    ev_fields = [
        "paper_id", "dblp_key", "congress", "level", "area", "year", "window", "country_code",
        "source", "method", "confidence", "matched_by", "source_work_id", "doi", "matched_title",
        "n_authors_with_profiles",
    ]
    write_csv(EVIDENCE_FILE, evidence, ev_fields)

    audit_fields = [
        "congress", "year", "venue_id", "api_version", "n_targets", "n_notes", "n_matched_papers",
        "n_evidence_rows", "n_profiles", "seconds", "status",
    ]
    write_csv(AUDIT_FILE, audits, audit_fields)

    # Unresolved within OpenReview target set.
    resolved_or = {str(r["paper_id"]) for r in evidence}
    target_paper_ids = set()
    for targets in target_index.values():
        for rows in targets.values():
            for row in rows:
                target_paper_ids.add(str(row["paper_id"]))
    unresolved_ids = target_paper_ids - resolved_or
    unresolved = papers[papers["paper_id"].astype(str).isin(unresolved_ids)].copy()
    unresolved.to_csv(UNRESOLVED_FILE, index=False)

    report = build_report(papers, target_total, evidence, audits)
    REPORT_FILE.write_text(report, encoding="utf-8")
    print("\n" + report)

    result = {
        "step": 10,
        "status": "COMPLETE",
        "target_papers": int(target_total),
        "resolved_papers": int(len(resolved_or)),
        "evidence_rows": int(len(evidence)),
        "venues_processed": int(len(audits)),
    }
    CHECKPOINT_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("\n  ✅ Paso 10 completado → outputs/affiliation_evidence_openreview.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default=None, help="Usuario OpenReview; también puede usarse OPENREVIEW_USERNAME")
    parser.add_argument("--password", default=None, help="Password OpenReview; también puede usarse OPENREVIEW_PASSWORD")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit-venues", type=int, default=None)
    parser.add_argument("--limit-papers", type=int, default=None, help="Limita papers por venue para pruebas")
    args = parser.parse_args()

    print("=" * 70)
    print("PASO 10 — Afiliaciones desde OpenReview")
    print("=" * 70)
    try:
        run(
            username=args.username,
            password=args.password,
            force=args.force,
            limit_venues=args.limit_venues,
            limit_papers=args.limit_papers,
        )
    except Exception as exc:
        print(f"❌ Error: {exc}")
        sys.exit(1)
