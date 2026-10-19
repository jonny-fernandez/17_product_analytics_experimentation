# CP1 — Implementation / Windows verification

Original checklist: CP1 read-only audit performed; CP2 event model, product metric tree and quality rules authored; CP3 deterministic scenario generator and offline validator authored. Windows verification **passed** October 19, 2026 based on provided pytest screenshot and three uploaded JSON evidence reports. Original CP4–CP17 are out of scope for this checkpoint. The CP1 validation is **not** SQL parity, A/B analysis or a deployment.

## Seven fixture types

| Name | Design | Contract expectation |
|---|---|---|
| baseline | pA=.10, pB=.105, 1:1 | pass |
| null | .10/.10, 1:1 | pass |
| positive | .10/.13, 1:1 | pass; **not** 5%-MDE scenario |
| underpowered | .10/.105, <=60 users | pass; invalid basis for inferential claims |
| srm | .10/.105, ~20:80 | event contract pass; statistical SRM failure tested in CP3 |
| contaminated | duplicated event ID + conflicting assignment | fail (intended) |
| invalid_event | negative-value purchase before checkout | fail (intended) |

## PowerShell from extracted root

```powershell
$root = 'C:\Users\Jonny Fernandez\Documents\github files\17_product_analytics_experimentation'
Set-Location -LiteralPath $root
$env:PYTHONPATH = Join-Path $root 'src'
python -m pytest -q
python -m product_analytics.data.cp1_report --scenario baseline --users 500 --seed 42 --out-dir artifacts\cp1
python -m product_analytics.data.cp1_report --scenario contaminated --users 500 --seed 42 --out-dir artifacts\cp1
python -m product_analytics.data.cp1_report --scenario invalid_event --users 500 --seed 42 --out-dir artifacts\cp1
```

All three report commands should print `"validation_as_expected": true` and exit successfully; intentional failures correctly report `validation.valid=false`. Tests and reports are offline. **Share screenshots plus `artifacts/cp1/cp1_baseline_report.json`, `cp1_contaminated_report.json`, and `cp1_invalid_event_report.json`**, but **never** share `.env`, keys, or other real credentials. Note: `artifacts/` is gitignored on purpose; the handoff is evidence for review, not yet a GitHub package.

### ZIP installation safety

The CP1 ZIP omits `.env`, `.pyc`, caches, logs and private artifacts. Extracting over an existing directory **does not remove its existing `.env`**. After rotating any genuine key, remove the local sensitive `.env` file manually (or keep it privately outside the project). `.env.example` is a nonsecret placeholder. Never commit the original starter ZIP.
