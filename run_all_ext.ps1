$ErrorActionPreference = "Continue"
$env:PYTHONPATH = "$(Get-Location)\scripts_ext;$env:PYTHONPATH"

$summary = @()

function Run-Step {
    param(
        [string]$Label,
        [string]$Command,
        [bool]$Optional = $false
    )
    Write-Host ""
    Write-Host "[$Label] $Command"
    $start = Get-Date
    Invoke-Expression $Command
    $code = $LASTEXITCODE
    $elapsed = (Get-Date) - $start

    if ($code -eq 0) {
        Write-Host "[$Label] OK ($($elapsed.ToString()))"
        $script:summary += [PSCustomObject]@{Step=$Label; Status="OK"; ExitCode=$code; Optional=$Optional; Elapsed=$elapsed.ToString()}
    } elseif ($Optional) {
        Write-Host "[$Label] SKIPPED/FAILED OPTIONAL with exit code $code ($($elapsed.ToString()))"
        $script:summary += [PSCustomObject]@{Step=$Label; Status="OPTIONAL_FAILED"; ExitCode=$code; Optional=$Optional; Elapsed=$elapsed.ToString()}
    } else {
        Write-Host "[$Label] FAILED with exit code $code ($($elapsed.ToString()))"
        $script:summary += [PSCustomObject]@{Step=$Label; Status="FAILED"; ExitCode=$code; Optional=$Optional; Elapsed=$elapsed.ToString()}
    }
}

Run-Step "00" "python scripts_ext\00_validate_inputs.py"
Run-Step "01" "python scripts_ext\01_fractional_vs_complete.py"
Run-Step "02" "python scripts_ext\02_denominators_and_normalisation.py" $true
Run-Step "03" "python scripts_ext\03_coverage_sensitivity.py"
Run-Step "04" "python scripts_ext\04_core_historical_sensitivity.py" $true
Run-Step "05" "python scripts_ext\05_area_reclassification_sensitivity.py" $true
Run-Step "06" "python scripts_ext\06_shift_share_decomposition.py"
Run-Step "07" "python scripts_ext\07_collaboration_profiles.py"
Run-Step "08" "python scripts_ext\08_institutional_analysis.py" $true
Run-Step "09" "python scripts_ext\09_impact_indicators.py" $true
Run-Step "10" "python scripts_ext\10_2025_maturity_check.py"
Run-Step "11" "python scripts_ext\11_rank_uncertainty_bounds.py"
Run-Step "13" "python scripts_ext\13_overlap_inflation_diagnostics.py"
Run-Step "14" "python scripts_ext\14_missingness_bias_diagnostics.py" $true
Run-Step "15" "python scripts_ext\15_statistical_uncertainty_bootstrap.py --B 500 --progress-every 25"
Run-Step "16" "python scripts_ext\16_corpus_expansion_decomposition.py"
Run-Step "17" "python scripts_ext\17_author_position_leadership.py" $true
Run-Step "19" "python scripts_ext\19_conclusion_verification.py" $true
Run-Step "20" "python scripts_ext\20_historical_mobile_corpus_gap.py" $true
Run-Step "21" "python scripts_ext\21_prioritize_historical_missing_venues.py" $true
Run-Step "22" "python scripts_ext\22_refine_historical_missing_venue_tiers.py" $true
Run-Step "12" "python scripts_ext\12_make_diagnostic_figures.py" $true

New-Item -ItemType Directory -Force -Path outputs_ext | Out-Null
$summary | Export-Csv -Path outputs_ext\run_all_ext_summary.csv -NoTypeInformation -Encoding UTF8
$summary | Format-Table -AutoSize

Write-Host ""
Write-Host "Finished. Check outputs_ext\run_all_ext_summary.csv"
