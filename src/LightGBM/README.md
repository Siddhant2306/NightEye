# LightGBM forecasting

Independent `LGBMRegressor` models forecast 1-, 21- and 252-session cumulative log returns. This module benchmarks the official LightGBM package against the existing frozen XGBoost context experiment. It reuses the same loaders, features, label construction, observation eligibility, purged folds and held-out companies. It does not train or alter XGBoost and introduces no new features.

## Setup and baseline training

From the repository root in PowerShell:

```powershell
$py = 'C:/Users/Siddhant/miniconda3/envs/NightEye/python.exe'
& $py -m pip install -r requirements.txt
& $py -m src.LightGBM.train --horizons 1 21 252 --output artifacts/lightgbm/my_baseline
```

The default runs all three horizons. Use a new output directory for every run. `--data-dir`, `--context-dir` and `--xgboost-dir` override the frozen source/reference locations. The compatible reference is the context study (`artifacts/context_v3`), not the older one-day Reliance artifact. Existing data must already be present; training does not download data.

Initial parameters: regression/GBDT, maximum 500 trees, learning rate 0.03, 15 leaves, depth 5, minimum 30 child samples, 0.8 row/column fractions, L2 regularization 1.0 and seed 42. `subsample_freq=1` explicitly activates the 0.8 row fraction. Four CPU threads, deterministic training and column-wise histograms are set for reproducibility. The default is 50-round validation early stopping. A median validation-selected tree count is used for final development-data fitting. Requested maximum trees and actual fitted tree count are both saved.

Input NaNs are passed to LightGBM natively. There is no feature scaling, no fitted feature imputation and no silent row dropping in the LightGBM adapter. Missing named inputs, duplicate feature names, nonnumeric columns and infinities are errors. The label is standardized using each training fold's mean/std, matching XGBoost's existing return-label handling; inverse scaling is stored in each artifact. This is not feature standardization.

## Optional bounded tuning

First run the baseline. Then use the already-defined small validation-only search:

```powershell
& $py -m src.LightGBM.train --tune --trials 8 --horizons 1 21 252 --output artifacts/lightgbm/my_tuned
```

The search contains the baseline plus seeded combinations of leaves/depth, learning rate, maximum trees, child samples, row/column fractions, L1 and L2 penalties. It is capped at 16 candidates. No feature-family search is performed. The lowest average validation macro-stock RMSE selects the tuned configuration. Test error or direction never selects a configuration. The baseline remains saved under `baseline/`; the tuned choice is saved separately under `tuned/`. The tuned model may choose the baseline itself.

Use `--config path/to/params.json` to override supported baseline constructor parameters and `--early-stopping-rounds 50` to control validation stopping. For example, a JSON object can set `min_child_samples` to 75 and `reg_lambda` to 10. Use canonical names `subsample` and `colsample_bytree`, not duplicate aliases. Constructor settings are recorded in `protocol.json` before fitting. Changing the configuration defines a new baseline, so retain the original benchmark and choose another output directory.

## Data and comparison contract

Training origins begin in 2017. Validation windows are `[2021, 2023)` and `[2023, 2025)`, with the final test boundary at January 2025. Training targets and validation targets must mature strictly before their next boundary. Five companies—ASIANPAINT, BAJFINANCE, NTPC, TITAN and COALINDIA—are excluded from all fitting/tuning. The reference's past-only training protocol has **zero additional embargo sessions**: strict target-date purging supplies the horizon-dependent label gap, and no future/right-side samples enter training. This is documented rather than silently adding a gap and changing observations.

Features are fixed to the existing validation-selected XGBoost family: daily `price_only` (5 features); monthly/annual `market_sector_fundamentals` (37 features). Source hashes, feature names/order, training counts, validation counts/date boundaries, test keys, prices, outcomes, target dates and held-out assignments must match the corresponding reference. A discrepancy stops the run rather than generating a comparison on different observations.

`price_only` in the comparison is the previously trained **price-feature-only XGBoost model**, distinct from the zero-return/unchanged-price baseline. Both are evaluated, together with the selected XGBoost model, the training historical mean and the per-stock training mean. Held-out stocks use the universe mean when no training stock mean exists.

The historical test has already been inspected in earlier research. The implementation freezes tuning before test evaluation, but these experiments cannot be described as a new untouched prospective test. The source study also has retrospective archive, financial taxonomy and broad static sector-proxy limitations. Original features/fundamentals retain their existing causal publication lags; LightGBM does not revise or backfill them.

## Artifacts and prediction

For each stage and horizon, the directory contains a joblib model bundle (`lightgbm_daily.joblib`, `lightgbm_monthly.joblib` or `lightgbm_annual.joblib`), native `model.txt`, feature-importance CSV and `report.json`. Bundles include the fitted model, feature order, horizon, target definition, label scaling, configuration, seed, model version, training/validation ranges, source snapshot and metrics. Load only trusted generated bundles.

