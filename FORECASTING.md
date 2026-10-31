# Return, direction and Monte Carlo experiments

This is an additional, versioned pipeline for **both XGBoost and LightGBM**. Existing implementations and benchmark artifacts remain unchanged. Active linear regression remains removed. Run from `C:\Users\Siddhant\NightEye` in PowerShell.

## Train and test

```powershell
$py = 'C:/Users/Siddhant/miniconda3/envs/NightEye/python.exe'
& $py -m src.forecasting.train --trials 3 --max-rounds 500 --output artifacts/forecasting/my_run
```

This trains and tests both algorithms, all three horizons (1, 21, 252 trading sessions), return regressors and direction classifiers, and two feature families. A fresh output directory is required. It uses existing frozen data; no new market data is downloaded. The initial reference run is `artifacts/forecasting/experiment_v1`; the broader eight-configuration run is `artifacts/forecasting/intensive_v1`.

For a larger **new experiment**, with the same validation rules:

```powershell
& $py -m src.forecasting.train --trials 8 --epochs 1000 --patience 50 --output artifacts/forecasting/intensive_run
```

`--epochs` is an alias for `--max-rounds`: boosting iterations/trees, **not** repeated fresh fits or neural-network epochs. Early stopping can select substantially fewer rounds. More rounds are not guaranteed to help. Search is bounded to 1..16 configurations per feature family/task/algorithm. Default 3 trials means 144 validation fits across the entire experiment plus final models. Eight trials means 384 validation fits plus final models. A repeat on the same data/seed does not accumulate knowledge.

Optional: `--horizons 21`, `--algorithms xgboost`, `--signal-threshold 0.60`, `--data-dir`, `--context-dir`. Choose any threshold before looking at final-test results.

## Exactly what 80/20 means

All stocks share chronological boundaries calculated from unique eligible daily origin dates, never random rows. The final 20% is the test block. The first 80% is development, divided as follows:

```text
0%                 40%        52%        64%              80%           100%
| expanding model fitting / validation | calibration     | final test   |
                     fold 1    fold 2
```

Fold 1 fits before 40% and validates on 40..52%; fold 2 fits before 52% and validates on 52..64%. Feature family and configuration are selected by average macro-stock validation loss. Median validation best rounds set the final fitting length. The final estimator fits eligible observations before 64%, not on the calibration/test blocks.

64..80% fits a logistic probability calibrator and the empirical return-residual distribution. These observations never fit the underlying boosted models. This is ordinary probability calibration, not another linear stock-price regression algorithm. Direction thresholds are predeclared (default UP >= .60, NOT_UP <= .40, otherwise NO_SIGNAL); they are not optimized on test or calibration performance.

Every fit/validation/calibration block drops labels whose future target date reaches the next boundary. This is particularly important at 252 sessions. Therefore final row counts are not exactly 80/20 after purging and removal of unavailable future labels. Boundaries are identical for all horizons, derived including recent rows with labels not yet available. No additional embargo is used because only past training observations are allowed and overlapping labels are strictly purged.

ASIANPAINT, BAJFINANCE, NTPC, TITAN and COALINDIA are excluded from **all fitting, tuning and calibration**. Test reports show both those unseen companies and the other companies. The dataset has 40 stocks, starting eligible origins in 2017. It is a retrospective, repeatedly studied dataset, not an untouched prospective holdout.

## Features from the supplied image

`existing`: the old chosen feature definition (daily five price features; monthly/annual 37 price/context features), freshly retrained on the new boundaries. This does not reuse incompatible historical predictions.

`technical_context`: existing price/market/sector/valuation/published financial context plus 28 normalized technical features: log momentum at 1/5/21/63 sessions; volatility at 5/10/20/30/63; distance to MA10/20/30 and EMA10/30; RSI14; normalized MACD and signal; Bollinger z-score/width; relative volume; log-volume change; normalized OBV pressure; overnight gap; intraday range/return; weekday and cyclic month.

Raw YesterdayClose, MA and OBV levels are not used because their scales differ by stock. A fixed logarithmic volume change avoids applying a price-return formula to volume. MA ratios and normalized OBV express comparable quantities. After-close forecasts may use the just-completed session. They cannot be advertised as pre-close forecasts.

No insider transactions, news sentiment or article counts are invented: timestamped historical sources are absent. No unsafe current company P/E is backfilled. Existing fundamental/context publication lags and missing-data handling are reused. Features never include future prices or target dates. Missing contextual features remain NaN for native tree handling.

The feature test is controlled: identical rows, dates, algorithms and configurations for both families. Features are retained only by validation loss. More features do not necessarily improve the final test.

## Model outputs and metrics

Return model: squared-error regression on training-only standardized cumulative log returns. Convert using `adjusted_close * exp(predicted_log_return)`.

Direction model: binary log loss, UP if cumulative log return > 0; NOT_UP includes flat outcomes. Selection uses macro-stock validation log loss rather than inflated majority-class accuracy. Later logistic calibration uses no test observations. There is no automatic class weighting: changing prevalence weights can distort probability estimates.

The seeded search varies depth (1..4), learning rate (.015/.03/.05), row sampling (.65/.8/1), L2 regularization (1/10/30/100), and a minimum-leaf setting (30/75/150). That leaf setting maps to XGBoost's minimum child Hessian weight and LightGBM's minimum child sample count; these are different units, so shared parameter values do not imply identical tree complexity. Feature sampling is .8, L1 is .1, seed is 42, and CPU threads are limited to four.

