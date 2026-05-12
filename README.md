# InformeBibliometrico2026

Repositorio de reproducibilidad del informe bibliométrico **“Presencia española en congresos internacionales de Informática (2001–2025)”**.

Este repositorio contiene los scripts, ficheros de entrada, salidas intermedias y resultados finales utilizados para analizar la presencia de España en congresos internacionales de Informática clasificados como **CORE/ICORE 2026 A\*** y **A**.

El informe estudia la evolución de la publicación española en congresos top de Informática entre 2001 y 2025, comparando España con el bloque **UE27 + Reino Unido**, con otros países europeos de referencia y con las principales áreas temáticas de la disciplina.

Repositorio: <https://github.com/AVallecillo/InformeBibliometrico2026>

---

## 1. Objetivo del estudio

La Informática tiene una estructura de comunicación científica singular: en muchas de sus áreas nucleares, los congresos internacionales selectivos son el canal principal de publicación de resultados originales. En áreas como inteligencia artificial, visión por computador, ingeniería del software, sistemas, seguridad, bases de datos, redes o teoría, congresos como NeurIPS, CVPR, ICSE, SIGCOMM, CCS, SIGMOD, STOC o CHI son foros de máxima relevancia científica.

El objetivo de este estudio es proporcionar una imagen cuantitativa, verificable y reproducible de la presencia española en los congresos internacionales de mayor nivel en Informática durante el periodo **2001–2025**.

Las preguntas principales son:

1. ¿Cómo ha evolucionado la posición relativa de España dentro del bloque europeo de referencia en congresos top de Informática?
2. ¿Cómo se compara España con los principales países europeos?
3. ¿Existen diferencias significativas entre áreas temáticas?
4. ¿Qué congresos concentran la mayor presencia española?

---

## 2. Resumen metodológico

### 2.1 Corpus

El corpus principal está definido por los congresos clasificados como **CORE/ICORE 2026 A\*** y **A**.

- **170 congresos oficiales**:
  - 62 CORE/ICORE A\*
  - 108 CORE/ICORE A
- Periodo: **2001–2025**
- Fuente bibliográfica principal: **DBLP XML dump**
- Filtro: solo artículos de la conferencia principal; se excluyen workshops, companions, demos, posters, challenges, doctoral consortia y proceedings secundarios.
- Corpus final DBLP auditado:
  - **535.144 artículos**
  - 170/170 congresos con datos
  - 0 booktitles secundarios detectados en la auditoría final

### 2.2 Conteo por país

El estudio emplea **conteo completo por país**:

> Un artículo con autores afiliados a N países cuenta una vez para cada uno de esos países.

La unidad final de análisis país-artículo es:

```text
paper_id + country_code
```

Un artículo con autores de España y Francia genera dos filas en la tabla `paper_country.csv`: una para `ES` y otra para `FR`.

### 2.3 Definición de Europa

El denominador europeo principal es:

```text
UE27 + Reino Unido
```

Un “artículo europeo” se define como un artículo con al menos un país afiliado perteneciente a **UE27 + Reino Unido**.

La cuota española dentro de Europa se calcula como:

```text
artículos con España / artículos con ≥1 país de UE27 + Reino Unido
```

### 2.4 Fuentes para resolución de afiliaciones

La resolución de afiliaciones se hace mediante un pipeline multifuente:

1. **OpenAlex DOI**
2. **OpenAlex source/venue-year**
3. **DROPS/LIPIcs**
4. **CrossRef DOI**
5. **OpenReview**
6. **OpenReview expanded/discovery**
7. **Semantic Scholar selectivo**

Cada fuente escribe una tabla de evidencias separada. La consolidación final deduplica por `paper_id + country_code` y conserva trazabilidad de fuentes.

Cobertura consolidada final:

- Artículos en `paper_master`: **535.144**
- Artículos con ≥1 país consolidado: **452.515**
- Cobertura acumulada: **84,56 %**
- Filas `paper_id + country_code`: **618.919**
- Países distintos: **182**
- Artículos con España: **8.082**
- Artículos UE27 + Reino Unido: **140.725**

