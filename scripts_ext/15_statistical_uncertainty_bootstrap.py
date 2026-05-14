"""
15_statistical_uncertainty_bootstrap.py

Bootstrap de incertidumbre para la cuota española ES/UE27+RU por ventana y área.

Incluye:
  - progreso con ETA;
  - --B para iteraciones;
  - --progress-every;
  - --windows-only;
  - salida incremental al terminar cada grupo.
"""

from pathlib import Path
import argparse
import time
import numpy as np
import pandas as pd

from common import load_inputs, EU27_UK

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

def fmt_seconds(seconds):
    if seconds is None or np.isnan(seconds) or seconds < 0:
        return "?"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"

class Progress:
    def __init__(self, total, label, every=25):
        self.total = max(int(total), 1)
        self.label = label
        self.every = max(int(every), 1)
        self.start = time.time()
        self.last_print = 0

    def update(self, i):
        if i != self.total and i - self.last_print < self.every:
            return
        self.last_print = i
        elapsed = time.time() - self.start
        rate = i / elapsed if elapsed > 0 else 0
        remaining = (self.total - i) / rate if rate > 0 else np.nan
        pct = 100 * i / self.total
        print(
            f"\r{self.label}: {i}/{self.total} ({pct:5.1f}%) | elapsed {fmt_seconds(elapsed)} | ETA {fmt_seconds(remaining)}",
            end="",
            flush=True,
        )
        if i == self.total:
            print("")

def prepare_article_matrix():
    pm, pc = load_inputs("outputs")
    pc = pc.drop_duplicates(["paper_id", "country_code"])

    countries = pc.groupby("paper_id")["country_code"].apply(set).reset_index()
    countries["has_ES"] = countries["country_code"].apply(lambda s: "ES" in s)
    countries["has_EU"] = countries["country_code"].apply(lambda s: bool(set(s) & EU27_UK))

    df = pm[["paper_id", "window", "area", "venue", "year"]].merge(
        countries[["paper_id", "has_ES", "has_EU"]],
        on="paper_id",
        how="left",
    )
    df[["has_ES", "has_EU"]] = df[["has_ES", "has_EU"]].fillna(False)
    return df

def make_clusters(data):
    return [g.index.to_numpy() for _, g in data.groupby(["venue", "year"], sort=False)]

def bootstrap_share(data, B, rng, label, progress_every):
    if data.empty:
        return None

    data = data.reset_index(drop=True)
    clusters = make_clusters(data)
    n_clusters = len(clusters)
    if n_clusters == 0:
        return None

    has_es = data["has_ES"].to_numpy(dtype=np.int8)
    has_eu = data["has_EU"].to_numpy(dtype=np.int8)

    observed_den = has_eu.sum()
    observed = has_es.sum() / observed_den if observed_den else np.nan

    vals = np.empty(B, dtype=float)
    prog = Progress(B, label=label, every=progress_every)

    for b in range(B):
        sampled = rng.integers(0, n_clusters, n_clusters)
        idx = np.concatenate([clusters[j] for j in sampled])
        den = has_eu[idx].sum()
        vals[b] = has_es[idx].sum() / den if den else np.nan
        prog.update(b + 1)

    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return None

    return {
        "observed": observed,
        "ci_low_2_5": np.quantile(vals, 0.025),
        "ci_high_97_5": np.quantile(vals, 0.975),
        "bootstrap_sd": np.std(vals, ddof=1) if len(vals) > 1 else 0.0,
        "B": B,
        "n_clusters": n_clusters,
        "n_articles": len(data),
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--B", type=int, default=500, help="Bootstrap iterations per group.")
    parser.add_argument("--progress-every", type=int, default=25, help="Update progress every N iterations.")
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--windows-only", action="store_true", help="Skip area-window bootstrap.")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    df = prepare_article_matrix()

    print(f"Bootstrap iterations per group: {args.B}")
    print(f"Progress update every: {args.progress_every} iterations")
    print(f"Articles in matrix: {len(df):,}\n")

    rows = []
    windows = list(df.groupby("window", sort=True))
    for gi, (w, g) in enumerate(windows, start=1):
        label = f"[window {gi}/{len(windows)}] {w}"
        t0 = time.time()
        r = bootstrap_share(g, args.B, rng, label, args.progress_every)
        if r:
            r["window"] = w
            r["elapsed_seconds"] = round(time.time() - t0, 2)
            rows.append(r)
            pd.DataFrame(rows).to_csv(OUT / "bootstrap_es_share_by_window.csv", index=False)

    if args.windows_only:
        print("windows-only mode: skipping area-window bootstrap.")
        print("OK: bootstrap uncertainty generated.")
        return

    rows = []
    groups = list(df.groupby(["window", "area"], sort=True))
    for gi, ((w, area), g) in enumerate(groups, start=1):
        label = f"[area-window {gi}/{len(groups)}] {w} | {area}"
        t0 = time.time()
        r = bootstrap_share(g, args.B, rng, label, args.progress_every)
        if r:
            r["window"] = w
            r["area"] = area
            r["elapsed_seconds"] = round(time.time() - t0, 2)
            rows.append(r)
            pd.DataFrame(rows).to_csv(OUT / "bootstrap_es_share_by_area_window.csv", index=False)

    print("OK: bootstrap uncertainty generated.")

if __name__ == "__main__":
    main()
