# LSTM and market-testing results — 1 November 2026

Implemented and ran a PyTorch LSTM baseline, connected its forecasts to the Monte Carlo output, added a cost-aware historical strategy backtest, and initialized an actual fresh-data prospective forecast journal. No brokerage account or real order execution is involved.

## LSTM experiment

Completed run: `artifacts/forecasting/lstm_sequence_v1`. A single unidirectional LSTM layer with 16 hidden units takes 20 historical sessions, with return/direction output heads. Input median imputation/scaling and target scaling use training data only; missingness masks are additional channels. The joint loss is standardized return MSE plus 0.25 binary cross entropy. Dropout, AdamW, gradient clipping and validation early stopping are used.

One predeclared architecture was tested across two purged folds for each of three horizons: **six validation fits and three final fits**. The ceiling was eight epochs, patience three. The median validation best epoch selected **one final epoch for each horizon**; later epochs generally overfit. This is an initial baseline, not extensive architecture optimization or a claim about maximum LSTM accuracy. A second architecture and longer runs are supported by the CLI.

The reference is `artifacts/forecasting/intensive_v1`: same frozen 40-stock data, five excluded companies, chronological date boundaries, calibration period and **exact final-test observation keys**. Initial sequence warmup removes the first 19 eligible training dates per stock. The family is fixed to the existing features, five daily and 37 monthly/annual. Return and direction share the LSTM encoder; they optimize a joint objective and can disagree. Monte Carlo uses this model's own later, out-of-fit residual bank.

### Unseen-company prediction error

Lower cumulative log-return RMSE is better:

| Trading sessions | XGBoost | LightGBM | LSTM |
|---|---|---|---|
| 1 | 0.014887 | 0.014887 | 0.014863 |
| 21 | 0.065444 | 0.064539 | 0.067169 |
| 252 | 0.125376 | 0.126992 | 0.134015 |

Daily LSTM is essentially tied with the unchanged-price baseline, whose RMSE is 0.014863423. The tiny error difference is not established useful prediction skill. Monthly LSTM is about 4.1% worse than LightGBM on this test; annual is about 6.9% worse than XGBoost. These comparisons use the previously validated tree selections, not a new selection based on this final test.

LSTM's return-sign direction accuracy is **50.79%, 46.36%, 85.43%** on unseen companies for 1/21/252 sessions. Its calibrated classifiers give **49.67%, 50.87%, 86.47%**, matching always-UP, with **50% balanced accuracy**. High annual accuracy is not evidence of detecting declines. Probabilities remain experimental; probability calibration fails to generalize broadly across regimes/companies.

### Monte Carlo coverage

LSTM nominal 80% endpoint intervals cover **80.08%, 80.26%, 75.43%** of unseen-company outcomes, but **79.44%, 78.47%, 50.62%** when all test companies are pooled. Annual uncertainty is seriously under-calibrated across the universe. Annual calibration and test windows contain few independent overlapping outcomes. Simulation paths/drawdowns are illustrative, and high simulated UP frequencies are not validated confidence.

Model save/reload and full test predictions, probability outputs, residual banks and interval endpoints were independently reproduced. All 94 protected original source/reference files, price sources and frozen context remain unchanged. See `verification_lstm_v1.log` and the experiment's `verification.json`.

## Historical strategy backtest

Final corrected report: `artifacts/backtests/all_algorithms_v2/report.html`.

The study runs from **7 November 2024 through 23 October 2026**, on all 40 companies. Values below are **total returns over that entire period**, not daily/monthly/yearly returns. The horizon identifies the forecast/holding rule.

| Forecast horizon | XGBoost strategy | LightGBM strategy | LSTM strategy |
|---|---|---|---|
| 1 session | 0.00% | +0.23% | 0.00% |
| 21 sessions | −6.17% | −7.96% | −0.45% |
| 252 sessions | −1.97% | −1.97% | −1.97% |

The equal-initial-capital buy-and-hold benchmark returns **−1.68%**, and cash returns 0% with no interest modeled. LSTM's monthly strategy loses less than the tree strategies and buy-and-hold in this particular period, but this does not establish a persistent edge. Its monthly price forecasts are less accurate, illustrating that forecast error and a strategy's exposure/costs are different quantities.