---

## 3. Estructura recomendada del repositorio

```text
InformeBibliometrico2026/
│
├── README.md
├── LICENSE
├── requirements.txt
│
├── data/
│   ├── core_official/
│   │   ├── COREA-2026.csv
│   │   ├── COREAstar-2026.csv
│   │   └── ...
│   │
│   ├── core_historical/
│   │   ├── COREA-2008.csv
│   │   ├── COREAstar-2008.csv
│   │   ├── COREAstarA-2010.csv
│   │   ├── COREA-2013.csv
│   │   ├── COREAstar-2013.csv
│   │   └── ...
│   │
│   └── external/
│       └── README.md
│
├── scripts/
│   ├── 02_dblp_map_oficial.py
│   ├── 03_dblp_download_oficial.py
│   ├── 03b_validate_corpus_oficial.py
│   ├── 03c_audit_dblp_corpus.py
│   ├── 04_prepare_paper_master.py
│   ├── 05_resolve_affiliations_openalex_doi.py
│   ├── 06_resolve_affiliations_openalex_venue.py
│   ├── 07_resolve_affiliations_drops.py
│   ├── 08_resolve_affiliations_crossref.py
│   ├── 09_build_paper_country.py
│   ├── 10_resolve_affiliations_openreview.py
│   ├── 10b_resolve_affiliations_openreview_expanded.py
│   ├── 11_resolve_affiliations_official_sources.py
│   ├── 12_resolve_affiliations_semantic_scholar_selective.py
│   ├── 13_create_congress_area_subarea.py
│   └── 14_build_report_indicators.py
│
├── outputs/
│   ├── conf_dblp_map.csv
│   ├── dblp_inproceedings.csv
│   ├── paper_master.csv
│   ├── paper_country.csv
│   ├── report_indicators_summary.txt
│   ├── report_indicators_*.csv
│   └── ...
│
├── checkpoints/
│   └── *.json
│
├── reports/
│   ├── informe_bibliometrico_core_espana.docx
│   └── figures/
│
└── docs/
    ├── metodologia.md
    ├── core_historico.md
    └── areas_subareas.md
```

---

## 4. Contenido de las carpetas

### `data/core_official/`

Contiene los ficheros oficiales CORE/ICORE 2026 utilizados para definir el corpus principal:

```text
COREA-2026.csv
COREAstar-2026.csv
```

Estos ficheros son la base del corpus fijo del informe.

### `data/core_historical/`

Contiene versiones históricas de CORE usadas para análisis metodológico o futuros análisis de sensibilidad:

```text
COREA-2008.csv
COREAstar-2008.csv
COREAstarA-2010.csv
COREA-2013.csv
COREAstar-2013.csv
COREA-2014.csv
COREAstar-2014.csv
COREA-2017.csv
COREAstar-2017.csv
COREA-2018.csv
COREAstar-2018.csv
COREA-2020.csv
COREAstar-2020.csv
COREA-2021.csv
COREAstar-2021.csv
COREA-2023.csv
COREAstar-2023.csv
COREA-2026.csv
COREAstar-2026.csv
```

Nota metodológica importante: en **CORE 2010** no se distinguió entre A\* y A; la clasificación agrupó ambas categorías.

### `scripts/`

Contiene el pipeline completo de extracción, validación, afiliación, consolidación e indicadores.

### `outputs/`

Contiene las salidas intermedias y finales reproducibles. Los ficheros más importantes son:

```text
conf_dblp_map.csv
paper_master.csv
paper_country.csv
report_indicators_summary.txt
```

### `checkpoints/`

Contiene marcadores JSON que permiten evitar repetir pasos largos ya completados. La mayoría de scripts aceptan `--force` para regenerar resultados.

### `reports/`

Contiene el informe final y, en su caso, figuras o tablas exportadas.

---

## 5. Pipeline de reproducibilidad

A continuación se describe el pipeline principal. Los nombres de script reflejan el orden recomendado de ejecución.

