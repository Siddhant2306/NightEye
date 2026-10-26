"""Explain the frozen reduced-feature experiment, including uncertainty and generalization."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.pipeline import ROOT


def paired_intervals(frame, horizon, baseline, repeats=1000):
    values = pd.DataFrame({
        'Date': frame.Date,
        'mse_difference': (frame.target-frame.xgboost)**2-(frame.target-frame[baseline])**2,
        'direction_excess': ((np.sign(frame.xgboost)==np.sign(frame.target)).astype(float)-(frame.target>0).astype(float)),
    }).groupby('Date')[['mse_difference', 'direction_excess']].mean().to_numpy()
    rng = np.random.default_rng(1701)
    n = len(values)
    block = max(21, horizon)
    samples = []
    for _ in range(repeats):
        starts = rng.integers(0, n, int(np.ceil(n/block)))
        indices = ((starts[:, None]+np.arange(block)) % n).ravel()[:n]
        samples.append(values[indices].mean(axis=0))
    intervals = np.quantile(samples, [.025, .975], axis=0)
    return dict(baseline=baseline, block_sessions=block, approximate_mse_difference_ci95=intervals[:, 0].tolist(),
                approximate_direction_excess_vs_always_up_ci95=intervals[:, 1].tolist(),
                note='Negative MSE difference favors XGBoost. Date blocks preserve cross-stock dependence; regime uncertainty remains.')


def summarize(directory):
    selected = json.loads((directory/'selected.json').read_text())
    manifest = json.loads((ROOT/'data'/'research_v2'/'manifest.json').read_text())
    reports = sorted([json.loads(p.read_text()) for p in directory.glob('*/h*/report.json')],
                     key=lambda r: (r['horizon'], r['family']))
    lines = ['# Reduced-feature XGBoost study', '',
             f'Downloaded {len(manifest["records"])} stocks and {sum(r.get("rows", 0) for r in manifest["records"]):,} clean daily observations. '
             'Prices and ex-dividend cash histories are frozen in data/research_v2.', '',
             '35 companies enter training and validation. ASIANPAINT, BAJFINANCE, NTPC, TITAN, and COALINDIA '
             'are excluded from every training and validation fold. They were not in the previous 15-stock experiment.', '',
             'The 2021–2026 period was already inspected in the earlier study. These results are further research, '
             'with new cross-stock holdouts, not a fresh prospective temporal test.', '',
             '## Selected models (chosen using validation only)', '',
             '| Sessions | Family | Features | Seen-stock direction | Unseen-stock direction | Unseen always-up | Unseen return RMSE | Zero RMSE | Stock-mean RMSE | Unseen price MAPE |',
             '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    uncertainties, rankings, all_rows, interpretations = [], [], [], []
    for report in reports:
        h, family = report['horizon'], report['family']
        seen, unseen = report['metrics']['seen'], report['metrics']['unseen']
        all_rows.append(dict(horizon=h, family=family, feature_count=report['feature_count'],
                             cv_rmse=report['best_trial']['cv_rmse'],
                             seen_direction=seen['xgboost']['directional_accuracy'],
                             unseen_direction=unseen['xgboost']['directional_accuracy'],
                             unseen_rmse=unseen['xgboost']['rmse'], unseen_zero_rmse=unseen['zero_return']['rmse'],
                             unseen_mean_rmse=unseen['historical_mean']['rmse'],
                             unseen_positive_fraction=unseen['positive_prediction_fraction']))
        if selected[str(h)]['family'] != family:
            continue
        lines.append(f'| {h} | {family} | {report["feature_count"]} | {seen["xgboost"]["directional_accuracy"]:.2%} | '
                     f'{unseen["xgboost"]["directional_accuracy"]:.2%} | {unseen["always_up_direction"]:.2%} | '
                     f'{unseen["xgboost"]["rmse"]:.6f} | {unseen["zero_return"]["rmse"]:.6f} | '
                     f'{unseen["stock_mean"]["rmse"]:.6f} | {unseen["xgboost"]["price_mape"]:.2%} |')
        gain_zero = 1-unseen['xgboost']['rmse']/unseen['zero_return']['rmse']
        gain_mean = 1-unseen['xgboost']['rmse']/unseen['historical_mean']['rmse']
        excess = unseen['xgboost']['directional_accuracy']-unseen['always_up_direction']
        interpretations.append(f'- {h} sessions, {family}: unseen-stock return RMSE reduction versus '
                               f'unchanged price {gain_zero:+.2%}, versus training mean {gain_mean:+.2%}; '
                               f'direction advantage over always-up {excess*100:+.2f} percentage points. '
                               f'{unseen["positive_prediction_fraction"]:.2%} of forecasts predict a rise.')
        prediction_path = directory/family/f'h{h}'/'test_predictions.csv'
        pred = pd.read_csv(prediction_path, parse_dates=['Date', 'target_date'])
        for group_name, frame in pred.groupby('group'):
            for baseline in ['zero_return', 'historical_mean', 'stock_mean']:
                uncertainties.append(dict(horizon=h, family=family, group=group_name,
                                          **paired_intervals(frame, h, baseline)))
            # Daily cross-sectional ranking is diagnostic; no trade fills or profits are simulated.
            ic = []
            for date, g in frame.groupby('Date'):
                if len(g)>=5 and g.xgboost.nunique()>1 and g.target.nunique()>1:
                    ic.append(g.xgboost.corr(g.target, method='spearman'))
            rankings.append(dict(horizon=h, group=group_name, rank_ic_mean=float(np.mean(ic)) if ic else None,
                                 dates=len(ic), caveat='Overlapping outcomes are dependent; not a profitability backtest'))
    lines += ['', '## Interpretation', ''] + interpretations
    lines += ['', 'For the selected models, the approximate unseen-stock paired MSE intervals versus '
              'the historical-mean baseline include zero at the daily and monthly horizons. The annual '
              'interval is positive, favoring the historical mean. This study does not demonstrate a '
              'reliable incremental forecasting edge sufficient to justify live-money deployment.', '',
              'Nine automated tests passed. All 15 final models passed artifact checks for purged label '
              'boundaries, held-out company exclusion, identical test observations across feature families, '
              'native model reload, inverse target scaling, and latest-row inference. See verification.json.']
    lines += ['', 'Return RMSE is on log returns; lower is better. Price MAPE is mean absolute percentage '
              'error relative to realized adjusted price. Direction is up/down sign accuracy, not percentage '
              'price accuracy. For unseen companies the stock-mean baseline falls back to the training-universe '
              'mean. Annual daily-origin outcomes overlap strongly.', '',
              '## All predefined feature families', '',
              '| Sessions | Family | Features | Validation RMSE | Unseen direction | Unseen RMSE | Unseen zero RMSE |',
              '|---|---|---:|---:|---:|---:|---:|']
    for row in sorted(all_rows, key=lambda r: (r['horizon'], r['cv_rmse'])):
        lines.append(f'| {row["horizon"]} | {row["family"]} | {row["feature_count"]} | {row["cv_rmse"]:.6f} | '
                     f'{row["unseen_direction"]:.2%} | {row["unseen_rmse"]:.6f} | {row["unseen_zero_rmse"]:.6f} |')
    lines += ['', '## What was tested', '',
              '- Core: 1/21/63-session returns and 21/63-session volatility (5 inputs).',
              '- Statistics: 21/63-session returns and rolling return mean, median, standard deviation (8 inputs).',
              '- Statistics plus a fixed-bin return mode (9 inputs). The mode uses fixed 10-basis-point bins with deterministic ties.',
              '- Statistics plus mode and trailing 365-calendar-day realized dividend yield/event count (11 inputs). Yield uses raw price and cash dividends on the same vendor share basis.',
              '- Original technical feature control (18 inputs), under the same sample, search budget, and evaluation rules.', '',
              'Every family uses the same 253-session warmup, common eligible dates, identical 16 parameter '
              'candidates, and three purged chronological validation folds. Parameter candidates also test full '
              'history versus a trailing ten-year training window. Labels are standardized using each fold’s '
              'training mean and standard deviation; inverse scaling is saved for inference. Family and parameter '
              'selection use macro-stock validation RMSE, not test direction accuracy. This differs from v1, '
              'so changes cannot be attributed to feature count alone.', '',
              '## P/E: implemented, not empirically tested', '',
              'No verified historical EPS publication records were available in this dataset. The saved '
              'fundamental_coverage_audit.json shows Reliance quarterly snapshot periods only in 2025–2026 '
              'and annual periods in 2022–2026, without as-published historical release records. Current P/E and '
              'current financial snapshots were not copied backward. The optional statistics_fundamentals family '
              'supports trailing P/E and earnings yield using timestamped EPS releases. Its importer requires '
              'available_at with timezone, period_end, eps_ttm, source, currency=INR, and share_basis=matches_raw_close. '
              'It joins only data published by 15:30 IST on the prediction date, masks stale EPS, and leaves '
              'nonpositive-earnings P/E undefined. EPS must be consolidated TTM and aligned with the raw price '
              'share basis; an exchange filing archive or a suitable historical data provider is needed to '
              'populate it. A schema is not evidence that P/E improves prediction.', '',
              '## Real-market assessment', '',
              'XGBoost is a reasonable tabular benchmark for nonlinear interactions, but this study cannot '
              'establish a maximum achievable accuracy or guarantee profitable forecasting. Redundant means '
              'and momentum can add little new information, and volatility primarily describes uncertainty '
              'rather than the expected direction. Dividend yield and earnings yield are testable hypotheses, '
              'not automatic sources of an edge.', '',
              'Judge models against both drift/unchanged-price baselines and uncertainty intervals in '
              'uncertainty.json. Check yearly and per-stock stability in each report, the nonoverlapping '
              'diagnostics, and positive-prediction fractions. An always-positive model must not be presented '
              'as evidence of market timing skill. There are only five entirely held-out companies and a '
              'small number of independent annual periods.', '',
              'Before risking real money, freeze the selected model, record predictions prospectively, '
              'and compare with the same baselines. Daily/monthly paper tests can mature sooner; annual '
              'labels require a full year. A tradable strategy additionally needs next-session executable '
              'prices, spread, slippage, fees/taxes, liquidity, position limits, turnover and drawdown analysis. '
              'No live trading or profitability backtest was performed here.', '',
              'The next informative inputs are point-in-time earnings/valuation and market/sector context, '
              'with a universe including delisted companies. Compare a regularized linear baseline and '
              'other algorithms on exactly the same frozen protocol before adding model complexity. '
              'A later Monte Carlo stage must calibrate its ranges on held-out outcomes; simulations cannot '
              'repair an uninformative mean forecast.', '',
              'Sources: [XGBoost parameter documentation](https://xgboost.readthedocs.io/en/stable/parameter.html), '
              '[scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html), '
              '[NSE financial results with broadcast timestamps](https://www.nseindia.com/companies-listing/corporate-filings-financial-results).']
    pd.DataFrame(all_rows).to_csv(directory/'comparison.csv', index=False)
    (directory/'uncertainty.json').write_text(json.dumps(uncertainties, indent=2))
    (directory/'ranking_diagnostics.json').write_text(json.dumps(rankings, indent=2))
    (ROOT/'RESULTS_REDUCED.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT/'artifacts'/'reduced_v2')
    summarize(parser.parse_args().directory)
