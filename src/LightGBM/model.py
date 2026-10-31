"""Native missing-value handling; no feature scaling or test-based preprocessing."""
import inspect
import numpy as np
import lightgbm as lgb
from src.helper.benchmark import ordered_features
from src.pipeline import weights


def fit_model(frame, columns, params, valid=None, stopping_rounds=50, trees=None):
    center = float(frame.target.mean())
    scale = max(float(frame.target.std()), 1e-8)
    effective = dict(params)
    if trees is not None:
        effective["n_estimators"] = int(trees)
    model = lgb.LGBMRegressor(**effective)
    kwargs = dict(sample_weight=weights(frame), callbacks=[lgb.log_evaluation(0)])
    if valid is not None:
        validation_X = ordered_features(valid, columns)
        validation_y = (valid.target-center)/scale
        if "eval_X" in inspect.signature(lgb.LGBMRegressor.fit).parameters:
            kwargs.update(eval_X=validation_X, eval_y=validation_y)
        else:  # LightGBM 4.5/4.6 compatibility.
            kwargs["eval_set"] = [(validation_X, validation_y)]
        kwargs["eval_metric"] = "rmse"
        kwargs["callbacks"].append(lgb.early_stopping(stopping_rounds, first_metric_only=True, verbose=False))
    model.fit(ordered_features(frame, columns), (frame.target-center)/scale, **kwargs)
    return model, center, scale


def predict_returns(model, frame, columns, center, scale):
    prediction = model.predict(ordered_features(frame, columns)) * scale + center
    if not np.isfinite(prediction).all():
        raise ValueError("Nonfinite LightGBM forecasts")
    return prediction
