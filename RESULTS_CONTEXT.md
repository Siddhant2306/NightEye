# Market, sector and fundamental context # Task: Implement LightGBM as a New Forecasting Algorithm in NightEye

You are working on my existing **NightEye stock forecasting ML project**. I want you to implement LightGBM as a new forecasting algorithm and benchmark it against my existing XGBoost implementation.

This is an extension of an existing research pipeline, NOT a new project. First inspect the repository, understand its architecture and current experiments, and then implement the changes.

## 1. Primary objective

Implement LightGBM forecasting models for three independent prediction horizons:

1. **1 trading session (daily)**
2. **21 trading sessions (monthly)**
3. **252 trading sessions (annual)**

The objective is to determine whether LightGBM can produce meaningful improvements over the existing XGBoost models.

Do not assume LightGBM will perform better. The experiment must establish that through controlled evaluation.

## 2. First inspect the existing codebase

Before modifying anything, inspect:

- Existing XGBoost training and prediction modules.
- Feature engineering implementation.
- Data loading and preprocessing.
- Target construction for all three horizons.
- Chronological train/validation/test splitting.
- Purging and embargo logic.
- Existing held-out company methodology.
- Evaluation metrics and baseline calculations.
- Model serialization and prediction reports.
- Existing automated tests.

Identify reusable components and existing interfaces.

Do not duplicate existing functionality unnecessarily.

Do not modify or replace the existing XGBoost implementation.

## 3. LightGBM implementation

Use the official Python LightGBM package (`lightgbm`).

Implement a separate LightGBM module following the existing project architecture.

Suggested structure (adapt to the actual repository):

src/
    LightGBM/
        __init__.py
        config.py
        train.py
        predict.py
        model_report.py

If the project already has a better modular structure, follow that instead.

Use `LGBMRegressor` for return forecasting.

Start with conservative parameters:

- objective: regression
- boosting_type: gbdt
- n_estimators: 500
- learning_rate: 0.03
- num_leaves: 15
- max_depth: 5
- min_child_samples: 30
- subsample: 0.8
- colsample_bytree: 0.8
- reg_lambda: 1.0
- random_state: 42
- verbosity: -1

These are initial parameters, not guaranteed optimal values.

Make parameters configurable so that future experiments can tune them.

Handle missing values appropriately and ensure the model receives only valid features.

Avoid unnecessary scaling because tree-based LightGBM does not generally require feature standardization.

## 4. Separate models for each horizon

Train independent models for:

- Daily: 1-session future log return.
- Monthly: 21-session future log return.
- Annual: 252-session future log return.

Do not use one model for all three horizons.

Inspect how the existing XGBoost pipeline constructs each target and preserve the same target definitions.

For a horizon H, the general target should be:

log(close[t + H] / close[t])

Ensure that target construction, feature availability and target dates are consistent with the existing implementation.

The feature set can be horizon-specific, but initially use the existing validated feature configurations for each horizon to ensure a fair algorithm comparison.

Do not introduce additional features during the initial LightGBM benchmark.

## 5. Data leakage prevention

This is extremely important.

Preserve the existing research methodology:

- Chronological splits.
- Purged validation windows.
- Appropriate embargoes for overlapping forward-return labels.
- Held-out companies excluded from fitting and hyperparameter selection.
- No random train/test splitting.
- No future information in features.
- Fundamentals available only after their actual publication dates.
- No future revisions or backfilled financial information.
- No preprocessing fitted on validation or test data.
- No test-set-driven feature selection or hyperparameter tuning.

Use exactly the same train, validation and test observations as the corresponding XGBoost experiment.

If the existing pipeline cannot provide identical observations for a comparison, report the discrepancy instead of silently comparing different samples.

## 6. Hyperparameter tuning

Start with the baseline configuration above.

After the initial benchmark works, implement optional, bounded hyperparameter tuning using validation data only.

Prefer a small search space or Optuna if it is already installed or appropriate for the project.

Potential parameters to investigate:

- num_leaves
- max_depth
- learning_rate
- n_estimators
- min_child_samples
- feature_fraction
- bagging_fraction
- reg_lambda
- reg_alpha

