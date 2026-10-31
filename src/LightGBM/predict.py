"""Inference for the independent daily, monthly and annual LightGBM artifacts."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
from src.helper.load_data import load_data
from src.helper.benchmark import ordered_features
from src.XGBoost.context_features import make_context_features
from src.LightGBM import MODEL_VERSION


def return_to_price(current_price, log_return):
    if not np.isfinite(current_price) or current_price <= 0 or not np.isfinite(log_return):
        raise ValueError("Price must be positive and return finite")
    with np.errstate(over="ignore", invalid="ignore"):
        price = float(current_price*np.exp(log_return))
    if not np.isfinite(price) or price <= 0:
        raise ValueError("Invalid implied price; regression outputs are not clipped")
    return price


def predict_features(artifact, frame):
    if artifact.get("algorithm") != "lightgbm" or artifact.get("model_version") != MODEL_VERSION:
        raise ValueError("Unsupported LightGBM artifact")
    features = ordered_features(frame, artifact["feature_cols"])
    values = artifact["model"].predict(features)*artifact["target_scale"]+artifact["target_center"]
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite forecasts")
    return values


def predict(history, model_path, ticker, context_dir=None):
    artifact = joblib.load(model_path)
    features, _ = make_context_features(history, artifact["horizon"], ticker,
                                       context_dir or artifact["context_dir"], artifact["feature_family"], include_target=False)
    if features.empty or features.index[-1] != history.index.max():
        raise ValueError("Latest stock row lacks eligible features; check history/context freshness")
    last = features.iloc[[-1]]
    log_return = float(predict_features(artifact, last)[0])
    current = float(last.close.iloc[0])
    return dict(ticker=ticker, stage=artifact["stage"], horizon_sessions=artifact["horizon"],
                as_of=str(last.index[-1].date()), predicted_log_return=log_return,
                predicted_return_pct=float(np.expm1(log_return)*100), current_adjusted_close=current,
                predicted_adjusted_price=return_to_price(current, log_return))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--context-dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(predict(load_data(args.history), args.model, args.ticker, args.context_dir), indent=2))
