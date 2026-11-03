# LSTM, historical backtests and prospective market paper tests

Run from `C:\Users\Siddhant\NightEye` in PowerShell. This adds LSTM alongside XGBoost and LightGBM. There is no broker integration or real-money order placement.

## Environment

```powershell
$py = 'C:/Users/Siddhant/miniconda3/envs/NightEye/python.exe'
& $py -m pip install -r requirements.txt
& $py -m pip install 'torch>=2.6,<3' --index-url https://download.pytorch.org/whl/cpu
```

PyTorch is optional for existing tree algorithms. `requirements-lstm.txt` is an alternative dependency list; the explicit CPU command avoids downloading unnecessary GPU components. The tested environment is recorded in `environment-lstm.lock.txt`.

## Train LSTM

```powershell
& $py -m src.LSTM.train --reference artifacts/forecasting/intensive_v1 --epochs 20 --patience 3 --lookback 20 --trials 1 --output artifacts/forecasting/my_lstm
```

Use a new output folder every time. The completed first run is `artifacts/forecasting/lstm_sequence_v1`, with an eight-epoch ceiling. `--horizons 21` restricts a run. `--trials 2` compares a second predeclared architecture using validation only. Maximum supported epochs: 200. More epochs or a larger network need not improve forecasting.

An LSTM consumes sequences of historical features, not one independent feature row. This implementation uses 20 past sessions by default, a single unidirectional layer (16 hidden units), dropout, and two output heads: standardized cumulative log return and an UP logit. The loss is standardized return MSE + 0.25 binary cross entropy. AdamW, gradient clipping and early stopping limit overfitting. Hidden state is reset for each window; windows never cross companies. Training mini-batches may shuffle complete past-only sequences; chronological dataset boundaries do not shuffle.

Training-only median imputation and standard-deviation scaling handle missing/context features; missingness masks are additional channels. Values are clipped to +/-10 normalized units by a fixed rule. The feature family is the existing tree definition (daily 5 features; monthly/annual 37); this is a baseline LSTM experiment, not a large architecture/feature search. The first lookback-1 origin dates per stock are removed as warmup. This slightly changes training counts but **all final-test keys must match the reference exactly**.

Validation/calibration/test dates and complete company holdouts match the frozen reference. Configuration and checkpoints use the predeclared joint validation objective; final fitting uses the median validation best epoch. These are real neural-network epochs, unlike the boosting-round alias in the tree command. Separate later probability calibration and residual-bank estimation do not see final-test outcomes.

Each `h1/lstm`, `h21/lstm`, `h252/lstm` contains `model.joblib`, selection/epoch curves, test predictions and metrics. Model bundles contain explicit NumPy state arrays and architecture/scaling metadata; PyTorch networks are reconstructed at inference. Load only trusted artifacts. The return and direction heads share an encoder and weights; they are not independently optimized networks. The control is the frozen matched XGBoost control, not the LSTM itself.

`comparison_all_algorithms.csv` compares all three algorithms on the same test observations. No algorithm is selected from its favorable test results. Reused historical evaluation is not prospective evidence; the first LSTM baseline does not establish maximum achievable LSTM performance.

## LSTM forecasts and Monte Carlo

```powershell
$history = 'data/research_v2/RELIANCE.NS_2000-01-01_to_2026-10-27.csv'
& $py -m src.forecasting.batch_predict --experiment artifacts/forecasting/lstm_sequence_v1 --history $history --ticker RELIANCE.NS --paths 5000 --output artifacts/forecasting/my_lstm_forecast
Start-Process artifacts/forecasting/my_lstm_forecast/index.html
```

Or just one horizon:

```powershell
& $py -m src.forecasting.predict --model artifacts/forecasting/lstm_sequence_v1/h21/lstm/model.joblib --history $history --ticker RELIANCE.NS --paths 5000 --output artifacts/forecasting/my_lstm_monthly
```

Inference builds full historical sequences before selecting the last row. Monte Carlo uses LSTM's own out-of-fit calibration residual bank and current volatility, then the same empirical endpoint/bridge method as the tree experiments. Reports contain price/return estimates, classifier probabilities, signal/no-signal, 50/80/95% empirical intervals, scenario paths and historical reliability warnings. The return estimate and direction classifier can give different signals because they optimize different objectives; an UP classification does not guarantee a positive expected return. The backtest requires both conditions. Monte Carlo does not improve LSTM accuracy or guarantee interval/path coverage. Annual independent evidence remains limited. See [FORECASTING.md](FORECASTING.md) for all assumptions.

## Historical strategy backtest

```powershell
& $py -m src.forecasting.backtest --experiments artifacts/forecasting/intensive_v1 artifacts/forecasting/lstm_sequence_v1 --cost-bps 10 --slippage-bps 5 --output artifacts/backtests/my_comparison
Start-Process artifacts/backtests/my_comparison/report.html
```

For a particular stock, add `--tickers RELIANCE.NS`. Starting cash defaults to 100,000; change with `--initial-cash`. The final all-stock comparison is `artifacts/backtests/all_algorithms_v2`.

Rules are fixed before the backtest: long only when calibrated P(UP) >= the experiment's predeclared threshold and predicted return >0; otherwise hold cash. An after-close signal enters at the **next session's open** and exits at an open after H sessions. Positions do not overlap within a stock. Capital is split equally across independent stock accounts; idle accounts remain cash, each invested account compounds. No shorting, leverage, futures or options are modeled. Remaining positions are liquidated at the predeclared final session's open and marked as truncated in the trade ledger.

