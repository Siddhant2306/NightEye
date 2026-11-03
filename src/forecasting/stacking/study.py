"""Run with python -m src.forecasting.stacking.study."""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from filelock import FileLock
from src.LSTM.model import sequences
from src.feature_engineering_v2.inference import keys,predict_pair,task_frame
from src.feature_engineering_v2.models import tree_fit,lstm_fit
from src.forecasting.protocol import span,window
from src.forecasting.train import save_json
from src.forecasting.tcn import model as tcn
from src.forecasting.stacking.oof import audit,inner_split
from src.forecasting.ensemble import loss
from src.repair_study.study import SOURCE,COMPACT

ROOT=Path('artifacts/forecasting/tcn_stacking_v1')
REPAIR=Path('artifacts/forecasting/repair_study_v1')
MODELS=['xgboost','lightgbm','lstm','tcn']
PARAMS=dict(depth=2,leaf_min=50,l2=10.,learning_rate=.03,sample=.8)
LSTM=dict(hidden=16,dropout=.1,learning_rate=.001,weight_decay=.001,batch_size=512,direction_weight=.25)


def hash_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def initialize(root):
    root.mkdir(parents=True,exist_ok=True)
    if (root/'experiment_manifest.json').exists():return
    protocol=json.loads((SOURCE/'protocol.json').read_text())
    repair=json.loads((REPAIR/'design.json').read_text())
    assert protocol['boundaries']==repair['boundaries'] and protocol['held_out_companies']==repair['holdouts']
    protected={str(p.resolve()):hash_file(p) for folder in [SOURCE,REPAIR] for p in folder.rglob('*') if p.is_file()}
    protected.update(json.loads((SOURCE/'protected_originals.json').read_text()))
    save_json(root/'protected.json',protected)
    save_json(root/'experiment_manifest.json',dict(protocol=protocol,columns=COMPACT,tree=PARAMS,lstm=LSTM,tcn=tcn.CONFIGS,
        data_version=hash_file(SOURCE/'protocol.json'),feature_version=hash_file(SOURCE/'feature_registry.json'),
        checkpoint_policy='Inner chronological validation within each outer fold; same procedure at final fit',
        comparison_policy='Fresh fixed-procedure base models for combinations; saved repair benchmarks evaluated separately',
        test_status='Previously inspected retrospective test'))


def slice_keys(frame,wanted):
    positions=pd.Series(np.arange(len(frame)),index=keys(frame)).reindex(keys(wanted))
    if positions.isna().any():raise ValueError('Missing sequence or prediction key')
    return frame.iloc[positions.astype(int).to_numpy()]


def predict_bases(bundles,panel,wanted):
    returns=[];probabilities=[]
    for name in MODELS:
        bundle=bundles[name]
        if name=='tcn':
            seq=sequences(panel,bundle['columns'],bundle['config']['lookback'])
            result=tcn.predict(bundle,slice_keys(seq,wanted))
            returns.append(result[:,0]);probabilities.append(result[:,1])
        else:
            result=slice_keys(predict_pair(bundle,panel),wanted)
            returns.append(result.regression.to_numpy());probabilities.append(result.probability_up.to_numpy())
    return np.column_stack(returns),np.column_stack(probabilities)


