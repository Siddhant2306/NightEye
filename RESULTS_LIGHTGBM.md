# LightGBM implementation and benchmark

LightGBM 4.7.0 is implemented as a separate forecasting module. The active linear-regression package is removed. Its old generated results/logs are retained under `artifacts/retired_linear_regression`. XGBoost's implementation and existing benchmark artifacts were not changed: all 94 protected files match their pre-task hashes.

## Architecture and files

New code:

- `src/LightGBM/__init__.py`: model format/version identifier.
- `src/LightGBM/config.py`: requested conservative baseline, JSON parameter overrides, seeded 1–16 candidate bounded search.
- `src/LightGBM/model.py`: official `LGBMRegressor`, native NaNs, train-only label scaling, validation early stopping.
- `src/LightGBM/train.py`: exact-source/observation checks, fixed per-horizon features, independent baseline/tuned fitting and serialization.
- `src/LightGBM/predict.py`: ordered-feature inference, inverse label scaling, return/adjusted-price output; no probability output.
- `src/LightGBM/metrics.py`: regression, three-state direction, class precision/recall, balanced accuracy, rank IC and paired date-block diagnostics.
- `src/LightGBM/model_report.py`: consolidated metrics, comparisons, validation-only algorithm preference and report regeneration.
- `src/LightGBM/verify.py`: reproduce every saved forecast and check source/inference integrity.
- `src/helper/benchmark.py`: reusable snapshot, chronological split, feature ordering and exact-reference alignment checks.
- `tests/test_lightgbm.py`, `tests/test_benchmark_alignment.py`: algorithm and comparison coverage.
- `src/LightGBM/README.md`: configuration, commands, architecture, metrics and limitations.

Modified files are `README.md`, `requirements.txt`, and `environment.lock.txt`. Removed active files are the `src/LinearRegression` package and its dedicated test file. The generic alignment cases were preserved in the shared benchmark tests. All former linear tests passed before retirement; no failing test was weakened to make LightGBM pass. Existing shared/XGBoost tests remain intact.

The implementation reuses `src.research_context.prepare`, the existing feature/label builder, `src.pipeline.purged_split` and stock weights. It fixes features to the original validation-selected XGBoost family: daily price-only (5 features), monthly/annual market/sector/fundamentals (37 features). No new features are introduced.

Both algorithms use the same frozen stock/context sources, 2017 training start, 2021–2022 and 2023–2024 purged validation windows, January 2025 test boundary and five entirely excluded training companies. Strict target-date purging supplies the horizon-dependent label gap. The reference's past-only protocol has zero additional embargo; adding one would change the requested comparison observations. Source hashes, fold counts/dates, prices, target dates, held-out assignments and actual outcomes are checked.

## Held-out-company benchmark

These are log-return RMSE values; lower is better. Every model is compared on identical observations within its horizon.

| Horizon | XGBoost selected | Price-only XGBoost | LightGBM baseline | LightGBM tuned | Tuned RMSE change versus XGBoost |
|---|---:|---:|---:|---:|---|
| 1 session | 0.014893 | 0.014893 | 0.014884 | 0.014881 | 0.08% lower |
| 21 sessions | 0.064079 | 0.064237 | 0.064427 | 0.063923 | 0.24% lower |
| 252 sessions | 0.125237 | 0.106693 | 0.106270 | 0.129114 | 3.10% higher/worse |

The untuned annual baseline is 15.15% better than the selected XGBoost model on test RMSE, but only about 0.40% better than the stronger price-only XGBoost control. The baseline did not win annual validation. Choosing it because of the favorable test result would be hindsight selection; it is retained separately rather than substituted for the validation-selected tuned model.

| Horizon | LightGBM baseline direction | LightGBM tuned direction | XGBoost direction | Always up |
|---|---:|---:|---:|---:|
| 1 session | 50.04% | 50.04% | 49.82% | 50.04% |
| 21 sessions | 52.21% | 52.21% | 52.35% | 52.21% |
| 252 sessions | 89.39% | 89.39% | 89.39% | 89.39% |

All annual LightGBM predictions are UP. UP/DOWN balanced accuracy is 50%, so the high annual direction percentage is not incremental directional skill. The same warning applies to monthly all-UP forecasts. The reports contain DOWN/FLAT/UP confusion matrices and UP/DOWN precision/recall, not just accuracy.

