# data/external/

Metadatos externos opcionales para los análisis extendidos (`scripts_ext/`). Los ficheros `*_TEMPLATE.csv` son plantillas: para usarlos, hay que rellenarlos y guardarlos sin el sufijo `_TEMPLATE`.

## venue_area_scenarios.csv

Escenarios de reclasificación temática usados por `05_area_reclassification_sensitivity.py`. Si falta, el script crea un escenario por defecto.

Columnas: `scenario,venue,area_alt`

Ejemplo:

```text
baseline,WWW,Bases de datos
WWW_as_IA,WWW,IA/ML
SIGIR_as_IA,SIGIR,IA/ML
KDD_as_DB,KDD,Bases de datos
```

## country_normalisers_TEMPLATE.csv

Plantilla de denominadores por país (`country_normalisers.csv`), usada por `02_denominators_and_normalisation.py` para normalizar por tamaño del sistema. Si falta, el script solo genera la tabla de denominadores alternativos.

Columnas: `country_code,population_millions,researchers_fte,gerd_musd,cs_faculty_or_researchers`

## historical_venue_review_overrides_TEMPLATE.csv y historical_venue_tier_overrides_TEMPLATE.csv

Plantillas para introducir correcciones manuales en la revisión de los congresos históricos ausentes del corpus: `historical_venue_review_overrides.csv` la lee `21_prioritize_historical_missing_venues.py` y `historical_venue_tier_overrides.csv` la lee `22_refine_historical_missing_venue_tiers.py`.

## Ficheros que se colocan en outputs/

Dos análisis opcionales necesitan además ficheros en `outputs/`:

- `outputs/openalex_work_metrics.csv` (columnas `paper_id,cited_by_count`), para `09_impact_indicators.py`. Se genera con `18_fetch_openalex_metrics.py`.
- `outputs/paper_author_affiliations.csv` (columnas `paper_id,author_id,author_order,country_code,institution_name`), para `17_author_position_leadership.py` si las evidencias existentes no contienen el orden de autoría.

Si faltan, los scripts correspondientes se saltan y generan un fichero `*_SKIPPED.txt` en `outputs_ext/`.
