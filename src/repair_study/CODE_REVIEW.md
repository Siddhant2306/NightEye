# Code and feature review

Scope: the active data loader, original/reduced/context feature builders, forecasting feature builder, v2 feature registry and cache preparation, tree/LSTM estimators, purged protocol, validation selection, calibration, saved-model inference, residual scenarios, backtesting/execution auditing, immutable paper journal and report paths. `code_inventory.json` lists Python source files, entry points and delivery hashes. Retired single-stock scripts are historical references, not the current multi-stock pipeline.

## Findings and controlled repairs

1. **The selection objective and headline baseline comparison differed.** Earlier tuning averaged per-stock RMSE; the full-universe headline used pooled RMSE. Both are legitimate estimands, but a win on one does not imply a win on the other. The repair study selects mean pooled RMSE across the two existing purged folds, retains macro RMSE separately, includes unchanged price explicitly, and requires each fold to be no worse than that baseline. An inspected test never selects the winner.
2. **Positive learned intercepts transfer poorly between regimes.** The failure review shows small point-prediction variation and upward bias. Fixed 0/0.25/0.5/1 output multipliers test how much of the estimator signal deserves retaining. A selected `current` estimator with multiplier below one isolates this output correction from new training/features. Zero is disclosed as unchanged-price fallback, not a learned improvement.
3. **More inputs did not imply more usable information.** `feature_audit.csv` measures missingness and variation only in the earliest fitting block. A ten-input compact set removes most correlated indicators and publication-limited inputs. It competes against the existing selected schema; missing inputs are never filled from the future. The experiment does not claim every dropped feature is individually harmful.
4. **Mixed-stock/horizon target scales can dominate squared error.** The risk-target trial predicts return divided by observable origin volatility and then multiplies by that same risk scale at inference. The optional saved output flag is applied exactly once in the shared v2 prediction path. Final validation selection remains in original log-return units. The transformed estimator has a different training/early-stopping objective; a win would not isolate that into a purely representational benefit.
5. **All-history fits can retain old regimes.** The recent trial restricts estimator fitting to the last three years of already mature training origins. It never uses labels crossing the next boundary. The combined compact/recent/risk recipe is reported alongside one-factor trials so its effect can be checked rather than attributed automatically to one component.
6. **LSTM return/direction heads share a representation.** The return-only trial disables the direction loss to test interference. Existing trained direction heads remain controls for LSTM; no untrained auxiliary head is presented as a classifier. Epoch ceilings and early stopping remain bounded. Reused and fresh checkpoint trials are distinguished in the records.
7. **Probability calibration was applied without proving forward improvement.** The prior fix now gates recalibration inside the pre-test calibration block, with target-date purging and date-support checks. Direction shrinkage toward neutral 0.5 is selected on validation log loss. A deliberately neutral choice is not recalibrated back into a confident signal. Raw probabilities remain estimates, not guaranteed probabilities.
8. **Annual Monte Carlo support is insufficient.** The historical calibration bank has 136 overlapping annual origin dates and a strong bullish residual shift. The study retains honest coverage diagnostics; it does not shift/widen intervals until they match the already inspected test. Monte Carlo paths do not improve the point estimator. Annual intervals remain unvalidated even if RMSE improves.

## Correct behavior retained

- Labels use forward adjusted-price log returns and actual target-session dates. Target-date purging is necessary; random 80/20 shuffling would introduce leakage.
- Features are computed per company before pooling. Publication timestamps, lagged market context and training-only preprocessing remain in force. Cross-sectional reference ranks exclude held-out firms and require contemporaneous peer data at inference.
- Existing model weights, cached datasets, old test outputs and both original paper journals are untouched. All new selections freeze before this experiment reads final-test labels.
- Next-open execution, costs and truncation rules are independent of return RMSE. Better test RMSE is not evidence of profitable trading.
- The reported scenario input is explicitly dated 30 October 2026. Final benchmark models fit before the original test period; no silent production refit or live-market performance claim is made.

## Limits

This is a finite, controlled exploratory search. The historical test has already informed diagnosis, so later/prospective evidence is needed to establish any gain. A neutral fallback only matches its baseline. No maximum attainable accuracy or universal stock predictor is claimed. The feature audit exposes missingness; it does not establish causality. A family-level ablation cannot establish which individual correlated indicator caused a change.

## Data quality follow-up

The source audit found no duplicate dates, missing OHLCV or inconsistent OHLC bounds. Synchronized zero-volume observations need provider/calendar verification. A descriptive check excluding zero-volume origins/targets preserves the broad conclusions; see zero_volume_sensitivity.csv. The 54 very large daily log returns occurred before 2017, outside the active study; do not extend training backwards without investigating them. Original source data and benchmark observation keys were retained.
