# data/core_historical/

Datos para el análisis de sensibilidad con las clasificaciones históricas CORE/ERA (`scripts_ext/04_core_historical_sensitivity.py`).

## Contenido

- `raw/`: listados históricos de congresos A* y A de CORE/ERA, uno por versión (`COREA-<año>.csv`, `COREAstar-<año>.csv`; la versión ERA 2010 combina ambos niveles en `COREAstarA-2010.csv`).
- `core_historical.csv`: tabla consolidada generada a partir de `raw/`, con las columnas `venue,core_year,level`. Ejemplo:

  ```text
  ICSE,2008,A*
  ICSE,2010,A*
  ICSE,2014,A*
  ```

- `core_historical_*.csv`: ficheros auxiliares y de auditoría generados en el mismo proceso (todas las filas leídas, resolución de duplicados, recuentos por año y nivel, y auditoría de la inferencia de 2010).
- `core_historical_README.txt`: resumen generado automáticamente con la política aplicada a 2010 y los recuentos por versión.

## Regeneración

```bash
python scripts_ext/build_core_historical.py --input-dir data/core_historical/raw --output-dir data/core_historical --policy-2010 infer_2008_2013
```

Los cambios de la versión actual del script se describen en [`docs/LEEME-CambiosV2.txt`](../../docs/LEEME-CambiosV2.txt).
