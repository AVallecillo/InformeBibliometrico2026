"""
Build data/core_historical/core_historical.csv from historical CORE/ERA CSV files.

Default input:
  data/core_historical/raw/

Default output:
  data/core_historical/

This version is robust to the uploaded CORE CSV format, which has no header row:
  col 0 = numeric id
  col 1 = conference name
  col 2 = acronym / venue code
  col 3 = ranking version
  col 4 = rank
  col 5 = DB flag

Policy for the undifferentiated 2010 ERA/CORE A*+A list:

  --policy-2010 infer_2008_2013   Recommended.
      Applies:
      CORE2010(C,A*,A*) = A*
      CORE2010(C,A*,A)  = A*
      CORE2010(C,A,A*)  = A*
      CORE2010(C,A,A)   = A
      CORE2010(C,A*,-)  = A
      CORE2010(C,A,-)   = A
      CORE2010(C,-,A)   = A
      CORE2010(C,-,A*)  = A
      CORE2010(C,-,-)   = -

  --policy-2010 all_A
      Treat every 2010 undifferentiated venue as A.

  --policy-2010 exclude
      Exclude 2010 from core_historical.csv.
"""

from pathlib import Path
import argparse
import re
import pandas as pd


def normalise_level(level):
    if pd.isna(level):
        return None
    s = str(level).strip().upper().replace(" ", "")
    if s in {"A*", "A-STAR", "ASTAR", "A_STAR"}:
        return "A*"
    if s == "A":
        return "A"
    if s in {"A*+A", "ASTAR+A", "A+A*"}:
        return "A*+A"
    return str(level).strip()


def clean_venue(v):
    if pd.isna(v):
        return None
    s = re.sub(r"\s+", " ", str(v).strip())
    if not s or s.lower() == "nan":
        return None
    return s


def looks_like_headerless_core(df: pd.DataFrame) -> bool:
    """
    Detects the CORE files uploaded by the user:
    [id, full name, acronym, CORE/ERA year, level, DB flag, FoR...]
    """
    if df.shape[1] < 5:
        return False
    c0 = pd.to_numeric(df.iloc[:, 0], errors="coerce").notna().mean()
    c2 = df.iloc[:, 2].astype(str).str.len().between(1, 40).mean()
    c3 = df.iloc[:, 3].astype(str).str.contains(r"CORE|ERA|ICORE", case=False, regex=True).mean()
    return c0 > 0.80 and c2 > 0.80 and c3 > 0.80


def guess_venue_col(df: pd.DataFrame):
    candidates = [
        "venue", "congress", "acronym", "Acronym", "Conference acronym",
        "Conference Acronym", "Abbreviation", "short_name", "Short name",
        "Short Name", "code", "Code"
    ]
    for c in candidates:
        if c in df.columns and df[c].notna().mean() > 0.5:
            return c

    # For numeric column labels from header=None, acronym is normally column 2.
    if 2 in df.columns and looks_like_headerless_core(df):
        return 2

    # fallback: object column with acronym-like strings, ignoring long title column.
    obj_cols = list(df.columns)
    best, best_score = None, -999
    for c in obj_cols:
        vals = df[c].dropna().astype(str).str.strip()
        if vals.empty:
            continue
        avg_len = vals.str.len().median()
        acronym_like = vals.str.match(r"^[A-Za-z0-9][A-Za-z0-9+._/-]{0,40}$").mean()
        contains_space = vals.str.contains(r"\s", regex=True).mean()
        score = acronym_like - contains_space - max(0, avg_len - 12) / 50
        if score > best_score:
            best, best_score = c, score
    if best is None:
        raise ValueError("Could not infer venue/acronym column")
    return best


