"""
PASO 13 — Tabla auxiliar de áreas y subáreas del corpus CORE/ICORE 2026 A/A*

Lee outputs/conf_dblp_map.csv si existe; si no, lee conf_dblp_map.csv desde el directorio actual.
Produce:
  outputs/congress_area_subarea.csv

La tabla NO forma parte de CORE/ICORE. Es una capa analítica auxiliar para el informe.
"""
from pathlib import Path
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR.parent if SCRIPT_DIR.name == 'scripts' else SCRIPT_DIR
OUTPUTS = BASE / 'outputs'
OUTPUTS.mkdir(exist_ok=True)

# Si se ejecuta desde scripts/, buscar en outputs; si se ejecuta junto al CSV, buscar local.
CANDIDATES = [OUTPUTS / 'conf_dblp_map.csv', BASE / 'conf_dblp_map.csv', SCRIPT_DIR / 'conf_dblp_map.csv', Path('conf_dblp_map.csv')]
for p in CANDIDATES:
    if p.exists():
        MAP_CSV = p
        break
else:
    raise FileNotFoundError('No encuentro conf_dblp_map.csv en outputs/ ni en el directorio actual')

AREA_REPORT_LABEL = {
    'IA / ML': 'IA / ML',
    'Ing. del Software': 'Ingeniería del Software',
    'Sistemas': 'Sistemas, arquitectura y computación',
    'Bases de datos': 'Bases de datos',
    'Seguridad': 'Seguridad',
    'Redes': 'Redes',
    'HCI': 'HCI',
    'Teoría': 'Teoría',
    'Bioinformática': 'Bioinformática',
}