Do not tune against the final test set.

Keep the initial baseline results separately from tuned results.

Do not introduce extensive tuning before the basic benchmark is working.

## 7. Evaluation metrics

Evaluate each horizon independently.

Regression metrics:

- MAE
- RMSE
- R²
- Pearson correlation between predicted and actual returns.
- Spearman rank correlation where appropriate.

Directional metrics:

- Directional accuracy.
- UP/DOWN precision and recall.
- Confusion matrix.
- Balanced accuracy.
- Directional accuracy against appropriate always-up, always-down and other existing baselines.

Additional requirements:

- Compare LightGBM against XGBoost on identical observations.
- Compare both against the existing price-only baseline.
- Report the difference in MAE and RMSE.
- Report percentage improvement or deterioration.
- Include uncertainty estimates using an appropriate date-level or block-based method, accounting for overlapping labels.

For the annual horizon, explicitly check whether predictions collapse into all-positive or all-negative predictions.

Do not report directional accuracy alone as evidence of predictive ability.

For multi-stock forecasting, also evaluate whether predicted returns can meaningfully rank stocks by their subsequent returns.

## 8. Model selection

Use validation performance to select models.

Do not choose the best model based on final test performance.

Keep the following separate:

1. LightGBM baseline.
2. LightGBM tuned model.
3. Existing XGBoost model.
4. Existing price-only baseline.

The final test set must remain untouched during model development.

If LightGBM does not improve performance, report that honestly. Do not force an improvement through test-set tuning or selective reporting.

## 9. Model artifacts and reproducibility

Save each trained model independently.

Use clear names, for example:

lightgbm_daily.joblib
lightgbm_monthly.joblib
lightgbm_annual.joblib

Each saved artifact should contain:

- Fitted model.
- Feature column names.
- Prediction horizon.
- Target definition.
- Training configuration.
- Training and validation date ranges.
- Relevant metrics.
- Model version.
- Random seed.

Ensure prediction code loads the correct saved model and uses the exact same feature ordering as training.

Do not overwrite XGBoost artifacts.

## 10. Prediction functionality

Implement inference functionality for all three horizons.

The system should eventually return:

- Predicted future log return.
- Predicted percentage return.
- Estimated future price.
- Directional probability, if a separately trained and properly calibrated classification model is implemented.

For a predicted log return r:

predicted_price = current_price * exp(r)

Do not convert a regression output directly into an UP/DOWN probability.

If probability output is implemented, train a separate classifier or use a properly calibrated methodology with validation-only calibration.

Do not label raw regression predictions as probabilities.

## 11. Reports and comparisons

Generate a consolidated comparison report.

Suggested structure:

reports/
    lightgbm/
        daily_metrics.json
        monthly_metrics.json
        annual_metrics.json
        daily_predictions.csv
        monthly_predictions.csv
        annual_predictions.csv

    comparisons/
        xgboost_vs_lightgbm.csv
        horizon_summary.csv

The comparison should make it easy to answer:

- Which algorithm performs better for daily forecasting?
- Which performs better for monthly forecasting?
- Which performs better for annual forecasting?
- Does LightGBM beat the price-only baseline?
- Are improvements statistically meaningful?
- Does the model generalize to held-out companies?
- Does performance remain stable across validation windows?
- Does the annual model still predict everything as UP?

Include actual and predicted returns, company identifier, prediction date and target date in prediction CSVs where applicable.

## 12. Automated tests

Add tests covering:

- Target horizon correctness.
- Feature ordering.
- No future leakage.
- Chronological splitting.
- Purging and embargo.
- Held-out company exclusion.
- Model save and reload.
- Prediction reproducibility.
- Missing feature handling.
- All three horizons.
- Regression-to-price conversion.
- No accidental modification of XGBoost artifacts.

Run the existing tests as well as the new tests.

Do not weaken or delete existing tests to make the implementation pass.

## 13. Dependencies and documentation

Update the appropriate dependency file with a compatible LightGBM version.

Document:

- How to train the three LightGBM models.
- How to run predictions.
- How to generate comparison reports.
- How to tune hyperparameters.
- How to interpret evaluation metrics.

