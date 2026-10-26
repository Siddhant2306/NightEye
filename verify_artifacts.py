import json
from pathlib import Path
import joblib
import numpy as np
import xgboost as xgb
from src.helper.load_data import load_data
from src.XGBoost.feature_eng import create_features
from src.XGBoost.predict import predict

manifest=json.loads(Path('data/download_manifest.json').read_text())
print('Stocks:', len(manifest['records']), 'downloaded rows:', sum(r['rows'] for r in manifest['records']))
history=load_data('data/RELIANCE.NS_2000-01-01_to_2026-10-27.csv')
for path in Path('artifacts').glob('*/h*/report.json'):
    report=json.loads(path.read_text())
    assert report['max_train_target'] < report['test_start']
    for trial in report['trials']:
        for fold in trial['folds']:
            assert fold['max_train_target'] < fold['start']
    artifact=joblib.load(path.parent/'model.joblib')
    features, columns=create_features(history, artifact['horizon'], include_target=False, extended=artifact['extended'])
    model=xgb.XGBRegressor()
    model.load_model(path.parent/'model.ubj')
    np.testing.assert_allclose(model.predict(features[columns].tail(5)), artifact['model'].predict(features[columns].tail(5)))
    result=predict(history,path.parent/'model.joblib')
    assert np.isfinite(result['predicted_adjusted_price'])
    print(path, 'OK', result['as_of'], result['horizon_sessions'])
print('All artifact reload, boundary, and latest-row inference checks passed.')
