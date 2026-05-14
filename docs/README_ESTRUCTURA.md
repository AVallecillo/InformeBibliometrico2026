# Estructura del paquete v5.1

- `scripts_ext/`: scripts extendidos nuevos.
- `outputs_ext/`: salidas de los análisis extendidos. Se incluye `.gitkeep` para que el directorio aparezca al descomprimir.
- `data/core_historical/raw/`: coloca aquí los CSV históricos CORE/ERA.
- `data/core_historical/`: aquí se genera `core_historical.csv`.
- `data/external/`: datos auxiliares opcionales, como `country_normalisers.csv` y `venue_area_scenarios.csv`.
- `outputs/`: no se incluye en este paquete; debe ser el directorio ya generado por tu pipeline original.
