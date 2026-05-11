"""
PASO 3b — Validación de cobertura del corpus DBLP oficial

Comprueba qué congresos del corpus oficial CORE/ICORE 2026 A*/A tienen
0 artículos extraídos en outputs/dblp_inproceedings.csv.

Entrada:
  outputs/conf_dblp_map.csv       (62 A* + 108 A = 170 congresos oficiales)
  outputs/dblp_inproceedings.csv  (generado por 03_dblp_download_oficial.py)

Salida:
  outputs/corpus_coverage_report.txt

USO:
  python 03b_validate_corpus_oficial.py
"""

import importlib.util
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE        = Path(__file__).resolve().parent.parent
OUTPUTS     = BASE / "outputs"
HEADERS     = {'User-Agent': 'bibliometric-replication/1.0'}
YEAR_MIN, YEAR_MAX = 2001, 2025
EXPECTED_ASTAR = 62
EXPECTED_A = 108
EXPECTED_TOTAL = 170
INHERITED_NON_OFFICIAL = {'COLING', 'EDBT', 'NSDI', 'PACT', 'SoCC'}
SUSPICIOUS_LOW_COVERAGE = {
    'ITCS': 50,
    'IJCAR': 20,
    'SIGSPATIAL': 50,
    'PETS': 50,
}


def _script_candidates() -> list[Path]:
    """Busca el script del paso 3 en nombres habituales."""
    return [
        BASE / "scripts" / "03_dblp_download_oficial.py",
        Path(__file__).resolve().with_name("03_dblp_download_oficial.py"),
        BASE / "scripts" / "03_dblp_download.py",
        Path(__file__).resolve().with_name("03_dblp_download.py"),
        Path("/mnt/data/03_dblp_download_oficial.py"),
    ]


def load_step3_filters():
    """Carga ACCEPTED_BOOKTITLES, BOOKTITLE_PREFIXES y ALT_DBLP_PREFIXES del paso 3."""
    for path in _script_candidates():
        if path.exists():
            spec = importlib.util.spec_from_file_location("step3_filters", path)
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
            return (
                getattr(module, "ACCEPTED_BOOKTITLES", {}),
                getattr(module, "BOOKTITLE_PREFIXES", {}),
                getattr(module, "ALT_DBLP_PREFIXES", {}),
                path,
            )
    raise FileNotFoundError("No se ha encontrado 03_dblp_download.py para cargar los filtros de booktitle.")


def load_official_map() -> pd.DataFrame:
    map_csv = OUTPUTS / "conf_dblp_map.csv"
    if not map_csv.exists():
        raise FileNotFoundError(f"No se encuentra {map_csv}. Ejecuta primero el paso 2 oficial.")

    conf_df = pd.read_csv(map_csv)
    required = {'acronym', 'level', 'area', 'dblp_key'}
    missing_cols = required - set(conf_df.columns)
    if missing_cols:
        raise ValueError(f"Faltan columnas en conf_dblp_map.csv: {sorted(missing_cols)}")

    n_astar = int((conf_df['level'] == 'A*').sum())
    n_a = int((conf_df['level'] == 'A').sum())
    if len(conf_df) != EXPECTED_TOTAL or n_astar != EXPECTED_ASTAR or n_a != EXPECTED_A:
        raise ValueError(
            "conf_dblp_map.csv no es el corpus oficial esperado "
            f"({EXPECTED_ASTAR} A* + {EXPECTED_A} A = {EXPECTED_TOTAL}); "
            f"encontrado {n_astar} A* + {n_a} A = {len(conf_df)}."
        )

    duplicated = conf_df[conf_df['acronym'].duplicated()]['acronym'].tolist()
    if duplicated:
        raise ValueError(f"Acrónimos duplicados en conf_dblp_map.csv: {duplicated}")

    inherited = sorted(INHERITED_NON_OFFICIAL & set(conf_df['acronym']))
    if inherited:
        raise ValueError(f"El corpus aún contiene congresos no oficiales heredados: {inherited}")

    if conf_df['dblp_key'].isna().any() or (conf_df['dblp_key'].astype(str).str.strip() == '').any():
        bad = conf_df[conf_df['dblp_key'].isna() | (conf_df['dblp_key'].astype(str).str.strip() == '')]['acronym'].tolist()
        raise ValueError(f"Congresos sin dblp_key: {bad}")

    return conf_df


def check_dblp_key(key: str, session: requests.Session | None = None) -> tuple[bool | None, str]:
    """Verifica si la clave DBLP existe y devuelve la URL final."""
    http = session or requests
    url = f"https://dblp.org/db/conf/{key}/"
    for attempt in range(3):
        try:
            r = http.get(url, timeout=15, headers=HEADERS, allow_redirects=True)
            time.sleep(1.5)
            if r.status_code == 200:
                return True, r.url
            if r.status_code == 404:
                return False, "HTTP 404"
            return None, f"HTTP {r.status_code} (posible rate limiting)"
        except Exception:
            time.sleep(3 * (attempt + 1))
    return None, "Sin respuesta tras 3 intentos (posible rate limiting DBLP)"


