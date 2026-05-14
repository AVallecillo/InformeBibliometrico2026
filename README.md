# InformeBibliometrico2026

Repositorio de reproducibilidad del informe bibliométrico **“Presencia española en congresos internacionales de Informática (2001-2025)”**, basado en el corpus de congresos **CORE/ICORE 2026 A\*** y **A**.

La Informática tiene una estructura de comunicación científica singular: en muchas de sus áreas nucleares, los congresos internacionales selectivos son el foro principal -y a menudo el definitivo- de publicación de resultados originales. Este repositorio reúne los datos, scripts, salidas intermedias y resultados utilizados para estudiar la presencia española en esos congresos durante el período 2001-2025, comparándola con el bloque UE27+Reino Unido, con otros países europeos de referencia y con las principales áreas temáticas de la disciplina.

El análisis completo, la metodología, las limitaciones y las conclusiones están recogidos en el informe PDF situado en la raíz del repositorio:

```text
informe_presencia_espana_congresos_informatica_2026.pdf
```

## Estructura del repositorio

```text
InformeBibliometrico2026/
|
|-- README.md
|-- .gitattributes
|-- informe_presencia_espana_congresos_informatica_2026.pdf
|-- run_all_ext.ps1
|-- run_all_ext.sh
|
|-- checkpoints/
|   |-- step*.json
|
|-- data/
|   |-- CORE-A.csv
|   |-- CORE-Astar.csv
|   |-- CORE2026-completo.csv
|   |-- dblp.xml.gz
|   |-- OLD_dblp.xml.gz
|   |-- core_historical/
|   |   |-- raw/
|   |   |-- core_historical.csv
|   |   |-- core_historical_*.csv
|   |   `-- README.md
|   `-- external/
|
|-- docs/
|   |-- informe_presencia_espana_congresos_informatica_2026_v5.docx
|   |-- figuras_informe_bibliometrico.zip
|   |-- README_*.md
|   |-- PLAN_ACCION_BIBLIOMETRICO_V6.md
|   `-- *.txt
|
|-- outputs/
|   |-- paper_master.csv
|   |-- paper_country.csv
|   |-- paper_country_sources.csv
|   |-- affiliation_evidence_*.csv
|   |-- report_indicators_*.csv
|   |-- corpus_*.*
|   `-- *_coverage_report.txt
|
|-- outputs_ext/
|   |-- figures/
|   |-- *_sensitivity*.csv
|   |-- bootstrap_*.csv
|   |-- shift_share_*.csv
|   |-- historical_*.csv
|   |-- conclusion_*.txt
|   `-- run_all_ext_summary.csv
|
|-- scripts/
|   |-- 00_setup.py
|   |-- 01_icore_oficial.py
|   |-- 02_dblp_map_oficial.py
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

- `data/`: contiene las entradas principales del estudio, incluyendo los ficheros CORE/ICORE 2026, el volcado DBLP y los datos auxiliares para el análisis histórico.
- `scripts/`: contiene el pipeline principal de construcción del corpus, validación DBLP, resolución de afiliaciones, consolidación artículo-país y generación de indicadores.
- `outputs/`: contiene las salidas reproducibles del pipeline principal, incluidas las tablas `paper_master.csv`, `paper_country.csv`, evidencias por fuente y tablas finales de indicadores.
- `scripts_ext/`: contiene los análisis complementarios de robustez y sensibilidad: conteo fraccionario, denominadores alternativos, sensibilidad por cobertura, CORE histórico, colaboración, bootstrap, expansión del corpus y auditorías históricas.
- `outputs_ext/`: contiene las salidas de los análisis extendidos, diagnósticos, figuras y resúmenes de ejecución.
- `checkpoints/`: contiene marcadores de ejecución de los pasos largos del pipeline.
- `docs/`: contiene documentación auxiliar, notas de ejecución, versiones editables del informe y material de apoyo.

Para la interpretación de los resultados debe consultarse el PDF final de la raíz del repositorio; el resto de ficheros documenta la trazabilidad y reproducibilidad del análisis.
