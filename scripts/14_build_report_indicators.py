#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PASO 14 v2 — Indicadores bibliométricos ampliados para el informe

Amplía el paso 14 con comparativas europeas explícitas:
  - cuotas por país europeo y ventana;
  - comparadores principales en formato ancho;
  - ratio España/Italia;
  - factores de crecimiento 2001-2005 → 2021-2025;
  - rankings europeos por nivel A*/A;
  - top congresos españoles por ventana;
  - clasificación descriptiva de tendencias por país.

Entradas:
  outputs/paper_master.csv
  outputs/paper_country.csv
  outputs/congress_area_subarea.csv   (opcional)

Salidas nuevas principales:
  outputs/report_indicators_primary_comparators_wide.csv
  outputs/report_indicators_europe_growth_factors.csv
  outputs/report_indicators_es_it_ratio_by_window.csv
  outputs/report_indicators_country_level_window.csv
  outputs/report_indicators_country_ranking_europe_by_level_window.csv
  outputs/report_indicators_europe_trend_classes.csv
  outputs/report_indicators_top_congresses_spain_by_window.csv

Uso:
  python scripts/14_build_report_indicators.py --force
  python scripts/14_build_report_indicators.py --include-bioinformatics --force
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step14_report_indicators.json"

PAPER_MASTER = OUTPUTS / "paper_master.csv"
PAPER_COUNTRY = OUTPUTS / "paper_country.csv"
AREA_SUBAREA = OUTPUTS / "congress_area_subarea.csv"

WINDOWS = ["2001-2005", "2006-2010", "2011-2015", "2016-2020", "2021-2025"]
LEVELS = ["A*", "A"]

EU27 = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
}
EU27_PLUS_UK = EU27 | {"GB"}
PRIMARY_EU_COMPARATORS = ["GB", "DE", "FR", "IT", "NL", "ES", "PT"]

COUNTRY_NAMES = {
    "ES": "Spain", "GB": "United Kingdom", "DE": "Germany", "FR": "France", "IT": "Italy",
    "NL": "Netherlands", "PT": "Portugal", "US": "United States", "CN": "China", "CA": "Canada",
    "JP": "Japan", "AU": "Australia", "CH": "Switzerland", "SE": "Sweden", "AT": "Austria",
    "BE": "Belgium", "DK": "Denmark", "FI": "Finland", "PL": "Poland", "CZ": "Czechia",
    "IE": "Ireland", "NO": "Norway", "GR": "Greece", "IL": "Israel", "IN": "India",
    "SG": "Singapore", "KR": "South Korea", "HK": "Hong Kong", "TW": "Taiwan", "BR": "Brazil",
}

AREA_REPORT_LABELS_DEFAULT = {
    "Sistemas": "Sistemas, arquitectura y computación",
}


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No se encuentra {path}")


def pct(num: float, den: float) -> float:
    if den is None or den == 0 or pd.isna(den):
        return float("nan")
    return round(float(num) / float(den), 6)


def pct100(num: float, den: float) -> float:
    if den is None or den == 0 or pd.isna(den):
        return float("nan")
    return round(100.0 * float(num) / float(den), 3)


def safe_int(x) -> int:
    if x is None or pd.isna(x):
        return 0
    return int(x)


def add_area_report_label(df: pd.DataFrame, area_labels: dict[str, str]) -> pd.DataFrame:
    out = df.copy()
    out["area_report_label"] = out["area"].map(area_labels).fillna(out["area"])
    return out


def load_area_labels() -> dict[str, str]:
    labels = dict(AREA_REPORT_LABELS_DEFAULT)
    if AREA_SUBAREA.exists():
        try:
            df = pd.read_csv(AREA_SUBAREA, usecols=lambda c: c in {"area", "area_report_label"})
            if {"area", "area_report_label"}.issubset(df.columns):
                for _, row in df.drop_duplicates("area").iterrows():
                    area = str(row["area"])
                    label = str(row["area_report_label"])
                    if area and label and label.lower() != "nan":
                        labels[area] = label
        except Exception:
            pass
    return labels


