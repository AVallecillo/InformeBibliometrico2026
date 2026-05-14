# Ejecución robusta v6

## Qué corrige esta versión

- Los scripts opcionales ya no interrumpen la ejecución:
  - `08_institutional_analysis.py` se salta si no hay `institution_name`.
  - `09_impact_indicators.py` se salta si falta `outputs/openalex_work_metrics.csv`.
  - `17_author_position_leadership.py` se salta si no hay datos a nivel autor.
- `05_area_reclassification_sensitivity.py` crea un escenario temático por defecto si falta `data/external/venue_area_scenarios.csv`.
- `15_statistical_uncertainty_bootstrap.py` incluye progreso, ETA y parámetros `--B`, `--progress-every`, `--windows-only`.
- `00_validate_inputs.py` genera tanto `preflight_report.txt` como `input_validation_report.txt`.
- `run_all_ext.ps1` y `run_all_ext.sh` generan un resumen de ejecución:
  - `outputs_ext/run_all_ext_summary.csv` en PowerShell.
  - `outputs_ext/run_all_ext_summary.tsv` en bash.

## Orden recomendado

1. Generar CORE histórico:

```powershell
python scripts_ext\build_core_historical.py --input-dir data\core_historical\raw --output-dir data\core_historical --policy-2010 infer_2008_2013
```

2. Ejecutar todo:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run_all_ext.ps1
```

O con bash:

```bash
./run_all_ext.sh
```

## Impacto por citas

Solo si quieres impacto:

```powershell
python scripts_ext\18_fetch_openalex_metrics.py --mailto tu_correo@example.org
python scripts_ext\09_impact_indicators.py
```

## Bootstrap

Por defecto `run_all_ext` usa:

```powershell
python scripts_ext\15_statistical_uncertainty_bootstrap.py --B 500 --progress-every 25
```

Para una prueba rápida:

```powershell
python scripts_ext\15_statistical_uncertainty_bootstrap.py --B 100 --windows-only
```
