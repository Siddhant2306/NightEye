"""After-close, scale-free screenshot indicators; no external signals invented."""
import numpy as np
import pandas as pd
from src.XGBoost.context_features import make_context_features


def technical_features(history):
    h = history.sort_index()
    c, v = h.close, h.volume
    r = np.log(c).diff()
    out = pd.DataFrame(index=h.index)
    for w in (1, 5, 21, 63):
        out[f"tech_momentum_{w}"] = np.log(c/c.shift(w))
    for w in (5, 10, 20, 30, 63):
        out[f"tech_volatility_{w}"] = r.rolling(w).std()
    for w in (10, 20, 30):
        out[f"tech_ma_distance_{w}"] = c/c.rolling(w).mean()-1
    for w in (10, 30):
        out[f"tech_ema_distance_{w}"] = c/c.ewm(span=w, adjust=False).mean()-1
    change = c.diff()
    gain = change.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    loss = (-change.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    out["tech_rsi"] = (gain/(gain+loss)).fillna(0.5)
    macd = c.ewm(span=12, adjust=False).mean()-c.ewm(span=26, adjust=False).mean()
    out["tech_macd"] = macd/c
    out["tech_macd_signal"] = macd.ewm(span=9, adjust=False).mean()/c
    sd = c.rolling(20).std()
    out["tech_bollinger_z"] = (c-c.rolling(20).mean())/sd.replace(0, np.nan)
    out["tech_bollinger_width"] = 4*sd/c.rolling(20).mean()
    out["tech_relative_volume"] = v/v.rolling(20).mean().replace(0, np.nan)-1
    out["tech_volume_log_change"] = np.log1p(v).diff()
    out["tech_obv_pressure"] = (np.sign(c.diff())*v).rolling(20).sum()/v.rolling(20).sum().replace(0, np.nan)
    out["tech_overnight_gap"] = np.log(h.open/c.shift(1))
    out["tech_intraday_range"] = (h.high-h.low)/c
    out["tech_intraday_return"] = np.log(c/h.open)
    out["tech_weekday"] = h.index.day_of_week
    out["tech_month_sin"] = np.sin(2*np.pi*h.index.month/12)
    out["tech_month_cos"] = np.cos(2*np.pi*h.index.month/12)
    return out.replace([np.inf, -np.inf], np.nan)


def build(history, horizon, ticker, context_dir, include_target=True):
    frame, old = make_context_features(history, horizon, ticker, context_dir,
                                       "market_sector_fundamentals", include_target=include_target)
    tech = technical_features(history)
    frame = frame.join(tech)
    frame["risk_scale"] = tech.tech_volatility_20.reindex(frame.index).clip(lower=0.003)*np.sqrt(horizon)
    frame["ticker"] = ticker
    # Matched rows for both feature sets. Baseline reproduces the old chosen family.
    baseline = old[:5] if horizon == 1 else old
    return frame, {"existing": baseline, "technical_context": list(dict.fromkeys(old+list(tech.columns)))}
