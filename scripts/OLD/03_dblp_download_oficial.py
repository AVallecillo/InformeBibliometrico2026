"""
PASO 3 — Descargar dump XML de DBLP y extraer inproceedings
Descarga dblp.xml.gz (~4 GB), lo parsea en streaming y extrae los artículos
de los congresos del corpus, para los años 2001-2025.
Filtro de track principal: solo se conservan artículos cuyo <booktitle> coincide
exactamente con el acrónimo del congreso (excluye workshops, companion, etc.)
Produce:
  outputs/dblp_inproceedings.csv   (congress, year, title, doi, arxiv_id, authors, booktitle)
  data/dblp.xml.gz                 (dump completo, conservado para auditoría)

NOTA sobre entidades HTML:
  El XML de DBLP usa entidades como &uuml; &auml; &eacute; etc. que no son
  entidades XML estándar. Las resolvemos al vuelo antes de entregar el XML al
  parser, preservando UTF-8 coherente para nombres y títulos con acentos.
"""

import argparse
import csv
import gzip
import json
import re
from html.entities import html5 as HTML5_ENTITIES
from pathlib import Path

import requests
from tqdm import tqdm

# ── Intentar importar lxml; si no está, usar xml.etree con workaround ────────
try:
    from lxml import etree as ET
    USING_LXML = True
except ImportError:
    from xml.etree import ElementTree as ET
    USING_LXML = False

# Tabla de entidades HTML más frecuentes en DBLP
# (las que no están cubiertas por las entidades XML básicas &amp; &lt; &gt; &quot; &apos;)
HTML_ENTITIES = {
    # Latin-1 supplement
    "&Agrave;":"À","&Aacute;":"Á","&Acirc;":"Â","&Atilde;":"Ã","&Auml;":"Ä",
    "&Aring;":"Å","&AElig;":"Æ","&Ccedil;":"Ç","&Egrave;":"È","&Eacute;":"É",
    "&Ecirc;":"Ê","&Euml;":"Ë","&Igrave;":"Ì","&Iacute;":"Í","&Icirc;":"Î",
    "&Iuml;":"Ï","&ETH;":"Ð","&Ntilde;":"Ñ","&Ograve;":"Ò","&Oacute;":"Ó",
    "&Ocirc;":"Ô","&Otilde;":"Õ","&Ouml;":"Ö","&Oslash;":"Ø","&Ugrave;":"Ù",
    "&Uacute;":"Ú","&Ucirc;":"Û","&Uuml;":"Ü","&Yacute;":"Ý","&THORN;":"Þ",
    "&szlig;":"ß","&agrave;":"à","&aacute;":"á","&acirc;":"â","&atilde;":"ã",
    "&auml;":"ä","&aring;":"å","&aelig;":"æ","&ccedil;":"ç","&egrave;":"è",
    "&eacute;":"é","&ecirc;":"ê","&euml;":"ë","&igrave;":"ì","&iacute;":"í",
    "&icirc;":"î","&iuml;":"ï","&eth;":"ð","&ntilde;":"ñ","&ograve;":"ò",
    "&oacute;":"ó","&ocirc;":"ô","&otilde;":"õ","&ouml;":"ö","&oslash;":"ø",
    "&ugrave;":"ù","&uacute;":"ú","&ucirc;":"û","&uuml;":"ü","&yacute;":"ý",
    "&thorn;":"þ","&yuml;":"ÿ",
    # Especiales frecuentes
    "&nbsp;":" ","&ndash;":"–","&mdash;":"—","&laquo;":"«","&raquo;":"»",
    "&ldquo;":"“","&rdquo;":"”","&lsquo;":"'","&rsquo;":"'",
    "&hellip;":"…","&bull;":"•","&copy;":"©","&reg;":"®","&trade;":"™",
    "&alpha;":"α","&beta;":"β","&gamma;":"γ","&delta;":"δ","&epsilon;":"ε",
    "&mu;":"μ","&pi;":"π","&sigma;":"σ","&tau;":"τ","&phi;":"φ","&omega;":"ω",
    "&times;":"×","&divide;":"÷","&plusmn;":"±","&middot;":"·",
    "&acute;":"´","&cedil;":"¸","&Ocirc;":"Ô",
}