def paper_sets_by_group(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    return df.groupby(group_cols, dropna=False)["paper_id"].nunique().reset_index(name="total_articles")


def resolved_sets_by_group(pc: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    return pc.groupby(group_cols, dropna=False)["paper_id"].nunique().reset_index(name="resolved_articles")


def country_counts(pc: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    return pc.groupby(group_cols + ["country_code"], dropna=False)["paper_id"].nunique().reset_index(name="country_articles")


def eu_papers_by_group(pc: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    eu = pc[pc["country_code"].isin(EU27_PLUS_UK)]
    return eu.groupby(group_cols, dropna=False)["paper_id"].nunique().reset_index(name="eu27_uk_articles")


def spain_papers_by_group(pc: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    es = pc[pc["country_code"] == "ES"]
    return es.groupby(group_cols, dropna=False)["paper_id"].nunique().reset_index(name="spain_articles")


def merge_basic_metrics(master: pd.DataFrame, pc: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    total = paper_sets_by_group(master, group_cols)
    resolved = resolved_sets_by_group(pc, group_cols)
    eu = eu_papers_by_group(pc, group_cols)
    es = spain_papers_by_group(pc, group_cols)
    out = total.merge(resolved, on=group_cols, how="left")
    out = out.merge(eu, on=group_cols, how="left")
    out = out.merge(es, on=group_cols, how="left")
    for col in ["resolved_articles", "eu27_uk_articles", "spain_articles"]:
        out[col] = out[col].fillna(0).astype(int)
    out["unresolved_articles"] = out["total_articles"] - out["resolved_articles"]
    out["coverage_rate"] = out.apply(lambda r: pct(r["resolved_articles"], r["total_articles"]), axis=1)
    out["coverage_pct"] = out.apply(lambda r: pct100(r["resolved_articles"], r["total_articles"]), axis=1)
    out["spain_share_world_resolved"] = out.apply(lambda r: pct(r["spain_articles"], r["resolved_articles"]), axis=1)
    out["spain_share_eu27_uk"] = out.apply(lambda r: pct(r["spain_articles"], r["eu27_uk_articles"]), axis=1)
    out["spain_share_eu27_uk_pct"] = out.apply(lambda r: pct100(r["spain_articles"], r["eu27_uk_articles"]), axis=1)
    return out


def sort_windows(df: pd.DataFrame) -> pd.DataFrame:
    if "window" in df.columns:
        df = df.copy()
        df["window"] = pd.Categorical(df["window"], categories=WINDOWS, ordered=True)
        return df.sort_values("window")
    return df


def build_global_by_window(master: pd.DataFrame, pc: pd.DataFrame) -> pd.DataFrame:
    return sort_windows(merge_basic_metrics(master, pc, ["window"]))


def build_country_by_window(pc: pd.DataFrame) -> pd.DataFrame:
    out = country_counts(pc, ["window"])
    eu_den = eu_papers_by_group(pc, ["window"])
    res_den = resolved_sets_by_group(pc, ["window"])
    out = out.merge(eu_den, on="window", how="left").merge(res_den, on="window", how="left")
    out["country_name"] = out["country_code"].map(COUNTRY_NAMES).fillna(out["country_code"])
    out["is_eu27_uk"] = out["country_code"].isin(EU27_PLUS_UK)
    out["share_resolved"] = out.apply(lambda r: pct(r["country_articles"], r["resolved_articles"]), axis=1)
    out["share_resolved_pct"] = out.apply(lambda r: pct100(r["country_articles"], r["resolved_articles"]), axis=1)
    out["share_eu27_uk"] = out.apply(lambda r: pct(r["country_articles"], r["eu27_uk_articles"]), axis=1)
    out["share_eu27_uk_pct"] = out.apply(lambda r: pct100(r["country_articles"], r["eu27_uk_articles"]), axis=1)
    out["window"] = pd.Categorical(out["window"], categories=WINDOWS, ordered=True)
    return out.sort_values(["window", "country_articles"], ascending=[True, False])


def build_country_ranking_europe_by_window(pc: pd.DataFrame) -> pd.DataFrame:
    out = build_country_by_window(pc)
    out = out[out["country_code"].isin(EU27_PLUS_UK)].copy()
    out["rank_eu27_uk"] = out.groupby("window", observed=False)["country_articles"].rank(method="min", ascending=False).astype(int)
    return out.sort_values(["window", "rank_eu27_uk", "country_code"])[
        ["window", "rank_eu27_uk", "country_code", "country_name", "country_articles", "eu27_uk_articles", "share_eu27_uk", "share_eu27_uk_pct"]
    ]


def build_spain_europe_by_window(master: pd.DataFrame, pc: pd.DataFrame) -> pd.DataFrame:
    out = merge_basic_metrics(master, pc, ["window"])
    cc = country_counts(pc[pc["country_code"].isin(PRIMARY_EU_COMPARATORS)], ["window"])
    pivot = cc.pivot(index="window", columns="country_code", values="country_articles").reset_index()
    for c in PRIMARY_EU_COMPARATORS:
        if c not in pivot.columns:
            pivot[c] = 0
    out = out.merge(pivot[["window"] + PRIMARY_EU_COMPARATORS], on="window", how="left")
    for c in PRIMARY_EU_COMPARATORS:
        out[c] = out[c].fillna(0).astype(int)
    es_ranks = build_country_ranking_europe_by_window(pc)
    es_ranks = es_ranks[es_ranks["country_code"] == "ES"][["window", "rank_eu27_uk"]]
    out = out.merge(es_ranks, on="window", how="left")
    out.rename(columns={"rank_eu27_uk": "rank_spain_eu27_uk"}, inplace=True)
    out["ratio_ES_IT"] = out.apply(lambda r: pct(r.get("ES", 0), r.get("IT", 0)), axis=1)
    out["ratio_ES_FR"] = out.apply(lambda r: pct(r.get("ES", 0), r.get("FR", 0)), axis=1)
    out["ratio_ES_DE"] = out.apply(lambda r: pct(r.get("ES", 0), r.get("DE", 0)), axis=1)
    out["ratio_ES_GB"] = out.apply(lambda r: pct(r.get("ES", 0), r.get("GB", 0)), axis=1)
    return sort_windows(out)


def build_country_by_area_window(pc: pd.DataFrame, area_labels: dict[str, str], include_bio: bool) -> pd.DataFrame:
    pc_area = pc.copy()
    if not include_bio:
        pc_area = pc_area[pc_area["area"] != "Bioinformática"].copy()
    out = country_counts(pc_area, ["area", "window"])
    out = add_area_report_label(out, area_labels)
    eu_den = eu_papers_by_group(pc_area, ["area", "window"])
    res_den = resolved_sets_by_group(pc_area, ["area", "window"])
    out = out.merge(eu_den, on=["area", "window"], how="left").merge(res_den, on=["area", "window"], how="left")
    out["country_name"] = out["country_code"].map(COUNTRY_NAMES).fillna(out["country_code"])
    out["is_eu27_uk"] = out["country_code"].isin(EU27_PLUS_UK)
    out["share_resolved"] = out.apply(lambda r: pct(r["country_articles"], r["resolved_articles"]), axis=1)
    out["share_eu27_uk"] = out.apply(lambda r: pct(r["country_articles"], r["eu27_uk_articles"]), axis=1)
    out["share_eu27_uk_pct"] = out.apply(lambda r: pct100(r["country_articles"], r["eu27_uk_articles"]), axis=1)
    out["window"] = pd.Categorical(out["window"], categories=WINDOWS, ordered=True)
    return out.sort_values(["area_report_label", "window", "country_articles"], ascending=[True, True, False])


def build_country_ranking_europe_by_area_window(pc: pd.DataFrame, area_labels: dict[str, str], include_bio: bool) -> pd.DataFrame:
    out = build_country_by_area_window(pc, area_labels, include_bio)
    out = out[out["country_code"].isin(EU27_PLUS_UK)].copy()
    out["rank_eu27_uk"] = out.groupby(["area", "window"], observed=False)["country_articles"].rank(method="min", ascending=False).astype(int)
    return out.sort_values(["area_report_label", "window", "rank_eu27_uk"])[
        ["area", "area_report_label", "window", "rank_eu27_uk", "country_code", "country_name", "country_articles", "eu27_uk_articles", "share_eu27_uk", "share_eu27_uk_pct"]
    ]


def build_spain_by_area_window(master: pd.DataFrame, pc: pd.DataFrame, area_labels: dict[str, str], include_bio: bool) -> pd.DataFrame:
    m = master.copy()
    p = pc.copy()
    if not include_bio:
        m = m[m["area"] != "Bioinformática"].copy()
        p = p[p["area"] != "Bioinformática"].copy()
    out = merge_basic_metrics(m, p, ["area", "window"])
    out = add_area_report_label(out, area_labels)
    ranks = build_country_ranking_europe_by_area_window(p, area_labels, include_bio=True)
    es_ranks = ranks[ranks["country_code"] == "ES"][["area", "window", "rank_eu27_uk"]]
    out = out.merge(es_ranks, on=["area", "window"], how="left")
    out["window"] = pd.Categorical(out["window"], categories=WINDOWS, ordered=True)
    return out.sort_values(["area_report_label", "window"])


def build_spain_by_level_window(master: pd.DataFrame, pc: pd.DataFrame) -> pd.DataFrame:
    out = merge_basic_metrics(master, pc, ["level", "window"])
    out["level"] = pd.Categorical(out["level"], categories=LEVELS, ordered=True)
    out["window"] = pd.Categorical(out["window"], categories=WINDOWS, ordered=True)
    return out.sort_values(["level", "window"])


def build_country_level_window(pc: pd.DataFrame) -> pd.DataFrame:
    out = country_counts(pc, ["level", "window"])
    eu_den = eu_papers_by_group(pc, ["level", "window"])
    res_den = resolved_sets_by_group(pc, ["level", "window"])
    out = out.merge(eu_den, on=["level", "window"], how="left").merge(res_den, on=["level", "window"], how="left")
    out["country_name"] = out["country_code"].map(COUNTRY_NAMES).fillna(out["country_code"])
    out["is_eu27_uk"] = out["country_code"].isin(EU27_PLUS_UK)
    out["share_eu27_uk"] = out.apply(lambda r: pct(r["country_articles"], r["eu27_uk_articles"]), axis=1)
    out["share_eu27_uk_pct"] = out.apply(lambda r: pct100(r["country_articles"], r["eu27_uk_articles"]), axis=1)
    out["level"] = pd.Categorical(out["level"], categories=LEVELS, ordered=True)
    out["window"] = pd.Categorical(out["window"], categories=WINDOWS, ordered=True)
    return out.sort_values(["level", "window", "country_articles"], ascending=[True, True, False])


def build_country_ranking_europe_by_level_window(pc: pd.DataFrame) -> pd.DataFrame:
    out = build_country_level_window(pc)
    out = out[out["country_code"].isin(EU27_PLUS_UK)].copy()
    out["rank_eu27_uk"] = out.groupby(["level", "window"], observed=False)["country_articles"].rank(method="min", ascending=False).astype(int)
    return out.sort_values(["level", "window", "rank_eu27_uk"])[
        ["level", "window", "rank_eu27_uk", "country_code", "country_name", "country_articles", "eu27_uk_articles", "share_eu27_uk", "share_eu27_uk_pct"]
    ]


def build_area_coverage(master: pd.DataFrame, pc: pd.DataFrame, area_labels: dict[str, str]) -> pd.DataFrame:
    out = merge_basic_metrics(master, pc, ["area"])
    out = add_area_report_label(out, area_labels)
    n_conf = master.groupby("area")["congress"].nunique().reset_index(name="n_congresses")
    out = out.merge(n_conf, on="area", how="left")
    return out.sort_values(["coverage_pct", "total_articles"], ascending=[False, False])


def build_congress_spain_top(master: pd.DataFrame, pc: pd.DataFrame, area_labels: dict[str, str], top_n: int = 100) -> pd.DataFrame:
    out = merge_basic_metrics(master, pc, ["congress", "area", "level"])
    out = add_area_report_label(out, area_labels)
    es_w = spain_papers_by_group(pc, ["congress", "window"])
    es_pivot = es_w.pivot(index="congress", columns="window", values="spain_articles").reset_index()
    for w in WINDOWS:
        if w not in es_pivot.columns:
            es_pivot[w] = 0
    es_pivot = es_pivot.fillna(0)
    out = out.merge(es_pivot[["congress"] + WINDOWS], on="congress", how="left")
    for w in WINDOWS:
        out[w] = out[w].fillna(0).astype(int)
    out = out.sort_values(["spain_articles", "spain_share_eu27_uk", "total_articles"], ascending=[False, False, False])
    return out.head(top_n)


def build_top_congresses_spain_by_window(master: pd.DataFrame, pc: pd.DataFrame, area_labels: dict[str, str], top_n: int = 30) -> pd.DataFrame:
    out = merge_basic_metrics(master, pc, ["window", "congress", "area", "level"])
    out = add_area_report_label(out, area_labels)
    out["rank_spain_in_window"] = out.groupby("window", observed=False)["spain_articles"].rank(method="first", ascending=False).astype(int)
    out = out[out["rank_spain_in_window"] <= top_n].copy()
    out["window"] = pd.Categorical(out["window"], categories=WINDOWS, ordered=True)
    return out.sort_values(["window", "rank_spain_in_window"])


def build_primary_comparators_wide(pc: pd.DataFrame) -> pd.DataFrame:
    cc = build_country_by_window(pc)
    cc = cc[cc["country_code"].isin(PRIMARY_EU_COMPARATORS)].copy()
    rows = []
    for w, g in cc.groupby("window", observed=False):
        if pd.isna(w):
            continue
        row = {"window": str(w)}
        eu_total = safe_int(g["eu27_uk_articles"].max()) if not g.empty else 0
        row["eu27_uk_articles"] = eu_total
        for c in PRIMARY_EU_COMPARATORS:
            sub = g[g["country_code"] == c]
            n = safe_int(sub["country_articles"].iloc[0]) if not sub.empty else 0
            row[f"{c}_articles"] = n
            row[f"{c}_share_eu27_uk_pct"] = pct100(n, eu_total)
        row["ratio_ES_IT"] = pct(row.get("ES_articles", 0), row.get("IT_articles", 0))
        row["ratio_ES_FR"] = pct(row.get("ES_articles", 0), row.get("FR_articles", 0))
        row["ratio_ES_DE"] = pct(row.get("ES_articles", 0), row.get("DE_articles", 0))
        row["ratio_ES_GB"] = pct(row.get("ES_articles", 0), row.get("GB_articles", 0))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["window"] = pd.Categorical(out["window"], categories=WINDOWS, ordered=True)
    return out.sort_values("window")


def build_es_it_ratio_by_window(pc: pd.DataFrame) -> pd.DataFrame:
    wide = build_primary_comparators_wide(pc)
    cols = ["window", "ES_articles", "IT_articles", "ratio_ES_IT", "ES_share_eu27_uk_pct", "IT_share_eu27_uk_pct"]
    return wide[[c for c in cols if c in wide.columns]].copy()


def build_growth_factors(pc: pd.DataFrame) -> pd.DataFrame:
    cw = build_country_by_window(pc)
    cw = cw[cw["country_code"].isin(EU27_PLUS_UK)].copy()
    first, last = WINDOWS[0], WINDOWS[-1]
    first_df = cw[cw["window"].astype(str) == first][["country_code", "country_name", "country_articles", "share_eu27_uk_pct"]].rename(
        columns={"country_articles": "articles_2001_2005", "share_eu27_uk_pct": "share_eu27_uk_pct_2001_2005"}
    )
    last_df = cw[cw["window"].astype(str) == last][["country_code", "country_name", "country_articles", "share_eu27_uk_pct"]].rename(
        columns={"country_articles": "articles_2021_2025", "share_eu27_uk_pct": "share_eu27_uk_pct_2021_2025"}
    )
    out = first_df.merge(last_df, on=["country_code", "country_name"], how="outer").fillna(0)
    out["growth_factor"] = out.apply(lambda r: pct(r["articles_2021_2025"], r["articles_2001_2005"]), axis=1)
    out["delta_articles"] = out["articles_2021_2025"] - out["articles_2001_2005"]
    out["delta_share_eu27_uk_pct"] = (out["share_eu27_uk_pct_2021_2025"] - out["share_eu27_uk_pct_2001_2005"]).round(3)
    out["is_primary_comparator"] = out["country_code"].isin(PRIMARY_EU_COMPARATORS)
    return out.sort_values(["is_primary_comparator", "growth_factor", "articles_2021_2025"], ascending=[False, False, False])


def build_trend_classes(pc: pd.DataFrame) -> pd.DataFrame:
    cw = build_country_by_window(pc)
    cw = cw[cw["country_code"].isin(PRIMARY_EU_COMPARATORS)].copy()
    rows = []
    for cc, g in cw.groupby("country_code"):
        g = g.sort_values("window")
        shares = {str(r["window"]): float(r["share_eu27_uk_pct"]) for _, r in g.iterrows()}
        first = shares.get(WINDOWS[0], float("nan"))
        last = shares.get(WINDOWS[-1], float("nan"))
        peak_window = max(shares, key=lambda w: shares[w]) if shares else ""
        peak = shares.get(peak_window, float("nan"))
        delta = round(last - first, 3) if not pd.isna(first) and not pd.isna(last) else float("nan")
        if pd.isna(delta):
            cls = "sin datos"
        elif delta >= 1.0:
            cls = "creciente"
        elif delta <= -1.0:
            cls = "decreciente"
        else:
            # Distinguir estable con pico intermedio apreciable.
            if not pd.isna(peak) and max(0.0, peak - max(first, last)) >= 1.0:
                cls = "pico intermedio / mixta"
            else:
                cls = "estable"
        rows.append({
            "country_code": cc,
            "country_name": COUNTRY_NAMES.get(cc, cc),
            "share_2001_2005_pct": first,
            "share_2021_2025_pct": last,
            "delta_share_pct": delta,
            "peak_window": peak_window,
            "peak_share_pct": peak,
            "trend_class": cls,
        })
    return pd.DataFrame(rows).sort_values("country_code")


def build_country_comparison(pc: pd.DataFrame) -> pd.DataFrame:
    cc = build_country_by_window(pc)
    cc = cc[cc["country_code"].isin(PRIMARY_EU_COMPARATORS)].copy()
    cc["country_code"] = pd.Categorical(cc["country_code"], categories=PRIMARY_EU_COMPARATORS, ordered=True)
    return cc.sort_values(["window", "country_code"])


def write_summary(
    master: pd.DataFrame,
    pc: pd.DataFrame,
    global_w: pd.DataFrame,
    spain_eu_w: pd.DataFrame,
    area_cov: pd.DataFrame,
    spain_area_w: pd.DataFrame,
    ranks_w: pd.DataFrame,
    congress_top: pd.DataFrame,
    primary_wide: pd.DataFrame,
    growth: pd.DataFrame,
    es_it_ratio: pd.DataFrame,
    level_ranks: pd.DataFrame,
    top_by_window: pd.DataFrame,
    trend_classes: pd.DataFrame,
    include_bio: bool,
) -> str:
    lines: list[str] = []
    lines.append("=== PASO 14 v2 — INDICADORES BIBLIOMÉTRICOS AMPLIADOS PARA EL INFORME ===")
    lines.append("")
    lines.append("=== CORPUS Y COBERTURA ===")
    lines.append(f"Artículos en paper_master: {master['paper_id'].nunique():,}")
    lines.append(f"Artículos con >=1 país: {pc['paper_id'].nunique():,}")
    lines.append(f"Filas paper-país: {len(pc):,}")
    lines.append(f"Países distintos: {pc['country_code'].nunique():,}")
    lines.append(f"Cobertura acumulada: {pct100(pc['paper_id'].nunique(), master['paper_id'].nunique()):.2f}%")
    lines.append(f"Bioinformática incluida en comparativas por área: {'sí' if include_bio else 'no'}")
    lines.append("")

    lines.append("=== ESPAÑA EN UE27+REINO UNIDO POR VENTANA ===")
    for _, r in spain_eu_w.sort_values("window").iterrows():
        lines.append(
            f"  {r['window']}: ES={int(r['spain_articles']):5d} "
            f"UE27+UK={int(r['eu27_uk_articles']):6d} "
            f"ES/UE27+UK={r['spain_share_eu27_uk_pct']:.3f}% "
            f"rank={int(r['rank_spain_eu27_uk']) if not pd.isna(r['rank_spain_eu27_uk']) else 'NA'}"
        )
    lines.append("")

    lines.append("=== COMPARADORES EUROPEOS PRINCIPALES: CUOTA EN UE27+UK ===")
    for _, r in primary_wide.sort_values("window").iterrows():
        parts = []
        for c in PRIMARY_EU_COMPARATORS:
            parts.append(f"{c}={r.get(c + '_share_eu27_uk_pct', float('nan')):.3f}%")
        lines.append(f"  {r['window']}: " + " | ".join(parts))
    lines.append("")

    lines.append("=== RATIO ESPAÑA / ITALIA ===")
    for _, r in es_it_ratio.sort_values("window").iterrows():
        lines.append(
            f"  {r['window']}: ES={int(r['ES_articles'])} IT={int(r['IT_articles'])} "
            f"ES/IT={r['ratio_ES_IT']:.3f} "
            f"(ES={r['ES_share_eu27_uk_pct']:.3f}% vs IT={r['IT_share_eu27_uk_pct']:.3f}% en UE27+UK)"
        )
    lines.append("")

    lines.append("=== FACTORES DE CRECIMIENTO 2001-2005 → 2021-2025 (comparadores principales) ===")
    growth_primary = growth[growth["country_code"].isin(PRIMARY_EU_COMPARATORS)].copy()
    growth_primary["country_code"] = pd.Categorical(growth_primary["country_code"], categories=PRIMARY_EU_COMPARATORS, ordered=True)
    for _, r in growth_primary.sort_values("country_code").iterrows():
        gf = "NA" if pd.isna(r["growth_factor"]) else f"×{r['growth_factor']:.2f}"
        lines.append(
            f"  {r['country_code']}: {int(r['articles_2001_2005']):5d} → {int(r['articles_2021_2025']):5d} "
            f"{gf}; Δ cuota UE={r['delta_share_eu27_uk_pct']:+.3f} pp"
        )
    lines.append("")

    lines.append("=== CLASIFICACIÓN DESCRIPTIVA DE TENDENCIAS EUROPEAS ===")
    for _, r in trend_classes.sort_values("country_code").iterrows():
        lines.append(
            f"  {r['country_code']}: {r['trend_class']} "
            f"({r['share_2001_2005_pct']:.3f}% → {r['share_2021_2025_pct']:.3f}%; "
            f"pico {r['peak_share_pct']:.3f}% en {r['peak_window']})"
        )
    lines.append("")

    lines.append("=== COBERTURA POR VENTANA ===")
    for _, r in global_w.sort_values("window").iterrows():
        lines.append(
            f"  {r['window']}: total={int(r['total_articles']):7d} "
            f"resueltos={int(r['resolved_articles']):7d} cobertura={r['coverage_pct']:.2f}%"
        )
    lines.append("")

    lines.append("=== COBERTURA POR ÁREA ===")
    for _, r in area_cov.sort_values("area_report_label").iterrows():
        lines.append(
            f"  {r['area_report_label']}: congresos={int(r['n_congresses']):2d} "
            f"total={int(r['total_articles']):7d} resueltos={int(r['resolved_articles']):7d} "
            f"cobertura={r['coverage_pct']:.2f}%"
        )
    lines.append("")

    lines.append("=== ESPAÑA POR ÁREA Y VENTANA (ES/UE27+UK) ===")
    for area_label, g in spain_area_w.groupby("area_report_label", sort=True):
        lines.append(f"  [{area_label}]")
        for _, r in g.sort_values("window").iterrows():
            share = "NA" if pd.isna(r["spain_share_eu27_uk_pct"]) else f"{r['spain_share_eu27_uk_pct']:.3f}%"
            rank = "NA" if pd.isna(r.get("rank_eu27_uk")) else str(int(r["rank_eu27_uk"]))
            lines.append(
                f"    {r['window']}: ES={int(r['spain_articles']):5d} "
                f"UE27+UK={int(r['eu27_uk_articles']):6d} ES/UE={share} rank={rank}"
            )
    lines.append("")

    lines.append("=== ESPAÑA POR NIVEL A*/A ===")
    spain_level = level_ranks[level_ranks["country_code"] == "ES"].copy()
    for _, r in spain_level.sort_values(["level", "window"]).iterrows():
        lines.append(
            f"  {r['level']} {r['window']}: ES={int(r['country_articles']):5d} "
            f"UE27+UK={int(r['eu27_uk_articles']):6d} ES/UE={r['share_eu27_uk_pct']:.3f}% "
            f"rank={int(r['rank_eu27_uk'])}"
        )
    lines.append("")

    lines.append("=== TOP 20 CONGRESOS POR ARTÍCULOS CON ESPAÑA (global 2001-2025) ===")
    for _, r in congress_top.head(20).iterrows():
        lines.append(
            f"  {r['congress']:18s} {r['level']:2s} {r['area_report_label'][:36]:36s} "
            f"ES={int(r['spain_articles']):5d} UE27+UK={int(r['eu27_uk_articles']):6d} "
            f"ES/UE={r['spain_share_eu27_uk_pct'] if not pd.isna(r['spain_share_eu27_uk_pct']) else float('nan'):.3f}%"
        )
    lines.append("")

    lines.append("=== TOP 15 CONGRESOS POR ARTÍCULOS CON ESPAÑA EN 2021-2025 ===")
    top_latest = top_by_window[top_by_window["window"].astype(str) == "2021-2025"].head(15)
    for _, r in top_latest.iterrows():
        lines.append(
            f"  {int(r['rank_spain_in_window']):2d}. {r['congress']:18s} {r['level']:2s} {r['area_report_label'][:34]:34s} "
            f"ES={int(r['spain_articles']):4d} UE27+UK={int(r['eu27_uk_articles']):5d} ES/UE={r['spain_share_eu27_uk_pct']:.3f}%"
        )
    lines.append("")

    lines.append("=== NOTAS METODOLÓGICAS PARA EL INFORME ===")
    lines.append("- El conteo es completo por país: cada artículo cuenta una vez por país con al menos un autor afiliado.")
    lines.append("- El denominador europeo se define como artículos con >=1 país de UE27 + Reino Unido.")
    lines.append("- Bioinformática/ISMB se mantiene en totales globales y anexos, pero no se interpreta como área comparativa principal salvo que se use --include-bioinformatics.")
    lines.append("- Las cuotas por país se calculan sobre artículos con afiliación resuelta; los sesgos de cobertura deben documentarse por área y congreso.")
    lines.append("- Las ratios y factores de crecimiento comparan ventanas no solapadas; no implican causalidad, solo evolución descriptiva.")
    lines.append("")
    return "\n".join(lines)


def run(force: bool = False, include_bioinformatics: bool = False) -> None:
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭ Paso 14 ya completado (usa --force para repetir).")
        return

    require_file(PAPER_MASTER)
    require_file(PAPER_COUNTRY)
    OUTPUTS.mkdir(exist_ok=True)
    CHECKPOINTS.mkdir(exist_ok=True)

    print("=" * 70)
    print("PASO 14 v2 — Indicadores bibliométricos ampliados")
    print("=" * 70)

    area_labels = load_area_labels()

    print("  Cargando paper_master...")
    master_cols = ["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "title", "doi", "booktitle"]
    master = pd.read_csv(PAPER_MASTER, usecols=lambda c: c in master_cols, low_memory=False)
    master["paper_id"] = master["paper_id"].astype(str)
    master["year"] = pd.to_numeric(master["year"], errors="coerce").astype("Int64")
    master["window"] = pd.Categorical(master["window"], categories=WINDOWS, ordered=True)
    print(f"  Artículos: {master['paper_id'].nunique():,}")

    print("  Cargando paper_country...")
    pc_cols = ["paper_id", "dblp_key", "congress", "level", "area", "year", "window", "country_code", "country_name", "sources"]
    pc = pd.read_csv(PAPER_COUNTRY, usecols=lambda c: c in pc_cols, low_memory=False)
    pc["paper_id"] = pc["paper_id"].astype(str)
    pc["country_code"] = pc["country_code"].astype(str).str.upper().str.strip()
    pc = pc[pc["country_code"].str.len() == 2].copy()
    pc = pc.drop_duplicates(["paper_id", "country_code"])
    pc["window"] = pd.Categorical(pc["window"], categories=WINDOWS, ordered=True)
    print(f"  Filas paper-país: {len(pc):,}")
    print(f"  Papers con país: {pc['paper_id'].nunique():,}")

    print("  Construyendo indicadores base...")
    global_w = build_global_by_window(master, pc)
    spain_eu_w = build_spain_europe_by_window(master, pc)
    country_w = build_country_by_window(pc)
    ranks_w = build_country_ranking_europe_by_window(pc)
    country_area_w = build_country_by_area_window(pc, area_labels, include_bioinformatics)
    ranks_area_w = build_country_ranking_europe_by_area_window(pc, area_labels, include_bioinformatics)
    spain_area_w = build_spain_by_area_window(master, pc, area_labels, include_bioinformatics)
    spain_level_w = build_spain_by_level_window(master, pc)
    area_cov = build_area_coverage(master, pc, area_labels)
    congress_top = build_congress_spain_top(master, pc, area_labels, top_n=100)
    country_comp = build_country_comparison(pc)

    print("  Construyendo indicadores ampliados europeos...")
    primary_wide = build_primary_comparators_wide(pc)
    es_it_ratio = build_es_it_ratio_by_window(pc)
    growth = build_growth_factors(pc)
    trend_classes = build_trend_classes(pc)
    country_level = build_country_level_window(pc)
    level_ranks = build_country_ranking_europe_by_level_window(pc)
    top_by_window = build_top_congresses_spain_by_window(master, pc, area_labels, top_n=30)

    # Salidas base del v1.
    global_w.to_csv(OUTPUTS / "report_indicators_global_by_window.csv", index=False)
    spain_eu_w.to_csv(OUTPUTS / "report_indicators_spain_europe_by_window.csv", index=False)
    ranks_w.to_csv(OUTPUTS / "report_indicators_country_ranking_europe_by_window.csv", index=False)
    ranks_area_w.to_csv(OUTPUTS / "report_indicators_country_ranking_europe_by_area_window.csv", index=False)
    spain_area_w.to_csv(OUTPUTS / "report_indicators_spain_by_area_window.csv", index=False)
    spain_level_w.to_csv(OUTPUTS / "report_indicators_spain_by_level_window.csv", index=False)
    area_cov.to_csv(OUTPUTS / "report_indicators_area_coverage.csv", index=False)
    congress_top.to_csv(OUTPUTS / "report_indicators_congress_spain_top.csv", index=False)
    country_comp.to_csv(OUTPUTS / "report_indicators_country_comparison.csv", index=False)
    country_w.to_csv(OUTPUTS / "report_indicators_country_by_window.csv", index=False)
    country_area_w.to_csv(OUTPUTS / "report_indicators_country_by_area_window.csv", index=False)

    # Salidas ampliadas.
    primary_wide.to_csv(OUTPUTS / "report_indicators_primary_comparators_wide.csv", index=False)
    es_it_ratio.to_csv(OUTPUTS / "report_indicators_es_it_ratio_by_window.csv", index=False)
    growth.to_csv(OUTPUTS / "report_indicators_europe_growth_factors.csv", index=False)
    trend_classes.to_csv(OUTPUTS / "report_indicators_europe_trend_classes.csv", index=False)
    country_level.to_csv(OUTPUTS / "report_indicators_country_level_window.csv", index=False)
    level_ranks.to_csv(OUTPUTS / "report_indicators_country_ranking_europe_by_level_window.csv", index=False)
    top_by_window.to_csv(OUTPUTS / "report_indicators_top_congresses_spain_by_window.csv", index=False)

    summary = write_summary(
        master=master,
        pc=pc,
        global_w=global_w,
        spain_eu_w=spain_eu_w,
        area_cov=area_cov,
        spain_area_w=spain_area_w,
        ranks_w=ranks_w,
        congress_top=congress_top,
        primary_wide=primary_wide,
        growth=growth,
        es_it_ratio=es_it_ratio,
        level_ranks=level_ranks,
        top_by_window=top_by_window,
        trend_classes=trend_classes,
        include_bio=include_bioinformatics,
    )
    (OUTPUTS / "report_indicators_summary.txt").write_text(summary, encoding="utf-8")

    CHECKPOINT_FILE.write_text(
        json.dumps(
            {
                "step": 14,
                "version": "v2_europe_comparisons",
                "status": "COMPLETE",
                "n_articles": int(master["paper_id"].nunique()),
                "n_resolved_articles": int(pc["paper_id"].nunique()),
                "coverage_pct": pct100(pc["paper_id"].nunique(), master["paper_id"].nunique()),
                "include_bioinformatics_area_comparison": include_bioinformatics,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n" + summary)
    print("  ✅ Paso 14 v2 completado → outputs/report_indicators_summary.txt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--include-bioinformatics",
        action="store_true",
        help="Incluye Bioinformática/ISMB en comparativas principales por área. Por defecto se excluye.",
    )
    args = parser.parse_args()
    try:
        run(force=args.force, include_bioinformatics=args.include_bioinformatics)
    except Exception as exc:
        print(f"❌ Error: {exc}")
        raise