```powershell
& $py -m src.LightGBM.predict --model artifacts/lightgbm/my_baseline/baseline/h1/lightgbm_daily.joblib --history data/research_v2/RELIANCE.NS_2000-01-01_to_2026-10-27.csv --ticker RELIANCE.NS --context-dir data/context_v3
& $py -m src.LightGBM.predict --model artifacts/lightgbm/my_baseline/baseline/h21/lightgbm_monthly.joblib --history data/research_v2/RELIANCE.NS_2000-01-01_to_2026-10-27.csv --ticker RELIANCE.NS --context-dir data/context_v3
& $py -m src.LightGBM.predict --model artifacts/lightgbm/my_baseline/baseline/h252/lightgbm_annual.joblib --history data/research_v2/RELIANCE.NS_2000-01-01_to_2026-10-27.csv --ticker RELIANCE.NS --context-dir data/context_v3
```

For a tuned artifact replace `baseline` with `tuned` and use that experiment's output directory. Inference reconstructs the exact features, orders them using saved metadata, inverses target scaling, and converts the estimate with `current_adjusted_close * exp(predicted_log_return)`. It returns log return, percentage return and adjusted-price estimate. It does not report a probability; no classifier/calibration has been fitted. Latest eligible inputs must match the supplied history date, and stale context cannot be reused indefinitely. These are pre-2025 evaluation models, not models refitted through today for live deployment.

## Reports

```powershell
& $py -m src.LightGBM.model_report --directory artifacts/lightgbm/my_tuned
```

This regenerates reports from saved predictions without fitting models or selecting new settings. Reports are also generated automatically after training:

| Output | Contents |
|---|---|
| `reports/daily_metrics.json`, `monthly_metrics.json`, `annual_metrics.json` | Seen/unseen/all regression metrics, direction confusion matrices and ranking diagnostics |
| `reports/*_predictions.csv` | Company, origin date, target date, price, actual return, each model/baseline prediction |
| `comparisons/xgboost_vs_lightgbm.csv` | Paired MAE/RMSE differences, improvement/deterioration percentages and uncertainty |
| `comparisons/horizon_summary.csv` | MAE, RMSE, R², Pearson, Spearman, direction, precision/recall, balanced accuracy and rank IC |
| `comparisons/validation_stability.csv` | Selected-model performance in each validation window |
| `comparisons/per_stock.csv`, `yearly.csv` | Company/year stability |
| `comparisons/uncertainty.json`, `ranking.json` | Date-block intervals and cross-sectional ranking results |
| `comparisons/comparison.md` | Consolidated readable benchmark and limitations |
| `xgboost_integrity.json` | Protected XGBoost files unchanged during the run |
| `selected.json` | Best LightGBM stage and algorithm preference using validation only |

Lower MAE/RMSE is better. Direction uses DOWN/FLAT/UP, with actual classes as confusion-matrix rows and predictions as columns. UP/DOWN precision/recall are reported separately. Balanced accuracy averages their recalls if both actual classes occur; flat predictions count as errors. Undefined precision/correlations are marked explicitly, and constant forecasts do not receive invented correlations. Always-up, always-down and training-majority direction baselines are separate from point-price baselines.

Pooled Pearson/Spearman and mean cross-sectional daily Spearman IC answer different questions. IC uses dates with at least five stocks and nonconstant forecasts/outcomes. Rankable-date coverage is reported; undefined dates stay on the bootstrap time axis so gaps do not compress the overlapping-label blocks. Annual all-UP/all-DOWN collapse is flagged directly. None of these metrics alone establish trading profitability.

Uncertainty uses circular **date-level** blocks of `max(21, horizon)` sessions, after averaging simultaneous cross-stock losses. It reports paired MAE/RMSE and direction differences. Fewer than two horizon-sized blocks produces no interval; the current annual test has only 196 origin dates. The intervals are approximate and do not fully correct for market regime shifts or repeated experimentation. They must not be treated as proof of a live-market edge.

## Tests and module map

```powershell
& $py -m unittest discover -s tests -v
& $py -m src.LightGBM.verify --directory artifacts/lightgbm/my_tuned
```

`config.py` defines settings/search; `model.py` fits `LGBMRegressor`; `train.py` orchestrates matched validation and saving; `predict.py` handles inference; `metrics.py` implements direction/ranking/uncertainty; `model_report.py` builds consolidated outputs. `src/helper/benchmark.py` contains shared alignment and split checks, including the generic alignment cases preserved from the removed linear module. Existing shared/XGBoost feature, label and publication-timing tests remain intact. The two OLS/Ridge-specific tests were retired with the removed algorithm; all four former linear tests had passed before the removal.

The active linear-regression package is removed. Historical generated linear results/logs are retained only under `artifacts/retired_linear_regression`. No XGBoost implementation or artifacts are rewritten. There is no trading or Monte Carlo code in this addition.

Official references: [LGBMRegressor](https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.LGBMRegressor.html), [parameters](https://lightgbm.readthedocs.io/en/stable/Parameters.html), [early stopping](https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.early_stopping.html).