# Ampliar con las entidades HTML5 de la librería estándar, sin tocar las
# entidades XML básicas que el parser debe resolver por sí mismo.
XML_BASIC_ENTITIES = {"&amp;", "&lt;", "&gt;", "&quot;", "&apos;"}
HTML_ENTITIES.update({
    f"&{name}": value
    for name, value in HTML5_ENTITIES.items()
    if name.endswith(";") and f"&{name}" not in XML_BASIC_ENTITIES
})
HTML_ENTITIES["&nbsp;"] = " "

BASE = Path(__file__).resolve().parent.parent
OUTPUTS     = BASE / "outputs"
DATA        = BASE / "data"
CHECKPOINTS = BASE / "checkpoints"
CHECKPOINT_FILE = CHECKPOINTS / "step3.json"

DBLP_DUMP_URL = "https://dblp.org/xml/dblp.xml.gz"
DBLP_DTD_URL  = "https://dblp.org/xml/dblp.dtd"
YEAR_MIN, YEAR_MAX = 2001, 2025
TARGET_DBLP_TAGS = {"inproceedings", "article"}
CLEARABLE_DBLP_TAGS = TARGET_DBLP_TAGS | {
    "book",
    "data",
    "incollection",
    "mastersthesis",
    "person",
    "phdthesis",
    "proceedings",
    "www",
}

XML_DECL_RE = re.compile(
    r'(<\?xml[^>]*encoding=)(["\'])iso-8859-1\2',
    flags=re.IGNORECASE,
)

# ── Filtro de track principal ──────────────────────────────────────────────────
# Booktitles aceptados por congreso. La clave es el acrónimo del corpus;
# los valores son los booktitles que DBLP usa para el track principal.
# Algunos congresos usan variantes (e.g. "ACL (1)"/"ACL (2)" para volúmenes).
# Los workshops/companion/extended-abstracts quedan EXCLUIDOS.
#
# BOOKTITLE_PREFIXES: para congresos cuyo booktitle incluye año/edición/ciudad
# (cambia cada año), se acepta si el booktitle CONTIENE alguno de estos tokens.
BOOKTITLE_PREFIXES = {
    "ECCV":      {"ECCV"},
    "SIGGRAPH":  {"SIGGRAPH"},
    "SiggraphA": {"SIGGRAPH Asia"},
    # APPROX/RANDOM aparece en DBLP con variantes de proceedings combinados.
    "APPROX/RANDOM": {"APPROX", "RANDOM"},
}

# Prefijos DBLP adicionales que no son conf/<dblp_key> pero corresponden al
# track principal del congreso. Caso importante: desde 2008 VLDB publica como
# Proceedings of the VLDB Endowment, que DBLP indexa bajo journals/pvldb.
ALT_DBLP_PREFIXES = {
    "VLDB": {"journals/pvldb"},
    # Desde 2015 PETS se publica como Proceedings on Privacy Enhancing Technologies (PoPETs).
    "PETS": {"journals/popets"},
}

