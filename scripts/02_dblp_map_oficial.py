"""
PASO 2 — Mapeo acrónimo → clave DBLP

Lee los corpus oficiales A*/A generados por el paso 1 y añade la clave DBLP
de cada congreso.

Requisitos metodológicos:
  - El corpus debe contener exactamente los congresos oficiales CORE/ICORE 2026:
      62 A* + 108 A = 170 congresos.
  - No se admiten congresos B, nacionales ni elevaciones manuales previas.
  - Si falta cualquier mapeo DBLP, el paso falla para evitar salidas parciales.

Produce:
  outputs/conf_dblp_map.csv
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import requests

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step2.json"

EXPECTED_ASTAR = 62
EXPECTED_A = 108
EXPECTED_TOTAL = EXPECTED_ASTAR + EXPECTED_A

# Acrónimos que pertenecían a la versión reconciliada anterior, pero no al
# listado oficial CORE/ICORE 2026 A/A* usado en este informe.
NON_OFFICIAL_LEGACY = {"COLING", "EDBT", "NSDI", "PACT", "SoCC"}

# ── Mapa acrónimo CORE/ICORE 2026 A/A* → clave DBLP ──────────────────────────
# La URL de proceedings de cada congreso es: https://dblp.org/db/conf/<key>/
DBLP_MAP = {
    'AAAI': 'aaai',
    'AAMAS': 'atal',
    'ACL': 'acl',
    'ACMMM': 'mm',
    'ACSAC': 'acsac',
    'AIED': 'aied',
    'AISTATS': 'aistats',
    'ALENEX': 'alenex',
    'APPROX/RANDOM': 'approx',
    'ASE': 'kbse',
    'AsiaCCS': 'asiaccs',
    'ASIACRYPT': 'asiacrypt',
    'ASPLOS': 'asplos',
    'ASSETS': 'assets',
    'BMVC': 'bmvc',
    'BPM': 'bpm',
    'CADE': 'cade',
    'CaiSE': 'caise',
    'CAV': 'cav',
    'CCC': 'coco',
    'CCS': 'ccs',
    'CGO': 'cgo',
    'CHES': 'ches',
    'CHI': 'chi',
    'CIDR': 'cidr',
    'CIKM': 'cikm',
    'COLT': 'colt',
    'CoNEXT': 'conext',
    'CP': 'cp',
    'CRYPTO': 'crypto',
    'CSCW': 'cscw',
    'CSF': 'csfw',
    'CVPR': 'cvpr',
    'DAC': 'dac',
    'DATE': 'date',
    'DIS': 'ACMdis',
    'DISC': 'wdag',
    'DSN': 'dsn',
    'EACL': 'eacl',
    'EASE': 'ease',
    'EC': 'sigecom',
    'ECAI': 'ecai',
    'ECCV': 'eccv',
    'ECIR': 'ecir',
    'ECML PKDD': 'pkdd',
    'ECOOP': 'ecoop',
    'EMNLP': 'emnlp',
    'ER': 'er',
    'ESA': 'esa',
    'ESEM': 'esem',
    'ESOP': 'esop',
    'ESORICS': 'esorics',
    'EuroCrypt': 'eurocrypt',
    'EuroS&P': 'eurosp',
    'EuroSys': 'eurosys',
    'FAST': 'fast',
    'FC': 'fc',
    'FOCS': 'focs',
    'FOGA': 'foga',
    'FPGA': 'fpga',
    'FSE': 'sigsoft',
    'GD': 'gd',
    'GECCO': 'gecco',
    'HotOS': 'hotos',
    'HPCA': 'hpca',
    'HPDC': 'hpdc',
    'HRI': 'hri',
    'ICALP': 'icalp',
    'ICAPS': 'aips',
    'ICCAD': 'iccad',
    'ICCV': 'iccv',
    'ICDAR': 'icdar',
    'ICDCS': 'icdcs',
    'ICDE': 'icde',
    'ICDM': 'icdm',
    'ICDT': 'icdt',
    'ICER': 'icer',
    'ICFP': 'icfp',
    'ICLR': 'iclr',
    'ICME': 'icmcs',
    'ICML': 'icml',
    'ICPC': 'iwpc',
    'ICRA': 'icra',
    'ICS': 'ics',
    'ICSA': 'icsa',
    'ICSE': 'icse',
    'ICSME': 'icsm',
    'ICSOC': 'icsoc',
    'ICST': 'icst',
    'ICWS': 'icws',
    'ICWSM': 'icwsm',
    'IEEE VIS': 'visualization',
    'IJCAI': 'ijcai',
    'IJCAR': 'ijcar',
    'IMC': 'imc',
    'INFOCOM': 'infocom',
    'Interspeech': 'interspeech',
    'IPDPS': 'ipps',
    'IROS': 'iros',
    'ISCA': 'isca',
    'ISLPED': 'islped',
    'ISMAR': 'ismar',
    'ISMB': 'ismb',
    'ISSRE': 'issre',
    'ISSTA': 'issta',
    'ISWC': 'semweb',
    'ITC': 'itc',
    'ITCS': 'innovations',
    'IUI': 'iui',
    'KDD': 'kdd',
    'KR': 'kr',
    'LAK': 'lak',
    'LICS': 'lics',
    'MICCAI': 'miccai',
    'MICRO': 'micro',
    'Middleware': 'middleware',
    'MMSys': 'mmsys',
    'MOBICOM': 'mobicom',
    'Mobisys': 'mobisys',
    'MODELS': 'models',
    'MSR': 'msr',
    'MSWIM': 'mswim',
    'NAACL': 'naacl',
    'NDSS': 'ndss',
    'NeurIPS': 'nips',
    'OOPSLA': 'oopsla',
    'OSDI': 'osdi',
    'PERCOM': 'percom',
    'PETS': 'pet',
    'PLDI': 'pldi',
    'PODC': 'podc',
    'PODS': 'pods',
    'POPL': 'popl',
    'PPSN': 'ppsn',
    'RAID': 'raid',
    'RE': 're',
    'RecSys': 'recsys',
    'RTAS': 'rtas',
    'RTSS': 'rtss',
    'SANER': 'wcre',
    'SAT': 'sat',
    'SC': 'sc',
    'SDM': 'sdm',
    'SEAMS': 'seams',
    'SIGCOMM': 'sigcomm',
    'SIGCSE': 'sigcse',
    'SIGGRAPH': 'siggraph',
    'SiggraphA': 'siggrapha',
    'SIGIR': 'sigir',
    'SIGMETRICS': 'sigmetrics',
    'SIGMOD': 'sigmod',
    'SIGSPATIAL': 'gis',
    'SoCG': 'compgeom',
    'SODA': 'soda',
    'SOSP': 'sosp',
    'SOUPS': 'soups',
    'SP': 'sp',
    'STACS': 'stacs',
    'STOC': 'stoc',
    'TACAS': 'tacas',
    'UAI': 'uai',
    'UIST': 'uist',
    'UMAP': 'um',
    'USENIX': 'usenix',
    'USENIX-Security': 'uss',
    'VLDB': 'vldb',
    'VR': 'vr',
    'WACV': 'wacv',
    'WSDM': 'wsdm',
    'WWW': 'www',
}


def verify_dblp_key(key: str) -> bool:
    """Comprueba que la URL del congreso en DBLP responde correctamente."""
    url = f"https://dblp.org/db/conf/{key}/"
    try:
        r = requests.head(
            url,
            timeout=10,
            allow_redirects=True,
            headers={"User-Agent": "bibliometric-replication/1.0"},
        )
        return r.status_code == 200
    except Exception:
        return False


def load_corpus() -> pd.DataFrame:
    """Carga los ficheros A* y A producidos por el paso 1."""
    path_astar = OUTPUTS / "icore2026_astar.csv"
    path_a = OUTPUTS / "icore2026_a.csv"

    missing_files = [str(p) for p in (path_astar, path_a) if not p.exists()]
    if missing_files:
        raise FileNotFoundError(
            "No se encuentran los ficheros del paso 1: "
            + ", ".join(missing_files)
            + ". Ejecuta primero 01_icore_oficial.py --force."
        )

    df_astar = pd.read_csv(path_astar)
    df_a = pd.read_csv(path_a)

    df_astar["level"] = df_astar["level"].astype(str).str.strip()
    df_a["level"] = df_a["level"].astype(str).str.strip()
    df_astar["acronym"] = df_astar["acronym"].astype(str).str.strip()
    df_a["acronym"] = df_a["acronym"].astype(str).str.strip()

    return pd.concat([df_astar, df_a], ignore_index=True)


def validate_official_corpus(df_all: pd.DataFrame) -> None:
    """Valida que el corpus cargado sea el oficial A*/A 2026."""
    required_cols = {"acronym", "title", "level"}
    missing_cols = sorted(required_cols - set(df_all.columns))
    if missing_cols:
        raise ValueError(f"Faltan columnas obligatorias en el corpus: {missing_cols}")

    n_astar = int((df_all["level"] == "A*").sum())
    n_a = int((df_all["level"] == "A").sum())
    n_total = len(df_all)

    errors = []
    if n_astar != EXPECTED_ASTAR:
        errors.append(f"A* esperado={EXPECTED_ASTAR}, encontrado={n_astar}")
    if n_a != EXPECTED_A:
        errors.append(f"A esperado={EXPECTED_A}, encontrado={n_a}")
    if n_total != EXPECTED_TOTAL:
        errors.append(f"total esperado={EXPECTED_TOTAL}, encontrado={n_total}")

    bad_levels = sorted(set(df_all["level"]) - {"A*", "A"})
    if bad_levels:
        errors.append(f"niveles no oficiales detectados: {bad_levels}")

    duplicated = sorted(df_all[df_all["acronym"].duplicated()]["acronym"].unique())
    if duplicated:
        errors.append(f"acrónimos duplicados: {duplicated}")

    legacy = sorted(set(df_all["acronym"]) & NON_OFFICIAL_LEGACY)
    if legacy:
        errors.append(f"congresos no oficiales de la reconciliación anterior: {legacy}")

    if errors:
        raise ValueError(
            "El corpus cargado no coincide con el listado oficial CORE/ICORE 2026 A/A*:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


def run(force=False, verify=False):
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭  Paso 2 ya completado (usa --force para repetir).")
        return

    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    df_all = load_corpus()
    validate_official_corpus(df_all)

    n_astar = int((df_all["level"] == "A*").sum())
    n_a = int((df_all["level"] == "A").sum())
    print(f"  Congresos oficiales cargados: {len(df_all)} ({n_astar} A* + {n_a} A)")

    # Añadir clave DBLP
    df_all["dblp_key"] = df_all["acronym"].map(DBLP_MAP)
    df_all["dblp_conf_url"] = df_all["dblp_key"].apply(
        lambda k: f"https://dblp.org/db/conf/{k}/" if pd.notna(k) else None
    )

    unmapped = sorted(df_all[df_all["dblp_key"].isna()]["acronym"].tolist())
    if unmapped:
        raise ValueError(
            "Faltan claves DBLP para estos congresos oficiales: "
            + ", ".join(unmapped)
        )

    print(f"  ✅ {len(df_all)}/{EXPECTED_TOTAL} congresos oficiales mapeados a DBLP")

    # Verificación opcional de URLs
    if verify:
        print("  Verificando URLs en dblp.org...")
        df_all["dblp_url_ok"] = df_all["dblp_key"].apply(verify_dblp_key)
        bad = sorted(df_all[~df_all["dblp_url_ok"]]["acronym"].tolist())
        if bad:
            raise ValueError(f"URLs DBLP que no responden: {bad}")
        print("  ✅ Todas las URLs DBLP verificadas")

    df_all.to_csv(OUTPUTS / "conf_dblp_map.csv", index=False)

    result = {
        "step": 2,
        "status": "COMPLETE",
        "official_astar": n_astar,
        "official_a": n_a,
        "official_total": len(df_all),
        "total_mapped": int(df_all["dblp_key"].notna().sum()),
        "total_unmapped": int(df_all["dblp_key"].isna().sum()),
    }
    CHECKPOINT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print("  ✅ Paso 2 completado → outputs/conf_dblp_map.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Repetir aunque ya esté completado")
    parser.add_argument("--verify", action="store_true", help="Verificar cada URL en dblp.org")
    args = parser.parse_args()

    print("=" * 55)
    print("PASO 2 — Mapeo acrónimo → clave DBLP")
    print("=" * 55)

    try:
        run(force=args.force, verify=args.verify)
    except Exception as exc:
        print(f"  ❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)
