# Bootstrap con barra de progreso

Sustituye tu fichero:

```text
scripts_ext/15_statistical_uncertainty_bootstrap.py
```

por el incluido aquí.

Ejemplos:

```powershell
python scripts_ext\15_statistical_uncertainty_bootstrap.py --B 100 --progress-every 10
python scripts_ext\15_statistical_uncertainty_bootstrap.py --B 200 --progress-every 10
python scripts_ext\15_statistical_uncertainty_bootstrap.py --B 1000 --progress-every 25
```

Para un cálculo mucho más rápido solo por ventanas:

```powershell
python scripts_ext\15_statistical_uncertainty_bootstrap.py --B 500 --windows-only
```

Salidas:

```text
outputs_ext/bootstrap_es_share_by_window.csv
outputs_ext/bootstrap_es_share_by_area_window.csv
```