SUBAREA = {
    # IA / ML
    'NeurIPS': 'Aprendizaje automático y representación',
    'ICML': 'Aprendizaje automático y representación',
    'ICLR': 'Aprendizaje automático y representación',
    'AISTATS': 'Aprendizaje automático y representación',
    'UAI': 'Aprendizaje automático y representación',
    'COLT': 'Aprendizaje automático y representación',
    'CVPR': 'Visión por computador, imagen médica y reconocimiento',
    'ICCV': 'Visión por computador, imagen médica y reconocimiento',
    'ECCV': 'Visión por computador, imagen médica y reconocimiento',
    'WACV': 'Visión por computador, imagen médica y reconocimiento',
    'BMVC': 'Visión por computador, imagen médica y reconocimiento',
    'MICCAI': 'Visión por computador, imagen médica y reconocimiento',
    'ICDAR': 'Visión por computador, imagen médica y reconocimiento',
    'ACL': 'Procesamiento del lenguaje natural y habla',
    'EMNLP': 'Procesamiento del lenguaje natural y habla',
    'NAACL': 'Procesamiento del lenguaje natural y habla',
    'EACL': 'Procesamiento del lenguaje natural y habla',
    'Interspeech': 'Procesamiento del lenguaje natural y habla',
    'AAAI': 'IA general, planificación y razonamiento',
    'IJCAI': 'IA general, planificación y razonamiento',
    'ECAI': 'IA general, planificación y razonamiento',
    'ICAPS': 'IA general, planificación y razonamiento',
    'KR': 'IA general, planificación y razonamiento',
    'AAMAS': 'Agentes, recomendación, web social y analítica educativa',
    'RecSys': 'Agentes, recomendación, web social y analítica educativa',
    'ICWSM': 'Agentes, recomendación, web social y analítica educativa',
    'AIED': 'Agentes, recomendación, web social y analítica educativa',
    'LAK': 'Agentes, recomendación, web social y analítica educativa',
    'ACMMM': 'Multimedia, minería de datos y aprendizaje aplicado',
    'ICME': 'Multimedia, minería de datos y aprendizaje aplicado',
    'SDM': 'Multimedia, minería de datos y aprendizaje aplicado',
    'ECML PKDD': 'Multimedia, minería de datos y aprendizaje aplicado',
    'GECCO': 'Multimedia, minería de datos y aprendizaje aplicado',
    'FOGA': 'Multimedia, minería de datos y aprendizaje aplicado',
    'PPSN': 'Multimedia, minería de datos y aprendizaje aplicado',
    'ICRA': 'Robótica',
    'IROS': 'Robótica',

    # Sistemas, arquitectura y computación
    'ISCA': 'Arquitectura de computadores y microarquitectura',
    'MICRO': 'Arquitectura de computadores y microarquitectura',
    'HPCA': 'Arquitectura de computadores y microarquitectura',
    'ASPLOS': 'Arquitectura de computadores y microarquitectura',
    'DAC': 'Diseño electrónico, hardware y EDA',
    'ICCAD': 'Diseño electrónico, hardware y EDA',
    'DATE': 'Diseño electrónico, hardware y EDA',
    'FPGA': 'Diseño electrónico, hardware y EDA',
    'ISLPED': 'Diseño electrónico, hardware y EDA',
    'ITC': 'Diseño electrónico, hardware y EDA',
    'SOSP': 'Sistemas operativos, almacenamiento y middleware',
    'OSDI': 'Sistemas operativos, almacenamiento y middleware',
    'EuroSys': 'Sistemas operativos, almacenamiento y middleware',
    'FAST': 'Sistemas operativos, almacenamiento y middleware',
    'Middleware': 'Sistemas operativos, almacenamiento y middleware',
    'HotOS': 'Sistemas operativos, almacenamiento y middleware',
    'USENIX': 'Sistemas operativos, almacenamiento y middleware',
    'SC': 'HPC, paralelismo y sistemas distribuidos',
    'IPDPS': 'HPC, paralelismo y sistemas distribuidos',
    'HPDC': 'HPC, paralelismo y sistemas distribuidos',
    'ICS': 'HPC, paralelismo y sistemas distribuidos',
    'PODC': 'HPC, paralelismo y sistemas distribuidos',
    'DISC': 'HPC, paralelismo y sistemas distribuidos',
    'ICDCS': 'HPC, paralelismo y sistemas distribuidos',
    'DSN': 'HPC, paralelismo y sistemas distribuidos',
    'SIGMETRICS': 'Rendimiento, medición y evaluación de sistemas',
    'RTAS': 'Tiempo real y sistemas embebidos',
    'RTSS': 'Tiempo real y sistemas embebidos',

    # Ingeniería del Software
    'ICSE': 'Ingeniería del software general y automatización',
    'FSE': 'Ingeniería del software general y automatización',
    'ASE': 'Ingeniería del software general y automatización',
    'ESEM': 'Ingeniería del software general y automatización',
    'MSR': 'Ingeniería del software general y automatización',
    'SANER': 'Ingeniería del software general y automatización',
    'ICPC': 'Ingeniería del software general y automatización',
    'ICST': 'Testing, mantenimiento, fiabilidad y requisitos',
    'ISSTA': 'Testing, mantenimiento, fiabilidad y requisitos',
    'ICSME': 'Testing, mantenimiento, fiabilidad y requisitos',
    'ISSRE': 'Testing, mantenimiento, fiabilidad y requisitos',
    'RE': 'Testing, mantenimiento, fiabilidad y requisitos',
    'EASE': 'Testing, mantenimiento, fiabilidad y requisitos',
    'ICSA': 'Arquitectura, modelos y sistemas adaptativos',
    'MODELS': 'Arquitectura, modelos y sistemas adaptativos',
    'SEAMS': 'Arquitectura, modelos y sistemas adaptativos',
    'PLDI': 'Lenguajes de programación y compiladores',
    'POPL': 'Lenguajes de programación y compiladores',
    'OOPSLA': 'Lenguajes de programación y compiladores',
    'ECOOP': 'Lenguajes de programación y compiladores',
    'ICFP': 'Lenguajes de programación y compiladores',
    'ESOP': 'Lenguajes de programación y compiladores',
    'CGO': 'Lenguajes de programación y compiladores',
    'CAV': 'Métodos formales y verificación',
    'TACAS': 'Métodos formales y verificación',
    'BPM': 'Procesos, servicios y sistemas de información',
    'ICSOC': 'Procesos, servicios y sistemas de información',
    'CaiSE': 'Procesos, servicios y sistemas de información',

    # Bases de datos
    'SIGMOD': 'Bases de datos y gestión de datos',
    'VLDB': 'Bases de datos y gestión de datos',
    'ICDE': 'Bases de datos y gestión de datos',
    'CIDR': 'Bases de datos y gestión de datos',
    'KDD': 'Minería de datos, recuperación de información y búsqueda',
    'ICDM': 'Minería de datos, recuperación de información y búsqueda',
    'CIKM': 'Minería de datos, recuperación de información y búsqueda',
    'SIGIR': 'Minería de datos, recuperación de información y búsqueda',
    'WSDM': 'Minería de datos, recuperación de información y búsqueda',
    'ECIR': 'Minería de datos, recuperación de información y búsqueda',
    'PODS': 'Teoría de bases de datos',
    'ICDT': 'Teoría de bases de datos',
    'WWW': 'Web, conocimiento y datos semánticos',
    'ISWC': 'Web, conocimiento y datos semánticos',
    'SIGSPATIAL': 'Información geoespacial',
    'ER': 'Modelado conceptual',

    # Seguridad
    'SP': 'Seguridad de sistemas, redes y privacidad',
    'CCS': 'Seguridad de sistemas, redes y privacidad',
    'USENIX-Security': 'Seguridad de sistemas, redes y privacidad',
    'NDSS': 'Seguridad de sistemas, redes y privacidad',
    'ESORICS': 'Seguridad de sistemas, redes y privacidad',
    'ACSAC': 'Seguridad de sistemas, redes y privacidad',
    'RAID': 'Seguridad de sistemas, redes y privacidad',
    'AsiaCCS': 'Seguridad de sistemas, redes y privacidad',
    'EuroS&P': 'Seguridad de sistemas, redes y privacidad',
    'CRYPTO': 'Criptografía',
    'EuroCrypt': 'Criptografía',
    'ASIACRYPT': 'Criptografía',
    'CHES': 'Criptografía',
    'FC': 'Criptografía',
    'CSF': 'Fundamentos de seguridad',
    'PETS': 'Privacidad y seguridad usable',
    'SOUPS': 'Privacidad y seguridad usable',

    # Redes
    'SIGCOMM': 'Redes de comunicación e Internet',
    'INFOCOM': 'Redes de comunicación e Internet',
    'CoNEXT': 'Redes de comunicación e Internet',
    'IMC': 'Redes de comunicación e Internet',
    'MOBICOM': 'Redes móviles, inalámbricas y sensores',
    'Mobisys': 'Redes móviles, inalámbricas y sensores',
    'MSWIM': 'Redes móviles, inalámbricas y sensores',
    'MMSys': 'Sistemas multimedia y servicios',
    'ICWS': 'Sistemas multimedia y servicios',

    # HCI
    'CHI': 'Interacción persona-ordenador general',
    'UIST': 'Interacción persona-ordenador general',
    'DIS': 'Interacción persona-ordenador general',
    'IUI': 'Interacción persona-ordenador general',
    'CSCW': 'Interacción persona-ordenador general',
    'SIGGRAPH': 'Visualización, gráficos y realidad extendida',
    'SiggraphA': 'Visualización, gráficos y realidad extendida',
    'IEEE VIS': 'Visualización, gráficos y realidad extendida',
    'VR': 'Visualización, gráficos y realidad extendida',
    'ISMAR': 'Visualización, gráficos y realidad extendida',
    'ASSETS': 'Accesibilidad, educación e interacción aplicada',
    'SIGCSE': 'Accesibilidad, educación e interacción aplicada',
    'ICER': 'Accesibilidad, educación e interacción aplicada',
    'UMAP': 'Accesibilidad, educación e interacción aplicada',
    'PERCOM': 'Accesibilidad, educación e interacción aplicada',
    'HRI': 'Accesibilidad, educación e interacción aplicada',

    # Teoría
    'STOC': 'Algoritmos y complejidad',
    'FOCS': 'Algoritmos y complejidad',
    'SODA': 'Algoritmos y complejidad',
    'ICALP': 'Algoritmos y complejidad',
    'STACS': 'Algoritmos y complejidad',
    'ESA': 'Algoritmos y complejidad',
    'ALENEX': 'Algoritmos y complejidad',
    'APPROX/RANDOM': 'Algoritmos y complejidad',
    'CCC': 'Algoritmos y complejidad',
    'SoCG': 'Geometría computacional y optimización combinatoria',
    'GD': 'Geometría computacional y optimización combinatoria',
    'LICS': 'Lógica, autómatas y concurrencia',
    'SAT': 'Satisfacción, restricciones y razonamiento automatizado',
    'CP': 'Satisfacción, restricciones y razonamiento automatizado',
    'CADE': 'Satisfacción, restricciones y razonamiento automatizado',
    'IJCAR': 'Satisfacción, restricciones y razonamiento automatizado',
    'COLT': 'Teoría del aprendizaje y economía computacional',
    'EC': 'Teoría del aprendizaje y economía computacional',
    'ITCS': 'Teoría del aprendizaje y economía computacional',

    # Bioinformática
    'ISMB': 'Bioinformática computacional',
}