def get_dblp_booktitles(
    key: str,
    n_recent: int = 4,
    session: requests.Session | None = None,
) -> list[str]:
    """Obtiene títulos/cabeceras de ediciones recientes en DBLP para diagnóstico."""
    http = session or requests
    url = f"https://dblp.org/db/conf/{key}/"
    try:
        r = http.get(url, timeout=15, headers=HEADERS, allow_redirects=True)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, 'html.parser')
        recent_years = range(max(YEAR_MIN, YEAR_MAX - 7), YEAR_MAX + 1)
        links = [
            a['href'] for a in soup.find_all('a', href=True)
            if f'conf/{key}' in a['href'] and any(str(y) in a['href'] for y in recent_years)
        ]
        booktitles = []
        seen = set()
        for href in links:
            if len(booktitles) >= n_recent:
                break
            yr_url = href if href.startswith('http') else f'https://dblp.org{href}'
            if yr_url in seen:
                continue
            seen.add(yr_url)
            try:
                r2 = http.get(yr_url, timeout=10, headers=HEADERS, allow_redirects=True)
                if r2.status_code == 200:
                    soup2 = BeautifulSoup(r2.text, 'html.parser')
                    h1 = soup2.find('h1')
                    if h1:
                        booktitles.append(h1.text.strip()[:160])
                time.sleep(0.3)
            except Exception:
                pass
        return booktitles
    except Exception:
        return []


def matches_filter(booktitle: str, filters: set[str], prefixes: set[str]) -> bool:
    bt = (booktitle or '').casefold()
    filters_norm = {f.casefold() for f in filters}
    prefixes_norm = {p.casefold() for p in prefixes}
    # Misma lógica que el paso 3: exacto por defecto; parcial solo si existe
    # entrada explícita en BOOKTITLE_PREFIXES.
    return bt in filters_norm or any(p in bt for p in prefixes_norm)


