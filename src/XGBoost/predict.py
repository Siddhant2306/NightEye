"""Inference from raw daily history using exactly the training feature configuration."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
from src.helper.load_data import load_data
from src.XGBoost.feature_eng import create_features
from src.XGBoost.reduced_features import make_reduced_features, load_actions


def predict(history, model_path, actions=None, fundamentals_path=None):
    artifact = joblib.load(model_path)
    if 'feature_family' in artifact:
        features, _ = make_reduced_features(history, artifact['horizon'], artifact['feature_family'],
                                           actions, fundamentals_path, include_target=False)
    else:
        features, _ = create_features(history, artifact['horizon'], include_target=False, extended=artifact['extended'])
    if features.empty or features.index[-1] != history.index.max():
        raise ValueError('Latest row lacks valid features; supply at least 253 clean sessions')
    last = features.iloc[[-1]]
    log_return = float(artifact['model'].predict(last[artifact['feature_cols']])[0])
    log_return = log_return*artifact.get('target_scale', 1.) + artifact.get('target_center', 0.)
    return dict(as_of=str(last.index[0].date()), horizon_sessions=artifact['horizon'],
                predicted_log_return=log_return, predicted_return_pct=float(np.expm1(log_return)*100),
                current_adjusted_close=float(last.close.iloc[0]),
                predicted_adjusted_price=float(last.close.iloc[0]*np.exp(log_return)))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--history', type=Path, required=True)
    parser.add_argument('--actions', type=Path, help='Historical raw_close and dividend CSV for dividend features')
    parser.add_argument('--fundamentals', type=Path, help='Point-in-time EPS publication CSV for valuation features')
    args = parser.parse_args()
    print(json.dumps(predict(load_data(args.history), args.model,
                             load_actions(args.actions) if args.actions else None, args.fundamentals), indent=2))
