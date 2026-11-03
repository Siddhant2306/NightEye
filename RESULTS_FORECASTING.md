# Forecasting implementation and completed experiments — 1 November 2026

Implemented `src/forecasting` as a separate matched pipeline for XGBoost and LightGBM. Existing algorithm code and frozen benchmarks remain unchanged. Active standalone linear price regression remains removed. Logistic regression appears only as the standard sigmoid probability-calibration step for direction classifiers.

## Completed work

- `--max-rounds` / `--epochs`: a boosting-round ceiling with validation early stopping, not repeated learning from the same data. The intensive run allowed 1,000 rounds; final selected counts were 1..58, depending on task/horizon.
- Chronological 80% development / 20% final test by unique eligible dates, with identical boundaries for all horizons/stocks. Inside development: expanding folds at 40..52% and 52..64%, final model fit before 64%, separate calibration at 64..80%. Labels crossing each next boundary are removed.
- Frozen boundaries: fold1 2020-12-04; fold2 2022-02-07; calibration 2023-04-12; test 2024-11-07. Daily test includes 484 dates; monthly 463 overall/462 unseen; annual 233 overall/232 unseen. Horizon maturity reduces final test eligibility.
- Forty stocks. Five complete company holdouts excluded from fitting, selection and calibration. Reports separate seen, unseen and pooled all-stock tests.
- Existing features versus 28 normalized screenshot-derived technical indicators plus existing context. Native missing-value handling; no invented insider/news data or unsafe historical company P/E.
- Separate direct-horizon return regressors and UP/NOT_UP classifiers; later probability calibration; predeclared .60/.40 UP/NOT_UP thresholds with NO_SIGNAL in between.
- Volatility-scaled empirical residual endpoint distributions, tested 50/80/95% interval coverage, 5-session block-bootstrap bridge scenarios, JSON/CSV and standalone HTML outputs. No distribution-free or path-drawdown calibration claim.
- Model reload, source-hash, shared-key, label-maturity and full saved-prediction verification commands. All 94 protected source/reference files and source price/context hashes unchanged.

## Runs and verification

1. `artifacts/forecasting/experiment_v1`: 3 configurations × 2 feature families × 2 tasks × 2 algorithms × 3 horizons × 2 folds = **144 validation fits**, plus final fits.
2. `artifacts/forecasting/intensive_v1`: 8 configurations, ceiling 1,000 rounds and patience 50 = **384 validation fits**, plus final fits.

Total **528 validation fits**, twelve algorithm/horizon bundles, each containing return/direction models and a matched return control. All full test forecasts, calibration residual banks and interval endpoints reproduced from saved bundles and original sources. Test suite: **38 tests passed**. See `verification_forecasting_v1.log`, `verification_forecasting_intensive_v1.log`, `tests_forecasting.log` and the experiment `verification.json` files.

Search settings were declared before evaluation; test outcomes never selected configurations, feature families, rounds or preferred algorithms. Existing historical tests have been inspected repeatedly, so these runs do not establish prospective performance. Running a broader search can overfit validation and worsen the final test; the measurements below show that happening.

## Intensive run: unseen-company results

| Horizon | Algorithm | Return RMSE | Matched-control RMSE | Price MAPE | Regressor direction | Classifier accuracy | Always UP |
|---|---|---|---|---|---|---|---|
| 1 | XGBoost | 0.014887 | 0.014871 | 1.07% | 49.67% | 49.67% | 49.67% |
| 1 | LightGBM | 0.014887 | 0.014869 | 1.07% | 49.67% | 49.71% | 49.67% |
| 21 | XGBoost | 0.065444 | 0.064758 | 5.29% | 48.61% | 50.87% | 50.87% |
| 21 | LightGBM | 0.064539 | 0.064758 | 5.23% | 51.69% | 50.87% | 50.87% |
| 252 | XGBoost | 0.125376 | 0.128185 | 9.94% | 86.47% | 86.47% | 86.47% |
| 252 | LightGBM | 0.126992 | 0.126797 | 10.03% | 86.47% | 86.47% | 86.47% |

Control is the existing feature family and first conservative configuration, freshly fitted on identical new dates. It is not a historical artifact evaluated on different samples. RMSE is on cumulative log returns. MAPE is average absolute percentage price error, not “100 minus error = accuracy”. Regressor direction and separately trained classifier direction are distinct outputs.

The monthly LightGBM RMSE improves about **0.34% relative** to its control. Its return-sign accuracy improves about 0.82 percentage points over always-UP. This is a small research result, not established trading usefulness. Daily models do not beat the unchanged-price baseline on this unseen-company RMSE test. Annual XGBoost improves unseen-company error but worsens the all-stock error versus its control.