Rules: long/cash only; P(UP)>=0.60 and predicted return>0; after-close signal enters the next open; exit after H sessions at an open. Equal initial capital per stock account, non-overlapping positions, fractional adjusted-price units, no leverage. Entry/exit each charge **10 basis points assumed cost + 5 basis points slippage**. The benchmark pays the same assumptions. No taxes, integer lots, cash interest, liquidity constraints or market impact are included. Adjusted OHLCV provide a total-return proxy, not literal executable share/dividend accounting.

All eligible test-origin features generate signals, **including origins without available future labels**. Final-date open liquidation is explicit, with truncated trades flagged. This prevents an artificial cash period at the end of the annual study. Earlier preliminary `trees_v1` and `all_algorithms_v1` reports used only matured-label rows and should not be used; the corrected v2 results above supersede them.

Daily XGBoost/LSTM never pass the confidence/return entry rule and therefore stay in cash. Daily LightGBM makes only **eight trades**, with average invested exposure about 0.04%; its small positive return and high descriptive Sharpe do not demonstrate broad skill. Monthly trade counts: XGBoost 886, LightGBM 920, LSTM 713. Annual: 80 trades per algorithm, **40 truncated at the final date**; there is very little independent annual evidence.

The execution audit independently checks all nine strategy runs: source/context hashes, matching signal keys, next-open entries, no overlap, exit timing, entry/exit prices, costs, capital compounding and reconstructed portfolio equity. See `artifacts/backtests/all_algorithms_v2/verification.json` and `backtest_verification_v2.log`. Repeatedly inspected historical data and fixed-rule simulations cannot establish live profitability.

## Actual market-data paper test initialized

Snapshot: `artifacts/market/reliance_snapshot_v1`, retrieved **1 November 2026 IST**. Timestamps in files use UTC. Yahoo/yfinance supplies OHLCV through the last completed session **30 October 2026**; official Nifty market/energy indices and market valuation were refreshed through that date. The model's publication lag uses eligible prior-session context dated 29 October. Latest adjusted Reliance close: approximately **₹1,164.90**. Copied as-published company financials remain the prior snapshot, with their age/missingness disclosed; they were not automatically updated.

Journal: `artifacts/market/paper_reliance/index.html`. **Nine immutable timestamped forecasts** were recorded: XGBoost, LightGBM and LSTM, each at 1/21/252 sessions. Model and snapshot hashes are retained. Re-running the record command preserves original prediction files and timestamps. New records require a recently retrieved, fresh EOD/context snapshot and must precede the next weekday opening; the conservative guard does not model exchange holidays.

All **nine outcomes are PENDING**, with **zero matured outcomes** and no measured prospective accuracy yet. Scores become available only after actual subsequent sessions occur. No future results have been fabricated, and no recurring job or broker order has been created. A fresh later snapshot can score the original forecasts without changing them; outcomes are grouped by algorithm/horizon and preserve mature records. Actual adjusted returns use one consistent new price basis, with historical adjustment revisions flagged.

Fresh-data LSTM examples as of 30 October: approximately ₹1,165.51 at one session, ₹1,162.34 at 21 sessions and ₹1,404.29 at 252 sessions. These are experimental point estimates, not recommendations or reliable probabilities. The monthly direction head says UP while its return estimate is slightly negative; the two objectives differ, and the strategy requires both entry conditions.

## Files and commands

- `src/LSTM/model.py`, `train.py`: true PyTorch LSTM, per-stock sequence construction, epoch training and shared-head inference.
- `src/forecasting/backtest.py`, `backtest_verify.py`: full-origin historical signals, cost-aware execution and independent ledger audit.
- `src/forecasting/market_data.py`, `paper.py`: isolated fresh snapshots, readiness checks, exclusive forecast recording, pending/matured scoring and journal page.
- Existing shared inference, reports and verification now support LSTM; existing tree model artifacts remain unchanged.
- `requirements-lstm.txt`, `environment-lstm.lock.txt`: optional dependency specification and exact tested environment (CPU PyTorch 2.15.0).
- Test suite: **48 tests**, including causal sequence windows/order, no stock mixing, training-only preprocessing, save/reload, execution/cost/end handling, stale data rejection and pending/late-record checks.

Full runnable commands and architecture: [LSTM_MARKET_TESTING.md](LSTM_MARKET_TESTING.md). Open `artifacts/forecasting/reliance_lstm_v1/index.html` for the cached-history LSTM Monte Carlo overview, and the journal above for fresh-data forecasts.