Reports include MAE/RMSE/R², price MAPE, macro-stock error, pooled correlations, return-sign direction, classifier accuracy/balanced accuracy, UP precision/recall, NOT_UP recall, Brier/log loss, reliability bins, selective signal precision and coverage. Always-UP, unchanged-price, training-mean return and constant training-UP-probability baselines are included. A separate control is the existing feature set with the first conservative configuration, on identical new splits.

Probabilities near .5 can yield NO_SIGNAL. Undefined UP precision means zero UP signals, not 100% precision. A high UP precision alongside low coverage/NOT_UP recall can be unhelpful. Negative R² and tiny differences from naive baselines must be reported. Final-test metrics never pick the preferred algorithm; `selected.json` uses validation only.

Approximate paired date-block uncertainty versus the matched control is saved. Strongly overlapping annual outcomes are not independent rows. A confidence interval is withheld when fewer than two horizon-sized origin-date blocks exist. This protocol does not prove a maximum achievable accuracy or live trading profitability.

## Monte Carlo and forecast output

First choose a completed model, then supply supported stock history:

```powershell
$run = 'artifacts/forecasting/experiment_v1'
$history = 'data/research_v2/RELIANCE.NS_2000-01-01_to_2026-10-27.csv'
& $py -m src.forecasting.predict --model "$run/h21/lightgbm/model.joblib" --history $history --ticker RELIANCE.NS --paths 5000 --output artifacts/forecasting/reliance_monthly
```

Replace `h21` with `h1` or `h252`, and `lightgbm` with `xgboost`. Each forecast output directory must be new. Models are trusted local joblib files only. Other tickers need eligible OHLCV and a configured historical sector/context mapping; this is not arbitrary ticker coverage. Update context together with stock history. The existing cached data ends 2026-10-23; a filename ending 2026-10-27 does not imply newer observations.

For **all six models in one command**, including an overview page:

```powershell
& $py -m src.forecasting.batch_predict --experiment artifacts/forecasting/intensive_v1 --history $history --ticker RELIANCE.NS --paths 5000 --output artifacts/forecasting/my_stock_overview
Start-Process artifacts/forecasting/my_stock_overview/index.html
```

Each forecast embeds historical diagnostics for its company group (seen or excluded from training), plus all-stock interval coverage. It displays warnings if direction skill is absent, probability scoring fails the naive baseline, interval coverage is poor, or independent long-horizon evidence is insufficient. A numerical probability is not automatically a trustworthy confidence estimate. Inspect both seen/unseen and all-stock results: a favorable subset can hide severe undercoverage elsewhere.

The output includes adjusted-price point estimate, percentage return, classifier P(UP), UP/NOT_UP/NO_SIGNAL, 50/80/95% empirical price intervals, Monte Carlo terminal quantiles, scenario frequency of UP and a loss exceeding 10%, and illustrative paths/drawdowns. The classifier probability and Monte Carlo frequency are different estimators; disagreement is exposed.

For endpoints, sample the out-of-fit calibration residual `(actual_log_return - predicted_log_return) / historical_risk_scale`, then rescale by current volatility times sqrt(horizon). Five-session block-bootstrap daily returns form bridges conditioned on those endpoints. The residual mean is retained, so the simulation median may differ from the regressor point estimate. Endpoints are sampled empirically, not forced to follow a Gaussian distribution. Finite samples cannot represent every unseen crash or regime.

Nominal 50/80/95% endpoint coverage is measured on final-test outcomes, separately for seen/unseen companies. It is **empirical coverage, without an IID/conformal guarantee**. Good coverage alone is insufficient: very wide intervals can cover everything. Path bridges, intra-horizon bands and drawdowns are illustrative and are not calibrated maximum-loss forecasts. More simulation paths reduce sampling noise; they do not improve the underlying prediction.

Forecast files:

- `forecast.json`: complete machine-readable result and limitations.
- `forecast.html`: offline visual report; open in a browser.
- `path_quantiles.csv`: per-session scenario percentiles.
- `sample_paths.csv`: first 100 illustrative paths.

These are historical evaluation models, not production models fitted through today. Latest input date, latest fit label and latest calibration label are disclosed. Vendor-adjusted prices are not guaranteed future exchange quotes.

## Inspect, reproduce and test

```powershell
& $py -m src.forecasting.report --directory $run
& $py -m src.forecasting.verify --directory $run
& $py -m unittest discover -s tests -v
```

Experiment files: `protocol.json` (frozen settings/date/source hashes); `summary.csv`; `selected.json`; `comparison.md` and `comparison.html`; `verification.json`; and per-horizon/algorithm `model.joblib`, `selection.json` (all trials/fold losses/learning curves), `metrics.json`, `per_stock.csv`, `test_predictions.csv`. Model save/reload predictions are checked over the full test panel. Old XGBoost source/artifact hashes and price/context hashes must remain unchanged.

Code: `features.py` indicators; `protocol.py` splits/purging; `models.py` both algorithm adapters/calibration/precision; `train.py` orchestration and controlled search; `uncertainty.py` residual intervals and simulation; `predict.py` JSON/HTML output; `batch_predict.py` all-model overview; `report.py` comparison; `verify.py` independent source/split/prediction reconstruction.

Official background: [LightGBM early stopping](https://lightgbm.readthedocs.io/en/stable/Python-Intro.html#early-stopping), [chronological validation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html), [probability calibration](https://scikit-learn.org/stable/modules/calibration.html).
