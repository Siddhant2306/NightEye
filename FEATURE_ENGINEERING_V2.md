# Feature engineering v2

The follow-up [failure review](artifacts/analysis/feature_v2_failure_review/VERDICT_AND_FIXES.md) diagnoses the full-universe baseline failure, probability calibration shift, annual lower-tail misses and company/regime dependence. Future v2 fits now gate probability calibration on a purged chronological check inside the pre-test calibration block. Existing frozen models and reports remain unchanged; resuming the completed study does not retrofit this fix. The guard does not certify raw probabilities or improve point forecasts by itself.

The isolated study is in `artifacts/forecasting/feature_engineering_v2`. Open its `index.html` for comparisons, learning curves and historical forecast errors; `FINAL_REPORT.md` answers the research questions; `forecasts/index.html` shows Reliance Monte Carlo paths and downloadable forecasts. Each forecast also saves JSON, sample path CSV, PNG and SVG.

## Completed run findings

The bounded search evaluated 153 non-alias configurations across the three algorithms/horizons, using two past-only folds. All nine saved-model audits and 59 automated tests passed. XGBoost retained F0 for both tasks at every horizon. On the five held-out companies, LSTM monthly return RMSE improved from 0.06717 to 0.06518, while annual RMSE worsened from 0.13401 to 0.14488. These are log-return errors, not percentage price accuracy. Final results are retained even when worse.

Annual held-out direction accuracy of about 86.5% came with 50% balanced accuracy: these classifiers predicted UP throughout that bullish sample. Full-test annual nominal 80% interval coverage was only 51.6% (XGBoost), 49.6% (LightGBM) and 38.0% (LSTM). The monthly backtested strategies lost money after costs. No general directional edge or reliable annual probability range was established. The next research priority is interval calibration across regimes and a genuinely prospective evaluation, with the frozen benchmark retained.

## Commands (PowerShell, from the repository)

```powershell
conda activate NightEye
# Open completed results without retraining
Start-Process .\artifacts\forecasting\feature_engineering_v2\index.html
Start-Process .\artifacts\forecasting\feature_engineering_v2\forecasts\index.html
# Resume the same frozen experiment, including fresh market snapshot and paper records
python -m src.feature_engineering_v2.run --resume --market --workers 3
# Run a new independent study (expensive; do not overwrite the existing one)
python -m src.feature_engineering_v2.run --output artifacts/forecasting/feature_engineering_v2_new --market --workers 3
# Audit the completed study
python -m src.feature_engineering_v2.verify
```

`--resume` reuses completed configurations; it does not repeatedly fit identical models to create more information. A saved market snapshot is immutable. For a later as-of date, fetch a new snapshot and write forecasts/journal to new directories:

```powershell
python -m src.feature_engineering_v2.market --experiment artifacts/forecasting/feature_engineering_v2 --output artifacts/market/v2_next_snapshot
python -m src.feature_engineering_v2.forecast --experiment artifacts/forecasting/feature_engineering_v2 --snapshot artifacts/market/v2_next_snapshot --output artifacts/market/v2_next_forecasts
python -m src.forecasting.paper record --experiments artifacts/forecasting/feature_engineering_v2 --snapshot artifacts/market/v2_next_snapshot --journal artifacts/forecasting/feature_engineering_v2/paper_journal_v2
```

## What is trained

Three algorithms (XGBoost, LightGBM and LSTM), three horizons (1, 21 and 252 trading sessions), and separate return/direction heads are compared. The target is forward log return. Predicted adjusted price is current adjusted close multiplied by the exponential of predicted return. UP means a strictly positive return, not a percentage price accuracy.

All 40 original stock histories, company holdouts, date boundaries and final-test observation keys are retained. Five entire companies are excluded from training, tuning, calibration and peer-rank reference sets. Two expanding validation folds purge targets crossing boundaries. A separate calibration block precedes the final chronological test. Every algorithm/task/horizon choice is frozen before this study reads test labels. The historical test was already used in earlier research; prospective paper outcomes are stronger evidence.

F0 uses the existing selected input schema. F1–F7 test marginal feature families, F8 combines families, and F9 combines up to three families that improved both folds. W0 continues compatible saved weights. Native trees test bounded regularization variants. LSTM tests 20/60/120-session windows, 16/32/64 hidden units, bounded optimization variants and 20/40/60 epoch ceilings with early stopping. Longer ceilings reuse an identical naturally stopped fit. Return RMSE and direction log loss choose separate checkpoints. The stable selection rule rejects material one-fold deterioration and favors fewer features among near ties. Configuration records retain absolute minima too.

Existing tree weights are reused only with matching features, target scaling and compatible checkpoints. Fold continuation starts from past-only fold models, never a model trained beyond validation. New feature schemas require fresh fits. LSTM compatible fine-tuning reuses weights/scalers but resets AdamW because the previous optimizer state was not saved. Epochs apply to LSTM; tree boosting rounds are the analogous bounded training iterations.

## Features and availability

`feature_registry.json` documents formulas, lookbacks, source, availability and missing-data rules. Families include normalized momentum/trend/drawdown; volatility/range/gap/tails; RSI/MACD/stochastic/Bollinger/ADX; relative volume/flow; lagged market/sector risk and trend; cross-sectional ranks; and existing as-published fundamentals/dividends. Calendar features are tested in the full combination. Equivalent columns are deduplicated. Absolute price, ticker identity, hindsight financials, unavailable insider/news data and a return mode are not added as shortcuts.

Inputs are available after the origin session closes. Context uses its publication/as-of timing. Training medians/scalers are fitted only on training observations. Cross ranks use eligible reference-company observations on the same date; held-out firms never influence the reference distribution. If selected ranks are needed at inference, current eligible peers and sector context are required; stale peer data fails closed. The live builder is checked against cached feature values and future-prefix invariance.

## Uncertainty, backtests and limits

Monte Carlo endpoints use held-out calibration residuals scaled by current risk; historical residual bridges create scenario paths. Bands summarize these conditional scenarios. They do not establish a true future probability, capture every crash or guarantee nominal coverage. Inspect interval coverage together with width, particularly at 252 sessions where overlapping labels provide few independent outcomes. These are adjusted-price scenarios, not guaranteed future quoted prices.

Backtests retain the existing strategy: next-open execution, long/cash thresholds, fixed costs/slippage, explicit final-open liquidation, equal-initial-capital company accounts and fractional adjusted units. No configuration is selected using test returns. This is research/paper tracking, with no broker orders.

The final evaluation model remains fitted before the test period; it is not silently refitted through today. Fresh forecasts apply that historical model to current inputs and warn about age/reliability. More features, rounds, epochs or data do not guarantee gains. The study cannot prove a maximum attainable accuracy or a universal market edge. The original data, artifacts and nine paper records are hash-protected.

## Code map

`prepare` freezes sources/protocol and separates development from evaluation labels. `features` creates causal inputs. `develop` performs resumable fold ablations and bounded tuning. `models` handles fitting, early stopping and safe continuation. `finalize` freezes choices, fits selected models, calibrates and evaluates. `inference` aligns separate-head schemas/windows. `report`, `importance` and `conclusions` create comparisons and charts. `market` obtains isolated current sources; `forecast` produces Monte Carlo outputs. `verify` audits hashes, observation keys, preprocessing and inference parity. `run` orchestrates these stages and writes logs.