ACCEPTED_BOOKTITLES = {
    # IA / ML
    "NeurIPS":    {"NeurIPS", "NIPS"},
    "CVPR":       {"CVPR"},
    "ICML":       {"ICML"},
    "IJCAI":      {"IJCAI"},
    "AAAI":       {"AAAI"},
    "ICCV":       {"ICCV"},
    "ICLR":       {"ICLR"},
    "ECCV":       {"ECCV"},
    "EMNLP":      {"EMNLP", "EMNLP (1)", "EMNLP (2)"},
    "ACL":        {"ACL", "ACL (1)", "ACL (2)"},
    "ICRA":       {"ICRA"},
    "ACMMM":      {"ACM Multimedia", "MM"},
    "ICAPS":      {"ICAPS"},
    "KR":         {"KR"},
    "AISTATS":    {"AISTATS"},
    "Interspeech":{"Interspeech", "INTERSPEECH"},
    "IROS":       {"IROS"},
    "ECML PKDD":  {"ECML/PKDD", "ECML PKDD", "PKDD", "ECML"},
    "MICCAI":     {"MICCAI"},
    "WACV":       {"WACV"},
    "ICDAR":      {"ICDAR"},
    "ICME":       {"ICME"},
    "AAMAS":      {"AAMAS"},
    "UAI":        {"UAI"},
    "GECCO":      {"GECCO"},
    "FOGA":       {"FOGA"},
    "PPSN":       {"PPSN"},
    "NAACL":      {"NAACL-HLT", "NAACL"},
    "EACL":       {"EACL"},
    "RecSys":     {"RecSys"},
    "ICWSM":      {"ICWSM"},
    "ECAI":       {"ECAI"},
    "BMVC":       {"BMVC"},
    "SDM":        {"SDM"},
    "AIED":       {"AIED"},
    "LAK":        {"LAK"},
    "ISMB":       {"ISMB"},
    # Ing. del Software
    "ICSE":       {"ICSE"},
    "FSE":        {"SIGSOFT FSE", "FSE", "ESEC/FSE"},
    "ASE":        {"ASE"},
    "PLDI":       {"PLDI"},
    "POPL":       {"POPL"},
    "CAV":        {"CAV"},
    "ICSME":      {"ICSM", "ICSME"},
    "ESEM":       {"ESEM"},
    "BPM":        {"BPM"},
    "MODELS":     {"MoDELS", "MODELS"},
    "EASE":       {"EASE"},
    "ICSA":       {"ICSA"},
    "ICST":       {"ICST"},
    "ISSRE":      {"ISSRE"},
    "SEAMS":      {"SEAMS"},
    "ESOP":       {"ESOP"},
    "ICFP":       {"ICFP"},
    "OOPSLA":     {"OOPSLA"},
    "ECOOP":      {"ECOOP"},
    "CGO":        {"CGO"},
    "MSR":        {"MSR"},
    "SANER":      {"SANER", "WCRE", "CSMR"},
    "ISSTA":      {"ISSTA"},
    "ICPC":       {"ICPC"},
    "RE":         {"RE"},
    "TACAS":      {"TACAS"},
    "ICSOC":      {"ICSOC"},
    "CaiSE":      {"CAiSE"},
    # Sistemas
    "MICRO":      {"MICRO"},
    "DAC":        {"DAC"},
    "ISCA":       {"ISCA"},
    "ASPLOS":     {"ASPLOS"},
    "SIGMETRICS": {"SIGMETRICS"},
    "OSDI":       {"OSDI"},
    "SOSP":       {"SOSP"},
    "PODC":       {"PODC"},
    "HPCA":       {"HPCA"},
    "ICDCS":      {"ICDCS"},
    "EuroSys":    {"EuroSys"},
    "USENIX":     {"USENIX ATC", "USENIX Annual Technical Conference"},
    "HotOS":      {"HotOS"},
    "Middleware": {"Middleware"},
    "FAST":       {"FAST", "FAST (General Track)"},
    "SC":         {"SC"},
    "HPDC":       {"HPDC"},
    "IPDPS":      {"IPDPS"},
    "ICS":        {"ICS"},
    "ICCAD":      {"ICCAD"},
    "ISLPED":     {"ISLPED"},
    "ITC":        {"ITC"},
    "FPGA":       {"FPGA"},
    "DATE":       {"DATE"},
    "RTAS":       {"RTAS"},
    "RTSS":       {"RTSS"},
    "DSN":        {"DSN"},
    "DISC":       {"DISC"},
    # Redes
    "INFOCOM":    {"INFOCOM"},
    "SIGCOMM":    {"SIGCOMM"},
    "MOBICOM":    {"MobiCom"},
    "IMC":        {"IMC"},
    "CoNEXT":     {"CoNEXT"},
    "Mobisys":    {"MobiSys"},
    "ICWS":       {"ICWS"},
    "MMSys":      {"MMSys"},
    "MSWIM":      {"MSWiM", "MSWIM"},
    # Seguridad
    "SP":         {"IEEE Symposium on Security and Privacy", "S&P"},
    "CCS":        {"CCS"},
    "USENIX-Security": {"USENIX Security Symposium"},
    "NDSS":       {"NDSS"},
    "EuroCrypt":  {"EUROCRYPT"},
    "CRYPTO":     {"CRYPTO"},
    "ESORICS":    {"ESORICS"},
    "ASIACRYPT":  {"ASIACRYPT"},
    "FC":         {"FC"},
    "RAID":       {"RAID"},
    "ACSAC":      {"ACSAC"},
    "AsiaCCS":    {"AsiaCCS"},
    "PETS":       {"PETS", "PoPETs", "Proceedings on Privacy Enhancing Technologies"},
    "CHES":       {"CHES"},
    "EuroS&P":    {"EuroS&P"},
    "CSF":        {"CSF"},
    "SOUPS":      {"SOUPS"},
    # Bases de datos
    "WWW":        {"WWW", "TheWebConf"},
    "VLDB":       {"VLDB", "Proc. VLDB Endow.", "PVLDB"},
    "KDD":        {"KDD"},
    "ICDE":       {"ICDE"},
    "SIGMOD":     {"SIGMOD Conference", "ACM SIGMOD Conference"},
    "SIGIR":      {"SIGIR"},
    "ICDM":       {"ICDM"},
    "PODS":       {"PODS"},
    "WSDM":       {"WSDM"},
    "CIKM":       {"CIKM"},
    "ECIR":       {"ECIR"},
    "ISWC":       {"ISWC"},
    "SIGSPATIAL": {"GIS", "SIGSPATIAL", "SIGSPATIAL/GIS"},
    "ICDT":       {"ICDT"},
    "CIDR":       {"CIDR"},
    "ER":         {"ER"},
    # Teoría
    "ICALP":      {"ICALP"},
    "SODA":       {"SODA"},
    "STOC":       {"STOC"},
    "FOCS":       {"FOCS"},
    "LICS":       {"LICS"},
    "SoCG":       {"SoCG"},
    "EC":         {"EC"},
    "COLT":       {"COLT"},
    "STACS":      {"STACS"},
    "ESA":        {"ESA"},
    "ALENEX":     {"ALENEX"},
    "APPROX/RANDOM": {"APPROX/RANDOM", "APPROX", "RANDOM"},
    "IJCAR":      {"IJCAR"},
    "CADE":       {"CADE"},
    "GD":         {"GD"},
    "CCC":        {"Computational Complexity Conference", "CCC"},
    "ITCS":       {"ITCS", "Innovations in Theoretical Computer Science"},
    "SAT":        {"SAT"},
    "CP":         {"CP"},
    # HCI
    "CHI":        {"CHI"},
    "UIST":       {"UIST"},
    "VR":         {"VR"},
    "HRI":        {"HRI"},
    "PERCOM":     {"PerCom"},
    "ISMAR":      {"ISMAR"},
    "SIGGRAPH":   {"SIGGRAPH", "ACM SIGGRAPH"},
    "SiggraphA":  {"SIGGRAPH Asia"},
    "CSCW":       {"CSCW"},
    "DIS":        {"DIS"},
    "IUI":        {"IUI"},
    "ASSETS":     {"ASSETS"},
    "UMAP":       {"UMAP"},
    "SIGCSE":     {"SIGCSE"},
    "ICER":       {"ICER"},
    "IEEE VIS":   {"VIS", "IEEE Visualization"},
}