SUBAREA_NOTES = {
    'Aprendizaje automático y representación': 'Aprendizaje estadístico, representación, teoría/aplicaciones de ML y conferencias nucleares de ML.',
    'Visión por computador, imagen médica y reconocimiento': 'Visión, reconocimiento visual, análisis de imágenes, imagen médica y documentación visual.',
    'Procesamiento del lenguaje natural y habla': 'Lenguaje natural, lingüística computacional, diálogo y procesamiento del habla.',
    'IA general, planificación y razonamiento': 'IA general, planificación, representación del conocimiento, razonamiento y búsqueda.',
    'Agentes, recomendación, web social y analítica educativa': 'Sistemas multiagente, recomendación, web social, aprendizaje/analítica educativa.',
    'Multimedia, minería de datos y aprendizaje aplicado': 'Multimedia, minería/aprendizaje aplicado, computación evolutiva y optimización heurística.',
    'Robótica': 'Robótica, percepción/acción, planificación robótica y sistemas autónomos.',
    'Arquitectura de computadores y microarquitectura': 'Arquitectura, microarquitectura y soporte arquitectónico para sistemas y lenguajes.',
    'Diseño electrónico, hardware y EDA': 'Diseño electrónico, EDA, hardware, FPGA, test y eficiencia energética.',
    'Sistemas operativos, almacenamiento y middleware': 'Sistemas operativos, almacenamiento, middleware y sistemas experimentales.',
    'HPC, paralelismo y sistemas distribuidos': 'Computación de altas prestaciones, paralelismo, concurrencia distribuida y fiabilidad.',
    'Rendimiento, medición y evaluación de sistemas': 'Modelado, medición, rendimiento y evaluación cuantitativa de sistemas.',
    'Tiempo real y sistemas embebidos': 'Tiempo real, sistemas embebidos y aplicaciones críticas.',
    'Ingeniería del software general y automatización': 'Ingeniería del software, automatización, minería de repositorios y análisis de programas.',
    'Testing, mantenimiento, fiabilidad y requisitos': 'Pruebas, mantenimiento/evolución, fiabilidad, requisitos y evaluación empírica.',
    'Arquitectura, modelos y sistemas adaptativos': 'Arquitectura software, modelado, sistemas adaptativos y auto-gestión.',
    'Lenguajes de programación y compiladores': 'Lenguajes, paradigmas, compiladores, generación/optimización de código.',
    'Métodos formales y verificación': 'Verificación, model checking, herramientas formales y análisis de sistemas.',
    'Procesos, servicios y sistemas de información': 'Procesos de negocio, servicios, ingeniería de sistemas de información.',
    'Bases de datos y gestión de datos': 'Gestión de datos, sistemas de bases de datos y arquitectura de datos.',
    'Minería de datos, recuperación de información y búsqueda': 'Minería de datos, recuperación de información, búsqueda y gestión de conocimiento.',
    'Teoría de bases de datos': 'Fundamentos, modelos y teoría de bases de datos.',
    'Web, conocimiento y datos semánticos': 'Web, web semántica, conocimiento y datos enlazados.',
    'Información geoespacial': 'Sistemas de información geográfica y datos espaciales.',
    'Modelado conceptual': 'Modelado conceptual, requisitos de datos y diseño conceptual.',
    'Seguridad de sistemas, redes y privacidad': 'Seguridad de sistemas, redes, ataques, privacidad y seguridad aplicada.',
    'Criptografía': 'Criptografía teórica/aplicada, protocolos, hardware criptográfico y cripto financiera.',
    'Fundamentos de seguridad': 'Fundamentos formales y lógicos de la seguridad.',
    'Privacidad y seguridad usable': 'Privacidad, tecnologías de privacidad y seguridad usable.',
    'Redes de comunicación e Internet': 'Internet, protocolos, medición, redes de datos y sistemas de comunicación.',
    'Redes móviles, inalámbricas y sensores': 'Redes móviles, inalámbricas, ad hoc, sensores y sistemas móviles.',
    'Sistemas multimedia y servicios': 'Sistemas multimedia y servicios web/cloud relacionados con redes.',
    'Interacción persona-ordenador general': 'Interacción, diseño interactivo, CSCW e interfaces inteligentes.',
    'Visualización, gráficos y realidad extendida': 'Gráficos, visualización, realidad virtual/aumentada y rendering.',
    'Accesibilidad, educación e interacción aplicada': 'Accesibilidad, educación, HRI, computación ubicua y personalización.',
    'Algoritmos y complejidad': 'Algoritmos, complejidad, teoría de la computación y análisis de algoritmos.',
    'Geometría computacional y optimización combinatoria': 'Geometría computacional, graph drawing y optimización combinatoria.',
    'Lógica, autómatas y concurrencia': 'Lógica computacional, autómatas, concurrencia y fundamentos formales.',
    'Satisfacción, restricciones y razonamiento automatizado': 'SAT, CP, deducción automática y razonamiento formal.',
    'Teoría del aprendizaje y economía computacional': 'Teoría del aprendizaje, economía computacional y fundamentos de CS.',
    'Bioinformática computacional': 'Bioinformática, biología computacional y sistemas inteligentes en biomedicina.',
}

