from pathlib import Path
import pandas as pd

from common import standardise_master_columns, EU27_UK

OUT = Path("outputs_ext")
OUT.mkdir(exist_ok=True)

pm_path = Path("outputs/paper_master.csv")
pc_path = Path("outputs/paper_country.csv")

errors = []
warnings = []

if not pm_path.exists():
    errors.append("Missing outputs/paper_master.csv")
if not pc_path.exists():
    errors.append("Missing outputs/paper_country.csv")

if errors:
    report = "PREFLIGHT VALIDATION\n" + "="*70 + "\n\nERRORS\n  " + "\n  ".join(errors) + "\n"
    for name in ["preflight_report.txt", "input_validation_report.txt"]:
        (OUT / name).write_text(report, encoding="utf-8")
    print(report)
    raise SystemExit(1)

pm = standardise_master_columns(pd.read_csv(pm_path))
pc = pd.read_csv(pc_path)

required_pm = {"paper_id", "year", "window", "venue", "congress", "level", "area"}
required_pc = {"paper_id", "country_code"}

missing_pm = required_pm - set(pm.columns)
missing_pc = required_pc - set(pc.columns)

if missing_pm:
    warnings.append(f"paper_master.csv missing columns: {sorted(missing_pm)}")
if missing_pc:
    errors.append(f"paper_country.csv missing columns: {sorted(missing_pc)}")

if "paper_id" in pm.columns:
    paper_master_rows = len(pm)
    paper_master_unique_papers = pm["paper_id"].nunique()
else:
    paper_master_rows = len(pm)
    paper_master_unique_papers = None

if "paper_id" in pc.columns:
    paper_country_rows = len(pc)
    paper_country_unique_papers = pc["paper_id"].nunique()
else:
    paper_country_rows = len(pc)
    paper_country_unique_papers = None

paper_country_unique_countries = pc["country_code"].nunique() if "country_code" in pc.columns else None
spain_papers = pc.loc[pc["country_code"].eq("ES"), "paper_id"].nunique() if {"country_code","paper_id"}.issubset(pc.columns) else None
eu27_uk_papers = pc.loc[pc["country_code"].isin(EU27_UK), "paper_id"].nunique() if {"country_code","paper_id"}.issubset(pc.columns) else None
coverage = paper_country_unique_papers / paper_master_unique_papers if paper_master_unique_papers else None

summary = {
    "paper_master_rows": paper_master_rows,
    "paper_master_unique_papers": paper_master_unique_papers,
    "paper_country_rows": paper_country_rows,
    "paper_country_unique_papers": paper_country_unique_papers,
    "paper_country_unique_countries": paper_country_unique_countries,
    "spain_papers": spain_papers,
    "eu27_uk_papers": eu27_uk_papers,
    "coverage": coverage,
}

report_lines = ["PREFLIGHT VALIDATION", "="*70, "", "SUMMARY"]
for k, v in summary.items():
    report_lines.append(f"  {k}: {v}")

report_lines += ["", "WARNINGS"]
report_lines += [f"  {w}" for w in warnings] if warnings else ["  none"]
report_lines += ["", "ERRORS"]
report_lines += [f"  {e}" for e in errors] if errors else ["  none"]
report = "\n".join(report_lines) + "\n"

for name in ["preflight_report.txt", "input_validation_report.txt"]:
    (OUT / name).write_text(report, encoding="utf-8")

print(report)
if errors:
    raise SystemExit(1)