## Selection, uncertainty and ranking

- Validation prefers XGBoost for daily and monthly forecasting. Annual LightGBM validation RMSE is 0.204397604 versus XGBoost 0.204401548: a negligible advantage that did not carry into this test. `selected.json` records algorithm preference using validation only.
- The tuned daily paired date-block interval favors LightGBM's very small error reduction in this reused period. It is not a demonstrated practical/prospective edge or a correction for repeated experimentation.
- The monthly paired interval includes no improvement. The small 0.24% point improvement is uncertain.
- The annual test contains only 196 unique origin dates, less than the 252-session horizon. No annual confidence interval is manufactured from these overlapping outcomes.
- Cross-sectional ranking does not establish a dependable advantage: tuned held-out rank IC is approximately -0.021 daily and +0.050 monthly, with intervals spanning zero. The annual point IC is approximately -0.214 with insufficient independent time coverage. Many daily/monthly forecasts are tied; rankable-date coverage and undefined dates are reported explicitly. Undefined dates remain on the bootstrap time axis.

MAE changes/percentages, Pearson and pooled Spearman, per-stock/year performance, validation-window stability, rank coverage and paired intervals are in the CSV/JSON outputs. In particular, the full tuned comparison is `artifacts/lightgbm/tuned_v1/comparisons/comparison.md`, and the baseline-only comparison is under `artifacts/lightgbm/baseline_v1`.

## Verification

- All 33 active tests passed, including all retained shared/XGBoost tests.
- Baseline-only training fitted three independent horizon models. The eight-candidate tuned run saved another three baseline and three tuned models.
- All nine saved bundles reproduced every recorded test prediction after reload. Native LightGBM model reloads also matched.
- Latest-row inference was verified for every saved model/horizon, with the correct feature ordering and inverse scaling.
- Source snapshots, purged label boundaries, held-out exclusions and common test observations passed verification.
- The repeated baseline predictions are identical between the initial baseline and tuning experiments, including the LightGBM 4.7 validation-API compatibility update.
- All 94 protected XGBoost files match the original pre-task snapshot. No XGBoost model was retrained or overwritten.

## Commands

Run from the project root in PowerShell. Always choose a new training output directory.

```powershell
$py = 'C:/Users/Siddhant/miniconda3/envs/NightEye/python.exe'
& $py -m src.LightGBM.train --horizons 1 21 252 --output artifacts/lightgbm/run2
& $py -m src.LightGBM.train --tune --trials 8 --horizons 1 21 252 --output artifacts/lightgbm/tuned_run2
```

Predictions from the already trained tuned models:

```powershell
$history = 'data/research_v2/RELIANCE.NS_2000-01-01_to_2026-10-27.csv'
$run = 'artifacts/lightgbm/tuned_v1'
& $py -m src.LightGBM.predict --model "$run/tuned/h1/lightgbm_daily.joblib" --history $history --ticker RELIANCE.NS
& $py -m src.LightGBM.predict --model "$run/tuned/h21/lightgbm_monthly.joblib" --history $history --ticker RELIANCE.NS
& $py -m src.LightGBM.predict --model "$run/tuned/h252/lightgbm_annual.joblib" --history $history --ticker RELIANCE.NS
& $py -m src.LightGBM.model_report --directory $run
& $py -m src.LightGBM.verify --directory $run
& $py -m unittest discover -s tests -v
```

## Limitations and conclusion

There are modest daily/monthly test error reductions, but no convincing overall improvement suitable for live use. Annual tuning worsened test error, ranking evidence is weak, and the high direction scores mostly reflect positive forecasts. There is no maximum-accuracy claim.

The historical test dates and companies had already been inspected before this task. The new implementation evaluates test metrics only after selecting configurations on validation, but that cannot turn reused history into a pristine holdout. The annual sample is particularly inadequate. Existing archive/taxonomy and sector-proxy limitations remain. No directional probability, classifier calibration, trading, Monte Carlo simulation or production refit was implemented. Models are evaluation fits with labels strictly before 2025; a prospective paper trial and execution-cost evaluation remain necessary.
