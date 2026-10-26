"""Pooled, direct-horizon XGBoost experiments with purged date-based folds."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
from xgboost import XGBRegressor
from src.helper.load_data import load_data
from src.XGBoost.feature_eng import create_features

ROOT = Path(__file__).resolve().parents[1]


def read_panel(data_dir, horizon, extended=True, tickers=None):
    # Prefer the longest cached history for a ticker; never count overlapping files twice.
    histories = {}
    for path in sorted(Path(data_dir).glob('*.csv')):
        ticker = path.stem.split('_')[0]
        if tickers and ticker not in tickers:
            continue
        history = load_data(path)
        if ticker not in histories or len(history) > len(histories[ticker][0]):
            histories[ticker] = (history, path)
    if not histories:
        raise ValueError('No matching price CSV files found')
    frames, sources = [], []
    for ticker, (history, path) in histories.items():
        frame, columns = create_features(history, horizon, extended=extended)
        frame['ticker'] = ticker
        frames.append(frame)
        sources.append(dict(ticker=ticker, path=str(path), rows=len(history),
                            start=str(history.index.min().date()), end=str(history.index.max().date()),
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return pd.concat(frames).sort_index(), columns, sources


def purged_split(data, start, end=None):
    train = data.loc[(data.index < start) & (data.target_date < start)]
    valid = data.loc[data.index >= start]
    if end is not None:
        valid = valid.loc[(valid.index < end) & (valid.target_date < end)]
    if train.empty or valid.empty:
        raise ValueError('Empty purged split; use more history or a shorter horizon')
    return train, valid


def score(y, pred):
    y, pred = np.asarray(y), np.asarray(pred)
    error = y - pred
    return dict(mae=float(np.abs(error).mean()), rmse=float(np.sqrt((error**2).mean())),
                directional_accuracy=float((np.sign(y) == np.sign(pred)).mean()),
                r2=float(1 - (error**2).sum() / ((y-y.mean())**2).sum()) if y.var() else None)


def estimator(params, trees=800, early=False):
    return XGBRegressor(objective='reg:squarederror', tree_method='hist',
                        n_estimators=trees, learning_rate=0.03, random_state=42,
                        n_jobs=4, early_stopping_rounds=40 if early else None, **params)


def weights(frame):
    # Each stock contributes equally, regardless of listing age.
    counts = frame.ticker.value_counts()
    w = 1 / frame.ticker.map(counts).to_numpy()
    return w / w.mean()


def train(args, horizon):
    out = Path(args.output) / f'h{horizon}'
    if out.exists():
        raise ValueError(f'{out} already exists; choose a new output directory to preserve results')
    data, columns, sources = read_panel(args.data_dir, horizon, not args.original_features, args.tickers)
    dates = data.index.unique().sort_values()
    test_start = pd.Timestamp(args.test_start) if args.test_start else dates[int(len(dates)*0.8)]
    development = data.loc[(data.index < test_start) & (data.target_date < test_start)]
    test = data.loc[data.index >= test_start]
    if args.holdout_tickers:
        held = set(args.holdout_tickers)
        development = development.loc[~development.ticker.isin(held)]
        test = test.loc[test.ticker.isin(held)]
    if development.empty or test.empty:
        raise ValueError('No development/test rows; check dates and held-out tickers')
    dev_dates = development.index.unique().sort_values()
    if len(dev_dates) < max(500, horizon*3):
        raise ValueError('Too little development history for three purged validation folds')
    edges = [dev_dates[int(len(dev_dates)*p)] for p in (0.55, 0.70, 0.85)] + [test_start]
    rng = np.random.default_rng(42)
    candidates = [dict(max_depth=2, min_child_weight=50, subsample=0.8, colsample_bytree=0.8, reg_lambda=30., reg_alpha=0.1)]
    for _ in range(args.trials-1):
        candidates.append(dict(max_depth=int(rng.choice([1, 2, 3, 4])),
                               min_child_weight=int(rng.choice([10, 30, 75, 150])),
                               subsample=float(rng.choice([0.65, 0.85, 1.])),
                               colsample_bytree=float(rng.choice([0.65, 0.85, 1.])),
                               reg_lambda=float(rng.choice([1, 10, 50, 100])),
                               reg_alpha=float(rng.choice([0, 0.1, 1]))))
    trials = []
    for number, params in enumerate(candidates):
        folds, iterations = [], []
        for start, end in zip(edges[:-1], edges[1:]):
            fit, valid = purged_split(development, start, end)
            model = estimator(params, early=True)
            model.fit(fit[columns], fit.target, sample_weight=weights(fit),
                      eval_set=[(valid[columns], valid.target)], verbose=False)
            pred = model.predict(valid[columns])
            # Macro stock RMSE prevents long histories dominating model selection.
            rmses = [score(group.target, pred[valid.ticker.to_numpy() == ticker])['rmse']
                     for ticker, group in valid.groupby('ticker')]
            folds.append(dict(start=str(start.date()), end=str(end.date()), train_rows=len(fit),
                              valid_rows=len(valid), max_train_target=str(fit.target_date.max()),
                              macro_rmse=float(np.mean(rmses)), **score(valid.target, pred)))
            iterations.append(model.best_iteration + 1)
        record = dict(trial=number, params=params, folds=folds, trees=int(np.median(iterations)),
                      cv_rmse=float(np.mean([f['macro_rmse'] for f in folds])))
        trials.append(record)
        print(f'h={horizon} trial={number+1}/{len(candidates)} CV RMSE={record["cv_rmse"]:.6f}', flush=True)
    best = min(trials, key=lambda t: t['cv_rmse'])
    model = estimator(best['params'], best['trees'])
    model.fit(development[columns], development.target, sample_weight=weights(development))
    predictions = test[['ticker', 'close', 'target', 'target_date']].copy()
    predictions['xgboost'] = model.predict(test[columns])
    predictions['zero_return'] = 0.
    predictions['historical_mean'] = float(development.target.mean())
    predictions['historical_median'] = float(development.target.median())
    predictions['actual_adjusted_price'] = predictions.close * np.exp(predictions.target)
    predictions['predicted_adjusted_price'] = predictions.close * np.exp(predictions.xgboost)
    names = ['xgboost', 'zero_return', 'historical_mean', 'historical_median']
    metrics = {name: score(test.target, predictions[name]) for name in names}
    per_stock = {ticker: {name: score(group.target, group[name]) for name in names}
                 for ticker, group in predictions.groupby('ticker')}
    metrics['xgboost']['price_mae'] = float((predictions.actual_adjusted_price-predictions.predicted_adjusted_price).abs().mean())
    metrics['xgboost']['price_mape'] = float(((predictions.actual_adjusted_price-predictions.predicted_adjusted_price).abs()/predictions.actual_adjusted_price).mean())
    # Nonoverlapping origin dates reduce, but do not remove, dependence in long-horizon errors.
    nonoverlap = predictions.groupby('ticker', group_keys=False).apply(lambda g: g.iloc[::horizon], include_groups=False)
    report = dict(horizon_sessions=horizon, features=columns, sources=sources, selection='macro stock RMSE over 3 chronological purged folds',
                  test_start=str(test_start.date()), train_rows=len(development), test_rows=len(test),
                  max_train_target=str(development.target_date.max()), held_out_tickers=args.holdout_tickers,
                  train_tickers=sorted(development.ticker.unique()), test_tickers=sorted(test.ticker.unique()),
                  best_trial=best, trials=trials, metrics=metrics, per_stock=per_stock,
                  nonoverlapping_test={n: score(nonoverlap.target, nonoverlap[n]) for n in names},
                  nonoverlapping_rows=len(nonoverlap),
                  versions=dict(python=platform.python_version(), xgboost=xgboost.__version__, pandas=pd.__version__, sklearn=sklearn.__version__))
    out.mkdir(parents=True)
    predictions.to_csv(out/'test_predictions.csv', index_label='Date')
    pd.Series(model.feature_importances_, index=columns).sort_values(ascending=False).to_csv(out/'feature_importance.csv')
    (out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    model.save_model(out/'model.ubj')
    joblib.dump(dict(model=model, feature_cols=columns, horizon=horizon, extended=not args.original_features,
                     train_end=str(development.index.max()), metrics=metrics), out/'model.joblib')
    print(json.dumps(dict(horizon=horizon, test_metrics=metrics, output=str(out)), indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default=str(ROOT/'data'))
    parser.add_argument('--output', default=str(ROOT/'artifacts'/'experiment'))
    parser.add_argument('--horizons', type=int, nargs='+', default=[1, 21, 252])
    parser.add_argument('--trials', type=int, default=12)
    parser.add_argument('--test-start', help='Fixed first test origin date, e.g. 2021-01-01')
    parser.add_argument('--tickers', nargs='+')
    parser.add_argument('--holdout-tickers', nargs='+', default=[])
    parser.add_argument('--original-features', action='store_true', help='Ablation: original 18 features')
    args = parser.parse_args()
    if args.trials < 1 or any(h < 1 for h in args.horizons):
        parser.error('trials and horizons must be positive')
    for horizon in args.horizons:
        train(args, horizon)
