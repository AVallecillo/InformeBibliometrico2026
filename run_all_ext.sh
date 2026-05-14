#!/usr/bin/env bash
set +e
export PYTHONPATH="$(pwd)/scripts_ext:${PYTHONPATH:-}"
mkdir -p outputs_ext
summary="outputs_ext/run_all_ext_summary.tsv"
echo -e "step\tstatus\texit_code\toptional" > "$summary"

run_step () {
  label="$1"
  optional="$2"
  shift 2
  echo ""
  echo "[$label] $*"
  start=$(date +%s)
  "$@"
  code=$?
  end=$(date +%s)
  elapsed=$((end-start))
  if [ "$code" -eq 0 ]; then
    echo "[$label] OK (${elapsed}s)"
    echo -e "${label}\tOK\t${code}\t${optional}" >> "$summary"
  elif [ "$optional" = "true" ]; then
    echo "[$label] OPTIONAL_FAILED (${elapsed}s), exit code ${code}"
    echo -e "${label}\tOPTIONAL_FAILED\t${code}\t${optional}" >> "$summary"
  else
    echo "[$label] FAILED (${elapsed}s), exit code ${code}"
    echo -e "${label}\tFAILED\t${code}\t${optional}" >> "$summary"
  fi
}

run_step "00" false python scripts_ext/00_validate_inputs.py
run_step "01" false python scripts_ext/01_fractional_vs_complete.py
run_step "02" true  python scripts_ext/02_denominators_and_normalisation.py
run_step "03" false python scripts_ext/03_coverage_sensitivity.py
run_step "04" true  python scripts_ext/04_core_historical_sensitivity.py
run_step "05" true  python scripts_ext/05_area_reclassification_sensitivity.py
run_step "06" false python scripts_ext/06_shift_share_decomposition.py
run_step "07" false python scripts_ext/07_collaboration_profiles.py
run_step "08" true  python scripts_ext/08_institutional_analysis.py
run_step "09" true  python scripts_ext/09_impact_indicators.py
run_step "10" false python scripts_ext/10_2025_maturity_check.py
run_step "11" false python scripts_ext/11_rank_uncertainty_bounds.py
run_step "13" false python scripts_ext/13_overlap_inflation_diagnostics.py
run_step "14" true  python scripts_ext/14_missingness_bias_diagnostics.py
run_step "15" false python scripts_ext/15_statistical_uncertainty_bootstrap.py --B 500 --progress-every 25
run_step "16" false python scripts_ext/16_corpus_expansion_decomposition.py
run_step "17" true  python scripts_ext/17_author_position_leadership.py
run_step "19" true  python scripts_ext/19_conclusion_verification.py
run_step "20" true  python scripts_ext/20_historical_mobile_corpus_gap.py
run_step "21" true  python scripts_ext/21_prioritize_historical_missing_venues.py
run_step "22" true  python scripts_ext/22_refine_historical_missing_venue_tiers.py
run_step "12" true  python scripts_ext/12_make_diagnostic_figures.py

echo ""
echo "Finished. Check $summary"
