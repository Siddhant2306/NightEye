# Reduced-feature XGBoost study

Downloaded 40 stocks and 248,335 clean daily observations. Prices and ex-dividend cash histories are frozen in data/research_v2.

35 companies enter training and validation. ASIANPAINT, BAJFINANCE, NTPC, TITAN, and COALINDIA are excluded from every training and validation fold. They were not in the previous 15-stock experiment.

The 2021–2026 period was already inspected in the earlier study. These results are further research, with new cross-stock holdouts, not a fresh prospective temporal test.

## Selected models (chosen using validation only)

| Sessions | Family | Features | Seen-stock direction | Unseen-stock direction | Unseen always-up | Unseen return RMSE | Zero RMSE | Stock-mean RMSE | Unseen price MAPE |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | core | 5 | 50.80% | 51.01% | 51.03% | 0.016503 | 0.016523 | 0.016512 | 1.17% |
| 21 | original | 18 | 55.53% | 56.01% | 56.01% | 0.075174 | 0.076437 | 0.075176 | 5.91% |
| 252 | original | 18 | 70.10% | 73.25% | 73.25% | 0.255006 | 0.301550 | 0.250855 | 19.28% |

## Interpretation

- 1 sessions, core: unseen-stock return RMSE reduction versus unchanged price +0.12%, versus training mean +0.05%; direction advantage over always-up -0.01 percentage points. 99.93% of forecasts predict a rise.
- 21 sessions, original: unseen-stock return RMSE reduction versus unchanged price +1.65%, versus training mean +0.00%; direction advantage over always-up +0.00 percentage points. 100.00% of forecasts predict a rise.
- 252 sessions, original: unseen-stock return RMSE reduction versus unchanged price +15.43%, versus training mean -1.66%; direction advantage over always-up +0.00 percentage points. 100.00% of forecasts predict a rise.

For the selected models, the approximate unseen-stock paired MSE intervals versus the historical-mean baseline include zero at the daily and monthly horizons. The annual interval is positive, favoring the historical mean. This study does not demonstrate a reliable incremental forecasting edge sufficient to justify live-money deployment.

Nine automated tests passed. All 15 final models passed artifact checks for purged label boundaries, held-out company exclusion, identical test observations across feature families, native model reload, inverse target scaling, and latest-row inference. See verification.json.

Return RMSE is on log returns; lower is better. Price MAPE is mean absolute percentage error relative to realized adjusted price. Direction is up/down sign accuracy, not percentage price accuracy. For unseen companies the stock-mean baseline falls back to the training-universe mean. Annual daily-origin outcomes overlap strongly.

## All predefined feature families

| Sessions | Family | Features | Validation RMSE | Unseen direction | Unseen RMSE | Unseen zero RMSE |
|---|---|---:|---:|---:|---:|---:|
| 1 | core | 5 | 0.019074 | 51.01% | 0.016503 | 0.016523 |
| 1 | statistics_dividends | 11 | 0.019082 | 51.03% | 0.016603 | 0.016523 |
| 1 | original | 18 | 0.019082 | 50.90% | 0.016514 | 0.016523 |
| 1 | statistics_mode | 9 | 0.019083 | 51.01% | 0.016513 | 0.016523 |
| 1 | statistics | 8 | 0.019083 | 51.03% | 0.016512 | 0.016523 |
| 21 | original | 18 | 0.086233 | 56.01% | 0.075174 | 0.076437 |
| 21 | statistics_mode | 9 | 0.086242 | 56.01% | 0.075183 | 0.076437 |
| 21 | statistics | 8 | 0.086243 | 56.01% | 0.075183 | 0.076437 |
| 21 | statistics_dividends | 11 | 0.086244 | 56.01% | 0.075176 | 0.076437 |
| 21 | core | 5 | 0.086248 | 56.01% | 0.075183 | 0.076437 |
| 252 | original | 18 | 0.257417 | 73.25% | 0.255006 | 0.301550 |
| 252 | statistics_mode | 9 | 0.259570 | 73.25% | 0.251577 | 0.301550 |
| 252 | statistics | 8 | 0.259808 | 73.25% | 0.252030 | 0.301550 |
| 252 | core | 5 | 0.259848 | 73.25% | 0.252692 | 0.301550 |
| 252 | statistics_dividends | 11 | 0.263373 | 73.25% | 0.251497 | 0.301550 |

## What was tested

- Core: 1/21/63-session returns and 21/63-session volatility (5 inputs).
- Statistics: 21/63-session returns and rolling return mean, median, standard deviation (8 inputs).
- Statistics plus a fixed-bin return mode (9 inputs). The mode uses fixed 10-basis-point bins with deterministic ties.
- Statistics plus mode and trailing 365-calendar-day realized dividend yield/event count (11 inputs). Yield uses raw price and cash dividends on the same vendor share basis.
- Original technical feature control (18 inputs), under the same sample, search budget, and evaluation rules.

Every family uses the same 253-session warmup, common eligible dates, identical 16 parameter candidates, and three purged chronological validation folds. Parameter candidates also test full history versus a trailing ten-year training window. Labels are standardized using each fold’s training mean and standard deviation; inverse scaling is saved for inference. Family and parameter selection use macro-stock validation RMSE, not test direction accuracy. This differs from v1, so changes cannot be attributed to feature count alone.

## P/E: implemented, not empirically tested

No verified historical EPS publication records were available in this dataset. The saved fundamental_coverage_audit.json shows Reliance quarterly snapshot periods only in 2025–2026 and annual periods in 2022–2026, without as-published historical release records. Current P/E and current financial snapshots were not copied backward. The optional statistics_fundamentals family supports trailing P/E and earnings yield using timestamped EPS releases. Its importer requires available_at with timezone, period_end, eps_ttm, source, currency=INR, and share_basis=matches_raw_close. It joins only data published by 15:30 IST on the prediction date, masks stale EPS, and leaves nonpositive-earnings P/E undefined. EPS must be consolidated TTM and aligned with the raw price share basis; an exchange filing archive or a suitable historical data provider is needed to populate it. A schema is not evidence that P/E improves prediction.

## Real-market assessment

XGBoost is a reasonable tabular benchmark for nonlinear interactions, but this study cannot establish a maximum achievable accuracy or guarantee profitable forecasting. Redundant means and momentum can add little new information, and volatility primarily describes uncertainty rather than the expected direction. Dividend yield and earnings yield are testable hypotheses, not automatic sources of an edge.

Judge models against both drift/unchanged-price baselines and uncertainty intervals in uncertainty.json. Check yearly and per-stock stability in each report, the nonoverlapping diagnostics, and positive-prediction fractions. An always-positive model must not be presented as evidence of market timing skill. There are only five entirely held-out companies and a small number of independent annual periods.

Before risking real money, freeze the selected model, record predictions prospectively, and compare with the same baselines. Daily/monthly paper tests can mature sooner; annual labels require a full year. A tradable strategy additionally needs next-session executable prices, spread, slippage, fees/taxes, liquidity, position limits, turnover and drawdown analysis. No live trading or profitability backtest was performed here.

The next informative inputs are point-in-time earnings/valuation and market/sector context, with a universe including delisted companies. Compare a regularized linear baseline and other algorithms on exactly the same frozen protocol before adding model complexity. A later Monte Carlo stage must calibrate its ranges on held-out outcomes; simulations cannot repair an uninformative mean forecast.

Sources: [XGBoost parameter documentation](https://xgboost.readthedocs.io/en/stable/parameter.html), [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html), [NSE financial results with broadcast timestamps](https://www.nseindia.com/companies-listing/corporate-filings-financial-results).