The final classifiers have balanced accuracy about **50%**, despite high annual headline accuracy. Monthly/annual forecasts classify every unseen-stock outcome as UP; they cannot identify declines. Daily LightGBM reports 100% high-threshold UP precision on **one UP signal out of 2,420 observations**. That is inadequate evidence, and counts/coverage/warnings expose it. Probability Brier scores fail the constant-training-probability baseline; calibration has not made them reliable in the later regime.

The validation-preferred return algorithm is XGBoost for all three horizons; the direction preference is XGBoost daily and LightGBM monthly/annual. These choices are retained even where the test favors another model. See `selected.json`; do not select by the favorable table entries after the fact.

## Interval coverage is the important simulation limitation

| Horizon | XGBoost nominal 80% coverage, unseen | LightGBM nominal 80% coverage, unseen | XGBoost, all stocks | LightGBM, all stocks |
|---|---|---|---|---|
| 1 | 80.00% | 79.83% | 79.40% | 79.26% |
| 21 | 78.66% | 78.96% | 77.03% | 77.30% |
| 252 | 78.10% | 75.52% | **51.56%** | **49.39%** |

Annual intervals fail badly across all stocks. The calibration period has just 136 annual origin dates and the test only 233; overlapping outcomes provide much less independent evidence than the row counts suggest. Annual uncertainty intervals for paired model differences are withheld because fewer than two horizon-sized test blocks exist. A bullish calibration regime produces overly optimistic annual endpoint probabilities and ranges.

The Monte Carlo output therefore remains **experimental scenarios**, especially annually. It does not increase accuracy, guarantee coverage, discover future crashes, or validate path drawdowns. Probability and coverage warnings appear beside forecast outputs. A scenario frequency near 99% must not be interpreted as validated 99% confidence.

## Example output from the completed intensive models

Reliance cached history ends **2026-10-23**, starting adjusted price **₹1,190**. These are historical-input examples, not current quotes or latest-date production refits.

| Horizon | Algorithm | Point estimate | Empirical 80% endpoint interval | Classifier signal |
|---|---|---|---|---|
| 1 | XGBoost | ₹1,190.64 | ₹1,168.04–₹1,216.15 | NO_SIGNAL |
| 1 | LightGBM | ₹1,190.77 | ₹1,168.18–₹1,216.09 | NO_SIGNAL |
| 21 | XGBoost | ₹1,207.17 | ₹1,110.81–₹1,349.62 | UP, experimental |
| 21 | LightGBM | ₹1,206.34 | ₹1,109.68–₹1,348.64 | UP, experimental |
| 252 | XGBoost | ₹1,625.75 | ₹1,497.07–₹3,117.28 | UP, unreliable annual calibration |
| 252 | LightGBM | ₹1,655.23 | ₹1,552.74–₹3,246.97 | UP, unreliable annual calibration |

The annual ranges illustrate the bullish-calibration failure, not a defensible promise of upside. Scenario medians can differ from point forecasts because the empirical residual bias is retained. The forecast report discloses model-fit/calibration dates, relevant company-group metrics and all-stock coverage. Models require eligible OHLCV and configured sector/context mapping; coverage is not “every stock”.

Open `artifacts/forecasting/reliance_final_v1/index.html` for the six-model overview and per-model charts. The first and broader experiments have offline `comparison.html` and readable `comparison.md`, complete metrics, learning curves, per-stock files and saved forecasts.

## Assessment of the requested changes

- **More epochs:** implemented correctly as boosting rounds; early stopping chooses fewer. Repeated fresh fits on identical inputs do not accumulate learning.
- **80/20:** improves the evaluation structure, not the underlying information. Random splitting would leak overlapping future outcomes; chronological splitting/purging is required here.
- **Technical features:** small/mixed error changes; no broad directional improvement. Validation chooses them only when their loss improves.
- **Direction classifiers/calibration:** implemented and honestly tested. They have not established reliable directional skill; adding a classifier is not a guarantee.
- **Monte Carlo:** provides reproducible scenario output. Daily/monthly coverage is more plausible than annual coverage; annual probabilities/intervals are not deployment-ready.

The next research priority is broader independent market regimes and sufficiently long annual validation/calibration windows, followed by better probability/interval stability and prospective monitoring. These runs do not establish a maximum accuracy for either algorithm.

Full commands, architecture, feature definitions and assumptions: [FORECASTING.md](FORECASTING.md).
