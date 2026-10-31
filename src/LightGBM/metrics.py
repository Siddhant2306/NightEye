"""Return errors, explicit direction/flat handling and date-dependent uncertainty."""
import numpy as np
import pandas as pd
from src.pipeline import score


def correlation(actual, prediction, rank=False):
    actual, prediction = np.asarray(actual), np.asarray(prediction)
    if len(actual) < 3 or np.ptp(actual) < 1e-12 or np.ptp(prediction) < 1e-12:
        return None
    if rank:
        actual = pd.Series(actual).rank().to_numpy()
        prediction = pd.Series(prediction).rank().to_numpy()
    value = float(np.corrcoef(actual, prediction)[0, 1])
    return value if np.isfinite(value) else None


def directional_metrics(actual, prediction):
    actual, prediction = np.sign(actual).astype(int), np.sign(prediction).astype(int)
    matrix = np.zeros((3, 3), dtype=int)
    np.add.at(matrix, (actual+1, prediction+1), 1)
    classes = {}
    for label, index in [("DOWN", 0), ("UP", 2)]:
        true_count, predicted_count = int(matrix[index].sum()), int(matrix[:, index].sum())
        correct = int(matrix[index, index])
        classes[label] = dict(precision=correct/predicted_count if predicted_count else 0.,
                              recall=correct/true_count if true_count else None,
                              precision_defined=predicted_count > 0, support=true_count,
                              predicted_count=predicted_count)
    recalls = [classes[name]["recall"] for name in ["DOWN", "UP"]]
    balanced = float(np.mean(recalls)) if all(r is not None for r in recalls) else None
    fraction = float((prediction > 0).mean())
    collapse = "all_UP" if (prediction > 0).all() else "all_DOWN" if (prediction < 0).all() else "mixed_or_flat"
    return dict(accuracy=float((actual == prediction).mean()), balanced_accuracy_nonflat=balanced,
                classes=classes, confusion_matrix=matrix.tolist(),
                confusion_labels=["DOWN", "FLAT", "UP"],
                confusion_orientation="rows=actual, columns=predicted",
                positive_prediction_fraction=fraction, negative_prediction_fraction=float((prediction < 0).mean()),
                flat_prediction_count=int((prediction == 0).sum()), flat_actual_count=int((actual == 0).sum()),
                collapse=collapse)


def summary_metrics(frame, name):
    actual, prediction = frame.target.to_numpy(), frame[name].to_numpy()
    result = score(actual, prediction)
    result.update(pearson=correlation(actual, prediction), spearman=correlation(actual, prediction, True))
    with np.errstate(over="ignore", invalid="ignore"):
        price_error = np.abs(np.expm1(prediction-actual)).mean()
    result["price_mape"] = float(price_error) if np.isfinite(price_error) else None
    result["macro_stock_rmse"] = float(np.mean([score(g.target, g[name])["rmse"] for _, g in frame.groupby("ticker")]))
    result["direction"] = directional_metrics(actual, prediction)
    return result


def block_samples(values, horizon, repeats=1000, seed=42):
    """Circular date blocks retain simultaneous cross-stock dependence and overlapping-label dependence."""
    values = np.asarray(values, dtype=float)
    n, block = len(values), max(21, horizon)
    if n < 2*block:
        return None, dict(dates=n, block_sessions=block, reason="fewer than two horizon-sized time blocks")
    rng = np.random.default_rng(seed)
    samples = []
    has_missing = np.isnan(values).any()
    for _ in range(repeats):
        starts = rng.integers(0, n, int(np.ceil(n/block)))
        indices = ((starts[:, None]+np.arange(block)) % n).ravel()[:n]
        sample = values[indices]
        if has_missing:
            counts = np.isfinite(sample).sum(axis=0)
            if np.any(counts == 0):
                continue
            samples.append(np.nansum(sample, axis=0)/counts)
        else:
            samples.append(sample.mean(axis=0))
    if not samples:
        return None, dict(dates=n, block_sessions=block, reason="No rankable observations in resampled blocks")
    return np.asarray(samples), dict(dates=n, block_sessions=block, repeats=repeats,
                                    caveat="Approximate; does not correct for repeated research or regime changes")


def paired_uncertainty(frame, candidate, reference, horizon):
    values = pd.DataFrame({
        "date": frame.index,
        "candidate_mae": abs(frame[candidate].to_numpy()-frame.target.to_numpy()),
        "reference_mae": abs(frame[reference].to_numpy()-frame.target.to_numpy()),
        "candidate_mse": (frame[candidate].to_numpy()-frame.target.to_numpy())**2,
        "reference_mse": (frame[reference].to_numpy()-frame.target.to_numpy())**2,
        "direction_difference": ((np.sign(frame[candidate].to_numpy()) == np.sign(frame.target.to_numpy())).astype(float)
                                 -(np.sign(frame[reference].to_numpy()) == np.sign(frame.target.to_numpy())).astype(float)),
    }).groupby("date").mean().to_numpy()
    samples, metadata = block_samples(values, horizon)
    result = dict(candidate=candidate, reference=reference, **metadata,
                  estimand="Difference in date-weighted cross-stock losses; negative error difference favors candidate",
                  mae_difference_ci95=None, rmse_difference_ci95=None, direction_difference_ci95=None)
    if samples is not None:
        for key, series in [
            ("mae_difference_ci95", samples[:, 0]-samples[:, 1]),
            ("rmse_difference_ci95", np.sqrt(samples[:, 2])-np.sqrt(samples[:, 3])),
            ("direction_difference_ci95", samples[:, 4]),
        ]:
            result[key] = np.quantile(series, [.025, .975]).tolist()
    return result


def ranking_metrics(frame, name, horizon):
    values = []
    eligible = 0
    for date, group in frame.groupby(level=0):
        value = None
        if len(group) >= 5:
            eligible += 1
            value = correlation(group.target, group[name], True)
        # Keep unrankable dates in the time axis; dropping them would compress label-overlap blocks.
        values.append(np.nan if value is None else value)
    values = np.asarray(values)
    count = int(np.isfinite(values).sum())
    coverage = dict(total_dates=len(values), eligible_dates=eligible, evaluated_dates=count,
                    evaluated_date_fraction=count/len(values) if len(values) else 0.)
    if not count:
        return dict(mean_rank_ic=None, mean_ic_ci95=None, **coverage,
                    reason="No dates with at least five stocks and nonconstant predictions/outcomes")
    samples, metadata = block_samples(values, horizon)
    finite=values[np.isfinite(values)]
    return dict(mean_rank_ic=float(finite.mean()), positive_ic_fraction=float((finite > 0).mean()), **coverage,
                mean_ic_ci95=np.quantile(samples, [.025, .975]).tolist() if samples is not None else None,
                **metadata, caveat_ranking="Cross-sectional Spearman IC, not a trading profitability measure")
