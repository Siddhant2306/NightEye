"""Verify frozen reduced-feature artifacts after the complete experiment."""
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from src.pipeline import ROOT
from src.helper.load_data import load_data
from src.XGBoost.reduced_features import make_reduced_features, load_actions
from src.XGBoost.predict import predict


def main():
    directory = ROOT/'artifacts'/'reduced_v2'
    selection = json.loads((directory/'selected.json').read_text())
    protocol = json.loads((directory/'protocol.json').read_text())
    records = list(directory.glob('*/h*/report.json'))
    assert len(records) == len(protocol['families'])*len(protocol['horizons'])
    history = load_data(ROOT/'data'/'research_v2'/'RELIANCE.NS_2000-01-01_to_2026-10-27.csv')
    actions = load_actions(ROOT/'data'/'research_v2'/'actions'/'RELIANCE.NS.csv')
    keys = {}
    for path in records:
        report = json.loads(path.read_text())
        assert not set(report['train_tickers']).intersection(report['holdout_tickers'])
        assert pd.Timestamp(report['max_train_target']) < pd.Timestamp(report['test_start'])
        for trial in report['trials']:
            for fold in trial['folds']:
                assert pd.Timestamp(fold['max_train_target']) < pd.Timestamp(fold['start'])
                assert pd.Timestamp(fold['max_validation_target']) < pd.Timestamp(fold['end'])
        keys.setdefault(report['horizon'], set()).add(report['test_keys_sha256'])
        artifact = joblib.load(path.parent/'model.joblib')
        features, columns = make_reduced_features(history, report['horizon'], report['family'], actions)
        saved = pd.read_csv(path.parent/'test_predictions.csv', parse_dates=['Date']).set_index('Date')
        saved = saved.loc[saved.ticker=='RELIANCE.NS'].tail(5)
        x = features.loc[saved.index, columns]
        prediction = artifact['model'].predict(x)*artifact['target_scale']+artifact['target_center']
        np.testing.assert_allclose(prediction, saved.xgboost, rtol=1e-5, atol=1e-7)
        native = XGBRegressor()
        native.load_model(path.parent/'model.ubj')
        np.testing.assert_allclose(native.predict(x), artifact['model'].predict(x))
        latest = predict(history, path.parent/'model.joblib', actions)
        assert latest['as_of'] == str(history.index.max().date())
        assert np.isfinite(latest['predicted_adjusted_price'])
        print(f'{report["family"]} h={report["horizon"]}: boundaries, reloaded predictions, inverse scaling, inference OK')
    assert all(len(values)==1 for values in keys.values())
    for horizon, choice in selection.items():
        reports = [json.loads(p.read_text()) for p in records if p.parent.name==f'h{horizon}']
        expected = min(reports, key=lambda r:r['best_trial']['cv_rmse'])
        assert expected['family']==choice['family']
    result = dict(verified_models=len(records), common_samples=True, holdout_exclusion=True,
                  purged_boundaries=True, inverse_scaling=True, native_reload=True,
                  latest_row_inference=True, validation_only_family_selection=True)
    (directory/'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