Signals are reconstructed from the frozen fitted models for **all eligible test dates, including dates whose future labels are not yet known**. Using only saved accuracy-evaluation rows would incorrectly remove the final 21/252 sessions of opportunities and leave the strategy in cash. Each run saves the actual signal panel. The earlier preliminary `trees_v1`/`all_algorithms_v1` runs used only matured forecast rows; use the corrected `all_algorithms_v2` report.

Default assumed per-side cost is 10 basis points plus 5 basis points of slippage, charged on entry and exit. The benchmark buys the same stocks at next open, holds to the final open, and pays the same costs. Files include portfolio/buy-and-hold/cash equity curves, trade ledgers, total return, CAGR, volatility, zero-risk-free Sharpe, drawdown, win rate, exposure and costs. Forecast-key hashes must match between algorithms; price-source hashes must match the frozen study.

Execution returns are open-to-open, whereas the predictive label is close-to-close. Adjusted OHLCV are a total-return proxy, not actual exchange quotes or literal share/dividend accounting. Fractional adjusted-price units are allowed; integer share/lot constraints are not modeled. There is no liquidity/market-impact, taxes, cash interest or exchange-specific fee model. Trade profitability is a different question from price/direction accuracy. Sparse annual trades and repeatedly inspected test data cannot establish a robust strategy. Do not tune thresholds/cost assumptions until a favorable backtest appears.

## Test on fresh market data: prospective paper forecasts

This workflow fetches public EOD data, freezes it, records predictions **before the next weekday session starts**, and scores them later when actual future sessions exist. It does not send orders or access a brokerage account. The next-weekday guard is conservative and may reject exchange holidays, because no exchange trading calendar is installed.

Step 1 — fetch a new snapshot:

```powershell
& $py -m src.forecasting.market_data --ticker RELIANCE.NS --output artifacts/market/reliance_today
```

This retrieves adjusted OHLCV and raw provider data from Yahoo via yfinance, copies historical context to the new snapshot and refreshes the market index, relevant sector index and market valuation from official Nifty endpoints. Frozen research files remain unchanged. Annual company financials are copied from the prior as-published snapshot, **not automatically refreshed**; their age/missingness remains visible to the features.

Partial bars are conservatively excluded until 17:00 IST. Snapshots older than 12 hours, stock bars more than five calendar days old, and prior-session context more than four calendar days old are rejected for new paper records. Provider/API failures produce an incomplete manifest and stop recording rather than silently substituting stale data. All source CSVs are hashed. Supported stocks require a configured sector/context mapping.

Step 2 — record all nine model/horizon forecasts:

```powershell
& $py -m src.forecasting.paper record --experiments artifacts/forecasting/intensive_v1 artifacts/forecasting/lstm_sequence_v1 --snapshot artifacts/market/reliance_today --journal artifacts/market/my_paper_journal --paths 2000
Start-Process artifacts/market/my_paper_journal/index.html
```

Predictions are written with exclusive creation, timestamps, model hashes and snapshot hashes. A duplicate model/stock/origin forecast keeps the first record and timestamp. This is an auditable local journal, not tamper-proof external notarization. It contains research reliability warnings and experimental simulation probabilities. It tests the frozen historical model prospectively; this is not an automatic production refit through today.

Step 3 — after future sessions close, fetch another **new** snapshot and score the original records:

```powershell
& $py -m src.forecasting.market_data --ticker RELIANCE.NS --output artifacts/market/reliance_later
& $py -m src.forecasting.paper score --snapshot artifacts/market/reliance_later --journal artifacts/market/my_paper_journal
Start-Process artifacts/market/my_paper_journal/index.html
```

One-session forecasts mature after one subsequent trading session; monthly after 21, annual after 252. Outcomes remain PENDING until those sessions exist. Scoring cannot manufacture future outcomes. Records created after their target session closed are invalid. `status.json`, `status.csv` and `group_summary.csv` show pending/matured results and metrics separately by algorithm/horizon. Actual returns use origin and target closes from the **same new adjusted series**, preserving consistency across corporate-action revisions; original forecasts are unchanged and revisions are flagged. Matured outcome files are preserved on later scoring runs.

As of **1 November 2026**, the first real-data snapshot is `artifacts/market/reliance_snapshot_v1`, with last completed bar **30 October 2026**, refreshed official context and an initialized journal at `artifacts/market/paper_reliance`. Forecast outcomes are pending; there is no measured live-market accuracy yet. Refresh and score manually after future sessions; no recurring job has been scheduled.

## Verify

```powershell
& $py -m src.forecasting.verify --directory artifacts/forecasting/lstm_sequence_v1
& $py -m src.forecasting.backtest_verify --directory artifacts/backtests/all_algorithms_v2 --experiments artifacts/forecasting/intensive_v1 artifacts/forecasting/lstm_sequence_v1
& $py -m unittest discover -s tests -v
```

Verification reconstructs full per-company sequences and purged splits and reproduces saved return/direction predictions, calibration residuals and intervals. Tests cover causal windows, stock boundaries, training-only preprocessing, reloads, next-open execution, non-overlap/costs, pending outcomes, corporate-action return consistency and rejection of late records.

Implementation: `src/LSTM/model.py`, `src/LSTM/train.py`, `src/forecasting/backtest.py`, `market_data.py`, `paper.py`; shared inference/report/verification adapters support LSTM. Official references: [PyTorch LSTM](https://docs.pytorch.org/docs/stable/generated/torch.nn.modules.rnn.LSTM.html), [reproducibility](https://docs.pytorch.org/docs/stable/notes/randomness.html). Seeds/deterministic CPU settings improve repeatability on this setup; they do not guarantee bit-for-bit results across framework versions/hardware.