ACCEPTED_BOOKTITLES_NORM = {
    acronym: {booktitle.casefold() for booktitle in booktitles}
    for acronym, booktitles in ACCEPTED_BOOKTITLES.items()
}

# Solo estos congresos usan coincidencia parcial. Para el resto exigimos
# coincidencia exacta del booktitle y evitamos falsos positivos con siglas cortas.
BOOKTITLE_PREFIXES_NORM = {
    acronym: {prefix.casefold() for prefix in prefixes}
    for acronym, prefixes in BOOKTITLE_PREFIXES.items()
}

# Tokens que identifican proceedings secundarios. Se aplican antes del filtro
# positivo para evitar que reglas parciales o variantes de DBLP introduzcan
# workshops, companions, demos, posters, tutoriales o doctorales.
SECONDARY_BOOKTITLE_PATTERNS = (
    "workshop", "workshops", "studentworkshop",
    "companion", "extended abstracts", "extended abstract",
    "demo", "demos", "demonstration", "demonstrations",
    "poster", "posters",
    "tutorial", "tutorials",
    "doctoral", "doctorial", "phd", "consortium",
    "late breaking", "late-breaking",
)

# Algunos congresos oficiales tienen nombres que históricamente aparecen bajo
# streams DBLP compartidos. CADE/IJCAR es el caso crítico: no se puede asignar
# todo conf/cade a uno solo de los dos congresos.
def route_special_case(prefix: str, booktitle: str, current_acronym: str) -> str:
    bt = (booktitle or "").casefold()
    if prefix == "conf/cade":
        if "ijcar" in bt or "international joint conference on automated reasoning" in bt:
            return "IJCAR"
        if "cade" in bt or "automated deduction" in bt:
            return "CADE"
    return current_acronym


