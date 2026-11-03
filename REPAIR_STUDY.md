# Controlled repair study

The completed experiment is `artifacts/forecasting/repair_study_v1`. Open `index.html` for learning curves and actual/predicted training, validation and test prices; `RESULTS.md` for measured outcomes; `forecasts/index.html` for nine Monte Carlo reports. `code_review.md`, `feature_audit.csv`, `attribution.csv` and `validation_trials.csv` document the diagnosis and all failed/successful trials.

The study uses the existing 40-stock v2 cache and company holdouts. The two chronological, target-date-purged validation folds select from saved-weight controls, fresh controls, compact inputs, three-year fitting windows, volatility-normalized return targets, LSTM return-only loss and fixed output shrinkage. Native and LSTM estimator families are unchanged. It compares pooled return RMSE with unchanged price explicitly and reports macro-stock errors separately. Direction uses a separate validation log-loss objective and the pre-test calibration safeguard. All choices freeze before this run opens final-test labels. The historical test has already informed diagnosis, so these results are exploratory.

Point forecasts improved modestly: all three annual models beat unchanged price on pooled test RMSE, and monthly LightGBM narrowly beats it. Daily models still miss that baseline. Balanced directional accuracy stays near 50%, and annual interval coverage remains inadequate. Consult the result tables rather than treating RMSE as a percentage accuracy or assuming profitable trading.

The scenario input is the existing **30 October 2026** Reliance snapshot. It is explicitly dated historical input, not a live quote. Evaluation models fit before the original test period. The charts retain Monte Carlo reliability warnings; simulation does not add predictive skill. Original models, datasets and journals remain unchanged.

```powershell
conda activate NightEye
Start-Process .\artifacts\forecasting\repair_study_v1\index.html
Start-Process .\artifacts\forecasting\repair_study_v1\forecasts\index.html

# Resume this same study; completed configurations are reused.
python -m src.repair_study.study

# Reproduce in a new isolated folder.
python -m src.repair_study.study --output artifacts/forecasting/repair_study_new
```

For another report from the same dated snapshot, choose a new prediction output:

```powershell
python -m src.forecasting.predict --model artifacts/forecasting/repair_study_v1/h21/lightgbm/model.joblib --history artifacts/forecasting/feature_engineering_v2/market_snapshot/RELIANCE.NS.csv --ticker RELIANCE.NS --context-dir artifacts/forecasting/feature_engineering_v2/market_snapshot/context --paths 5000 --output artifacts/predictions/repair_reliance_example
```

The source audit found synchronized zero-volume rows. `zero_volume_sensitivity.csv` excludes only observations with zero volume at origin or target as a descriptive robustness check; frozen headline observations and model choices stay unchanged. Broad conclusions survive that check. Older extreme returns precede the active 2017-onward study and need investigation before extending training backwards. These checks do not certify the vendor history as point-in-time data.