def read_csv_flex(path: Path) -> pd.DataFrame:
    """
    Reads both headerless CORE CSVs and potential headered CSVs.
    The uploaded files are headerless, so header=None is tried first.
    """
    last_err = None
    for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
        for sep in [None, ",", ";", "\t"]:
            for header in [None, 0]:
                try:
                    df = pd.read_csv(path, encoding=enc, sep=sep, engine="python", header=header)
                    if df.shape[0] > 0 and df.shape[1] >= 3:
                        # Headerless CORE files should be interpreted as headerless;
                        # if header=0 was used accidentally, the first record becomes columns.
                        if header is None or not looks_like_headerless_core(df):
                            return df
                except Exception as e:
                    last_err = e
    raise RuntimeError(f"Could not read {path}: {last_err}")


def read_core_file(path: Path, year: int, level: str):
    df = read_csv_flex(path)

    if looks_like_headerless_core(df):
        venue_col = 2
        title_col = 1
        version_col = 3
        level_col = 4
        out = pd.DataFrame({
            "venue": df.iloc[:, venue_col].map(clean_venue),
            "conference_name": df.iloc[:, title_col].map(clean_venue),
            "core_year": year,
            "level": level,
            "level_in_file": df.iloc[:, level_col].map(clean_venue),
            "ranking_version_in_file": df.iloc[:, version_col].map(clean_venue),
            "source_file": path.name,
            "source_venue_col": str(venue_col),
        })
    else:
        venue_col = guess_venue_col(df)
        out = pd.DataFrame({
            "venue": df[venue_col].map(clean_venue),
            "conference_name": None,
            "core_year": year,
            "level": level,
            "level_in_file": None,
            "ranking_version_in_file": None,
            "source_file": path.name,
            "source_venue_col": str(venue_col),
        })

    out = out[out["venue"].notna() & (out["venue"].astype(str).str.len() > 0)]
    # Remove accidental header rows, if any.
    out = out[~out["venue"].astype(str).str.lower().isin({"acronym", "venue", "conference acronym"})]
    return out


def apply_2010_policy(raw, policy):
    raw_no_2010 = raw[raw["core_year"] != 2010].copy()
    undiff = raw[raw["core_year"] == 2010].copy()

    if policy == "exclude" or undiff.empty:
        return raw_no_2010, pd.DataFrame()

    pre = raw_no_2010[raw_no_2010.core_year == 2008].groupby("venue")["level"].apply(
        lambda s: "A*" if "A*" in set(s) else ("A" if "A" in set(s) else "-")
    )
    post = raw_no_2010[raw_no_2010.core_year == 2013].groupby("venue")["level"].apply(
        lambda s: "A*" if "A*" in set(s) else ("A" if "A" in set(s) else "-")
    )

    inferred_rows, audit_rows = [], []
    for venue in sorted(set(undiff["venue"])):
        x = pre.get(venue, "-")
        y = post.get(venue, "-")

        if policy == "all_A":
            lvl, reason = "A", "2010 undifferentiated list treated as A"
        elif policy == "infer_2008_2013":
            if x == "-" and y == "-":
                lvl, reason = "-", "in 2010 list but absent from both adjacent rankings; excluded"
            elif x == "A*" and y in {"A*", "A"}:
                lvl, reason = "A*", "A* in 2008 and present in 2013"
            elif x == "A" and y == "A*":
                lvl, reason = "A*", "A in 2008 and A* in 2013"
            elif x == "A" and y == "A":
                lvl, reason = "A", "A in both adjacent rankings"
            elif x in {"A*", "A"} and y == "-":
                lvl, reason = "A", "present in 2008 only; conservative A"
            elif x == "-" and y in {"A", "A*"}:
                lvl, reason = "A", "present in 2013 only; conservative A"
            else:
                lvl, reason = "A", "fallback conservative A"
        else:
            raise ValueError(policy)

        audit_rows.append({
            "venue": venue,
            "core_year": 2010,
            "level_2008": x,
            "level_2013": y,
            "level_2010_inferred": lvl,
            "policy_2010": policy,
            "reason": reason,
        })
        if lvl != "-":
            inferred_rows.append({
                "venue": venue,
                "conference_name": None,
                "core_year": 2010,
                "level": lvl,
                "level_in_file": "A*+A_undifferentiated",
                "ranking_version_in_file": "ERA2010",
                "source_file": "COREAstarA-2010.csv",
                "source_venue_col": "inferred",
                "undifferentiated_2010": True,
                "policy_2010": policy,
            })

    return pd.concat([raw_no_2010, pd.DataFrame(inferred_rows)], ignore_index=True), pd.DataFrame(audit_rows)