### Paso 2 — Mapeo CORE/ICORE ↔ DBLP

```bash
python scripts/02_dblp_map_oficial.py --force
```

Genera:

```text
outputs/conf_dblp_map.csv
```

Este paso:

- carga los congresos oficiales CORE/ICORE 2026 A\* y A;
- excluye congresos B y nacionales;
- asigna claves DBLP;
- aplica correcciones especiales, por ejemplo:
  - `ITCS → conf/innovations`
  - `DIS → conf/ACMdis`
  - `SIGSPATIAL → conf/gis`

### Paso 3 — Extracción DBLP

```bash
python scripts/03_dblp_download_oficial.py --force
```

Genera:

```text
outputs/dblp_inproceedings.csv
```

Este paso:

- procesa el dump XML de DBLP;
- filtra artículos entre 2001 y 2025;
- conserva solo conferencias oficiales A\*/A;
- excluye proceedings secundarios;
- aplica reglas especiales para `PETS`, `VLDB/PVLDB`, `IJCAR/CADE`, `MICCAI`, `FC`, `SEAMS`, `DIS`, etc.

### Paso 3b — Validación de cobertura

```bash
python scripts/03b_validate_corpus_oficial.py
```

Genera:

```text
outputs/corpus_coverage_report.txt
```

Comprueba:

- 170 congresos oficiales;
- 0 congresos A\* sin artículos;
- 0 congresos A sin artículos;
- cobertura por congreso.

### Paso 3c — Auditoría DBLP

```bash
python scripts/03c_audit_dblp_corpus.py
```

Genera:

```text
outputs/corpus_congress_audit.csv
outputs/corpus_booktitle_audit.csv
outputs/corpus_year_coverage.csv
outputs/corpus_dblp_duplicates.csv
outputs/corpus_audit_report.txt
```

Comprueba:

- booktitles secundarios;
- duplicados;
- cobertura por año;
- congresos con cobertura sospechosa;
- casos sensibles como `ITCS`, `PETS`, `DIS`, `MICCAI`, `ISMB`, `IJCAR`, `SIGSPATIAL`.

### Paso 4 — Tabla maestra de artículos

```bash
python scripts/04_prepare_paper_master.py --force
```

Genera:

```text
outputs/paper_master.csv
```

Columnas principales:

```text
paper_id
dblp_key
congress
level
area
year
window
title
doi
arxiv_id
authors
booktitle
```

También genera tablas de conteo por año, congreso, área, nivel y ventana.

---

## 6. Resolución de afiliaciones

### Paso 5 — OpenAlex por DOI

```bash
python scripts/05_resolve_affiliations_openalex_doi.py --api-key MI_OA_KEY --force
```

Genera:

```text
outputs/affiliation_evidence_openalex_doi.csv
outputs/openalex_doi_coverage_report.txt
```

Fuente principal de afiliaciones.

### Paso 6 — OpenAlex por source/venue-año

```bash
python scripts/06_resolve_affiliations_openalex_venue.py --api-key MI_OA_KEY --max-pages 20 --force
```

Genera:

```text
outputs/affiliation_evidence_openalex_venue.csv
outputs/openalex_venue_coverage_report.txt
outputs/openalex_venue_combo_audit.csv
```

Complementa OpenAlex DOI, especialmente en NeurIPS, ICML, ICLR, USENIX-Security, UAI, DATE, COLT, ECAI, FAST y OSDI.

### Paso 7 — DROPS/LIPIcs

```bash
python scripts/07_resolve_affiliations_drops.py --force
```

Genera:

```text
outputs/affiliation_evidence_drops.csv
outputs/drops_coverage_report.txt
```

Aporta cobertura específica para congresos de teoría y LIPIcs.

### Paso 8 — CrossRef

```bash
python scripts/08_resolve_affiliations_crossref.py --mailto EMAIL --force
```

Genera:

```text
outputs/affiliation_evidence_crossref.csv
outputs/crossref_coverage_report.txt
```