def run():
    conf_df = load_official_map()
    accepted, prefixes, alt_prefixes, filter_path = load_step3_filters()

    official_acronyms = set(conf_df['acronym'])
    missing_filters = sorted(official_acronyms - set(accepted))
    if missing_filters:
        raise ValueError(f"Faltan filtros ACCEPTED_BOOKTITLES para congresos oficiales: {missing_filters}")

    stale_filters = sorted((set(accepted) - official_acronyms) & INHERITED_NON_OFFICIAL)
    if stale_filters:
        raise ValueError(f"El paso 3 conserva filtros de congresos no oficiales heredados: {stale_filters}")

    print(f"  Mapa oficial: {len(conf_df)} congresos ({EXPECTED_ASTAR} A* + {EXPECTED_A} A)")
    print(f"  Filtros de booktitle cargados desde: {filter_path}")
    if alt_prefixes:
        print(f"  Prefijos DBLP alternativos configurados: {alt_prefixes}")

    dblp_csv = OUTPUTS / "dblp_inproceedings.csv"
    if not dblp_csv.exists():
        raise FileNotFoundError("No se encuentra outputs/dblp_inproceedings.csv. Ejecuta primero el paso 3.")

    required = {'congress', 'level', 'year', 'booktitle'}
    df = pd.read_csv(
        dblp_csv,
        usecols=lambda col: col in required,
        dtype={'congress': 'string', 'level': 'string', 'booktitle': 'string'},
    )
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise ValueError(f"Faltan columnas en dblp_inproceedings.csv: {sorted(missing_cols)}")

    df['year'] = pd.to_numeric(df['year'], errors='coerce')
    if df['year'].isna().any():
        bad = df[df['year'].isna()][['congress', 'year']].head().to_dict('records')
        raise ValueError(f"Hay registros con año no numérico. Ejemplos: {bad}")

    outside = sorted(set(df['congress']) - official_acronyms)
    if outside:
        raise ValueError(f"El CSV extraído contiene congresos fuera del corpus oficial: {outside}")

    if not df.empty:
        years_bad = df[(df['year'] < YEAR_MIN) | (df['year'] > YEAR_MAX)]
        if not years_bad.empty:
            raise ValueError(
                f"Hay {len(years_bad)} registros fuera del rango {YEAR_MIN}-{YEAR_MAX}. "
                f"Ejemplos: {years_bad[['congress', 'year']].head().to_dict('records')}"
            )

    print(f"  Artículos en corpus: {len(df):,}")
    print(f"  Congresos únicos con datos: {df['congress'].nunique()}")

    counts = df.groupby(['congress', 'level']).size().reset_index(name='n_articles') if not df.empty else pd.DataFrame(columns=['congress', 'level', 'n_articles'])
    congresos_con_datos = set(counts['congress'].unique())
    todos_congresos = official_acronyms
    sin_datos = sorted(todos_congresos - congresos_con_datos)

    conf_levels = dict(zip(conf_df['acronym'], conf_df['level']))
    conf_keys = dict(zip(conf_df['acronym'], conf_df['dblp_key']))

    criticos = [c for c in sin_datos if conf_levels.get(c) == 'A*']
    revisar  = [c for c in sin_datos if conf_levels.get(c) != 'A*']

    print(f"\n  🔴 CRÍTICOS (A* con 0 artículos): {len(criticos)}")
    print(f"  🟡 A REVISAR (A con 0 artículos):  {len(revisar)}")
    print(f"  ✅ Con datos: {len(congresos_con_datos)}")

    report_lines = []
    report_lines.append("=== INFORME DE COBERTURA DEL CORPUS OFICIAL CORE/ICORE 2026 ===\n")
    report_lines.append(f"Rango temporal esperado: {YEAR_MIN}-{YEAR_MAX}")
    report_lines.append(f"Congresos oficiales: {len(todos_congresos)} ({EXPECTED_ASTAR} A* + {EXPECTED_A} A)")
    report_lines.append(f"Artículos totales: {len(df):,}")
    report_lines.append(f"Congresos con datos: {len(congresos_con_datos)}")
    report_lines.append(f"Congresos sin datos: {len(sin_datos)}")
    report_lines.append(f"  🔴 A* (críticos): {len(criticos)}")
    report_lines.append(f"  🟡 A (a revisar): {len(revisar)}\n")

    all_to_check = [(c, '🔴 A*') for c in sorted(criticos)] + [(c, '🟡 A ') for c in sorted(revisar)]
    if all_to_check:
        print(f"\n  Diagnosticando {len(all_to_check)} congresos sin datos")
        report_lines.append("=== DIAGNÓSTICO DE CONGRESOS SIN DATOS ===\n")

    with requests.Session() as session:
        session.headers.update(HEADERS)

        for congress, marker in all_to_check:
            key = conf_keys.get(congress, '???')
            filtro = set(accepted.get(congress, set()))
            pref = set(prefixes.get(congress, set()))
            booktitles = []
            print(f"  {marker} {congress:20s} key={key}", end="", flush=True)

            key_ok, final_url = check_dblp_key(key, session=session)
            if key_ok is None:
                diagnosis = f"⚠️ No verificable por posible rate limiting: '{key}'"
            elif not key_ok:
                diagnosis = f"❌ CLAVE DBLP INCORRECTA O NO ACCESIBLE: '{key}'"
            else:
                booktitles = get_dblp_booktitles(key, session=session)
                if not booktitles:
                    diagnosis = f"⚠️ Clave OK ({final_url}) pero sin ediciones recientes detectadas en la página de DBLP"
                elif any(matches_filter(bt, filtro, pref) for bt in booktitles):
                    diagnosis = "✅ Clave y filtro parecen coherentes; revisar si no hubo ediciones/artículos en el rango"
                else:
                    diagnosis = "⚠️ FILTRO NO COINCIDE con cabeceras recientes de DBLP"

            print(f" → {diagnosis}")
            report_lines.append(f"{marker} {congress}")
            report_lines.append(f"  clave DBLP: {key}")
            report_lines.append(f"  filtro booktitle exacto: {sorted(filtro)}")
            if pref:
                report_lines.append(f"  filtro booktitle parcial: {sorted(pref)}")
            if key_ok:
                report_lines.append(f"  URL DBLP: {final_url}")
                if booktitles:
                    report_lines.append(f"  cabeceras DBLP recientes: {booktitles}")
            report_lines.append(f"  DIAGNÓSTICO: {diagnosis}\n")

    report_lines.append("\n=== CONGRESOS CON MUY POCOS ARTÍCULOS (< 10 en todo el período) ===\n")
    if not df.empty:
        total_by_conf = df.groupby('congress').size()
        pocos = total_by_conf[total_by_conf < 10].sort_values()
        if pocos.empty:
            report_lines.append("  Ninguno")
        else:
            for congress, n in pocos.items():
                level = conf_levels.get(congress, '?')
                marker = "🔴" if level == "A*" else "🟡"
                report_lines.append(f"  {marker} {congress:20s} {n:3d} artículos (nivel {level})")

    report_path = OUTPUTS / "corpus_coverage_report.txt"
    report_path.write_text("\n".join(report_lines), encoding='utf-8')
    print(f"\n  Informe guardado en: {report_path}")

    if criticos:
        print(f"\n  ACCIÓN REQUERIDA: corregir {len(criticos)} congresos A* antes de continuar con el paso 4.")
    elif revisar:
        print(f"\n  Revisa los {len(revisar)} congresos A sin datos si parecen sospechosos.")
    else:
        print("\n  ✅ Todos los congresos oficiales tienen artículos.")


if __name__ == "__main__":
    print("=" * 60)
    print("PASO 3b — Validación de cobertura del corpus oficial")
    print("=" * 60)
    try:
        run()
    except Exception as exc:
        print(f"❌ {exc}")
        sys.exit(1)