AREA_ORDER = {
    'IA / ML': 1,
    'Sistemas': 2,
    'Ing. del Software': 3,
    'Bases de datos': 4,
    'Seguridad': 5,
    'Redes': 6,
    'HCI': 7,
    'Teoría': 8,
    'Bioinformática': 9,
}

SUBAREA_ORDER = {}
for i, sub in enumerate(dict.fromkeys(SUBAREA.values()), 1):
    SUBAREA_ORDER[sub] = i

m = pd.read_csv(MAP_CSV)
required = {'acronym','title','level','area','dblp_key','dblp_conf_url'}
missing_cols = required - set(m.columns)
if missing_cols:
    raise ValueError(f'conf_dblp_map.csv no contiene columnas esperadas: {missing_cols}')

missing_subarea = sorted(set(m['acronym']) - set(SUBAREA))
if missing_subarea:
    raise ValueError(f'Faltan subáreas para: {missing_subarea}')

out = m[['acronym','title','level','area','dblp_key','dblp_conf_url']].copy()
out['area_report_label'] = out['area'].map(AREA_REPORT_LABEL).fillna(out['area'])
out['subarea'] = out['acronym'].map(SUBAREA)
out['subarea_notes'] = out['subarea'].map(SUBAREA_NOTES)
out['area_order'] = out['area'].map(AREA_ORDER)
out['subarea_order'] = out['subarea'].map(SUBAREA_ORDER)
out['classification_status'] = 'Propuesta analítica auxiliar; no es una categoría oficial CORE/ICORE'
out = out[['area_order','area','area_report_label','subarea_order','subarea','acronym','title','level','dblp_key','dblp_conf_url','subarea_notes','classification_status']]
out = out.sort_values(['area_order','subarea_order','acronym']).reset_index(drop=True)

if len(out) != 170:
    raise ValueError(f'Se esperaban 170 congresos; encontrados {len(out)}')
if out['subarea'].isna().any():
    raise ValueError('Hay subáreas nulas')

out_path = OUTPUTS / 'congress_area_subarea.csv'
out.to_csv(out_path, index=False, encoding='utf-8')

summary = out.groupby(['area_report_label','subarea'], as_index=False).agg(n_congresses=('acronym','count'), congresses=('acronym', lambda s: ', '.join(s)))
summary_path = OUTPUTS / 'congress_area_subarea_summary.csv'
summary.to_csv(summary_path, index=False, encoding='utf-8')

print(f'✅ Generado {out_path} ({len(out)} congresos)')
print(f'✅ Generado {summary_path} ({len(summary)} subáreas)')
print(out.groupby('area_report_label')['acronym'].count().to_string())
