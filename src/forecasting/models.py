"""Two algorithms, separate squared-error and binary-log-loss objectives."""
import numpy as np
import lightgbm as lgb
from xgboost import XGBClassifier, XGBRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss
from src.helper.benchmark import ordered_features
from src.pipeline import weights


def candidates(count):
    if not 1 <= count <= 16:
        raise ValueError("Use 1..16 predeclared configurations per feature family")
    rng = np.random.default_rng(42)
    result = [dict(depth=2, leaf_min=75, l2=30., learning_rate=.03, sample=.8)]
    while len(result) < count:
        p = dict(depth=int(rng.choice([1, 2, 3, 4])), leaf_min=int(rng.choice([30, 75, 150])),
                 l2=float(rng.choice([1, 10, 30, 100])), learning_rate=float(rng.choice([.015, .03, .05])),
                 sample=float(rng.choice([.65, .8, 1.])))
        if p not in result:
            result.append(p)
    return result


def fit(algorithm, task, frame, columns, params, rounds, valid=None, patience=40):
    classification = task == "direction"
    center = 0. if classification else float(frame.target.mean())
    scale = 1. if classification else max(float(frame.target.std()), 1e-8)
    y = (frame.target > 0).astype(int) if classification else (frame.target-center)/scale
    if classification and y.nunique() != 2:
        raise ValueError("Direction fitting requires both classes")
    X = ordered_features(frame, columns)
    val_y = None if valid is None else ((valid.target > 0).astype(int) if classification else (valid.target-center)/scale)
    common = dict(learning_rate=params["learning_rate"], max_depth=params["depth"],
                  subsample=params["sample"], colsample_bytree=.8, reg_lambda=params["l2"],
                  reg_alpha=.1, random_state=42, n_jobs=4)
    if algorithm == "xgboost":
        constructor = XGBClassifier if classification else XGBRegressor
        model = constructor(**common, n_estimators=rounds, tree_method="hist",
                            min_child_weight=params["leaf_min"],
                            objective="binary:logistic" if classification else "reg:squarederror",
                            eval_metric="logloss" if classification else "rmse",
                            early_stopping_rounds=patience if valid is not None else None)
        kwargs = {} if valid is None else dict(eval_set=[(ordered_features(valid, columns), val_y)], verbose=False)
        model.fit(X, y, sample_weight=weights(frame), **kwargs)
        trees = model.best_iteration+1 if valid is not None else rounds
        learning = model.evals_result() if valid is not None else {}
    elif algorithm == "lightgbm":
        config = dict(objective="binary" if classification else "regression",
                      metric="binary_logloss" if classification else "rmse", verbosity=-1,
                      num_leaves=2**params["depth"], min_child_samples=params["leaf_min"],
                      subsample_freq=1, deterministic=True, force_col_wise=True, **common)
        training = lgb.Dataset(X, label=y, weight=weights(frame))
        learning = {}
        callbacks = [lgb.log_evaluation(0), lgb.record_evaluation(learning)]
        kwargs = {}
        if valid is not None:
            callbacks += [lgb.early_stopping(patience, first_metric_only=True, verbose=False)]
            kwargs["valid_sets"] = [lgb.Dataset(ordered_features(valid, columns), label=val_y, reference=training)]
            kwargs["valid_names"] = ["validation"]
        model = lgb.train(config, training, num_boost_round=rounds, callbacks=callbacks, **kwargs)
        trees = model.best_iteration if valid is not None else model.current_iteration()
    else:
        raise ValueError(algorithm)
    return dict(model=model, algorithm=algorithm, task=task, columns=columns, center=center,
                scale=scale, rounds=int(max(1, trees)), learning_curve=learning)


def raw_predict(bundle, frame):
    if bundle["algorithm"] == "lstm":
        from src.LSTM.model import predict
        return predict(bundle, frame)
    X = ordered_features(frame, bundle["columns"])
    model = bundle["model"]
    if bundle["task"] == "direction" and bundle["algorithm"] == "xgboost":
        pred = model.predict_proba(X)[:, 1]
    elif bundle["algorithm"] == "lightgbm":
        pred = model.predict(X, num_threads=4)
    else:
        pred = model.predict(X)
    pred = np.asarray(pred)*bundle["scale"]+bundle["center"]
    if not np.isfinite(pred).all():
        raise ValueError("Nonfinite prediction")
    return pred


def logit(probability):
    p = np.clip(probability, 1e-6, 1-1e-6)
    return np.log(p/(1-p)).reshape(-1, 1)


def calibrate(probability, actual):
    """Fit only on later calibration observations, never model-fit or final test rows."""
    y = np.asarray(actual) > 0
    if len(y) < 100 or len(np.unique(y)) != 2:
        return None
    return LogisticRegression(C=1., random_state=42).fit(logit(probability), y)


def probability(bundle, frame, calibrator):
    p = raw_predict(bundle, frame)
    return p if calibrator is None else calibrator.predict_proba(logit(p))[:, 1]


def direction_metrics(actual, p, threshold=.60):
    y = np.asarray(actual) > 0
    p = np.asarray(p)
    predicted = p >= .5
    up, down = p >= threshold, p <= 1-threshold
    selected = up | down
    bins = []
    for lower in np.arange(0, 1, .1):
        mask = (p >= lower) & (p < lower+.1 if lower < .9 else p <= 1)
        if mask.any():
            bins.append(dict(lower=float(lower), rows=int(mask.sum()),
                             mean_probability=float(p[mask].mean()), up_frequency=float(y[mask].mean())))
    balanced = float((predicted[y].mean()+(~predicted[~y]).mean())/2) if y.any() and (~y).any() else None
    return dict(accuracy=float((predicted == y).mean()), balanced_accuracy=balanced,
                up_precision=float(y[predicted].mean()) if predicted.any() else None,
                up_recall=float(predicted[y].mean()) if y.any() else None,
                not_up_recall=float((~predicted[~y]).mean()) if (~y).any() else None,
                up_prediction_fraction=float(predicted.mean()), always_up_accuracy=float(y.mean()),
                log_loss=float(log_loss(y, np.clip(p, 1e-6, 1-1e-6), labels=[0, 1])),
                brier=float(brier_score_loss(y, p)), reliability_bins=bins,
                signal_threshold=threshold, signal_coverage=float(selected.mean()),
                signal_count=int(selected.sum()), up_signal_count=int(up.sum()),
                up_signal_precision=float(y[up].mean()) if up.any() else None,
                not_up_signal_precision=float((~y[down]).mean()) if down.any() else None,
                signal_accuracy=float((up[selected] == y[selected]).mean()) if selected.any() else None,
                label_definition="UP = log return > 0; NOT_UP includes exactly flat outcomes")
