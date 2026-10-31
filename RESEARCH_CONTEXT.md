# Market, sector and financial-context study

The current study adds genuinely different information to the price features: market and sector histories, index valuations, and original annual company disclosures. Results are in `RESULTS_CONTEXT.md`; trained models and the frozen protocol are under `artifacts/context_v3`.

## Reproduce

```powershell
$py = 'C:/Users/Siddhant/miniconda3/envs/NightEye/python.exe'
& $py -m src.context_sources
& $py -m src.research_context --trials 12
& $py verify_context.py
& $py -m src.report_context
& $py -m unittest discover -s tests -v
```

These commands acquire the snapshot, train the comparisons, verify every saved prediction/model, and generate the report. Source acquisition caches raw responses. Existing experiment protocols are never overwritten: use another `--output` directory for a different training experiment. The recorded data snapshot ends with stock/index observations on October 23, 2026, retaining the previous stock dataset for matched comparisons. Acquisition dates and SHA256 hashes are saved.

The initial context preparation caught a missing Titan proxy before model fitting. Its protocol was retained as `aborted_setup.json`; the final `protocol.json` includes the complete mapping and source hashes. No scores from that setup attempt were used.

## What changed

- `src/context_sources.py` downloads official Nifty historical data in annual requests, including eleven broad economic sector proxies and Nifty 50. It also downloads legacy NSE annual-filing metadata, original XBRL files, and the replacement integrated-financial-filing feed for 2025–2026.
- `src/XGBoost/context_features.py` creates causal index signals, joins previous-day market valuations, and joins company financial facts only after publication. It supplies five predefined ablation families.
- `src/research_context.py` prepares the common panel and calls the existing XGBoost evaluator with explicit validation boundaries. `src/research_v2.py` now supports injected prepared data and fold boundaries; its original default behavior remains intact.
- `src/XGBoost/predict.py` recognizes saved context-model metadata and recreates the appropriate sector/market features. The ticker must be supplied to choose its declared sector proxy. A different frozen context directory can be passed explicitly.
- `verify_context.py` checks source hashes, held-out stock exclusion, purged label boundaries, common test observations, all saved predictions, native model reloads, inverse scaling, and latest-row inference. It also writes actual feature coverage by development/test group.
- `src/report_context.py` compares each new-input bundle directly with the matched price-only model using paired date-block diagnostics.

## Predeclared experiment

Training origins start in 2017. The final evaluation boundary is January 1, 2025. Two expanding validation windows are `[2021, 2023)` and `[2023, 2025)`. Training and validation labels whose outcomes cross the next boundary are excluded. Five companies—ASIANPAINT, BAJFINANCE, NTPC, TITAN, COALINDIA—are excluded from all fitting and tuning. The validation score is average per-stock return RMSE across the two folds.

Each of the five families uses the same twelve seeded XGBoost candidates, the same sample, and the same early-stopping rules, for horizons of 1, 21 and 252 sessions. Target scaling is fitted on each training fold only. This fits 360 validation models and fifteen final evaluation models. Every model is compared against unchanged-price, training-mean and stock-mean baselines. `selected.json` chooses the lowest validation RMSE, including the option to keep the price-only control.

This is a new recent-period protocol so that available financial disclosures can actually participate in training. Its results must be compared with its own retrained price-only control, not percentages from the earlier, much longer 2021-start test. The test years and held-out stocks were inspected in earlier work, so this is exploratory ablation evidence, not a genuinely new prospective test. The annual test includes fewer than one independent annual market period; daily-origin annual labels are highly overlapping.

## Feature families

| Family | Added information |
|---|---|
| `price_only` | Previously selected base: core five features for daily; original eighteen for monthly/annual |
| `market` | Nifty 1/21/63-session returns, 21/63-session volatility, stock momentum relative to Nifty |
| `market_sector` | Sector-proxy 21/63-session returns, 63-session volatility, stock momentum relative to sector |
| `market_sector_valuation` | Nifty earnings yield, book yield, dividend yield |
| `market_sector_fundamentals` | Published annual profit/income margin, symmetric annual income/profit growth, and release age |

There are 5/12/17/20/24 inputs in the daily families and 18/25/30/33/37 in monthly/annual families. Static economic proxies are deliberately broad: consumer firms use Nifty India Consumption; cement/materials firms use Nifty Commodities; energy firms use Nifty Energy. These are not historical membership claims and may fit some businesses poorly. Newly supported stocks require a declared proxy mapping, so this is not a universal model for arbitrary tickers.

Index signals are computed using past values only and made available the next calendar day. At a Monday stock observation, Friday's signal can therefore be used; Monday's closing index value cannot. Relative momentum uses the corresponding lagged stock momentum. Index data older than seven calendar days becomes missing. All families—including the control—use identical dates with eligible market/sector histories.

## Fundamental extraction and limits

NSE disclosures provide actual broadcast/dissemination times. The later of the provided times is used; the fact is not usable until the next calendar day, then is joined backward to stock sessions. Later revisions do not replace earlier observations before their publication date. Annual income/profit facts must use compatible INR units and the same annual context. The net margin is reported consolidated net profit divided by total income, not a price-derived indicator. Bank-specific profit tags are supported. Year-over-year growth requires an already published prior fiscal year; it is a bounded symmetric change `2*(new-old)/(abs(new)+abs(old))`, not ordinary percentage growth. Missing years remain missing.

Some original older XBRL files omit base context definitions. For annual metadata only, the recognized `FourD` current annual/YTD template is accepted and marked explicitly in the processed CSV. Newer filings are matched through explicit annual start/end dates. The accepted field names, source URL, date, currency, consolidation, and context interpretation are preserved. A fully reconciled financial database would need additional auditing, especially across taxonomy and accounting-definition changes.

The index valuation features are **Nifty P/E, P/B and dividend yield**, not each company's P/E. Stock-level EPS/P/E is not manufactured because historical EPS and vendor-adjusted price share bases have not been verified. Current P/E is never copied backward. The official index histories are dated snapshots and can contain methodology changes or revisions; they are not a guaranteed point-in-time archive.

There are 325 usable audited consolidated annual disclosures across all 40 companies. Four companies lack successfully parsed post-2024 annual records: BAJAJFINSV, HEROMOTOCO, POWERGRID and TATASTEEL. Facts expire 550 days after publication and then remain missing. XGBoost handles these missing inputs natively. `coverage.json` reports the actual fraction available in each evaluation group; do not confuse having at least one filing for a company with complete history.

## Inference

Use the family/horizon selected in `artifacts/context_v3/selected.json`, for example:

```powershell
& $py -m src.XGBoost.predict --model artifacts/context_v3/market_sector_fundamentals/h21/model.joblib --history data/research_v2/RELIANCE.NS_2000-01-01_to_2026-10-27.csv --ticker RELIANCE.NS --context-dir data/context_v3
```

The example shows the interface, not a claim that this family wins. Supply fresh, appropriately dated histories for subsequent inference. Stale context cannot silently be substituted indefinitely. Saved models are evaluation models trained strictly before 2025, not models refitted through today for deployment. No trades or Monte Carlo simulations are implemented by this study.