def is_secondary_booktitle(booktitle: str) -> bool:
    bt = (booktitle or "").casefold()
    return any(pattern in bt for pattern in SECONDARY_BOOKTITLE_PATTERNS)


def download_dump():
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / "dblp.xml.gz"
    if dest.exists():
        size_gb = dest.stat().st_size / 1e9
        print(f"  dblp.xml.gz ya existe ({size_gb:.1f} GB). Usando fichero local.")
        print("  (Borra data/dblp.xml.gz y vuelve a ejecutar para refrescar.)")
        return dest

    print(f"  Descargando {DBLP_DUMP_URL}")
    print("  ⚠️  El fichero pesa ~4 GB. Puede tardar 10-30 min según conexión.")

    tmp_dest = dest.with_suffix(dest.suffix + ".part")
    with requests.get(
        DBLP_DUMP_URL,
        stream=True,
        timeout=(10, 120),
        headers={"User-Agent": "bibliometric-replication/1.0"},
    ) as r:
        r.raise_for_status()
        total = int(r.headers.get('content-length', 0))

        with open(tmp_dest, 'wb') as f, tqdm(
            total=total, unit='B', unit_scale=True, desc="  dblp.xml.gz"
        ) as bar:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if not chunk:
                    continue
                f.write(chunk)
                bar.update(len(chunk))

    tmp_dest.replace(dest)

    print(f"  ✅ Guardado en {dest}")
    return dest


def load_dblp_keys():
    """Devuelve un dict {dblp_key: (acronym, level, area)} y valida el corpus oficial."""
    map_csv = OUTPUTS / "conf_dblp_map.csv"
    if not map_csv.exists():
        raise FileNotFoundError(
            f"No se encuentra {map_csv}. Ejecuta antes el paso 2 oficial."
        )

    rows = []
    with open(map_csv, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            rows.append(row)

    n_astar = sum(1 for r in rows if r.get('level') == 'A*')
    n_a = sum(1 for r in rows if r.get('level') == 'A')
    if len(rows) != 170 or n_astar != 62 or n_a != 108:
        raise ValueError(
            "conf_dblp_map.csv no parece ser el corpus oficial CORE/ICORE 2026 "
            f"(esperado: 62 A* + 108 A = 170; encontrado: {n_astar} A* + {n_a} A = {len(rows)})."
        )

    acronyms = [r['acronym'] for r in rows]
    inherited = {'COLING', 'EDBT', 'NSDI', 'PACT', 'SoCC'}
    present_inherited = sorted(inherited & set(acronyms))
    if present_inherited:
        raise ValueError(f"El mapa DBLP conserva congresos no oficiales del corpus anterior: {present_inherited}")

    missing_filters = sorted(set(acronyms) - set(ACCEPTED_BOOKTITLES))
    if missing_filters:
        raise ValueError(f"Faltan filtros ACCEPTED_BOOKTITLES para: {missing_filters}")

    df_map = {}
    duplicate_keys = []
    for row in rows:
        key = row.get('dblp_key', '').strip()
        if not key:
            raise ValueError(f"Congreso sin dblp_key: {row.get('acronym')}")
        if key in df_map:
            duplicate_keys.append(key)
        df_map[key] = (row['acronym'], row['level'], row['area'])

    if duplicate_keys:
        raise ValueError(f"Claves DBLP duplicadas en conf_dblp_map.csv: {sorted(set(duplicate_keys))}")

    print(f"  Claves DBLP cargadas: {len(df_map)} congresos oficiales")
    return df_map


def make_entity_pattern():
    """Compila una regex para sustituir entidades HTML de una pasada."""
    keys = sorted(HTML_ENTITIES.keys(), key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(k) for k in keys))
    return pattern