Complementa afiliaciones por DOI, especialmente en ACM/IEEE y otras editoriales.

### Paso 10 — OpenReview

```bash
python scripts/10_resolve_affiliations_openreview.py --force
```

Genera:

```text
outputs/affiliation_evidence_openreview.csv
outputs/openreview_coverage_report.txt
```

Aporta cobertura importante para NeurIPS, ICLR, ICML y UAI.

### Paso 10b — OpenReview expandido

```bash
python scripts/10b_resolve_affiliations_openreview_expanded.py --force
```

Genera:

```text
outputs/affiliation_evidence_openreview_expanded.csv
outputs/openreview_expanded_coverage_report.txt
```

Paso exploratorio controlado. En el análisis final aportó principalmente AISTATS 2025.

### Paso 11 — Fuentes oficiales/PDFs

```bash
python scripts/11_resolve_affiliations_official_sources.py --force
```

Este paso está incluido por completitud metodológica, pero en la ejecución final no aportó evidencias porque la tabla `paper_master.csv` no conserva enlaces `ee`/`url` de DBLP. Puede reutilizarse si se reconstruye el corpus conservando enlaces oficiales o si se implementan scrapers específicos.

### Paso 12 — Semantic Scholar selectivo

```bash
python scripts/12_resolve_affiliations_semantic_scholar_selective.py \
  --api-key MI_S2_KEY \
  --title-workers 4 \
  --doi-workers 2 \
  --rate-limit 0.9 \
  --save-every 5000 \
  --force
```

Genera:

```text
outputs/affiliation_evidence_semantic_scholar_selective.csv
outputs/semantic_scholar_selective_coverage_report.txt
```

Procesa selectivamente congresos con baja cobertura y alto impacto en el análisis:

```text
AAMAS, ICWSM, BMVC, Interspeech, AISTATS,
NDSS, USENIX, USENIX-Security, OSDI, FAST,
ICAPS, ICLR, NeurIPS, ICML, COLT
```

---

## 7. Consolidación país-artículo

### Paso 9 — Consolidación final

```bash
python scripts/09_build_paper_country.py --force
```

Genera:

```text
outputs/paper_country.csv
outputs/paper_country_sources.csv
outputs/paper_country_report.txt
```

`paper_country.csv` es la tabla principal para el análisis bibliométrico.

Columnas principales:

```text
paper_id
dblp_key
congress
level
area
year
window
country_code
country_name
is_spain
is_eu27
is_eu27_plus_uk
is_europe_extended
sources
methods
matched_by
source_work_ids
n_sources
```

Resultado consolidado final:

```text
Artículos en paper_master: 535.144
Artículos con >=1 país consolidado: 452.515
Artículos sin país consolidado: 82.629
Cobertura acumulada: 84,56 %
Filas paper-país: 618.919
Países distintos: 182
Artículos con España: 8.082
Artículos UE27+Reino Unido: 140.725
Cuota España dentro de UE27+UK: 5,743 %
```

---

## 8. Áreas y subáreas

### Paso 13 — Tabla auxiliar de áreas y subáreas

```bash
python scripts/13_create_congress_area_subarea.py --force
```

Genera:

```text
outputs/congress_area_subarea.csv
outputs/congress_area_subarea_summary.csv
```

Esta tabla documenta la clasificación temática de los 170 congresos.

Columnas:

```text
area_order
area
area_report_label
subarea_order
subarea
acronym
title
level
dblp_key
dblp_conf_url
subarea_notes
classification_status
```

Nota: el área interna `Sistemas` se presenta en el informe como:

```text
Sistemas, arquitectura y computación
```

Bioinformática/ISMB se conserva en el corpus técnico y anexos, pero no se interpreta como área comparativa principal porque está representada por un único congreso y tiene cobertura DBLP limitada.

---

## 9. Indicadores para el informe

### Paso 14 — Indicadores bibliométricos

```bash
python scripts/14_build_report_indicators.py --force
```

Genera:

```text
outputs/report_indicators_summary.txt
outputs/report_indicators_global_by_window.csv
outputs/report_indicators_spain_europe_by_window.csv
outputs/report_indicators_country_ranking_europe_by_window.csv
outputs/report_indicators_country_ranking_europe_by_area_window.csv
outputs/report_indicators_spain_by_area_window.csv
outputs/report_indicators_spain_by_level_window.csv
outputs/report_indicators_area_coverage.csv
outputs/report_indicators_congress_spain_top.csv
outputs/report_indicators_country_comparison.csv
outputs/report_indicators_country_by_window.csv
outputs/report_indicators_country_by_area_window.csv
outputs/report_indicators_primary_comparators_wide.csv
outputs/report_indicators_europe_growth_factors.csv
outputs/report_indicators_es_it_ratio_by_window.csv
outputs/report_indicators_country_level_window.csv
outputs/report_indicators_country_ranking_europe_by_level_window.csv
outputs/report_indicators_europe_trend_classes.csv
outputs/report_indicators_top_congresses_spain_by_window.csv
```

Indicadores calculados:

- artículos totales por ventana;
- cobertura por ventana;
- cobertura por área;
- artículos españoles por ventana;
- artículos UE27+Reino Unido por ventana;
- cuota España / UE27+Reino Unido;
- ranking europeo de España;
- comparación con GB, DE, FR, IT, NL y PT;
- ratio España/Italia;
- factores de crecimiento por país;
- resultados por nivel A\*/A;
- resultados por área;
- top congresos por presencia española.

---

## 10. Resultados principales

### 10.1 Corpus y cobertura

```text
Artículos en paper_master: 535.144
Artículos con >=1 país: 452.515
Filas paper-país: 618.919
Países distintos: 182
Cobertura acumulada: 84,56 %
```

### 10.2 España en UE27 + Reino Unido

```text
2001–2005: ES=967  UE27+UK=14.240  ES/UE27+UK=6,791 %  rank=6
2006–2010: ES=1.680  UE27+UK=22.048  ES/UE27+UK=7,620 %  rank=5
2011–2015: ES=1.909  UE27+UK=26.136  ES/UE27+UK=7,304 %  rank=5
2016–2020: ES=1.536  UE27+UK=31.263  ES/UE27+UK=4,913 %  rank=6
2021–2025: ES=1.990  UE27+UK=47.038  ES/UE27+UK=4,231 %  rank=8
```

### 10.3 Comparadores europeos principales

Cuota dentro de UE27+UK en 2021–2025:

```text
GB: 31,270 %
DE: 27,542 %
FR: 13,472 %
IT: 8,650 %
NL: 8,217 %
ES: 4,231 %
PT: 1,307 %
```

### 10.4 Ratio España / Italia

```text
2001–2005: ES/IT = 0,642
2006–2010: ES/IT = 0,788
2011–2015: ES/IT = 0,746
2016–2020: ES/IT = 0,549
2021–2025: ES/IT = 0,489
```

### 10.5 Áreas destacadas

- **Redes**: mayor crecimiento relativo de España dentro de UE27+UK; alcanza 14,612 % en 2021–2025.
- **IA / ML**: mayor volumen absoluto, pero caída relativa española dentro de UE27+UK en la fase reciente.
- **Teoría**: descenso sostenido de cuota relativa española.
- **Sistemas, arquitectura y computación**: posición relativamente sólida y estable.
- **Bases de datos**: pico en 2006–2015 y caída posterior.
- **HCI y Seguridad**: presencia española comparativamente más débil.

---

## 11. Decisión metodológica: CORE/ICORE 2026 frente a CORE histórico

Este informe usa un **corpus fijo CORE/ICORE 2026 A\*/A** para todo el periodo 2001–2025.

### Ventajas del corpus fijo 2026

- Comparabilidad longitudinal: el conjunto de congresos es estable.
- Reproducibilidad: el corpus se define por una única versión oficial.
- Permite estudiar retrospectivamente la presencia española en los venues que hoy constituyen el núcleo top internacional de la disciplina.

### Limitación

