"""
PASO 1 — Corpus oficial CORE/ICORE 2026 A* y A

Lee los CSV oficiales separados:
  data/CORE-Astar.csv
  data/CORE-A.csv

y produce:
  outputs/icore2026_astar.csv
  outputs/icore2026_a.csv
  outputs/reconciliacion_corpus.csv

Criterio metodológico:
  - El corpus se define exclusivamente por los congresos oficiales CORE/ICORE 2026 A* y A.
  - No se elevan congresos B ni congresos nacionales.
  - No se excluyen congresos oficiales A/A* por decisiones manuales.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUTPUTS = BASE / "outputs"
CHECKPOINTS = BASE / "checkpoints"
DATA = BASE / "data"
CHECKPOINT_FILE = CHECKPOINTS / "step1.json"

CORE_COLUMNS = [
    "id", "title", "acronym", "source", "rank",
    "dblp_flag", "for1", "for2", "for3",
]

# Asignación de área temática para congresos CORE/ICORE 2026.
# Si un congreso no está en el mapa, se conserva como "Sin clasificar" para
# evitar introducir decisiones no documentadas.
AREA_MAP = {
    # IA / ML
    "NeurIPS":"IA / ML","CVPR":"IA / ML","ICML":"IA / ML","IJCAI":"IA / ML",
    "AAAI":"IA / ML","ICCV":"IA / ML","ICLR":"IA / ML","ECCV":"IA / ML",
    "EMNLP":"IA / ML","ACL":"IA / ML","ICRA":"IA / ML","ACMMM":"IA / ML",
    "ICAPS":"IA / ML","KR":"IA / ML","AISTATS":"IA / ML","Interspeech":"IA / ML",
    "IROS":"IA / ML","ECML PKDD":"IA / ML","MICCAI":"IA / ML","WACV":"IA / ML",
    "ICDAR":"IA / ML","ICME":"IA / ML","AAMAS":"IA / ML","UAI":"IA / ML",
    "BMVC":"IA / ML",
    "GECCO":"IA / ML","NAACL":"IA / ML","EACL":"IA / ML",
    "ECAI":"IA / ML","PAKDD":"IA / ML","SDM":"IA / ML","RecSys":"IA / ML",
    "ICWSM":"IA / ML","AIED":"IA / ML","LAK":"IA / ML",
    "PPSN":"IA / ML","FOGA":"IA / ML",

    # Ing. del Software / Lenguajes / Métodos formales
    "ICSE":"Ing. del Software","FSE":"Ing. del Software","ASE":"Ing. del Software",
    "PLDI":"Ing. del Software","POPL":"Ing. del Software","CAV":"Ing. del Software",
    "ICSME":"Ing. del Software","ESEM":"Ing. del Software","BPM":"Ing. del Software",
    "MODELS":"Ing. del Software","EASE":"Ing. del Software","ICSA":"Ing. del Software",
    "ICST":"Ing. del Software","ISSRE":"Ing. del Software","SEAMS":"Ing. del Software",
    "ESOP":"Ing. del Software","ICFP":"Ing. del Software","OOPSLA":"Ing. del Software",
    "ECOOP":"Ing. del Software","MSR":"Ing. del Software","SANER":"Ing. del Software",
    "ISSTA":"Ing. del Software","CGO":"Ing. del Software","CC":"Ing. del Software",
    "ICPC":"Ing. del Software","RE":"Ing. del Software","TACAS":"Ing. del Software",
    "FM":"Ing. del Software","IFM":"Ing. del Software","ICSOC":"Ing. del Software",
    "CaiSE":"Ing. del Software",

    # Sistemas
    "MICRO":"Sistemas","DAC":"Sistemas","ISCA":"Sistemas","ASPLOS":"Sistemas",
    "SIGMETRICS":"Sistemas","OSDI":"Sistemas","SOSP":"Sistemas","PODC":"Sistemas",
    "HPCA":"Sistemas","ICDCS":"Sistemas","EuroSys":"Sistemas","USENIX":"Sistemas",
    "HotOS":"Sistemas","Middleware":"Sistemas",
    "USENIX-ATC":"Sistemas","FAST":"Sistemas","USENIX-FAST":"Sistemas",
    "SC":"Sistemas","PPoPP":"Sistemas","HPDC":"Sistemas","IPDPS":"Sistemas",
    "ICS":"Sistemas","ICCAD":"Sistemas","ISLPED":"Sistemas",
    "ITC":"Sistemas","FPGA":"Sistemas","DATE":"Sistemas","EMSOFT":"Sistemas",
    "RTAS":"Sistemas","RTSS":"Sistemas","Euro-Par":"Sistemas","CLUSTER":"Sistemas",
    "DSN":"Sistemas","DISC":"Sistemas",

    # Redes
    "INFOCOM":"Redes","SIGCOMM":"Redes","MOBICOM":"Redes","IMC":"Redes",
    "CoNEXT":"Redes","SECON":"Redes","MobiHoc":"Redes","MobiSys":"Redes",
    "SenSys":"Redes","ICWS":"Redes","MMSys":"Redes","Mobisys":"Redes",
    "MSWIM":"Redes",

    # Seguridad
    "SP":"Seguridad","CCS":"Seguridad","USENIX-Security":"Seguridad",
    "NDSS":"Seguridad","EuroCrypt":"Seguridad","CRYPTO":"Seguridad",
    "ESORICS":"Seguridad","PKC":"Seguridad","ASIACRYPT":"Seguridad",
    "TCC":"Seguridad","FC":"Seguridad","ACNS":"Seguridad","RAID":"Seguridad",
    "ACSAC":"Seguridad","AsiaCCS":"Seguridad","PETS":"Seguridad","CHES":"Seguridad",
    "EuroS&P":"Seguridad","CSF":"Seguridad","SOUPS":"Seguridad",

    # Bases de datos / Web / Recuperación de información
    "WWW":"Bases de datos","VLDB":"Bases de datos","KDD":"Bases de datos",
    "ICDE":"Bases de datos","SIGMOD":"Bases de datos","SIGIR":"Bases de datos",
    "ICDM":"Bases de datos","PODS":"Bases de datos","WSDM":"Bases de datos",
    "CIKM":"Bases de datos","DASFAA":"Bases de datos",
    "SSDBM":"Bases de datos","ECIR":"Bases de datos","CHIIR":"Bases de datos",
    "ISWC":"Bases de datos","SIGSPATIAL":"Bases de datos","ICDT":"Bases de datos",
    "CIDR":"Bases de datos","ER":"Bases de datos",

    # Teoría
    "ICALP":"Teoría","SODA":"Teoría","STOC":"Teoría","FOCS":"Teoría",
    "LICS":"Teoría","SoCG":"Teoría","EC":"Teoría","COLT":"Teoría",
    "STACS":"Teoría","ESA":"Teoría","APPROX":"Teoría","IPCO":"Teoría",
    "LATIN":"Teoría","SWAT":"Teoría","MFCS":"Teoría","FSTTCS":"Teoría",
    "ISAAC":"Teoría","CONCUR":"Teoría","IJCAR":"Teoría","CADE":"Teoría",
    "GD":"Teoría","CCC":"Teoría","ITCS":"Teoría","SAT":"Teoría","CP":"Teoría",
    "ALENEX":"Teoría","APPROX/RANDOM":"Teoría",

    # HCI / Visualización / Educación
    "CHI":"HCI","UIST":"HCI","VR":"HCI","HRI":"HCI","PERCOM":"HCI",
    "ISMAR":"HCI","SIGGRAPH":"HCI","SiggraphA":"HCI","CSCW":"HCI",
    "DIS":"HCI","IUI":"HCI","MobileHCI":"HCI","ASSETS":"HCI","IDC":"HCI",
    "INTERACT":"HCI","GROUP":"HCI","VRST":"HCI","UMAP":"HCI",
    "SIGCSE":"HCI","ICER":"HCI","IEEE VIS":"HCI",

    # Bioinformática computacional
    "ISMB":"Bioinformática",
}


def _clean_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["title", "acronym", "source", "rank", "dblp_flag", "for1", "for2", "for3"]:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()
    return df


def load_rank_file(path: Path, expected_rank: str) -> pd.DataFrame:
    """Carga un CSV oficial CORE sin cabecera y valida que todas las filas tengan el rank esperado."""
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Copia el CSV oficial CORE {expected_rank} en data/ "
            f"o pasa su ruta con --core-{expected_rank.lower().replace('*', 'star')}."
        )

    df = pd.read_csv(path, header=None, names=CORE_COLUMNS, on_bad_lines="skip", encoding="utf-8")
    df = _clean_string_columns(df)
    df = df[df["acronym"].notna() & (df["acronym"] != "")].copy()

    ranks = set(df["rank"].dropna().unique())
    if ranks != {expected_rank}:
        raise ValueError(
            f"{path.name} debe contener solo rank={expected_rank}; encontrados: {sorted(ranks)}"
        )

    duplicated = df[df["acronym"].duplicated(keep=False)]["acronym"].tolist()
    if duplicated:
        raise ValueError(f"Acrónimos duplicados en {path.name}: {sorted(set(duplicated))}")

    return df


def corpus_rows(df: pd.DataFrame, level: str) -> list[dict]:
    rows = []
    for _, row in df.sort_values("acronym", kind="stable").iterrows():
        acr = row["acronym"]
        rows.append({
            "acronym": acr,
            "title": row["title"],
            "level": level,
            "area": AREA_MAP.get(acr, "Sin clasificar"),
            "for1": row["for1"] if pd.notna(row["for1"]) else None,
            "status": "CORE_2026_OFICIAL",
        })
    return rows


def build_corpus(core_astar_path: Path, core_a_path: Path):
    """Devuelve (astar, a_level, reconciliation) usando solo listados oficiales CORE 2026."""
    astar_df = load_rank_file(core_astar_path, "A*")
    a_df = load_rank_file(core_a_path, "A")

    overlap = sorted(set(astar_df["acronym"]) & set(a_df["acronym"]))
    if overlap:
        raise ValueError(f"Acrónimos presentes tanto en A* como en A: {overlap}")

    astar = corpus_rows(astar_df, "A*")
    a_level = corpus_rows(a_df, "A")

    # Se conserva el fichero por compatibilidad con pasos posteriores, pero ya
    # no hay reconciliación manual: el corpus coincide con los CSV oficiales.
    reconciliation = [{
        "status": "SIN_RECONCILIACION_MANUAL",
        "detalle": "Corpus definido exclusivamente por CORE-Astar.csv y CORE-A.csv oficiales.",
        "astar": len(astar),
        "a_level": len(a_level),
        "total": len(astar) + len(a_level),
    }]

    return astar, a_level, reconciliation


def run(force=False, core_astar_path=None, core_a_path=None):
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭  Paso 1 ya completado (usa --force para repetir).")
        return

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    core_astar_path = Path(core_astar_path) if core_astar_path else DATA / "CORE-Astar.csv"
    core_a_path = Path(core_a_path) if core_a_path else DATA / "CORE-A.csv"

    astar, a_level, reconciliation = build_corpus(core_astar_path, core_a_path)

    df_astar = pd.DataFrame(astar)
    df_a = pd.DataFrame(a_level)
    df_rec = pd.DataFrame(reconciliation)

    df_astar.to_csv(OUTPUTS / "icore2026_astar.csv", index=False)
    df_a.to_csv(OUTPUTS / "icore2026_a.csv", index=False)
    df_rec.to_csv(OUTPUTS / "reconciliacion_corpus.csv", index=False)

    unclassified = sorted(
        {r["acronym"] for r in astar + a_level if r["area"] == "Sin clasificar"}
    )

    result = {
        "step": 1,
        "status": "COMPLETE",
        "source": "CORE_2026_OFICIAL_ASTAR_A",
        "core_astar_csv": str(core_astar_path),
        "core_a_csv": str(core_a_path),
        "astar": len(astar),
        "a_level": len(a_level),
        "total": len(astar) + len(a_level),
        "reconciliation_rows": len(reconciliation),
        "unclassified_area": unclassified,
    }
    CHECKPOINT_FILE.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"  CORE A*: {core_astar_path}")
    print(f"  CORE A : {core_a_path}")
    print(f"\n  A*: {len(astar)} | A: {len(a_level)} | Total: {len(astar) + len(a_level)}")
    print("  Reconciliación manual: desactivada; se usan solo listados oficiales.")
    if unclassified:
        print(f"  ⚠️  Congresos sin área asignada: {', '.join(unclassified)}")
    print("  ✅ Paso 1 completado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--core-astar", default=None, help="Ruta al CSV oficial CORE A*.")
    parser.add_argument("--core-a", default=None, help="Ruta al CSV oficial CORE A.")
    args = parser.parse_args()

    print("=" * 60)
    print("PASO 1 — Corpus oficial CORE/ICORE2026 (A* + A)")
    print("=" * 60)
    run(force=args.force, core_astar_path=args.core_astar, core_a_path=args.core_a)