Follow the existing command-line conventions.

## 14. Implementation workflow

Follow this order:

1. Inspect the entire existing pipeline.
2. Explain the architecture and identify reusable modules.
3. Implement LightGBM baseline training.
4. Integrate all three horizons.
5. Implement evaluation and comparison.
6. Implement model saving and inference.
7. Add automated tests.
8. Run the complete test suite.
9. Generate a final implementation and benchmark report.

Do not rewrite unrelated files.

Do not delete existing XGBoost functionality.

Do not silently change target definitions, feature sets, datasets, splits or evaluation methodology.

If an existing component is ambiguous, inspect its callers and tests before changing it.

## 15. Final response required

After implementation, provide:

1. Files created.
2. Files modified.
3. Architecture of the LightGBM integration.
4. Commands to train all three models.
5. Commands to generate predictions.
6. Tests executed and their results.
7. Benchmark results for daily, monthly and annual forecasting.
8. XGBoost vs LightGBM vs price-only comparison.
9. Any implementation limitations or unresolved issues.
10. Whether LightGBM actually improved the results.

**Most important principle: scientific validity is more important than achieving a higher accuracy number. I want NightEye to produce genuinely useful forecasting results, not artificially inflated metrics.**experiment

This is a matched recent-period study on the same 40-stock frozen price snapshot through October 23, 2026. Training origins start in 2017; the test begins January 2025. Two purged validation windows are 2021–2022 and 2023–2024. Five companies remain excluded from all fitting and tuning. These test years and companies were inspected before; this is exploratory research, not new prospective evidence.

Official exchange downloads contain 12 index-price series, Nifty 50 valuation history, and 325 usable original audited consolidated annual filings across all 40 companies.

## Validation-selected models

| Sessions | Selected family | Unseen direction | Always up | Selected RMSE | Matched price-only RMSE | RMSE reduction vs price-only | Price MAPE |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | price_only | 49.82% | 50.04% | 0.014893 | 0.014893 | +0.00% | 1.07% |
| 21 | market_sector_fundamentals | 52.35% | 52.21% | 0.064079 | 0.064237 | +0.25% | 5.20% |
| 252 | market_sector_fundamentals | 89.39% | 89.39% | 0.125237 | 0.106693 | -17.38% | 10.51% |

## Interpretation of this run

Daily validation preferred the price-only control. The validation-selected monthly fundamental/context bundle reduced unseen-stock RMSE by about 0.25% versus the matched control, but its paired uncertainty interval includes no improvement. The selected annual bundle increased unseen-stock RMSE by about 17.38%. All of its annual predictions were positive, and its 89.39% direction score equals the always-up baseline. These inputs did not establish a dependable incremental forecasting edge in this experiment.

The market-only monthly model happened to have a larger test RMSE reduction (about 0.77%), but did not win validation. Selecting it after inspecting that test result would be hindsight selection. No annual confidence interval is reported because the test contains only 196 unique annual-origin dates, fewer than the 252-session horizon.

Fifteen automated tests passed. All fifteen saved models reproduced every recorded test prediction and passed native reload, inverse scaling, held-out company exclusion, common-sample, purged-label-boundary and latest-row inference checks. Input hashes remained unchanged during the run. See verification.json.

Positive RMSE reduction means improvement. Selection is based on validation macro-stock RMSE, never the highest test direction percentage. Price MAPE is percentage error, not accuracy. The baseline is retrained on the same recent-period data and search budget; do not compare these percentages directly with the earlier 2021-start experiment.

## All predefined ablations on unseen companies