def develop(root,h):
    manifest=json.loads((root/'experiment_manifest.json').read_text())
    edges={k:pd.Timestamp(v) for k,v in manifest['protocol']['boundaries'].items()}
    dev=joblib.load(SOURCE/'data'/f'development_h{h}.joblib')
    assert not dev.ticker.isin(manifest['protocol']['held_out_companies']).any()
    labeled=dev.dropna(subset=['target','target_date','risk_scale'])
    directory=root/f'h{h}';directory.mkdir(exist_ok=True)
    rows=[]
    for fold,cutoff,end in [(1,edges['fold1'],edges['fold2']),(2,edges['fold2'],edges['calibration']),(3,edges['calibration'],None)]:
        path=directory/f'fold{fold}.joblib'
        if path.exists():
            bundles,metadata=joblib.load(path)
        else:
            bundles={};metadata={}
            train,valid=inner_split(labeled,cutoff,h)
            for name in MODELS:
                if name in MODELS[:2]:
                    heads=[tree_fit(name,task,train,COMPACT,PARAMS,180,valid,20) for task in ['return','direction']]
                    bundles[name]=dict(regression=heads[0],direction=heads[1],calibrator=None)
                    tr,va=train,valid
                elif name=='lstm':
                    seq=sequences(dev,COMPACT,20)
                    tr,va=seq.loc[keys(seq).isin(keys(train))],slice_keys(seq,valid)
                    heads=lstm_fit(tr,va,COMPACT,LSTM,epochs=4,patience=2)
                    bundles[name]=dict(regression=heads['return'],direction=heads['direction'],calibrator=None)
                else:
                    candidates=[]
                    for config in tcn.CONFIGS:
                        seq=sequences(dev,COMPACT,config['lookback'])
                        tr=seq.loc[keys(seq).isin(keys(train))]
                        va=slice_keys(seq,valid)
                        model=tcn.fit(tr,va,COMPACT,config)
                        p=tcn.predict(model,va)
                        value=loss(va.target.to_numpy(),p[:,0],'return')/max(float(np.mean(va.target**2)),1e-10)
                        value+=loss(va.target.to_numpy(),p[:,1],'direction')
                        candidates.append((value,model,span(tr)))
                        print(f'h{h} fold{fold} TCN {config["lookback"]}: {value:.5f}',flush=True)
                    _,bundles[name],selected_span=min(candidates,key=lambda c:c[0])
                    save_json(directory/f'tcn_fold{fold}_trials.json',[dict(score=v,**{k:m[k] for k in ['config','curves','best_epoch','seconds','device']}) for v,m,_ in candidates])
                metadata[name]=dict(training=selected_span if name=='tcn' else span(tr),selection_latest_label=span(va)['latest_label'])
            joblib.dump((bundles,metadata),path,compress=3)
        if end is None:continue
        wanted=window(labeled,cutoff,end)
        returns,probs=predict_bases(bundles,dev,wanted)
        for i,name in enumerate(MODELS):
            info=metadata[name];training=info['training']
            rows.append(pd.DataFrame(dict(origin=wanted.index,ticker=wanted.ticker.to_numpy(),target_date=wanted.target_date.to_numpy(),
                target=wanted.target.to_numpy(),horizon=h,fold=fold,model=name,prediction_timestamp=wanted.index,
                regression=returns[:,i],probability_up=probs[:,i],training_start=training['first'],training_end=training['last'],
                training_rows=training['rows'],latest_training_label=training['latest_label'],
                selection_latest_label=info['selection_latest_label'],feature_hash=manifest['feature_version'],
                model_configuration_hash=joblib.hash(bundles[name]),data_version=manifest['data_version'])))
    oof=pd.concat(rows,ignore_index=True);audit(oof);oof.to_csv(directory/'oof.csv',index=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT)
    parser.add_argument('--horizon',type=int,choices=[1,21,252])
    parser.add_argument('--evaluate',action='store_true')
    args=parser.parse_args()
    args.output=args.output.resolve()
    if any(args.output.is_relative_to(folder.resolve()) or folder.resolve().is_relative_to(args.output)
           for folder in [SOURCE,REPAIR]):
        parser.error('Choose an isolated experiment directory outside the source studies')
    args.output.mkdir(parents=True,exist_ok=True)
    with FileLock(args.output/'.initialize.lock'):
        initialize(args.output)
    if not args.evaluate and not (args.output/'selection_frozen.json').exists():
        for h in [args.horizon] if args.horizon else [1,21,252]:
            with FileLock(args.output/f'.h{h}.lock'):
                if (args.output/'selection_frozen.json').exists():
                    raise ValueError('Experiment is frozen')
                develop(args.output,h)
    if args.horizon:return
    from src.forecasting.stacking.evaluate import run
    with ExitStack() as locks:
        for h in [1,21,252]:locks.enter_context(FileLock(args.output/f'.h{h}.lock'))
        run(args.output)


if __name__=='__main__':main()
