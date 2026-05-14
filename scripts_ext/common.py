from pathlib import Path
import pandas as pd
import numpy as np

EU27_UK = {
    "AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU","IE",
    "IT","LV","LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE","GB"
}
EUROPE_EXTENDED = EU27_UK | {"CH","NO","IS","LI","IL","TR","UA","RS","BA","ME","MK","AL","GE","AM","MD"}
COMPARABLE = {"ES","IT","NL","SE","BE","AT","PT","PL","CH","FI","DK","IE","CZ","HU","GR","NO"}
WINDOW_LABELS = ["2001-2005","2006-2010","2011-2015","2016-2020","2021-2025"]

def add_window(df: pd.DataFrame, year_col: str = "year") -> pd.DataFrame:
    y = df[year_col].astype(int)
    bins = [2000, 2005, 2010, 2015, 2020, 2025]
    df = df.copy()
    df["window"] = pd.cut(y, bins=bins, labels=WINDOW_LABELS).astype(str)
    return df

def standardise_master_columns(pm: pd.DataFrame) -> pd.DataFrame:
    pm = pm.copy()
    if "venue" not in pm.columns and "congress" in pm.columns:
        pm["venue"] = pm["congress"]
    if "congress" not in pm.columns and "venue" in pm.columns:
        pm["congress"] = pm["venue"]
    if "venue" not in pm.columns and "congress" not in pm.columns:
        raise ValueError("paper_master.csv must contain either `venue` or `congress`.")
    if "window" not in pm.columns:
        pm = add_window(pm)
    return pm

def load_inputs(outputs="outputs"):
    out = Path(outputs)
    pm = pd.read_csv(out / "paper_master.csv")
    pc = pd.read_csv(out / "paper_country.csv")
    pm = standardise_master_columns(pm)
    keep = [c for c in ["paper_id","year","window","venue","congress","level","area","doi","title"] if c in pm.columns]
    pc = pc.merge(pm[keep], on="paper_id", how="left", suffixes=("", "_pm"))
    for col in ["venue","congress","year","window","level","area"]:
        alt = f"{col}_pm"
        if col not in pc.columns and alt in pc.columns:
            pc[col] = pc[alt]
        elif col in pc.columns and alt in pc.columns:
            pc[col] = pc[col].fillna(pc[alt])
    if "venue" not in pc.columns and "congress" in pc.columns:
        pc["venue"] = pc["congress"]
    if "congress" not in pc.columns and "venue" in pc.columns:
        pc["congress"] = pc["venue"]
    return pm, pc

def fractional_by_unique_country(pc: pd.DataFrame) -> pd.DataFrame:
    x = pc.drop_duplicates(["paper_id","country_code"]).copy()
    n = x.groupby("paper_id")["country_code"].transform("nunique")
    x["frac_country_weight"] = 1.0 / n
    return x

def safe_rank(df: pd.DataFrame, by_cols, value_col, ascending=False):
    df = df.copy()
    df["rank"] = df.groupby(by_cols)[value_col].rank(method="min", ascending=ascending).astype("Int64")
    return df