| Sessions | Family | Features | Validation RMSE | Unseen direction | Unseen RMSE | Reduction vs matched control |
|---|---|---:|---:|---:|---:|---:|
| 1 | price_only | 5 | 0.016078 | 49.82% | 0.014893 | +0.00% |
| 1 | market_sector_fundamentals | 24 | 0.016087 | 50.04% | 0.014888 | +0.04% |
| 1 | market_sector | 17 | 0.016088 | 50.09% | 0.014915 | -0.15% |
| 1 | market_sector_valuation | 20 | 0.016088 | 50.09% | 0.014883 | +0.07% |
| 1 | market | 12 | 0.016089 | 50.09% | 0.014891 | +0.01% |
| 21 | market_sector_fundamentals | 37 | 0.070432 | 52.35% | 0.064079 | +0.25% |
| 21 | market_sector_valuation | 33 | 0.070467 | 52.21% | 0.063817 | +0.65% |
| 21 | market | 25 | 0.070756 | 53.15% | 0.063745 | +0.77% |
| 21 | market_sector | 30 | 0.070825 | 52.21% | 0.063962 | +0.43% |
| 21 | price_only | 18 | 0.070900 | 52.21% | 0.064237 | +0.00% |
| 252 | market_sector_fundamentals | 37 | 0.204402 | 89.39% | 0.125237 | -17.38% |
| 252 | market_sector_valuation | 33 | 0.207424 | 89.39% | 0.110151 | -3.24% |
| 252 | price_only | 18 | 0.210919 | 89.39% | 0.106693 | +0.00% |
| 252 | market | 25 | 0.211029 | 89.39% | 0.106677 | +0.01% |
| 252 | market_sector | 30 | 0.211032 | 89.39% | 0.106677 | +0.01% |

## Inputs tested

- Price-only control: the previously selected 5-feature core for daily forecasts, original 18 features for monthly/annual forecasts.
- Market: lagged Nifty returns and volatility, plus stock momentum relative to the market (7 additional features).
- Market and sector: a declared economic sector-proxy index and relative momentum (5 additional features). These are broad static proxies, not claims of historical constituent membership.
- Index valuation: dated Nifty 50 earnings yield (1/P/E), book yield (1/P/B), and dividend yield (3 additional features). These describe the index, not individual company P/E.
- Company fundamentals: reported annual consolidated net profit/income, symmetric year-over-year income and profit growth from previously published annual filings, and publication age (4 additional features).

Market/sector observations and dated valuation figures are made usable on the next calendar day and joined backward to stock sessions. Corporate facts are joined only after their actual publication day; later revisions are not backfilled. Missing inputs remain missing and financial observations expire after 550 days. Growth is computed only when a prior annual period was already published; missing years are not treated as zero growth.

## Data and interpretation limits

Individual stock P/E and EPS yield were deliberately not constructed: the historical EPS and vendor-adjusted share bases have not been verified. The company fundamental test uses scale-independent income/profit ratios instead. It does not establish whether correctly constructed company P/E helps.

Older exchange XBRL files sometimes omit base context definitions. The parser accepts the recognized FourD annual/YTD template only for annual metadata, records that inference, and otherwise requires explicit annual dates. Financial tag names and bank formats differ; the exact accepted tags and source URLs are saved. This is a research extraction, not a fully reconciled financial database. Source revisions, taxonomy changes, and index valuation methodology changes remain risks. No current EPS or current P/E was copied into old dates.

The post-2025 integrated-filing feed was included. Four companies still lack successfully parsed post-2024 annual filings: BAJAJFINSV, HEROMOTOCO, POWERGRID, TATASTEEL. Their stale inputs become missing; coverage.json quantifies the actual model input coverage.

Paired moving date-block intervals in uncertainty.json compare every added-information family with the matched price-only model, preserving cross-stock dependence. They are approximate, do not account fully for repeated experimentation, and are particularly weak for annual forecasts: the available 2025 annual origins cover less than one independent annual market period, so no annual uncertainty interval is reported. Neither a high annual direction percentage nor a favorable point estimate demonstrates a real-market trading edge.

This study fits 360 validation models and 15 final evaluation models. It does not place trades, refit for live deployment, or implement Monte Carlo. A future prospective evaluation and an execution-cost study remain necessary before real-money use.

Sources: [Nifty historical prices and valuations](https://www.niftyindices.com/reports/historical-data), [NSE financial results](https://www.nseindia.com/companies-listing/corporate-filings-financial-results), [NSE integrated financial filings](https://www.nseindia.com/companies-listing/corporate-integrated-filing), [NSE index P/E methodology](https://www.nseindia.com/static/products-services/indices-price-earnings-ratio).
