"""Conservative baseline and optional, predeclared bounded validation-only search."""
import json
import numpy as np

BASE_PARAMS = dict(objective="regression", boosting_type="gbdt", n_estimators=500,
                   learning_rate=0.03, num_leaves=15, max_depth=5, min_child_samples=30,
                   subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.,
                   reg_alpha=0., random_state=42, verbosity=-1, n_jobs=4,
                   deterministic=True, force_col_wise=True, metric="rmse")
HORIZON_NAMES = {1: "daily", 21: "monthly", 252: "annual"}


def baseline_params(path=None):
    params = dict(BASE_PARAMS)
    if path:
        supplied = json.loads(path.read_text())
        if not isinstance(supplied, dict) or set(supplied) - set(params):
            raise ValueError("Config must contain supported LGBMRegressor parameter names")
        params.update(supplied)
    if params["objective"] != "regression" or params["boosting_type"] != "gbdt":
        raise ValueError("This benchmark supports gbdt regression only")
    if params["metric"] != "rmse":
        raise ValueError("Use RMSE for early stopping to preserve this benchmark's selection protocol")
    for key in ["n_estimators", "num_leaves", "min_child_samples", "n_jobs", "subsample_freq"]:
        if not isinstance(params[key], int) or params[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    if not isinstance(params["max_depth"], int) or params["max_depth"] < 1 or params["num_leaves"] > 2**params["max_depth"]:
        raise ValueError("Require positive max_depth and num_leaves <= 2**max_depth")
    for key in ["learning_rate", "subsample", "colsample_bytree"]:
        if not np.isfinite(params[key]) or not 0 < params[key] <= 1:
            raise ValueError(f"Invalid {key}")
    for key in ["reg_alpha", "reg_lambda"]:
        if not np.isfinite(params[key]) or params[key] < 0:
            raise ValueError(f"Invalid {key}")
    if not isinstance(params["random_state"], int):
        raise ValueError("random_state must be an integer")
    return params


def candidate_params(base, trials):
    if not 1 <= trials <= 16:
        raise ValueError("The bounded search supports 1–16 candidates including baseline")
    rng = np.random.default_rng(base["random_state"])
    choices = [dict(base)]
    while len(choices) < trials:
        leaves, depth = [(3, 2), (7, 3), (15, 5)][int(rng.integers(0, 3))]
        params = dict(base, num_leaves=leaves, max_depth=depth,
                      learning_rate=float(rng.choice([0.02, 0.03, 0.05])),
                      n_estimators=int(rng.choice([300, 500, 800])),
                      min_child_samples=int(rng.choice([30, 75, 150])),
                      subsample=float(rng.choice([0.65, 0.8, 1.])),
                      colsample_bytree=float(rng.choice([0.7, 0.8, 1.])),
                      reg_lambda=float(rng.choice([1., 10., 50.])),
                      reg_alpha=float(rng.choice([0., 0.1, 1.])))
        if params not in choices:
            choices.append(params)
    return choices