ENTITY_PATTERN = make_entity_pattern()
ENTITY_TAIL_CHARS = max(len(entity) for entity in HTML_ENTITIES) - 1

def replace_html_entities(text: str, *, fix_xml_declaration: bool = False) -> str:
    """
    Sustituye entidades HTML por su carácter Unicode antes del parseo XML.
    Mantiene intactas las entidades XML básicas (&amp;, &lt;, etc.).
    """
    if fix_xml_declaration:
        text = XML_DECL_RE.sub(r'\1"UTF-8"', text, count=1)
    return ENTITY_PATTERN.sub(lambda m: HTML_ENTITIES[m.group(0)], text)


class EntityFixReader:
    """
    Wrapper sobre un fichero gzip que descomprime en chunks y sustituye
    entidades HTML al vuelo, entregando un objeto file-like para ET.iterparse.
    Funciona tanto con xml.etree como con lxml.
    """
    CHUNK = 1 << 22  # 4 MB

    def __init__(self, gz_path):
        self._gz = gzip.open(gz_path, 'rb')
        self._out_buf = b''
        self._pending_text = ''
        self._done = False
        self._fix_xml_declaration = True

    def read(self, size=-1):
        while not self._done and (size < 0 or len(self._out_buf) < size):
            raw = self._gz.read(self.CHUNK)
            if not raw:
                self._done = True
                text = self._pending_text
                self._pending_text = ''
            else:
                # DBLP declara ISO-8859-1. Convertimos a texto y devolvemos UTF-8
                # coherente con la declaración XML que ajustamos en el primer bloque.
                text = self._pending_text + raw.decode('iso-8859-1')
                if len(text) <= ENTITY_TAIL_CHARS:
                    self._pending_text = text
                    continue
                text, self._pending_text = text[:-ENTITY_TAIL_CHARS], text[-ENTITY_TAIL_CHARS:]

            if text:
                fixed = replace_html_entities(
                    text,
                    fix_xml_declaration=self._fix_xml_declaration,
                )
                self._fix_xml_declaration = False
                self._out_buf += fixed.encode('utf-8')

        if size is None or size < 0:
            out, self._out_buf = self._out_buf, b''
            return out

        out, self._out_buf = self._out_buf[:size], self._out_buf[size:]
        return out

    def close(self):
        self._gz.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _get_text(elem, tag: str) -> str:
    """Extrae texto de un subelemento, compatiblemente con lxml y stdlib."""
    child = elem.find(tag)
    if child is None:
        return ''
    return _all_text(child)


def _all_text(elem) -> str:
    """Concatena texto y subtexto preservando títulos con etiquetas internas."""
    return ''.join(str(part) for part in elem.itertext()).strip()


