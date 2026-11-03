# TCN and chronological stacking

Run from the repository root in the existing NightEye environment.

```powershell
conda activate NightEye
python -m src.forecasting.stacking.study
Start-Process .\artifacts\forecasting\tcn_stacking_v1\index.html
```

For separate training jobs, run the module with `--horizon 1`, `--horizon 21` or `--horizon 252`. After all three succeed, use `--evaluate`. Existing fold checkpoints resume in the same directory. Frozen selections are reloaded for evaluation. A new `--output` directory starts a separate experiment.

The study reads the frozen v2 caches used by the controlled repair study. It verifies the shared boundaries, company exclusions, source hashes and final observation keys. The three saved repair models appear as separate benchmarks. For OOF stacking, XGBoost, LightGBM and LSTM use predeclared refit configurations and the existing ten-input compact schema. Reusing their previously selected validation checkpoints would let OOF targets influence the base inputs to the stack.

For each outer fold, an earlier inner split controls checkpoint and TCN architecture selection. Training labels mature before inner validation starts. Inner validation labels mature before the outer prediction origin. The audit records both dates. The final base fits use the same procedure with the calibration boundary as their cutoff. The inner tail reduces the data available for fitting compared with some saved repair benchmarks.

The TCN uses two dilated, left-padded convolutions per residual block, ReLU, dropout and a two-output head at the latest position. Explicit left padding preserves sequence length. The three recipes use 20, 60 or 120 input sessions with effective receptive fields of 15, 61 and 61 sessions, respectively. AdamW, gradient clipping, train-only scaling and missing-value masks follow the existing neural conventions. Checkpoints store configuration, preprocessing, weights, losses and run duration.

Equal averaging needs no fitted weights. The learned mixtures and two stacks fit on earlier OOF predictions and choose regularization or tree count on later OOF predictions. Both sections must support at least two horizon-sized origin-date blocks and at least 42 dates. A failed support check leaves equal averages available and records the reason for omitting learned combinations. With two outer folds, the study omits the optional temporal meta-model.

The pre-test calibration section provides a separate probability calibration check and each method's volatility-scaled residual bank. The selected scenario models use OOF performance. The report labels the cached Reliance input date. The existing residual bootstrap and bridge implementation generates 5,000 paths per scenario. Coverage and widths are measured on matched historical outcomes, with weaker support at long horizons.

The backtest calls the existing long/cash strategy directly. It admits every eligible test origin, including origins with no mature return label. It uses the existing threshold, next-open execution, holding and liquidation rules, plus 10 bp cost and 5 bp slippage per side. The stock ledger and portfolio equity are saved separately.

The report and CSVs are under `artifacts/forecasting/tcn_stacking_v1`. `selection_frozen.json` binds model choices, OOF inputs and saved checkpoints before test access. `stacking_config.json` contains sample support and tuning results. `metrics.csv` reports full, seen and held-out companies. `paired_intervals.csv` uses date blocks and leaves confidence limits unavailable where history is too short. The final test has been inspected in previous research and supports retrospective comparisons.
