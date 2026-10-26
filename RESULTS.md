# XGBoost experiment results

All hyperparameters were selected on three purged chronological validation folds before 2021. Test origin dates start January 2021. Test results are now observed and must not become tuning data.

| Experiment | Sessions | Stocks | Test rows | Direction | Always-up direction | Return RMSE | Zero RMSE | Mean RMSE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pooled_extended | 1 | 15 | 21496 | 50.77% | 50.67% | 0.015126 | 0.015122 | 0.015118 |
| pooled_extended | 21 | 15 | 21196 | 55.38% | 55.38% | 0.067265 | 0.067614 | 0.067414 |
| pooled_extended | 252 | 15 | 17746 | 71.81% | 71.81% | 0.206488 | 0.230580 | 0.212646 |
| pooled_original | 1 | 15 | 21496 | 50.66% | 50.67% | 0.015126 | 0.015122 | 0.015118 |
| pooled_original | 21 | 15 | 21196 | 55.38% | 55.38% | 0.067215 | 0.067614 | 0.067438 |
| pooled_original | 252 | 15 | 17746 | 71.81% | 71.81% | 0.209609 | 0.230580 | 0.212279 |
| unseen_stocks | 1 | 2 | 2866 | 49.37% | 49.23% | 0.014614 | 0.014595 | 0.014603 |
| unseen_stocks | 21 | 2 | 2826 | 52.19% | 52.19% | 0.066693 | 0.065884 | 0.066987 |
| unseen_stocks | 252 | 2 | 2366 | 69.10% | 69.10% | 0.211753 | 0.203183 | 0.219910 |

RMSE is on log returns; lower is better. Direction is not price accuracy or profitability.

## Interpretation of this run

The expanded daily model did not beat the historical-mean or unchanged-price baselines on test RMSE. The monthly model improved RMSE by about 0.22% versus the mean baseline; the annual model improved by about 2.90%. These are modest point estimates, not guarantees of future improvement. The approximate block-bootstrap intervals against the mean include zero for these pooled models.

All monthly and annual predictions in the pooled expanded experiment are positive. Their 55.38% and 71.81% direction scores equal the always-up baseline. They show no incremental directional skill. The original feature set slightly outperformed the expanded set at the monthly horizon; more features did not consistently help. On the entirely held-out TCS and Maruti stocks, none of the three horizons beat the unchanged-price baseline on pooled return RMSE. A general-purpose stock predictor is not established by these results.

All four feature/label/split tests passed. All nine saved model pairs were reloaded and checked for prediction equivalence, training label boundaries, and latest-row inference. Downloads contained incomplete October 26 rows; those were excluded, and the latest valid inference date is October 23, 2026.

The expanded and original feature searches have different budgets (24 vs 12 candidates), and the original features have a shorter warmup. Their comparison is exploratory, not a controlled feature ablation.

See each experiment directory for selected parameters, all validation scores, per-stock metrics, yearly metrics, predictions, feature importance, and saved models. comparison.json contains approximate paired block-bootstrap intervals against the historical-mean baseline.

The 15-stock universe uses current surviving large companies. It does not establish performance on delisted companies, small caps, other countries, or every stock. Corporate-action-adjusted histories are downloaded snapshots, not point-in-time vendor archives. The annual test window contains only a handful of independent annual periods; overlapping daily labels must not be treated as independent evidence.

These experiments establish a reproducible benchmark, not the maximum achievable XGBoost accuracy.
