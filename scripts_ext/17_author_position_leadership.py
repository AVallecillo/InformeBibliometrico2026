"""
17_author_position_leadership.py

Leadership indicators by author position. Optional.
If author-order data are unavailable, it writes a SKIPPED report and exits cleanly.
"""

from pathlib import Path
import glob
import pandas as pd

from common import load_inputs

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm, pc = load_inputs("outputs")

preferred = Path("outputs/paper_author_affiliations.csv")
frames = []

if preferred.exists():
    frames.append(pd.read_csv(preferred))
else:
    for f in glob.glob("outputs/affiliation_evidence_*.csv"):
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if {"paper_id", "country_code"}.issubset(df.columns) and (
            "author_order" in df.columns or "author_position" in df.columns
        ):
            frames.append(df)

if not frames:
    msg = (
        "SKIPPED: Need outputs/paper_author_affiliations.csv or affiliation evidence files "
        "with author_order/author_position.\n"
        "The current pipeline appears to consolidate at paper_id + country_code level only.\n"
    )
    (OUT / "author_position_leadership_SKIPPED.txt").write_text(msg, encoding="utf-8")
    print(msg.strip())
    raise SystemExit(0)

aa = pd.concat(frames, ignore_index=True).drop_duplicates()

if "author_order" not in aa.columns and "author_position" in aa.columns:
    aa["author_order"] = aa["author_position"]

required = {"paper_id", "country_code", "author_order"}
if not required.issubset(aa.columns):
    msg = f"SKIPPED: author table must contain {sorted(required)}"
    (OUT / "author_position_leadership_SKIPPED.txt").write_text(msg + "\n", encoding="utf-8")
    print(msg)
    raise SystemExit(0)

aa = aa.dropna(subset=["paper_id", "country_code", "author_order"]).copy()
aa["author_order"] = pd.to_numeric(aa["author_order"], errors="coerce")
aa = aa.dropna(subset=["author_order"])
aa["author_order"] = aa["author_order"].astype(int)

paper_n = aa.groupby("paper_id")["author_order"].max().reset_index(name="n_authors")
aa = aa.merge(paper_n, on="paper_id", how="left")
aa["is_first"] = aa["author_order"].eq(1)
aa["is_last"] = aa["author_order"].eq(aa["n_authors"])

ind = aa.groupby("paper_id").apply(lambda g: pd.Series({
    "has_es_author": (g["country_code"] == "ES").any(),
    "es_first": ((g["country_code"] == "ES") & (g["is_first"])).any(),
    "es_last": ((g["country_code"] == "ES") & (g["is_last"])).any(),
    "es_first_or_last": ((g["country_code"] == "ES") & (g["is_first"] | g["is_last"])).any(),
    "es_only_countries": set(g["country_code"].dropna()) == {"ES"},
    "n_authors": g["n_authors"].max(),
    "n_es_author_positions": (g["country_code"] == "ES").sum(),
})).reset_index()

ind = ind.merge(pm[["paper_id", "window", "area", "level", "venue", "year"]], on="paper_id", how="left")
es = ind[ind["has_es_author"]].copy()

summary = (
    es.groupby("window")
    .agg(
        es_papers=("paper_id", "nunique"),
        es_first=("es_first", "sum"),
        es_last=("es_last", "sum"),
        es_first_or_last=("es_first_or_last", "sum"),
        es_only=("es_only_countries", "sum"),
        mean_authors=("n_authors", "mean"),
    )
    .reset_index()
)
for col in ["es_first", "es_last", "es_first_or_last", "es_only"]:
    summary[f"share_{col}"] = summary[col] / summary["es_papers"]
summary.to_csv(OUT / "spain_author_position_leadership.csv", index=False)

area = (
    es.groupby(["window", "area"])
    .agg(
        es_papers=("paper_id", "nunique"),
        es_first=("es_first", "sum"),
        es_last=("es_last", "sum"),
        es_first_or_last=("es_first_or_last", "sum"),
        mean_authors=("n_authors", "mean"),
    )
    .reset_index()
)
for col in ["es_first", "es_last", "es_first_or_last"]:
    area[f"share_{col}"] = area[col] / area["es_papers"]
area.to_csv(OUT / "spain_author_position_by_area_window.csv", index=False)

print("OK: author position leadership generated.")
