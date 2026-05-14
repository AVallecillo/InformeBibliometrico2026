"""
Objetivo:
Generar figuras diagnósticas.
Soluciona:
- Visualizaciones insuficientes para explicar robustez, composición y concentración.
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

OUT = Path("outputs_ext/figures")
OUT.mkdir(parents=True, exist_ok=True)

def save_line_from_csv(csv_path, country="ES", y="share", title=None, outname=None):
    df = pd.read_csv(csv_path)
    if "country_code" in df.columns:
        df = df[df.country_code == country]
    plt.figure(figsize=(7,4))
    plt.plot(df["window"], df[y], marker="o")
    plt.xticks(rotation=30, ha="right")
    plt.ylabel(y)
    plt.title(title or csv_path)
    plt.tight_layout()
    plt.savefig(OUT / (outname or (Path(csv_path).stem + ".png")), dpi=200)
    plt.close()

# Figura completo vs fraccionario.
p = Path("outputs_ext/spain_complete_fractional_summary.csv")
if p.exists():
    df = pd.read_csv(p)
    plt.figure(figsize=(7,4))
    plt.plot(df["window"], df["complete_share_eu"], marker="o", label="Completo")
    plt.plot(df["window"], df["fractional_share_eu"], marker="o", label="Fraccionario")
    plt.xticks(rotation=30, ha="right")
    plt.ylabel("Cuota España / UE27+RU")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT / "spain_complete_vs_fractional.png", dpi=200)
    plt.close()

# Figura shift-share por segmento.
p = Path("outputs_ext/shift_share_segment_contributions.csv")
if p.exists():
    df = pd.read_csv(p)
    d = df[(df["from"]=="2006-2010") & (df["to"]=="2021-2025")].copy()
    d = d.sort_values("contribution_total_change").head(15)
    plt.figure(figsize=(8,6))
    plt.barh(d["segment"], d["contribution_total_change"])
    plt.xlabel("Contribución al cambio agregado")
    plt.tight_layout()
    plt.savefig(OUT / "shift_share_top_negative_segments.png", dpi=200)
    plt.close()

print("OK: figures generated in outputs_ext/figures/")
