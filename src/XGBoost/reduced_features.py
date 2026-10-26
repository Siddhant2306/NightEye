"""Small predefined feature families, evaluated without test-driven feature selection."""
from pathlib import Path
import numpy as np
import pandas as pd
from src.XGBoost.feature_eng import create_features

CORE = ['return_1', 'return_21', 'return_63', 'std_21', 'std_63']
STATS = ['return_21', 'return_63', 'mean_21', 'median_21', 'std_21', 'mean_63', 'median_63', 'std_63']
FAMILIES = {
    'core': CORE,
    'statistics': STATS,
    'statistics_mode': STATS + ['mode_63'],
    'statistics_dividends': STATS + ['mode_63', 'dividend_yield_365', 'dividend_events_365'],
}


def binned_mode(values, bin_width=0.001):
    """Mode of returns rounded to fixed 10-basis-point bins; ties nearest zero, then lower.

    Exact modes of continuously valued returns are typically arbitrary. The bin width is
    fixed before validation and never estimated from the future or the test period.
    """
    bins, counts = np.unique(np.rint(np.asarray(values)/bin_width).astype(np.int64), return_counts=True)
    choices = bins[counts == counts.max()]
    winner = sorted(choices, key=lambda b: (abs(b), b))[0]
    return float(winner*bin_width)


def load_actions(path):
    actions = pd.read_csv(path, parse_dates=['Date']).set_index('Date').sort_index()
    if actions.index.has_duplicates:
        raise ValueError(f'Duplicate action dates in {path}')
    required = actions[['raw_close', 'dividend']]
    if required.isna().any().any() or not np.isfinite(required).all().all():
        raise ValueError(f'Missing/nonfinite action inputs in {path}')
    if (actions.raw_close <= 0).any() or (actions.dividend < 0).any():
        raise ValueError(f'Invalid action inputs in {path}')
    return actions


def point_in_time_valuation(frame, raw_close, path):
    """Join only earnings publications actually available at the 15:30 IST decision time.

    Input EPS must be trailing-twelve-month consolidated EPS in INR, aligned to the
    same split/share basis as raw_close. Fiscal period end is not publication time.
    No current .info P/E or retrospectively dated financial statements are accepted.
    """
    facts = pd.read_csv(path)
    required = {'available_at', 'period_end', 'eps_ttm', 'source', 'currency', 'share_basis'}
    if not required.issubset(facts.columns) or facts.empty:
        raise ValueError(f'{path} requires {sorted(required)} and actual historical publications')
    if facts[list(required)].isna().any().any():
        raise ValueError('Fundamental publication fields cannot be missing')
    if any(pd.Timestamp(value).tzinfo is None for value in facts.available_at):
        raise ValueError('Publication timestamps require an explicit timezone and release time')
    facts['available_at'] = pd.to_datetime(facts.available_at, utc=True, errors='raise')
    facts['period_end'] = pd.to_datetime(facts.period_end, utc=True, errors='raise')
    facts['eps_ttm'] = pd.to_numeric(facts.eps_ttm, errors='raise')
    if not np.isfinite(facts.eps_ttm).all():
        raise ValueError('EPS must be finite')
    if (facts.available_at < facts.period_end).any() or facts.available_at.duplicated().any():
        raise ValueError('Invalid/duplicate publication timestamps')
    if not (facts.currency == 'INR').all() or not (facts.share_basis == 'matches_raw_close').all():
        raise ValueError('EPS currency/share basis must match the stock price')
    decisions = pd.DataFrame({'decision_at': (frame.index.tz_localize('Asia/Kolkata') + pd.Timedelta(hours=15, minutes=30)).tz_convert('UTC')})
    joined = pd.merge_asof(decisions, facts.sort_values('available_at'),
                           left_on='decision_at', right_on='available_at', direction='backward')
    eps = pd.Series(joined.eps_ttm.to_numpy(), index=frame.index)
    age = (joined.decision_at - joined.available_at).dt.days.to_numpy()
    eps = eps.mask(age > 550)  # do not carry stale earnings indefinitely
    price = raw_close.reindex(frame.index)
    frame['earnings_yield_ttm'] = eps / price
    frame['pe_ttm'] = price / eps.where(eps > 0)
    return frame


def make_reduced_features(history, horizon, family, actions=None, fundamentals_path=None, include_target=True):
    if len(history) <= 252:
        raise ValueError('Need at least 253 clean sessions for the common warmup')
    if family == 'original':
        frame, columns = create_features(history, horizon, extended=False, include_target=include_target)
        return frame.loc[frame.index >= history.index[252]], columns
    if family not in FAMILIES and family != 'statistics_fundamentals':
        raise ValueError(f'Unknown feature family {family}')
    if horizon < 1:
        raise ValueError('horizon must be positive')
    if len(history) <= 252:
        raise ValueError('Need at least 253 clean sessions for the common warmup')
    frame = history.copy().sort_index()
    log_return = np.log(frame.close).diff()
    for window in [1, 21, 63]:
        frame[f'return_{window}'] = np.log(frame.close/frame.close.shift(window))
    for window in [21, 63]:
        roll = log_return.rolling(window)
        frame[f'mean_{window}'] = roll.mean()
        frame[f'median_{window}'] = roll.median()
        frame[f'std_{window}'] = roll.std()
    if family in ['statistics_mode', 'statistics_dividends', 'statistics_fundamentals']:
        frame['mode_63'] = log_return.rolling(63).apply(binned_mode, raw=True)
    columns = list(FAMILIES.get(family, FAMILIES['statistics_dividends']))
    if family in ['statistics_dividends', 'statistics_fundamentals']:
        if actions is None or not frame.index.isin(actions.index).all():
            raise ValueError('Complete historical dividend coverage is required; missing is not zero')
        # Ex-dividend cash already observed. No future or announced-yet-unpaid dividends.
        dividends = actions.dividend.reindex(frame.index)
        frame['dividend_yield_365'] = dividends.rolling('365D').sum() / actions.raw_close.reindex(frame.index)
        frame['dividend_events_365'] = (dividends>0).astype(float).rolling('365D').sum()
        if family == 'statistics_fundamentals':
            if fundamentals_path is None:
                raise ValueError('Historical EPS publications with available_at timestamps are required for P/E')
            frame = point_in_time_valuation(frame, actions.raw_close, fundamentals_path)
            columns += ['earnings_yield_ttm', 'pe_ttm']
    frame['target'] = np.log(frame.close.shift(-horizon)/frame.close)
    frame['target_date'] = pd.Series(frame.index, index=frame.index).shift(-horizon)
    frame = frame.loc[frame.index >= history.index[252]].replace([np.inf, -np.inf], np.nan)
    required = [c for c in columns if c not in ['pe_ttm', 'earnings_yield_ttm']]
    frame = frame.dropna(subset=required + (['target', 'target_date'] if include_target else []))
    return frame, columns
