
import numpy as np
import pandas as pd


def create_features(df, horizon=1, include_target=True, extended=True):
    if not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be a positive number of trading sessions")
    data = df.copy().sort_index()

    # ==========================================
    # 1. SHORT-TERM AND LONG-TERM MOMENTUM
    # ==========================================
    data["return_1d"] = data["close"].pct_change(1)
    data["return_5d"] = data["close"].pct_change(5)
    data["return_10d"] = data["close"].pct_change(10)
    data["return_20d"] = data["close"].pct_change(20)
    data["return_60d"] = data["close"].pct_change(60)

    # ==========================================
    # 2. HISTORICAL VOLATILITY
    # ==========================================
    data["volatility_10d"] = (
        data["return_1d"].rolling(10).std()
    )
    data["volatility_20d"] = (
        data["return_1d"].rolling(20).std()
    )
    data["volatility_60d"] = (
        data["return_1d"].rolling(60).std()
    )

    # ==========================================
    # 3. PRICE TREND / MOVING AVERAGES
    # ==========================================
    for window in [10, 20, 50, 200]:
        moving_average = data["close"].rolling(window).mean()

        data[f"ma_ratio_{window}d"] = (
            data["close"] / moving_average - 1
        )

    # ==========================================
    # 4. DAILY PRICE MOVEMENT
    # ==========================================
    data["intraday_range"] = (
        (data["high"] - data["low"]) / data["close"]
    )

    data["open_close_return"] = (
        data["close"] / data["open"] - 1
    )

    # ==========================================
    # 5. VOLUME FEATURES
    # ==========================================
    data["volume_change"] = data["volume"].pct_change()

    volume_avg_20d = data["volume"].rolling(20).mean()

    data["volume_ratio_20d"] = (
        data["volume"] / volume_avg_20d - 1
    )

    # ==========================================
    # 6. AVERAGE TRUE RANGE (ATR)
    # ==========================================
    previous_close = data["close"].shift(1)

    true_range = pd.concat(
        [
            data["high"] - data["low"],
            (data["high"] - previous_close).abs(),
            (data["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr_14d = true_range.rolling(14).mean()

    # Normalize ATR so it is comparable across price levels.
    data["atr_14d_pct"] = atr_14d / data["close"]

    # ==========================================
    # 7. RELATIVE STRENGTH INDEX (RSI)
    # ==========================================
    price_change = data["close"].diff()

    gains = price_change.clip(lower=0)
    losses = -price_change.clip(upper=0)

    avg_gain = gains.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False,
    ).mean()

    avg_loss = losses.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False,
    ).mean()

    # Handle zero losses without producing infinity.
    relative_strength = avg_gain / avg_loss.replace(0, np.nan)

    data["rsi_14d"] = (
        100 - (100 / (1 + relative_strength))
    )

    # RSI is 100 when average losses are zero but gains exist.
    data.loc[
        (avg_loss == 0) & (avg_gain > 0),
        "rsi_14d",
    ] = 100

    # ==========================================
    # 8. TARGET: NEXT TRADING DAY'S LOG RETURN
    # ==========================================
    data["target"] = np.log(
        data["close"].shift(-horizon) / data["close"]
    )

    data["target_date"] = pd.Series(
        data.index,
        index=data.index,
    ).shift(-horizon)

    # ==========================================
    # 9. FEATURES USED BY XGBOOST
    # ==========================================
    feature_cols = [
        # Momentum
        "return_1d",
        "return_5d",
        "return_10d",
        "return_20d",
        "return_60d",

        # Volatility
        "volatility_10d",
        "volatility_20d",
        "volatility_60d",

        # Trends
        "ma_ratio_10d",
        "ma_ratio_20d",
        "ma_ratio_50d",
        "ma_ratio_200d",

        # Daily movement
        "intraday_range",
        "open_close_return",

        # Volume
        "volume_change",
        "volume_ratio_20d",

        # Technical indicators
        "atr_14d_pct",
        "rsi_14d",
    ]

    data.loc[(avg_loss == 0) & (avg_gain == 0), "rsi_14d"] = 50
    if extended:
        for window in [5, 20, 60, 120, 252]:
            data[f"log_momentum_{window}"] = np.log(data.close / data.close.shift(window))
            data[f"downside_vol_{window}"] = data.return_1d.clip(upper=0).rolling(window).std()
        data["overnight_gap"] = data.open / previous_close - 1
        data["close_location"] = ((data.close - data.low) / (data.high - data.low).replace(0, np.nan)).fillna(0.5)
        data["volume_log_change"] = np.log1p(data.volume).diff()
        data["volatility_ratio"] = data.volatility_10d / data.volatility_60d.replace(0, np.nan)
        data["drawdown_252"] = data.close / data.close.rolling(252).max() - 1
        data["distance_low_252"] = data.close / data.close.rolling(252).min() - 1
        data["trend_spread"] = data.close.ewm(span=12, adjust=False).mean() / data.close.ewm(span=26, adjust=False).mean() - 1
        feature_cols += [c for c in data if c.startswith(("log_momentum_", "downside_vol_"))]
        feature_cols += ["overnight_gap", "close_location", "volume_log_change", "volatility_ratio", "drawdown_252", "distance_low_252", "trend_spread"]
    # Features use only information available after the current session closes.
    data = data.replace([np.inf, -np.inf], np.nan)

    data = data.dropna(
        subset=feature_cols + (["target", "target_date"] if include_target else [])
    )

    print(f"Features created: {len(feature_cols)}")
    print(f"Usable rows after feature engineering: {len(data)}")

    return data, feature_cols
