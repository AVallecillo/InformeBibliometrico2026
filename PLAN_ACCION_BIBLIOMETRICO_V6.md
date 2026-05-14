# Plan de acción bibliométrico v6 robusto

Esta versión está pensada para ejecutar de nuevo todo el análisis extendido sin interrupciones por dependencias opcionales.

## Estructura

```text
data/
  core_historical/
    raw/
    core_historical.csv
  external/
    venue_area_scenarios.csv
    *_TEMPLATE.csv

outputs/
  paper_master.csv
  paper_country.csv
  ...

scripts_ext/
  *.py

outputs_ext/
  resultados extendidos
```

## Principio metodológico

El informe principal conserva el corpus fijo CORE/ICORE 2026 A*/A. Los congresos históricos adicionales detectados por el análisis móvil no se incorporan al corpus principal. Se documentan como alcance futuro.

## Scripts críticos

- `01_fractional_vs_complete.py`
- `03_coverage_sensitivity.py`
- `04_core_historical_sensitivity.py`
- `06_shift_share_decomposition.py`
- `07_collaboration_profiles.py`
- `10_2025_maturity_check.py`
- `11_rank_uncertainty_bounds.py`
- `13_overlap_inflation_diagnostics.py`
- `15_statistical_uncertainty_bootstrap.py`
- `16_corpus_expansion_decomposition.py`
- `19_conclusion_verification.py`

## Scripts opcionales

- `08_institutional_analysis.py`: requiere `institution_name`.
- `09_impact_indicators.py`: requiere `outputs/openalex_work_metrics.csv`.
- `17_author_position_leadership.py`: requiere datos a nivel autor.
- `20`–`22`: documentan alcance de corpus histórico móvil, no modifican el corpus principal.

## CORE 2010

La opción principal recomendada es:

```text
--policy-2010 infer_2008_2013
```

Las políticas `all_A` y `exclude` pueden usarse como sensibilidad.
