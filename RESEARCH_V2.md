# Reduced-feature experiments

This study tests the user's requested statistical return and dividend features against a smaller core and the original technical features. Its code lives in `src/research_v2.py`, leaving the original experiment artifacts intact. Final measurements are in `RESULTS_REDUCED.md` after training finishes.

## Reproduce

Use the existing NightEye environment on this machine:

```powershell
$py = 'C:/Users/Siddhant/miniconda3/envs/NightEye/python.exe'
& $py -m src.fetch_research_data --output-dir data/research_v2
& $py -m src.research_v2 --data-dir data/research_v2 --output artifacts/reduced_v2 --trials 16
& $py -m src.report_reduced --directory artifacts/reduced_v2
& $py -m unittest discover -s tests -v
```

The price snapshot and experiment protocol refuse overwrites. For another experiment, choose new directories. The downloader freezes 40 Indian stocks and observed ex-dividend cash events from 2000 onward, ending before 2026-10-27. Incomplete latest rows are discarded. Download failures are recorded in `manifest.json` and return a failure exit status. Corporate-action history is a revised vendor snapshot, not a point-in-time market database.

The 5-feature core uses returns and volatility. Statistics use 8 features: 21/63-session cumulative log returns, mean, median, and standard deviation of daily log returns. Mode adds one fixed-bin feature; dividends add trailing cash yield and event count, for 11 inputs. The original 18 inputs are the control. Volatility is standard deviation, so separate duplicates are not added. For complete windows, mean daily log return equals the matching cumulative log return divided by the window length. The statistics families deliberately test the requested transformations, including this redundancy; they do not necessarily supply new information.

Sixteen identical, seeded parameter candidates are evaluated for each family and horizon. The full study fits 720 validation models plus 15 final evaluation models. Three expanding folds end strictly before the 2021 test boundary. A training label must mature strictly before the next validation boundary; validation outcomes must mature before the following boundary. Every family uses identical eligible dates and a common 253-session warmup. Models are scored on validation macro-stock RMSE. Family selection uses validation only. Target scaling is fitted separately inside each training fold and saved for correct inverse scaling at prediction time. Some candidates restrict training to ten years rather than full history.

ASIANPAINT, BAJFINANCE, NTPC, TITAN, and COALINDIA are excluded from every fit and validation fold. Test reports separate future observations on seen companies from observations on these five unseen companies. The test years were inspected in the first study, so they are **not** a fresh prospective temporal test. The new company holdouts strengthen the generalization check without removing common-market dependence or universe selection bias.

## Inference

`artifacts/reduced_v2/selected.json` identifies the validation-selected model for each horizon. For a model using statistics plus dividends:

```powershell
& $py -m src.XGBoost.predict --model artifacts/reduced_v2/statistics_dividends/h21/model.joblib --history data/research_v2/RELIANCE.NS_2000-01-01_to_2026-10-27.csv --actions data/research_v2/actions/RELIANCE.NS.csv
```

Use the actual selected family and horizon. The actions CSV must cover the supplied price history and include Date, raw_close, dividend. Missing dividend history is an error, not a zero. Return features require adjusted close; dividend yield uses vendor raw close to avoid dividing cash dividends by dividend-adjusted price. The selected model is trained strictly before the evaluation boundary. It is not a deployment model refitted through today.

The price estimate is `current adjusted close * exp(predicted log return)`. This is a transformed conditional log-return estimate, not a guaranteed arithmetic expected price, execution price, or price interval. It should not be described as a literal quoted future price through splits or dividends.

## Historical P/E and EPS

No valid historical publication dataset was provided or obtained for this study; consequently P/E was **not trained or evaluated**. The optional importer is ready for a real dataset. It does not use current `.info` P/E as a historical value. NSE's [financial-results filings](https://www.nseindia.com/companies-listing/corporate-filings-financial-results) provide broadcast timestamps; retrieving, parsing, and verifying consolidated trailing EPS from the original disclosures is a separate data acquisition task. A vendor with historical as-published financial data is another option.

Store one file per ticker under a dedicated directory, e.g. `data/fundamentals/RELIANCE.NS.csv`, with these fields:

| Field | Required meaning |
|---|---|
| available_at | Actual publication timestamp including timezone, not fiscal quarter end |
| period_end | End date of the trailing earnings period |
| eps_ttm | Consolidated trailing-twelve-month EPS in INR, as published at that time |
| source | Filing/vendor provenance |
| currency | `INR` |
| share_basis | `matches_raw_close`, after verifying the EPS and price use compatible split/share units |

Do not fill these fields with guessed publication dates or current restated earnings. Later corrections should appear as new publication rows; original historical values must remain as published. The importer joins backward from the 15:30 IST prediction time, masks observations older than 550 days, computes earnings yield, and treats P/E as missing for nonpositive EPS. It accepts missing initial valuation coverage as missing inputs, not invented historical ratios. Inspect data coverage before comparing models.

```powershell
& $py -m src.research_v2 --families statistics_fundamentals --fundamentals-dir data/fundamentals --output artifacts/valuation_study
```

Every ticker in the frozen price directory must have a verified fundamentals file for that optional run. A schema and successful unit test do not demonstrate that P/E improves forecasting.

## Reading results

Each family/horizon saves a native XGBoost model, a joblib artifact with inverse target scaling, raw test predictions, feature importance, source hashes, every validation trial, per-stock/year metrics, and nonoverlapping-origin diagnostics. Feature gain importance is descriptive, not proof of causal predictive value. The reporting script writes paired date-block bootstrap intervals and cross-sectional rank diagnostics. Intervals are approximate and annual horizons have very few independent time periods.

Neither the highest direction percentage among all experiments nor the best hindsight test result is a defensible "maximum XGBoost accuracy." Report the validation-selected model, its baselines, uncertainty, and generalization limits. Freeze the pipeline before a prospective paper trial. A later trading evaluation must use executable next-session prices and realistic costs; the current study evaluates forecasts and does not place trades.
