# Script de priorización de venues históricos faltantes

Copia `scripts_ext/21_prioritize_historical_missing_venues.py` a tu repositorio.

Ejecuta después de:

```powershell
python scripts_ext\20_historical_mobile_corpus_gap.py
```

Luego:

```powershell
python scripts_ext\21_prioritize_historical_missing_venues.py
```

Salidas principales:

```text
outputs_ext/historical_missing_venue_prioritization.csv
outputs_ext/historical_missing_venue_priority_summary.csv
outputs_ext/historical_missing_venue_dblp_extraction_candidates.csv
outputs_ext/historical_missing_venue_review_template.csv
outputs_ext/historical_missing_venue_prioritization_report.txt
```

Opcionalmente puedes crear:

```text
data/external/historical_venue_review_overrides.csv
```

con columnas:

```csv
venue,priority_override,area_override,include_override,notes_override
COLING,HIGH,NLP,yes,Central NLP venue
AMIA,LOW,Biomedicina,no,Fuera del foco principal del informe
```
