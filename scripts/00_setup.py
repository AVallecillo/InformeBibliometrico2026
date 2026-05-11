"""
PASO 0 — Setup y verificación del entorno
Verifica dependencias, crea carpetas y valida que CORE.csv está en su lugar.
"""

import sys
import os
from pathlib import Path

# ── Rutas base ──────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent
DIRS = [
    BASE / "data",
    BASE / "outputs",
    BASE / "checkpoints",
]

def check_python():
    print(f"Python {sys.version}")
    if sys.version_info < (3, 9):
        print("❌ Se requiere Python 3.9+")
        sys.exit(1)
    print("✅ Python OK")

def check_packages():
    required = ["requests", "pandas", "openpyxl", "lxml", "tqdm"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"  ✅ {pkg}")
        except ImportError:
            print(f"  ❌ {pkg} — instalar con: pip install {pkg}")
            missing.append(pkg)
    if missing:
        print(f"\nInstala los paquetes faltantes:")
        print(f"  pip install {' '.join(missing)}")
        sys.exit(1)

def create_dirs():
    for d in DIRS:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  📁 {d.relative_to(BASE)}")

def check_core_csv():
    core_csv = BASE / "data" / "CORE.csv"
    if core_csv.exists():
        import pandas as pd
        df = pd.read_csv(core_csv, header=None, on_bad_lines='skip')
        print(f"  ✅ CORE.csv encontrado ({len(df)} filas)")
    else:
        print(f"  ⚠️  CORE.csv no encontrado en data/")
        print(f"     Descárgalo desde: https://portal.core.edu.au/conf-ranks/?do=Export")
        print(f"     y colócalo en: {core_csv}")
        print(f"     El paso 01 también puede descargarlo automáticamente.")

if __name__ == "__main__":
    print("=" * 55)
    print("PASO 0 — Verificación del entorno")
    print("=" * 55)

    print("\n[1] Python:")
    check_python()

    print("\n[2] Paquetes:")
    check_packages()

    print("\n[3] Carpetas:")
    create_dirs()

    print("\n[4] Datos de entrada:")
    check_core_csv()

    print("\n✅ Setup completado. Puedes continuar con el paso 01.")
