"""Predeclared reduced-feature study. Select using development CV, never test accuracy."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import joblib
import numpy as np
import pandas as pd
import xgboost
from xgboost import XGBRegressor
from src.helper.load_data import load_data
from src.pipeline import ROOT, purged_split, score, weights
from src.fetch_research_data import NEW_HOLDOUTS
from src.XGBoost.reduced_features import FAMILIES, make_reduced_features, load_actions


def candidates(count):
    rng = np.random.default_rng(1701)
    settings = [dict(max_depth=2, min_child_weight=75, subsample=0.85, colsample_bytree=1.,
                     reg_lambda=50., reg_alpha=0.1, learning_rate=0.03, lookback_years=0)]
    for _ in range(count-1):
        settings.append(dict(max_depth=int(rng.choice([1, 2, 3, 4])),
                             min_child_weight=int(rng.choice([30, 75, 150, 300])),
                             subsample=float(rng.choice([0.7, 1.])),
                             colsample_bytree=float(rng.choice([0.8, 1.])),
                             reg_lambda=float(rng.choice([10, 50, 100, 300])),
                             reg_alpha=float(rng.choice([0., 0.1, 1.])),
                             learning_rate=float(rng.choice([0.02, 0.05])),
                             lookback_years=int(rng.choice([0, 10]))))
    return settings


def restrict_window(frame, start, params):
    if params['lookback_years']:
        frame = frame.loc[frame.index >= start - pd.DateOffset(years=params['lookback_years'])]
    return frame


def fit_model(train, columns, params, valid=None, trees=1000):
    # Scale returns using this fit's labels only. This makes regularization comparable across horizons.
    center = float(train.target.mean())
    scale = max(float(train.target.std()), 1e-8)
    settings = {k: v for k, v in params.items() if k != 'lookback_years'}
    model = XGBRegressor(objective='reg:squarederror', tree_method='hist', n_estimators=trees,
                         random_state=1701, n_jobs=4, early_stopping_rounds=50 if valid is not None else None,
                         **settings)
    kwargs = dict(sample_weight=weights(train), verbose=False)
    if valid is not None:
        kwargs['eval_set'] = [(valid[columns], (valid.target-center)/scale)]
    model.fit(train[columns], (train.target-center)/scale, **kwargs)
    return model, center, scale


def panel(data_dir, horizon, family, fundamentals_dir=None):
    frames, sources = [], []
    seen_tickers = set()
    for path in sorted(data_dir.glob('*.csv')):
        ticker = path.stem.split('_')[0]
        if ticker in seen_tickers:
            raise ValueError(f'Multiple histories for {ticker}; use a frozen directory with one file per stock')
        seen_tickers.add(ticker)
        history = load_data(path)
        action_path = data_dir/'actions'/f'{ticker}.csv'
        actions = load_actions(action_path)
        facts_path = fundamentals_dir/f'{ticker}.csv' if fundamentals_dir else None
        frame, columns = make_reduced_features(history, horizon, family, actions, facts_path)
        # Common observations across ablations, including zero-volume exclusions in the control.
        reference, _ = make_reduced_features(history, horizon, 'original')
        frame = frame.loc[frame.index.intersection(reference.index)]
        frame['ticker'] = ticker
        frames.append(frame)
        sources.append(dict(ticker=ticker, rows=len(history), usable_rows=len(frame),
                            start=str(history.index.min().date()), end=str(history.index.max().date()),
                            price_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            actions_sha256=hashlib.sha256(action_path.read_bytes()).hexdigest(),
                            fundamentals_sha256=hashlib.sha256(facts_path.read_bytes()).hexdigest() if facts_path and family=='statistics_fundamentals' else None))
    if not frames:
        raise ValueError('No stock price files found')
    return pd.concat(frames).sort_index(), columns, sources


def metrics(frame):
    names = ['xgboost', 'zero_return', 'historical_mean', 'stock_mean', 'rolling_mean']
    report = {}
    for name in names:
        values = score(frame.target, frame[name])
        values['price_mape'] = float(np.abs(np.expm1(frame[name]-frame.target)).mean())
        values['macro_stock_rmse'] = float(np.mean([score(g.target, g[name])['rmse'] for _, g in frame.groupby('ticker')]))
        report[name] = values
    report['always_up_direction'] = float((frame.target>0).mean())
    report['positive_prediction_fraction'] = float((frame.xgboost>0).mean())
    report['rows'] = len(frame)
    report['stocks'] = frame.ticker.nunique()
    return report


def evaluate_family(args, horizon, family):
    out = args.output/family/f'h{horizon}'
    if out.exists():
        raise ValueError(f'{out} exists; choose a new output directory')
    data, columns, sources = panel(args.data_dir, horizon, family, args.fundamentals_dir)
    missing_holdouts = set(args.holdout_tickers) - set(data.ticker.unique())
    if missing_holdouts:
        raise ValueError(f'Missing holdout histories: {sorted(missing_holdouts)}')
    test_start = pd.Timestamp(args.test_start)
    held = data.ticker.isin(args.holdout_tickers)
    development = data.loc[(data.index < test_start) & (data.target_date < test_start) & ~held]
    test = data.loc[data.index >= test_start].copy()
    if development.empty or test.empty:
        raise ValueError('Empty training/test data')
    dates = development.index.unique().sort_values()
    edges = [dates[int(len(dates)*p)] for p in [.55, .70, .85]] + [test_start]
    trials = []
    for i, params in enumerate(candidates(args.trials)):
        folds, trees = [], []
        for start, end in zip(edges[:-1], edges[1:]):
            fit, valid = purged_split(development, start, end)
            fit = restrict_window(fit, start, params)
            model, center, scale = fit_model(fit, columns, params, valid)
            pred = model.predict(valid[columns])*scale+center
            macro_rmse = float(np.mean([score(g.target, pred[valid.ticker.to_numpy()==t])['rmse']
                                       for t, g in valid.groupby('ticker')]))
            trees.append(model.best_iteration+1)
            folds.append(dict(start=str(start.date()), end=str(end.date()), train_rows=len(fit), validation_rows=len(valid),
                              max_train_target=str(fit.target_date.max()), max_validation_target=str(valid.target_date.max()),
                              macro_rmse=macro_rmse, trees=trees[-1]))
        trial = dict(params=params, folds=folds, trees=int(np.median(trees)),
                     cv_rmse=float(np.mean([f['macro_rmse'] for f in folds])))
        trials.append(trial)
        print(f'{family} h={horizon} trial={i+1}/{args.trials} CV={trial["cv_rmse"]:.6f}', flush=True)
    best = min(trials, key=lambda t: t['cv_rmse'])
    fit = restrict_window(development, test_start, best['params'])
    model, center, scale = fit_model(fit, columns, best['params'], trees=best['trees'])
    test['xgboost'] = model.predict(test[columns])*scale+center
    test['zero_return'] = 0.
    test['historical_mean'] = float(fit.target.mean())
    stock_means = fit.groupby('ticker').target.mean()
    test['stock_mean'] = test.ticker.map(stock_means).fillna(fit.target.mean())
    # Same predeclared trailing mean baseline for all families; computed without future observations.
    for ticker, group in test.groupby('ticker'):
        history = load_data(next(args.data_dir.glob(f'{ticker}_*.csv')))
        means = np.log(history.close).diff().rolling(63).mean()*horizon
        mask = test.ticker == ticker
        test.loc[mask, 'rolling_mean'] = means.reindex(test.index[mask]).to_numpy()
    test['actual_adjusted_price'] = test.close*np.exp(test.target)
    test['predicted_adjusted_price'] = test.close*np.exp(test.xgboost)
    test['group'] = np.where(test.ticker.isin(args.holdout_tickers), 'unseen', 'seen')
    # All feature families must evaluate the exact same observations.
    key_bytes = ('|'.join(f'{date.isoformat()}:{ticker}' for date, ticker in zip(test.index, test.ticker))).encode()
    results = {label: metrics(group) for label, group in test.groupby('group')}
    results['all'] = metrics(test)
    year_rows, stock_rows = [], []
    for ticker, group in test.groupby('ticker'):
        stock_rows.append(dict(ticker=ticker, group=group.group.iloc[0], metrics=metrics(group)))
    for (label, year), group in test.groupby(['group', test.index.year]):
        year_rows.append(dict(group=label, year=int(year), metrics=metrics(group)))
    sampled = pd.concat([g.iloc[::horizon] for _, g in test.groupby('ticker')])
    report = dict(family=family, horizon=horizon, feature_cols=columns, feature_count=len(columns),
                  test_start=str(test_start.date()), test_end=str(test.index.max().date()),
                  holdout_tickers=args.holdout_tickers, train_tickers=sorted(fit.ticker.unique()),
                  training_rows=len(fit), max_train_target=str(fit.target_date.max()),
                  test_keys_sha256=hashlib.sha256(key_bytes).hexdigest(), sources=sources,
                  target_scaling='training-label mean and standard deviation, independently fitted in each fold',
                  best_trial=best, trials=trials, metrics=results, per_stock=stock_rows, yearly=year_rows,
                  nonoverlapping={label: metrics(g) for label, g in sampled.groupby('group')},
                  versions=dict(python=platform.python_version(), xgboost=xgboost.__version__, pandas=pd.__version__))
    out.mkdir(parents=True)
    test[['ticker', 'group', 'close', 'target', 'target_date', 'xgboost', 'zero_return',
          'historical_mean', 'stock_mean', 'rolling_mean', 'actual_adjusted_price', 'predicted_adjusted_price']].to_csv(out/'test_predictions.csv', index_label='Date')
    (out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    model.save_model(out/'model.ubj')
    joblib.dump(dict(model=model, feature_cols=columns, horizon=horizon, feature_family=family,
                     target_center=center, target_scale=scale, train_end=str(fit.index.max()),
                     requires_actions=family in ['statistics_dividends', 'statistics_fundamentals']), out/'model.joblib')
    pd.Series(model.feature_importances_, index=columns).sort_values(ascending=False).to_csv(out/'feature_importance.csv')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data'/'research_v2')
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts'/'reduced_v2')
    parser.add_argument('--families', nargs='+', default=['core', 'statistics', 'statistics_mode', 'statistics_dividends', 'original'],
                        choices=list(FAMILIES)+['original', 'statistics_fundamentals'])
    parser.add_argument('--horizons', nargs='+', type=int, default=[1, 21, 252])
    parser.add_argument('--trials', type=int, default=16)
    parser.add_argument('--test-start', default='2021-01-01')
    parser.add_argument('--holdout-tickers', nargs='+', default=NEW_HOLDOUTS)
    parser.add_argument('--fundamentals-dir', type=Path)
    args = parser.parse_args()
    if args.trials<1 or any(h<1 for h in args.horizons):
        parser.error('Positive trials and horizons are required')
    if 'statistics_fundamentals' in args.families and not args.fundamentals_dir:
        parser.error('P/E requires --fundamentals-dir containing historical publication records')
    # Freeze the complete protocol before training begins.
    args.output.mkdir(parents=True, exist_ok=True)
    protocol_path = args.output/'protocol.json'
    if protocol_path.exists():
        raise ValueError('Protocol already exists; select a new output directory')
    protocol_path.write_text(json.dumps(dict(families=args.families, horizons=args.horizons,
        trials_per_family=args.trials, test_start=args.test_start, holdout_tickers=args.holdout_tickers,
        candidates=candidates(args.trials), selection='lowest mean 3-fold validation macro-stock RMSE',
        caveat='Test years were inspected in v1. New held-out companies provide cross-stock evidence, not a fresh temporal test.'), indent=2))
    reports = []
    for horizon in args.horizons:
        for family in args.families:
            reports.append(evaluate_family(args, horizon, family))
    selections = {}
    for horizon in args.horizons:
        options = [r for r in reports if r['horizon']==horizon]
        if len({r['test_keys_sha256'] for r in options}) != 1:
            raise ValueError('Feature families evaluated different test observations')
        selected = min(options, key=lambda r: r['best_trial']['cv_rmse'])
        selections[str(horizon)] = dict(family=selected['family'], cv_rmse=selected['best_trial']['cv_rmse'],
                                       model_path=str(args.output/selected['family']/f'h{horizon}'/'model.joblib'))
    (args.output/'selected.json').write_text(json.dumps(selections, indent=2))
    print(json.dumps(selections, indent=2), flush=True)

if __name__ == '__main__':
    main()
