# Metadata auxiliar necesaria

## country_normalisers.csv
Columnas:
country_code,population_millions,researchers_fte,gerd_musd,cs_faculty_or_researchers

## core_historical.csv
Columnas:
venue,core_year,level

Ejemplo:
ICSE,2008,A*
ICSE,2010,A*
ICSE,2014,A*

## venue_area_scenarios.csv
Columnas:
scenario,venue,area_alt

Ejemplo:
baseline,WWW,Bases de datos
WWW_as_IA,WWW,IA/ML
SIGIR_as_IA,SIGIR,IA/ML
KDD_as_DB,KDD,Bases de datos

## openalex_work_metrics.csv
Debe ir en outputs/ si se usa 09_impact_indicators.py:
paper_id,cited_by_count


## paper_author_affiliations.csv
Necesario para 17_author_position_leadership.py si las evidencias existentes no contienen author_order.

Columnas:
paper_id,author_id,author_order,country_code,institution_name

## Nuevos scripts v2
13_overlap_inflation_diagnostics.py: cuantifica la suma de cuotas no excluyentes y la colaboración intraeuropea.
14_missingness_bias_diagnostics.py: diagnostica no-aleatoriedad de cobertura.
15_statistical_uncertainty_bootstrap.py: intervalos bootstrap de cuota española.
16_corpus_expansion_decomposition.py: separa venues presentes, nuevos y desaparecidos.
17_author_position_leadership.py: liderazgo por primera/última autoría cuando hay metadatos.
