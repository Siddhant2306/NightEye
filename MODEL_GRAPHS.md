# Training, validation and test graphs

The completed chart collection is `artifacts/diagnostics/reliance_v1/index.html`. It covers XGBoost, LightGBM and LSTM, each at 1, 21 and 252 trading sessions, using Reliance as the example stock. Raw prices from different companies should not be concatenated onto a single price axis.

Each of the nine model/horizon pages contains:

1. **Training:** final saved return model evaluated on the actual rows used for fitting. This is in-sample and optimistic.
2. **Validation fold 1:** predictions from the earlier model fitted only before that fold, with target-date purging.
3. **Validation fold 2:** the second expanding past-only fold model.
4. **Calibration:** final return model on the separate later calibration block. These rows did not fit the return model, but were used to estimate uncertainty/probability calibration.
5. **Test:** the original saved model on held-out dates, reproducing saved test forecasts.
6. **Learning curves:** training and validation loss versus boosting rounds or LSTM epochs, with the chosen checkpoint marked.

There are **45 split figures, nine learning-curve figures and three all-model test comparisons**. Every figure has PNG and SVG versions. Each split has a forecast CSV; each learning curve has its loss CSV. `summary.csv` contains per-stock metrics, and `verification.json` records reconstruction/integrity checks.

## Read the charts correctly

Each split figure has three panels:

- Actual future adjusted price, predicted future adjusted price and the unchanged-price baseline.
- Actual and predicted percentage return over the model's horizon.
- Signed percentage price error: `100 * (predicted_price / actual_price - 1)`. Above zero means overprediction; below zero means underprediction.

**The x-axis is the target date**, when the future outcome becomes observable. For an origin t and horizon H, the plotted prediction is `adjusted_close[t] * exp(predicted_log_return[t,H])`; the actual value is the close at t+H. Plotting those at the origin date instead would misalign the future outcomes.

Price curves can appear close because all forecasts start from the observed price. The unchanged-price baseline and return/error panels expose whether the model predicts movements. In particular, a nearly flat predicted-return line can coexist with a price curve that tracks the stock closely.

Test charts show empirical 80% endpoint intervals estimated on the earlier calibration period. These are not guaranteed bounds; annual coverage is especially weak. No training/validation uncertainty bands are backfilled from later calibration outcomes.

Validation-fold models were not saved in the original experiments. The graph command reconstructs **only the selected settings**, not another parameter search. It verifies the original best checkpoints and fold validation losses. Applying the final estimator to earlier validation dates would be misleading because those dates later entered its training data. Reconstructed fold bundles are saved inside the new diagnostics folder; original models and experiment files are untouched.

Validation was used to choose settings, so it is not an untouched final test. Learning curves use all fitting companies, whereas price figures and their footer metrics refer to the selected stock. Tree return curves use log-return RMSE; direction curves use binary log loss. Native LightGBM training loss is stock weighted and its validation loss unweighted; XGBoost's displayed evaluation losses are unweighted. LSTM uses its stock-weighted joint loss (standardized return MSE + 0.25 binary cross entropy), with epoch training loss averaged during updates and validation loss measured afterward. These different loss scales should not be compared as if they were the same metric.

The historical labeled snapshot ends **23 October 2026**. Fresh market paper forecasts use a different snapshot and remain pending until actual outcomes occur. Graphs do not fabricate future prices.

## Run

From `C:\Users\Siddhant\NightEye` in PowerShell:

```powershell
$py = 'C:/Users/Siddhant/miniconda3/envs/NightEye/python.exe'
& $py -m pip install -r requirements-plots.txt

& $py -m src.forecasting.diagnostics --ticker RELIANCE.NS --output artifacts/diagnostics/my_reliance_graphs
Start-Process artifacts/diagnostics/my_reliance_graphs/index.html
```

The default experiments are the completed `intensive_v1` tree run and `lstm_sequence_v1`. PyTorch must be installed for LSTM; see `LSTM_MARKET_TESTING.md`. The plotting dependency already exists in this machine's working NightEye environment (Matplotlib 3.11.2).

For another stock, change `--ticker`, for example `TCS.NS`, and choose a new output folder. The stock must be in the frozen dataset. If the stock was completely excluded from training/validation, those panels explicitly show that exclusion instead of inventing in-sample results. Its genuine test chart is still generated.

To plot just tree models, set `--experiments artifacts/forecasting/intensive_v1`. The command reconstructs two validation folds per selected task and can take several minutes. It does not overwrite or retrain the saved final estimators.

To refresh the presentation after the underlying chart data has been generated, without fitting anything:

```powershell
& $py -m src.forecasting.diagnostics --output artifacts/diagnostics/reliance_v1 --render-only
```

Output data directories must be new except for this explicit rendering operation. Diagnostic fold models are trusted local joblib files. Charts are historical research diagnostics, not proof of a deployable market edge.
