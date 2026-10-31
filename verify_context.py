"""Check the complete context experiment against frozen sources and reloaded models."""
import hashlib
import json
from types import SimpleNamespace
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from src.pipeline import ROOT
from src.research_context import prepare
from src.XGBoost.context_features import COMPANY, VALUATION
from src.XGBoost.predict import predict
from src.helper.load_data import load_data


def main():
    directory=ROOT/'artifacts'/'context_v3'
    protocol=json.loads((directory/'protocol.json').read_text())
    selection=json.loads((directory/'selected.json').read_text())
    context_dir=ROOT/'data'/'context_v3'
    for path,expected in protocol['context_hashes'].items():
        assert hashlib.sha256((context_dir/path).read_bytes()).hexdigest()==expected
    args=SimpleNamespace(data_dir=ROOT/'data'/'research_v2',context_dir=context_dir)
    coverage=[]; count=0
    history=load_data(next(args.data_dir.glob('RELIANCE.NS_*.csv')))
    for h in protocol['horizons']:
        data,_,_=prepare(args,h)
        indexed=data.reset_index(names='Date').set_index(['Date','ticker'])
        eligible=[]; trial_scores=[]
        for family in protocol['families']:
            path=directory/family/f'h{h}'
            report=json.loads((path/'report.json').read_text())
            assert not set(report['train_tickers']).intersection(protocol['held_out_tickers'])
            assert pd.Timestamp(report['max_train_target'])<pd.Timestamp(protocol['test_start'])
            for trial in report['trials']:
                for fold in trial['folds']:
                    assert pd.Timestamp(fold['max_train_target'])<pd.Timestamp(fold['start'])
                    assert pd.Timestamp(fold['max_validation_target'])<pd.Timestamp(fold['end'])
            eligible.append(report['test_keys_sha256'])
            trial_scores.append((family,report['best_trial']['cv_rmse']))
            artifact=joblib.load(path/'model.joblib')
            saved=pd.read_csv(path/'test_predictions.csv',parse_dates=['Date','target_date'])
            x=indexed.reindex(pd.MultiIndex.from_frame(saved[['Date','ticker']]))[artifact['feature_cols']]
            pred=artifact['model'].predict(x)*artifact['target_scale']+artifact['target_center']
            np.testing.assert_allclose(pred,saved.xgboost,rtol=1e-5,atol=1e-7)
            native=XGBRegressor(); native.load_model(path/'model.ubj')
            np.testing.assert_allclose(native.predict(x.tail(100)),artifact['model'].predict(x.tail(100)))
            latest=predict(history,path/'model.joblib',ticker='RELIANCE.NS',context_dir=context_dir)
            assert latest['as_of']==str(history.index.max().date())
            assert np.isfinite(latest['predicted_adjusted_price'])
            count+=1
            print(f'{family} h={h}: all saved predictions, native reload, scaling, boundaries and latest inference OK',flush=True)
        assert len(set(eligible))==1
        assert min(trial_scores,key=lambda x:x[1])[0]==selection[str(h)]['family']
        for name,mask in [
            ('development',(data.index<pd.Timestamp(protocol['test_start'])) & (data.target_date<pd.Timestamp(protocol['test_start'])) & ~data.ticker.isin(protocol['held_out_tickers'])),
            ('test_seen',(data.index>=pd.Timestamp(protocol['test_start'])) & ~data.ticker.isin(protocol['held_out_tickers'])),
            ('test_unseen',(data.index>=pd.Timestamp(protocol['test_start'])) & data.ticker.isin(protocol['held_out_tickers'])),
        ]:
            group=data.loc[mask]
            coverage.append(dict(horizon=h,split=name,rows=len(group),features={c:float(group[c].notna().mean()) for c in COMPANY+VALUATION}))
    (directory/'coverage.json').write_text(json.dumps(coverage,indent=2))
    result=dict(verified_models=count,source_snapshot_unchanged=True,common_samples=True,
                held_out_exclusion=True,purged_labels=True,all_saved_predictions_reproduced=True,
                native_model_reload=True,target_scaling=True,latest_row_inference=True,validation_only_selection=True)
    (directory/'verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
