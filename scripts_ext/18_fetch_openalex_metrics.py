"""
18_fetch_openalex_metrics.py

Optional local script to fetch cited_by_count from OpenAlex for papers with DOI.
It writes outputs/openalex_work_metrics.csv, which is consumed by
09_impact_indicators.py.

Usage:
  python scripts/18_fetch_openalex_metrics.py --mailto you@example.org --limit 1000
  python scripts/18_fetch_openalex_metrics.py --mailto you@example.org

Notes:
- This script needs internet access and the requests package.
- It uses a JSON cache to avoid repeated API calls.
- It fetches DOI-by-DOI for robustness. This is slower but less fragile than
  composing very large OR filters.
"""
from pathlib import Path
import argparse, json, time
import pandas as pd

try:
    import requests
except ImportError as e:
    raise SystemExit("Install requests first: pip install requests") from e

parser = argparse.ArgumentParser()
parser.add_argument("--mailto", default="", help="Email for OpenAlex polite pool")
parser.add_argument("--limit", type=int, default=None, help="Optional max DOI count for testing")
parser.add_argument("--sleep", type=float, default=0.1)
args = parser.parse_args()

out = Path("outputs")
pm = pd.read_csv(out/"paper_master.csv")
if "doi" not in pm.columns:
    raise SystemExit("paper_master.csv has no doi column")

df = pm[["paper_id","doi"]].dropna().copy()
df["doi"] = df["doi"].astype(str).str.replace("https://doi.org/", "", regex=False).str.strip()
df = df[df.doi.ne("")]
if args.limit:
    df = df.head(args.limit)

cache_path = out/"openalex_metrics_cache.json"
if cache_path.exists():
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
else:
    cache = {}

def fetch_one(doi):
    url = "https://api.openalex.org/works/https://doi.org/" + doi
    params = {"select": "doi,cited_by_count,publication_year"}
    if args.mailto:
        params["mailto"] = args.mailto
    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 404:
        return {"cited_by_count": None, "publication_year_openalex": None, "found": False}
    r.raise_for_status()
    js = r.json()
    return {
        "cited_by_count": js.get("cited_by_count"),
        "publication_year_openalex": js.get("publication_year"),
        "found": True,
    }

for i, row in enumerate(df.itertuples(index=False), 1):
    doi = row.doi
    if doi in cache:
        continue
    try:
        cache[doi] = fetch_one(doi)
    except Exception as e:
        cache[doi] = {"cited_by_count": None, "publication_year_openalex": None, "found": False, "error": str(e)}
    if i % 100 == 0:
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
        print(f"processed {i}/{len(df)}")
    time.sleep(args.sleep)
cache_path.write_text(json.dumps(cache), encoding="utf-8")

rows = []
for row in df.itertuples(index=False):
    rec = cache.get(row.doi, {})
    rows.append({
        "paper_id": row.paper_id,
        "doi": row.doi,
        "cited_by_count": rec.get("cited_by_count"),
        "publication_year_openalex": rec.get("publication_year_openalex"),
        "openalex_found": rec.get("found", False),
    })
pd.DataFrame(rows).to_csv(out/"openalex_work_metrics.csv", index=False)
print("OK: wrote outputs/openalex_work_metrics.csv")