def parse_dump(dump_path, dblp_keys):
    """
    Parsea el dump XML de DBLP en streaming, corrigiendo entidades HTML.
    Estrategia:
      1. EntityFixReader descomprime, convierte ISO-8859-1 a UTF-8 y sustituye
         entidades HTML no estándar antes de que el parser las vea.
      2. Si lxml está disponible: usa lxml.etree.iterparse con recover=True y
         limpieza agresiva de memoria.
      3. Si no: usa xml.etree.ElementTree como fallback.

    Para cada <inproceedings>:
      - Filtra por prefijo conf/<venue> del corpus
      - Filtra por año 2001-2025
      - Extrae: dblp_key, año, título, doi, autores, booktitle
    """
    records = []
    n_total = 0
    n_candidates = 0
    n_matched = 0

    key_prefixes = {f"conf/{k}": v for k, v in dblp_keys.items()}
    for _key, (acronym, level, area) in dblp_keys.items():
        for alt_prefix in ALT_DBLP_PREFIXES.get(acronym, set()):
            key_prefixes[alt_prefix] = (acronym, level, area)
    acronym_lookup = {acronym: (acronym, level, area) for acronym, level, area in dblp_keys.values()}

    print(f"  Parseando {dump_path} en streaming...")
    if USING_LXML:
        print("  Modo: lxml (recover=True) + sustitución de entidades HTML")
    else:
        print("  Modo: xml.etree + sustitución de entidades HTML")
    print("  (Puede tardar 20-40 min según hardware)")

    def _clear_elem(elem):
        if USING_LXML:
            parent = elem.getparent()
            elem.clear()
            while parent is not None and elem.getprevious() is not None:
                del parent[0]
        else:
            elem.clear()

    def _process_stream(stream):
        nonlocal n_total, n_candidates, n_matched

        if USING_LXML:
            context = ET.iterparse(stream, events=('end',), tag=('inproceedings', 'article'),
                                   recover=True, huge_tree=True)
        else:
            context = ET.iterparse(stream, events=('end',))

        for event, elem in tqdm(context, desc="  registros", unit=" rec",
                                mininterval=5):
            tag = elem.tag
            tag_name = tag.split('}')[-1] if isinstance(tag, str) else tag
            # lxml puede incluir namespace en el tag; lo normalizamos
            if tag_name not in TARGET_DBLP_TAGS:
                if not USING_LXML and tag_name in CLEARABLE_DBLP_TAGS:
                    _clear_elem(elem)
                continue

            n_total += 1
            dblp_key_attr = elem.get('key', '')

            parts = dblp_key_attr.split('/')
            if len(parts) < 2:
                _clear_elem(elem)
                continue
            prefix = f"{parts[0]}/{parts[1]}"

            if prefix not in key_prefixes:
                _clear_elem(elem)
                continue

            # Año
            year_text = _get_text(elem, 'year')
            try:
                year = int(year_text)
            except ValueError:
                _clear_elem(elem)
                continue
            if not (YEAR_MIN <= year <= YEAR_MAX):
                _clear_elem(elem)
                continue

            n_candidates += 1
            acronym, level, area = key_prefixes[prefix]

            title = _get_text(elem, 'title')

            # Extraer DOI principal y ArXiv ID de TODOS los campos <ee>
            doi      = ''
            arxiv_id = ''
            for ee_elem in elem.findall('ee'):
                ee_text = (ee_elem.text or '').strip()
                if not ee_text:
                    continue
                ee_lower = ee_text.lower()
                # ArXiv ID — puede ser https://arxiv.org/abs/2303.12345 o http://arxiv.org/abs/...
                if not arxiv_id and 'arxiv.org/abs/' in ee_lower:
                    raw = ee_lower.split('arxiv.org/abs/')[-1].strip()
                    raw = re.split(r'[?#]', raw, maxsplit=1)[0].rstrip('/')
                    # Limpiar versión: 2303.12345v2 → 2303.12345
                    raw = re.sub(r'v\d+$', '', raw)
                    arxiv_id = raw
                # DOI principal (primer que encontremos)
                if not doi:
                    if 'doi.org/' in ee_lower:
                        doi = re.split(r'doi\.org/', ee_text, flags=re.IGNORECASE)[-1].strip().rstrip('.')
                    elif ee_text.startswith('10.'):
                        doi = ee_text.strip()

            authors = '; '.join(
                author
                for a in elem.findall('author')
                for author in [_all_text(a)]
                if author
            )

            booktitle = _get_text(elem, 'booktitle') or _get_text(elem, 'journal')

            routed_acronym = route_special_case(prefix, booktitle, acronym)
            if routed_acronym != acronym:
                if routed_acronym not in acronym_lookup:
                    _clear_elem(elem)
                    continue
                acronym, level, area = acronym_lookup[routed_acronym]

            # Rechazo explícito de proceedings secundarios antes del filtro positivo.
            if is_secondary_booktitle(booktitle):
                _clear_elem(elem)
                continue

            # ── Filtro de track principal ──────────────────────────────────
            # Rechazar workshops, companion, extended abstracts, etc.
            # Por defecto se exige coincidencia exacta; la coincidencia parcial
            # queda limitada a congresos con variantes configuradas arriba.
            accepted_norm = ACCEPTED_BOOKTITLES_NORM.get(acronym)
            prefixes_norm = BOOKTITLE_PREFIXES_NORM.get(acronym, set())
            if accepted_norm:
                booktitle_norm = booktitle.casefold()
                exact_match = booktitle_norm in accepted_norm
                # Coincidencia parcial solo para casos configurados explícitamente.
                partial_match = any(p in booktitle_norm for p in prefixes_norm)
                if not exact_match and not partial_match:
                    _clear_elem(elem)
                    continue

            records.append({
                'dblp_key':  dblp_key_attr,
                'congress':  acronym,
                'level':     level,
                'area':      area,
                'year':      year,
                'title':     title,
                'doi':       doi,
                'arxiv_id':  arxiv_id,
                'authors':   authors,
                'booktitle': booktitle,
            })
            n_matched += 1
            _clear_elem(elem)

    # Siempre usar EntityFixReader para sustituir entidades HTML antes del parseo.
    # lxml con recover=True elimina silenciosamente las entidades desconocidas
    # en lugar de resolverlas, por lo que no es suficiente usarlo directamente.
    with EntityFixReader(dump_path) as reader:
        _process_stream(reader)

    n_filtered = n_candidates - n_matched
    print(f"  Registros DBLP escaneados:          {n_total:,}")
    print(f"  Candidatos corpus/año:              {n_candidates:,}")
    pct_matched = (n_matched / n_candidates * 100) if n_candidates else 0
    pct_filtered = (n_filtered / n_candidates * 100) if n_candidates else 0
    print(f"  Aceptados (track principal):        {n_matched:,}  ({pct_matched:.1f}%)")
    print(f"  Rechazados (workshops/secundarios): {n_filtered:,}  ({pct_filtered:.1f}%)")
    return records


