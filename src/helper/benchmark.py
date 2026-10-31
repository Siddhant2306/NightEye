"""Algorithm-independent checks for frozen stock-forecast comparisons."""
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from src.pipeline import purged_split


def context_hashes(directory):
    directory = Path(directory)
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for sub in ["indices", "fundamentals"] for path in sorted((directory / sub).glob("*.csv"))}


def observation_hash(frame):
    text = "|".join(f"{date.isoformat()}:{ticker}" for date, ticker in zip(frame.index, frame.ticker))
    return hashlib.sha256(text.encode()).hexdigest()


def ordered_features(frame, columns):
    if frame.columns.duplicated().any():
        raise ValueError("Input columns must be unique")
    if not columns or len(columns) != len(set(columns)):
        raise ValueError("Feature names must be nonempty and unique")
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing model features: {sorted(missing)}")
    result = frame.loc[:, columns]
    if not all(pd.api.types.is_numeric_dtype(dtype) for dtype in result.dtypes):
        raise ValueError("Only numeric features are supported")
    if np.isinf(result.to_numpy(dtype=float)).any():
        raise ValueError("Infinite features are invalid; NaN is allowed")
    return result


def development_split(data, boundary, holdouts):
    boundary = pd.Timestamp(boundary)
    development = data.loc[(data.index < boundary) & (data.target_date < boundary)
                           & ~data.ticker.isin(holdouts)]
    test = data.loc[data.index >= boundary].copy()
    if development.empty or test.empty or set(holdouts) - set(test.ticker):
        raise ValueError("Empty split or missing held-out companies")
    return development, test


def validation_folds(development, edges):
    """Reuse strict target-date purging; no extra embargo is added to the XGBoost protocol."""
    for start, end in zip(edges[:-1], edges[1:]):
        fit, valid = purged_split(development, pd.Timestamp(start), pd.Timestamp(end))
        yield fit, valid, dict(start=start, end=end, train_rows=len(fit), validation_rows=len(valid),
                              max_train_target=str(fit.target_date.max()),
                              max_validation_target=str(valid.target_date.max()),
                              train_keys_sha256=observation_hash(fit),
                              validation_keys_sha256=observation_hash(valid))


def align_reference(frame, reference, name="xgboost", prediction_column="xgboost"):
    """Match exact stock/date/outcome observations; fail instead of comparing different tests."""
    keys = ["Date", "ticker"]
    left = frame.reset_index(names="Date")
    if left.duplicated(keys).any() or reference.duplicated(keys).any():
        raise ValueError("Duplicate stock/date observations")
    expected = pd.MultiIndex.from_frame(left[keys])
    indexed = reference.set_index(keys)
    if len(indexed) != len(left) or not expected.isin(indexed.index).all():
        raise ValueError("Reference test observations differ")
    aligned = indexed.reindex(expected)
    for column in ["target", "close"]:
        if not np.allclose(left[column], aligned[column], rtol=1e-10, atol=1e-12):
            raise ValueError(f"Reference {column} values differ")
    if not np.array_equal(left.group.to_numpy(), aligned.group.to_numpy()):
        raise ValueError("Reference held-out groups differ")
    if not np.array_equal(pd.to_datetime(left.target_date).to_numpy(), pd.to_datetime(aligned.target_date).to_numpy()):
        raise ValueError("Reference target dates differ")
    predictions = aligned[prediction_column].to_numpy()
    if not np.isfinite(predictions).all():
        raise ValueError("Nonfinite reference predictions")
    result = frame.copy()
    result[name] = predictions
    return result