def resolve_duplicates(df):
    level_order = {"A": 1, "A*": 2}
    rows, dup_rows = [], []
    for (venue, year), g in df.groupby(["venue", "core_year"], dropna=False):
        levels = sorted(set(g["level"].dropna()), key=lambda x: level_order.get(x, 0), reverse=True)
        chosen = levels[0] if levels else None
        names = [str(x) for x in g.get("conference_name", pd.Series(dtype=str)).dropna().unique()]
        rows.append({
            "venue": venue,
            "conference_name": names[0] if names else None,
            "core_year": year,
            "level": chosen,
            "source_files": "|".join(sorted(set(g["source_file"].astype(str)))),
            "n_raw_rows": len(g),
            "had_conflict": len(set(g["level"])) > 1,
            "level_raw_values": "|".join(sorted(set(g["level"].astype(str)))),
        })
        if len(g) > 1 or len(set(g["level"])) > 1:
            dup_rows.append(g.assign(chosen_level=chosen))
    return pd.DataFrame(rows), pd.concat(dup_rows, ignore_index=True) if dup_rows else pd.DataFrame()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", default="data/core_historical/raw")
    ap.add_argument("--output-dir", default="data/core_historical")
    ap.add_argument("--policy-2010", choices=["infer_2008_2013", "all_A", "exclude"], default="infer_2008_2013")
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_parts = []
    for y in [2008, 2013, 2014, 2017, 2018, 2020, 2021, 2023, 2026]:
        for level, fname in [("A", f"COREA-{y}.csv"), ("A*", f"COREAstar-{y}.csv")]:
            p = input_dir / fname
            if p.exists():
                raw_parts.append(read_core_file(p, y, level))

    p2010 = input_dir / "COREAstarA-2010.csv"
    if p2010.exists():
        raw_parts.append(read_core_file(p2010, 2010, "A*+A"))

    if not raw_parts:
        raise FileNotFoundError(f"No CORE historical CSV files found in {input_dir}")

    raw = pd.concat(raw_parts, ignore_index=True)
    raw["level"] = raw["level"].map(normalise_level)
    raw["undifferentiated_2010"] = raw["core_year"].eq(2010)
    raw.to_csv(output_dir / "core_historical_raw_all_rows.csv", index=False)

    processed, audit2010 = apply_2010_policy(raw, args.policy_2010)
    if not audit2010.empty:
        audit2010.to_csv(output_dir / "core_historical_2010_inference_audit.csv", index=False)

    processed = processed[processed["level"].isin(["A*", "A"])].copy()
    resolved, dup = resolve_duplicates(processed)
    resolved = resolved.sort_values(["core_year", "level", "venue"]).reset_index(drop=True)
    resolved["policy_2010"] = args.policy_2010
    resolved.to_csv(output_dir / "core_historical.csv", index=False)

    if not dup.empty:
        dup.to_csv(output_dir / "core_historical_duplicate_resolution.csv", index=False)

    counts = resolved.groupby(["core_year", "level"])["venue"].nunique().unstack(fill_value=0)
    counts.to_csv(output_dir / "core_historical_counts_by_year_level.csv")

    readme = output_dir / "core_historical_README.txt"
    readme.write_text(
        "core_historical.csv generated by scripts_ext/build_core_historical.py\n"
        f"2010 policy: {args.policy_2010}\n\n"
        "Main output: data/core_historical/core_historical.csv\n"
        "2010 audit: data/core_historical/core_historical_2010_inference_audit.csv\n\n"
        + counts.to_string() + "\n",
        encoding="utf-8",
    )

    print(f"OK: wrote {output_dir / 'core_historical.csv'}")
    print(counts)


if __name__ == "__main__":
    main()
