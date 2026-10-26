# NightEye

The follow-up study with smaller statistical feature sets, 40 stocks, historical dividends, and a point-in-time valuation importer is documented in [RESEARCH_V2.md](RESEARCH_V2.md). Its measurements are in [RESULTS_REDUCED.md](RESULTS_REDUCED.md). The original study below remains a separate reference.

Direct-horizon stock return forecasting with XGBoost. Predictions use daily OHLCV available **after the current market close**. Models predict cumulative log return over a specified number of future trading sessions, then convert it to an adjusted price. No Monte Carlo simulation is included.

## Run

The existing working environment on this machine is `C:/Users/Siddhant/miniconda3/envs/NightEye/python.exe`. Use it in place of `python` below if your shell points to a different Python installation.

```powershell
python -m pip install -r requirements.txt
python -m src.fetch_data
python main.py --horizons 1 21 252 --trials 24 --test-start 2021-01-01 --output artifacts/my_experiment
python -m unittest discover -s tests -v
python -m src.summarize
python -m src.XGBoost.predict --model artifacts/my_experiment/h21/model.joblib --history data/RELIANCE.NS_2000-01-01_to_2026-10-27.csv
```

Output directories are never overwritten. Choose a new experiment name for each run. CSV paths are resolved from the repository root by default, so training also works from another working directory. `environment.lock.txt` records the packages used for the completed experiments; `requirements.txt` contains portable direct dependencies rather than machine-specific build paths.

The downloader fetches 15 Indian stocks across sectors from 2000 through the exclusive end date 2026-10-27. Supply `--tickers`, `--start`, `--end`, and `--output-dir` to change this. The download manifest records failures and adjustment settings; training reports include SHA256 hashes, dates, and row counts for the actual input files. The longest cached CSV for each ticker is selected to avoid duplicating overlapping histories. Use a separate data directory when you want to freeze a particular snapshot. Custom CSV names must begin with the ticker followed by an underscore and must contain Date, Open, High, Low, Close, Volume. Do not mix raw and adjusted OHLC in one file.

```powershell
# Unseen-company evaluation: these tickers are excluded from ALL training and tuning.
python main.py --holdout-tickers TCS.NS MARUTI.NS --trials 12 --test-start 2021-01-01 --output artifacts/my_holdout
# Explore the original 18 features.
python main.py --original-features --trials 12 --test-start 2021-01-01 --output artifacts/my_original
# Train a custom direct horizon (approximately 3 trading months).
python main.py --horizons 63 --trials 24 --output artifacts/my_quarter
```

## Training and evaluation

Features are calculated separately for every ticker, before pooling. Absolute prices, raw volume, and ticker IDs are excluded, making the inputs usable across different price scales. The 18 original momentum, volatility, trend, range, volume, ATR, and RSI features are retained. The expanded set adds longer momentum and downside volatility, opening gap, closing location, log volume change, volatility regime, annual high/low distance, and normalized EMA spread (35 features total). These are hypotheses to validate, not guaranteed improvements. Flat-price RSI is fixed at 50; no-loss rising prices retain RSI 100. Rolling windows never look forward or fill with future observations.

There is a separate target and model for each horizon: `log(close[t+h] / close[t])`. A month is approximated by 21 sessions and a year by 252 sessions, not exact calendar dates. Training requires at least 253 historical sessions for extended features, plus enough future observations to label that horizon. Inference keeps the latest row and never requires future labels.

Three expanding chronological validation folds select hyperparameters by average per-stock return RMSE. All ticker observations share date boundaries. A training row is excluded whenever its **target date** reaches the validation/test boundary, including the 252-session forecast. Validation labels crossing the next fold boundary are also excluded. Early stopping uses only the current validation fold. The median selected tree count is used when fitting the final evaluation model on all development rows; the test set is evaluated afterwards. Training weights give each ticker equal total weight.

Reports compare with zero return (unchanged price), development-set historical mean, and historical median. They include return MAE/RMSE/R2 and direction accuracy, adjusted-price MAPE, per-stock and yearly results, and a nonoverlapping-origin diagnostic. The summary also shows the always-up direction baseline and approximate moving-block bootstrap intervals against the mean baseline. Price errors in rupees should be compared within a stock; pooled rupee MAE mixes price scales. Overlapping month/year labels make ordinary independent-sample confidence intervals inappropriate. The bootstrap is approximate and does not solve regime shifts.

Each horizon saves `model.ubj`, `model.joblib`, `report.json`, `test_predictions.csv`, and `feature_importance.csv`. Load only trusted local joblib files. The saved model is an evaluation model trained strictly before the test period, not a model refitted through today's data. Future production refitting must preserve the benchmark and use only labels already observed at the refit date.

## Findings and limits

See [RESULTS.md](RESULTS.md) for completed measurements. A 52% direction score is not 52% price accuracy. A model must beat reasonable baselines on the relevant horizon and unseen data; more indicators, more stocks, or more parameter trials do not ensure this. No finite search proves the maximum possible XGBoost performance.

The universe contains surviving large Indian companies and therefore has selection/survivorship bias. These experiments do not establish a universal stock model. Yahoo's adjusted series incorporate corporate actions and may be revised; they are not point-in-time archives. Adjusted-price outputs are not literal future quoted market prices when dividends/splits occur. Data quality and licensing need separate review for deployment. For a stronger research benchmark, acquire point-in-time histories including delistings, market/sector context, fundamentals with publication timestamps, and a genuinely future evaluation period. Do not repeatedly tune against the reported 2021 onward test results. Trading profitability would require a separate evaluation with costs and execution timing.

The old `src/XGBoost/train.py`, `data_split.py`, and `model_report.py` and their Reliance artifacts remain as the original one-day reference. The active entry point is `main.py` → `src/pipeline.py`; inference is `python -m src.XGBoost.predict`. The old scripts do not implement the new tuning/evaluation protocol.

Implementation follows the official [XGBoost estimator documentation](https://xgboost.readthedocs.io/en/stable/python/sklearn_estimator.html) for validation-based early stopping and the chronological evaluation principle described in [scikit-learn's TimeSeriesSplit documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html). Date/target-date purging is implemented explicitly for pooled stock panels.