def run(force=False):
    if CHECKPOINT_FILE.exists() and not force:
        print("  ⏭  Paso 3 ya completado (usa --force para repetir).")
        return

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    dump_path  = download_dump()
    dblp_keys  = load_dblp_keys()
    records    = parse_dump(dump_path, dblp_keys)

    out_csv = OUTPUTS / "dblp_inproceedings.csv"
    fieldnames = ['dblp_key','congress','level','area','year','title','doi','arxiv_id','authors','booktitle']
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"  ✅ {len(records):,} artículos guardados en outputs/dblp_inproceedings.csv")

    # Estadísticas de ArXiv IDs
    n_arxiv = sum(1 for r in records if r.get('arxiv_id'))
    n_doi   = sum(1 for r in records if r.get('doi'))
    den = len(records) or 1
    print(f"  Con DOI:      {n_doi:,}  ({n_doi/den*100:.1f}%)")
    print(f"  Con ArXiv ID: {n_arxiv:,}  ({n_arxiv/den*100:.1f}%)")
    print(f"  → Los ArXiv IDs permiten cruzar con Semantic Scholar en el paso 4b")

    # Resumen por congreso
    from collections import Counter
    per_conf = Counter(r['congress'] for r in records)
    top10 = per_conf.most_common(10)
    print("\n  Top 10 congresos por número de artículos:")
    for conf, n in top10:
        print(f"    {conf:20s} {n:6,}")

    result = {
        "step": 3, "status": "COMPLETE",
        "total_articles": len(records),
        "years": f"{YEAR_MIN}-{YEAR_MAX}",
        "dblp_dump": str(dump_path),
    }
    CHECKPOINT_FILE.write_text(json.dumps(result, indent=2))
    print("  ✅ Paso 3 completado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    print("=" * 55)
    print("PASO 3 — Dump DBLP → extracción inproceedings")
    print("=" * 55)
    run(force=args.force)
