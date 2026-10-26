"""Summarize frozen test predictions without choosing models using test outcomes."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.pipeline import ROOT, score


def summarize():
    lines = ['# XGBoost experiment results', '',
             'All hyperparameters were selected on three purged chronological validation folds before 2021. '
             'Test origin dates start January 2021. Test results are now observed and must not become tuning data.', '',
             '| Experiment | Sessions | Stocks | Test rows | Direction | Always-up direction | Return RMSE | Zero RMSE | Mean RMSE |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    details = []
    for path in sorted((ROOT/'artifacts').glob('*/h*/report.json')):
        report = json.loads(path.read_text())
        pred = pd.read_csv(path.parent/'test_predictions.csv', parse_dates=['Date', 'target_date'])
        m = report['metrics']
        label = path.parent.parent.name
        lines.append(f'| {label} | {report["horizon_sessions"]} | {len(report["test_tickers"])} | {len(pred)} | '
                     f'{m["xgboost"]["directional_accuracy"]:.2%} | {(pred.target>0).mean():.2%} | '
                     f'{m["xgboost"]["rmse"]:.6f} | {m["zero_return"]["rmse"]:.6f} | {m["historical_mean"]["rmse"]:.6f} |')
        rows = []
        for ticker, group in pred.groupby('ticker'):
            for name in ['xgboost', 'zero_return', 'historical_mean', 'historical_median']:
                actual_price = group.close*np.exp(group.target)
                forecast_price = group.close*np.exp(group[name])
                rows.append(dict(ticker=ticker, model=name, **score(group.target, group[name]),
                                 price_mape=float((abs(actual_price-forecast_price)/actual_price).mean())))
        pd.DataFrame(rows).to_csv(path.parent/'per_stock_metrics.csv', index=False)
        yearly = []
        for year, group in pred.groupby(pred.Date.dt.year):
            for name in ['xgboost', 'zero_return', 'historical_mean']:
                yearly.append(dict(year=int(year), model=name, rows=len(group), **score(group.target, group[name])))
        pd.DataFrame(yearly).to_csv(path.parent/'yearly_metrics.csv', index=False)
        # Moving block bootstrap of date-level paired squared errors: preserve cross-stock dependence.
        # This is an approximate interval, not a formal significance guarantee under nonstationarity.
        error_diff = ((pred.target-pred.xgboost)**2 - (pred.target-pred.historical_mean)**2)
        daily = pd.DataFrame(dict(date=pred.Date, diff=error_diff)).groupby('date')['diff'].mean().to_numpy()
        block = max(21, report['horizon_sessions'])
        rng = np.random.default_rng(42)
        bootstrap = []
        for _ in range(1000):
            starts = rng.integers(0, len(daily), size=int(np.ceil(len(daily)/block)))
            sample = np.concatenate([daily[(np.arange(block)+s) % len(daily)] for s in starts])[:len(daily)]
            bootstrap.append(float(sample.mean()))
        interval = np.quantile(bootstrap, [.025, .975]).tolist()
        details.append(dict(experiment=label, horizon=report['horizon_sessions'],
                            mse_difference_vs_mean=float(daily.mean()), approximate_block_ci95=interval,
                            block_sessions=block, note='Negative favors XGBoost; overlapping outcomes remain dependent'))
    (ROOT/'artifacts'/'comparison.json').write_text(json.dumps(details, indent=2))
    lines += ['', 'RMSE is on log returns; lower is better. Direction is not price accuracy or profitability.', '',
              '## Interpretation of this run', '',
              'The expanded daily model did not beat the historical-mean or unchanged-price baselines on test RMSE. '
              'The monthly model improved RMSE by about 0.22% versus the mean baseline; the annual model improved '
              'by about 2.90%. These are modest point estimates, not guarantees of future improvement. The approximate '
              'block-bootstrap intervals against the mean include zero for these pooled models.', '',
              'All monthly and annual predictions in the pooled expanded experiment are positive. Their 55.38% and '
              '71.81% direction scores equal the always-up baseline. They show no incremental directional skill. '
              'The original feature set slightly outperformed the expanded set at the monthly horizon; more features '
              'did not consistently help. On the entirely held-out TCS and Maruti stocks, none of the three horizons '
              'beat the unchanged-price baseline on pooled return RMSE. A general-purpose stock predictor is not '
              'established by these results.', '',
              'All four feature/label/split tests passed. All nine saved model pairs were reloaded and checked for '
              'prediction equivalence, training label boundaries, and latest-row inference. Downloads contained '
              'incomplete October 26 rows; those were excluded, and the latest valid inference date is October 23, 2026.', '',
              'The expanded and original feature searches have different budgets (24 vs 12 candidates), and '
              'the original features have a shorter warmup. Their comparison is exploratory, not a controlled feature ablation.', '',
              'See each experiment directory for selected parameters, all validation scores, per-stock metrics, yearly '
              'metrics, predictions, feature importance, and saved models. comparison.json contains approximate paired '
              'block-bootstrap intervals against the historical-mean baseline.', '',
              'The 15-stock universe uses current surviving large companies. It does not establish performance on '
              'delisted companies, small caps, other countries, or every stock. Corporate-action-adjusted histories '
              'are downloaded snapshots, not point-in-time vendor archives. The annual test window contains only '
              'a handful of independent annual periods; overlapping daily labels must not be treated as independent evidence.', '',
              'These experiments establish a reproducible benchmark, not the maximum achievable XGBoost accuracy.']
    (ROOT/'RESULTS.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')

if __name__ == '__main__':
    summarize()
