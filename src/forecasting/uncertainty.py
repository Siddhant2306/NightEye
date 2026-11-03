"""Calibration-residual endpoint scenarios plus empirical daily bridge paths.

Intervals are empirical, volatility-scaled, and tested for coverage. No IID or
distribution-free coverage claim is made for overlapping financial time series.
"""
import numpy as np


def residual_bank(actual, prediction, risk_scale):
    bank = (np.asarray(actual)-np.asarray(prediction))/np.asarray(risk_scale)
    if len(bank) < 100 or not np.isfinite(bank).all():
        raise ValueError("Need at least 100 finite out-of-fit calibration residuals")
    return bank


def interval(prediction, risk_scale, bank, coverage=.80):
    tail = (1-coverage)/2
    lo, hi = np.quantile(bank, [tail, 1-tail])
    return np.asarray(prediction)+np.asarray(risk_scale)*lo, np.asarray(prediction)+np.asarray(risk_scale)*hi


def interval_metrics(actual, prediction, risk_scale, bank):
    result = {}
    for coverage in (.5, .8, .95):
        lower, upper = interval(prediction, risk_scale, bank, coverage)
        result[str(coverage)] = dict(nominal_coverage=coverage,
            observed_coverage=float(np.mean((actual >= lower) & (actual <= upper))),
            mean_log_return_width=float(np.mean(upper-lower)))
    return result


def simulate(current, prediction, risk_scale, bank, daily_returns, horizon, paths=5000, seed=42):
    if horizon < 1 or not 100 <= paths <= 50000 or current <= 0 or not np.isfinite([current, prediction, risk_scale]).all() or risk_scale <= 0:
        raise ValueError("Invalid simulation inputs; use 100..50000 paths and positive price/risk")
    rng = np.random.default_rng(seed)
    daily = np.asarray(daily_returns)
    daily = daily[np.isfinite(daily)]
    if len(daily) < 63 or len(bank) < 100 or not np.isfinite(bank).all():
        raise ValueError("Insufficient finite scenario history/calibration")
    terminal = prediction+rng.choice(bank, size=paths)*risk_scale
    block = min(5, len(daily))
    starts = rng.integers(0, len(daily), size=(paths, int(np.ceil(horizon/block))))
    indices = ((starts[:, :, None]+np.arange(block)) % len(daily)).reshape(paths, -1)[:, :horizon]
    innovations = daily[indices]-daily.mean()
    innovations *= (risk_scale/np.sqrt(horizon))/max(float(daily.std()), 1e-8)
    cumulative = np.cumsum(innovations, axis=1)
    time = np.arange(1, horizon+1)/horizon
    bridge = cumulative-cumulative[:, [-1]]*time[None, :]
    logs = bridge+terminal[:, None]*time[None, :]
    with np.errstate(over="raise", invalid="raise"):
        prices = current*np.exp(np.column_stack([np.zeros(paths), logs]))
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("Nonfinite scenario paths; no clipping applied")
    ending = prices[:, -1]
    quantiles = np.quantile(ending, [.025, .10, .25, .50, .75, .90, .975])
    result = dict(paths=paths, seed=seed, method="Volatility-scaled calibration residual endpoints; 5-session empirical return bridges",
                  forecast_adjusted_price=float(current*np.exp(prediction)),
                  median_scenario_price=float(quantiles[3]),
                  terminal_price_quantiles=dict(zip(["p2_5", "p10", "p25", "p50", "p75", "p90", "p97_5"], map(float, quantiles))),
                  scenario_probability_up=float((ending > current).mean()),
                  scenario_probability_loss_over_10pct=float((ending < .9*current).mean()),
                  scenario_mean_max_drawdown=float(np.mean(np.min(prices/np.maximum.accumulate(prices, axis=1)-1, axis=1))),
                  caveat="Scenario frequencies depend on the residual/volatility assumptions; path drawdowns are illustrative, not calibrated")
    return result, prices
