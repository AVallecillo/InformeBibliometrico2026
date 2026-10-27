# Presencia española en congresos internacionales de Informática (2001-2025)

Repositorio de reproducibilidad del informe bibliométrico **“[Presencia española en congresos internacionales de Informática (2001-2025)](./docs/A2_Informe_presencia_espanola_congresos_2001-2025.pdf)”**, basado en el corpus de congresos **[CORE/ICORE 2026](https://portal.core.edu.au/conf-ranks/) A\*** y **A**.

La Informática tiene una estructura de comunicación científica singular: en muchas de sus áreas nucleares, los congresos internacionales selectivos son el foro principal -y a menudo el definitivo- de publicación de resultados originales. Este repositorio reúne los datos, scripts, salidas intermedias y resultados utilizados para estudiar la presencia española en esos congresos durante el período 2001-2025, comparándola con el bloque UE27+Reino Unido, con otros países europeos de referencia y con las principales áreas temáticas de la disciplina.

El análisis completo, la metodología, las limitaciones y las conclusiones están recogidos en el [informe final](./docs/A2_Informe_presencia_espanola_congresos_2001-2025.pdf), situado en el directorio `docs/`.

El informe forma parte de un conjunto de documentos de la SCIE sobre el reconocimiento de los congresos de Informática, que también se encuentran en `docs/`:

- [`00_Propuesta_SCIE_congresos_informatica.pdf`](./docs/00_Propuesta_SCIE_congresos_informatica.pdf): propuesta de la SCIE (documento central).
- [`A1_Informe_fundamentacion_congresos_informatica.pdf`](./docs/A1_Informe_fundamentacion_congresos_informatica.pdf): informe de fundamentación.
- [`A2_Informe_presencia_espanola_congresos_2001-2025.pdf`](./docs/A2_Informe_presencia_espanola_congresos_2001-2025.pdf): informe bibliométrico (el que reproduce este repositorio).
- [`A3_Informe_congresos_sexenios_CNEAI_2001-2025.pdf`](./docs/A3_Informe_congresos_sexenios_CNEAI_2001-2025.pdf): informe sobre los criterios de sexenios de la CNEAI.
<!-- - `C1_*`, `C2_*` y `C3_*`: cartas de presentación de la propuesta. -->

## Estructura del repositorio

```text
InformeBibliometrico2026/
|
|-- README.md
|-- .gitattributes
|-- .gitignore
|-- run_all_ext.ps1
|-- run_all_ext.sh
|
|-- checkpoints/
|   `-- step*.json
|
|-- data/
|   |-- CORE-A.csv
|   |-- CORE-Astar.csv
|   |-- CORE2026-completo.csv
|   |-- dblp.xml.gz
|   |-- OLD_dblp.xml.gz
|   |-- core_historical/
|   |   |-- raw/
|   |   |   |-- COREA-*.csv
|   |   |   |-- COREAstar-*.csv
|   |   |   `-- COREAstarA-2010.csv
|   |   |-- core_historical.csv
|   |   |-- core_historical_*.csv
|   |   |-- core_historical_README.txt
|   |   `-- README.md
|   `-- external/
|       |-- venue_area_scenarios.csv
|       |-- *_TEMPLATE.csv
|       `-- README.md
|
|-- docs/
|   |-- 00_Propuesta_SCIE_congresos_informatica.{docx,pdf}
|   |-- A1_Informe_fundamentacion_congresos_informatica.{docx,pdf}
|   |-- A2_Informe_presencia_espanola_congresos_2001-2025.{docx,pdf}
|   |-- A3_Informe_congresos_sexenios_CNEAI_2001-2025.{docx,pdf}
|   |-- C1_Carta_Ministerio_SGU_Orden_1994.{docx,pdf}
|   |-- C2_Carta_CNEAI_criterios_sexenios.{docx,pdf}
|   |-- C3_Carta_ANECA_acreditacion.{docx,pdf}
|   |-- SCIE_JornadaSociedadesCOSCE_24-sept-2026_v0*.pptx
|   |-- figuras_informe_bibliometrico.zip
|   |-- PLAN_ACCION_BIBLIOMETRICO_V6.md
|   |-- README_*.md
|   `-- *.txt
|
|-- figuras/
|   `-- fig1.png ... fig4.png
|
|-- outputs/
|   |-- icore2026_a.csv
|   |-- icore2026_astar.csv
|   |-- conf_dblp_map.csv
|   |-- dblp_inproceedings.csv
|   |-- corpus_*.*
|   |-- paper_master.csv
|   |-- paper_master_*.*
|   |-- paper_counts_*.csv
|   |-- paper_country.csv
|   |-- paper_country_*.*
|   |-- congress_area_subarea*.csv
|   |-- affiliation_evidence_*.csv
|   |-- *_cache*.json
|   |-- *_unresolved.csv
|   |-- *_audit.csv
|   |-- *_coverage_report.txt
|   |-- reconciliacion_corpus.csv
|   `-- report_indicators_*.*
|
|-- outputs_ext/
|   |-- figures/
|   |   `-- *.png
|   |-- preflight_report.txt
|   |-- input_validation_report.txt
|   |-- fractional_vs_complete_*.csv
|   |-- alternative_denominators.csv
|   |-- coverage_*.csv
|   |-- sensitivity_threshold_*.csv
|   |-- *_sensitivity*.csv
|   |-- core_historical_corpus_retained.csv
|   |-- paper_master_with_historical_core.csv
|   |-- shift_share_*.csv
|   |-- spain_*.csv
|   |-- maturity_2021_2024_vs_2021_2025.csv
|   |-- rank_uncertainty_bounds.csv
|   |-- overlap_inflation_*.csv
|   |-- european_country_multiplicity_distribution.csv
|   |-- missingness_*.*
|   |-- bootstrap_*.csv
|   |-- corpus_expansion_*.csv
|   |-- conclusion_*.*
|   |-- historical_*.*
|   |-- *_SKIPPED.txt
|   `-- run_all_ext_summary.{csv,tsv}
|
|-- scripts/
|   |-- 00_setup.py
|   |-- 01_icore_oficial.py
|   |-- 02_dblp_map_oficial.py
|   |-- 03_dblp_download_oficial.py
|   |-- 03b_validate_corpus_oficial.py
|   |-- 03c_audit_dblp_corpus.py
|   |-- ...
|   |-- 10b_resolve_affiliations_openreview_expanded.py
|   |-- ...
|   `-- 14_build_report_indicators.py
|
`-- scripts_ext/
    |-- 00_validate_inputs.py
    |-- 01_fractional_vs_complete.py
    |-- ...
    |-- 22_refine_historical_missing_venue_tiers.py
    |-- build_core_historical.py
    `-- common.py
```

## Organización principal

- [`data/`](./data): contiene las entradas principales del estudio: los ficheros CORE/ICORE 2026, el volcado DBLP utilizado (`dblp.xml.gz`) y un volcado anterior (`OLD_dblp.xml.gz`), además de los datos auxiliares para el análisis histórico ([`data/core_historical/`](./data/core_historical)) y los metadatos externos opcionales ([`data/external/`](./data/external)). Cada uno de estos dos subdirectorios tiene su propio `README.md`.
- [`scripts/`](./scripts): contiene el pipeline principal de construcción del corpus, validación DBLP, resolución de afiliaciones, consolidación artículo-país y generación de indicadores.
- [`outputs/`](./outputs): contiene las salidas reproducibles del pipeline principal, incluidas las tablas `paper_master.csv`, `paper_country.csv`, las evidencias y cachés por fuente, las auditorías y las tablas finales de indicadores.
- [`scripts_ext/`](./scripts_ext): contiene los análisis complementarios de robustez y sensibilidad: conteo fraccionario, denominadores alternativos, sensibilidad por cobertura, CORE histórico, colaboración, bootstrap, expansión del corpus y auditorías históricas.
- [`outputs_ext/`](./outputs_ext): contiene las salidas de los análisis extendidos, diagnósticos, figuras y resúmenes de ejecución.
- [`checkpoints/`](./checkpoints): contiene marcadores de ejecución de los pasos largos del pipeline.
- [`figuras/`](./figuras): contiene las cuatro figuras del informe.
- [`docs/`](./docs): contiene el informe final y los demás documentos de la SCIE (en versión editable y PDF), las presentaciones, las notas de ejecución y otro material de apoyo.

## Ejecución de los análisis extendidos

Las instrucciones detalladas están en [`docs/README_EJECUCION_V6.md`](./docs/README_EJECUCION_V6.md). En resumen:

1. Generar el CORE histórico (no lo lanzan los scripts `run_all_ext`):

   ```bash
   python scripts_ext/build_core_historical.py --input-dir data/core_historical/raw --output-dir data/core_historical --policy-2010 infer_2008_2013
   ```

2. Ejecutar la batería completa con `run_all_ext.ps1` (PowerShell) o `run_all_ext.sh` (bash). El resumen de la ejecución se guarda en `outputs_ext/run_all_ext_summary.csv` con PowerShell y en `outputs_ext/run_all_ext_summary.tsv` con bash.

3. Opcionalmente, para los indicadores de impacto por citas, ejecutar antes `scripts_ext/18_fetch_openalex_metrics.py`, que tampoco forma parte de `run_all_ext`. Si faltan sus datos, `09_impact_indicators.py` se salta y deja un fichero `*_SKIPPED.txt`.

Para la interpretación de los resultados debe consultarse el [informe final](./docs/A2_Informe_presencia_espanola_congresos_2001-2025.pdf); el resto de ficheros documenta la trazabilidad y reproducibilidad del análisis.