Un congreso que hoy es A\*/A puede no haber tenido el mismo estatus en 2001 o 2005. Esto introduce una perspectiva ex post.

### Alternativa: CORE histórico

Una alternativa sería usar la clasificación CORE vigente en cada año o la versión histórica más cercana disponible.

Ventajas:

- Refleja mejor el contexto evaluativo contemporáneo.
- Evita clasificar retrospectivamente venues que alcanzaron prestigio después.

Inconvenientes:

- El corpus cambia con el tiempo.
- Las tendencias pueden reflejar cambios del ranking, no solo cambios de producción.
- Algunas versiones históricas no distinguen categorías igual que las actuales. En particular, en 2010 A\* y A aparecen agrupadas.

### Decisión adoptada

El análisis principal usa CORE/ICORE 2026 como corpus fijo. Las versiones históricas de CORE se conservan para futuros análisis de sensibilidad.

---

## 12. Requisitos

Ejemplo de `requirements.txt`:

```text
pandas
requests
tqdm
rapidfuzz
openreview-py
pypdf
python-docx
```

Algunos scripts pueden requerir librerías adicionales según la fuente utilizada.

---

## 13. Credenciales y variables sensibles

Algunos pasos requieren claves API:

- OpenAlex API key
- Semantic Scholar API key
- correo de contacto para CrossRef

No se deben subir claves al repositorio.

Ejemplo recomendado:

```bash
export OPENALEX_API_KEY="..."
export S2_API_KEY="..."
export CROSSREF_MAILTO="nombre@dominio.es"
```

Y ejecutar:

```bash
python scripts/05_resolve_affiliations_openalex_doi.py --api-key "$OPENALEX_API_KEY" --force
python scripts/12_resolve_affiliations_semantic_scholar_selective.py --api-key "$S2_API_KEY" --force
```

---

## 14. Notas sobre ficheros grandes

Algunos outputs pueden ser grandes:

```text
outputs/dblp_inproceedings.csv
outputs/paper_master.csv
outputs/paper_country.csv
outputs/*_cache.json
```

Recomendaciones:

- no subir cachés si son muy grandes o contienen datos no necesarios para reproducir resultados finales;
- usar Git LFS si se decide versionar ficheros grandes;
- incluir checksums de outputs principales;
- documentar fecha de generación de cada output.

---

## 15. Limitaciones principales

1. **Cobertura desigual de afiliaciones** por congreso, área y periodo.
2. **Conteo completo**: los artículos multinacionales cuentan para todos los países participantes.
3. **Movilidad investigadora**: el país se asigna por afiliación institucional en el momento de publicación.
4. **CORE/ICORE 2026 retroactivo**: la clasificación de 2026 se aplica a todo el periodo histórico.
5. **Asignación única de área**: congresos multidisciplinares se asignan a una única área principal.
6. **Bioinformática/ISMB**: se mantiene en el corpus, pero no se interpreta como área comparativa principal.
7. **Baja cobertura residual** en algunos congresos, especialmente USENIX, NDSS, AISTATS, AAMAS, ICWSM, FAST, OSDI, Interspeech y algunos venues de IA/ML.

---

## 16. Cita recomendada

Si se utiliza este repositorio o sus datos, citar como:

```text
Vallecillo, A. (2026). Informe bibliométrico sobre la presencia española en congresos internacionales de Informática CORE/ICORE A* y A (2001–2025). Repositorio GitHub: https://github.com/AVallecillo/InformeBibliometrico2026
```

---

## 17. Licencia

Indicar aquí la licencia elegida para el repositorio. Opciones habituales:

- MIT para scripts;
- CC BY 4.0 para informes, tablas y documentación;
- o una combinación de ambas.

Ejemplo recomendado:

```text
Código: MIT License
Documentación y resultados: Creative Commons Attribution 4.0 International (CC BY 4.0)
```

---

## 18. Contacto

Repositorio mantenido por **A. Vallecillo**.

GitHub: <https://github.com/AVallecillo/InformeBibliometrico2026>
