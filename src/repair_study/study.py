"""Bounded one-factor repairs, frozen selection, then historical-test assessment."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import joblib
import numpy as np
import pandas as pd
from src.feature_engineering_v2.prepare import DEFAULT as SOURCE
from src.feature_engineering_v2.models import tree_fit,lstm_fit,predict
from src.feature_engineering_v2.inference import task_frame,keys
from src.feature_engineering_v2.calibration import guarded_calibrate,losses
from src.feature_engineering_v2.metrics import score
from src.forecasting.protocol import before,window,span
from src.forecasting.train import save_json
from src.forecasting.models import logit
from src.forecasting.uncertainty import residual_bank,interval
from src.helper.benchmark import observation_hash

DEFAULT=Path('artifacts/forecasting/repair_study_v1')
COMPACT=['v2_momentum_1','v2_momentum_5','v2_momentum_21','v2_momentum_63','v2_std_21','v2_std_63',
         'v2_ma_distance_20','v2_relative_volume_21','market_return_21','relative_market_21']
RECIPES=[dict(id='current',reuse=True),dict(id='fresh_control'),dict(id='compact',compact=True),
         dict(id='recent',recent=True),dict(id='risk_target',risk=True),
         dict(id='compact_recent',compact=True,recent=True),dict(id='compact_recent_risk',compact=True,recent=True,risk=True)]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root):
    protocol=json.loads((SOURCE/'protocol.json').read_text())
    source={str(p.resolve()):digest(p) for p in SOURCE.rglob('*') if p.is_file()}
    save_json(root/'protected.json',source)
    design=dict(source=str(SOURCE.resolve()),boundaries=protocol['boundaries'],holdouts=protocol['held_out_companies'],
        recipes=RECIPES,compact_columns=COMPACT,shrinkage=[0.,.25,.5,1.],direction_mixture=[0.,.5,1.],
        lstm_recipes=['current','fresh_control','return_only','compact_recent','compact_recent_risk'],
        primary='mean pooled validation RMSE; require each fold no worse than unchanged price; macro RMSE reported separately',
        direction='mean validation log loss; require each fold no worse than neutral .5; ties prefer neutral',
        rounds=400,patience=30,lstm_epochs=10,lstm_patience=2,recent_years=3,
        caveat='Previously inspected historical test; not independent proof. No new test-based choices. All nine selections frozen before this run reads test labels.')
    save_json(root/'design.json',design)
    review=Path(__file__).with_name('CODE_REVIEW.md')
    if review.exists():(root/'code_review.md').write_text(review.read_text(encoding='utf-8'),encoding='utf-8')
    inventory=[]
    for path in Path('src').rglob('*.py'):
        syntax=ast.parse(path.read_text(encoding='utf-8-sig'))
        inventory.append(dict(file=str(path),sha256=digest(path),functions=[n.name for n in syntax.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]))
    save_json(root/'code_inventory.json',inventory)
    findings=[]
    for h in [1,21,252]:
        frame=joblib.load(SOURCE/'data'/f'development_h{h}.joblib')
        training=before(frame.dropna(subset=['target','target_date']),pd.Timestamp(protocol['boundaries']['fold1']))
        cols=[c for c in training.select_dtypes(include='number') if c not in ['target','close','open','high','low','volume','risk_scale']]
        for c in cols:
            findings.append(dict(horizon=h,feature=c,training_missing=float(training[c].isna().mean()),unique_values=int(training[c].nunique()),training_std=float(training[c].std()) if training[c].notna().any() else None))
    pd.DataFrame(findings).to_csv(root/'feature_audit.csv',index=False)


def folds(frame,protocol):
    b={k:pd.Timestamp(v) for k,v in protocol['boundaries'].items()}
    return [(before(frame,start),window(frame,start,end)) for start,end in [(b['fold1'],b['fold2']),(b['fold2'],b['calibration'])]]


def fit_recipe(a,task,train,valid,columns,params,recipe,count=None):
    actual=train
    if recipe.get('recent'):actual=train.loc[train.index>=train.index.max()-pd.DateOffset(years=3)]
    tr=actual.copy();va=None if valid is None else valid.copy()
    risk=recipe.get('risk',False) and task=='return'
    if risk:
        tr['target']=tr.target/tr.risk_scale
        if va is not None:va['target']=va.target/va.risk_scale
    if a=='lstm':
        models=lstm_fit(tr,va,columns,params,epochs=count or 10,patience=2,
            final_checkpoints={task:count} if va is None else None)
        model=models[task]
    else:model=tree_fit(a,task,tr,columns,params,count or 400,va,30)
    model['output_risk_scaled']=risk
    model['fit_span']=span(actual)
    return model,span(actual)


def return_errors(frame,p):
    y=frame.target.to_numpy();return dict(rmse=float(np.sqrt(np.mean((p-y)**2))),macro_rmse=score(frame,p,'return')['macro_rmse'])


def select(trials,task):
    options=[t for t in trials if t['task']==task]
    neutral=next(t for t in options if t['recipe']=='neutral')
    base=np.array(neutral['fold_errors'])
    safe=[t for t in options if np.all(np.array(t['fold_errors'])<=base+1e-12)]
    best=min(safe,key=lambda t:(np.mean(t['fold_errors']),t['recipe']!='neutral',t.get('mix',0.)))
    absolute=min(options,key=lambda t:np.mean(t['fold_errors']))
    return dict(selected=best,absolute_minimum=absolute)


def develop(root,a):
    protocol=json.loads((SOURCE/'protocol.json').read_text())
    for h in [1,21,252]:
        directory=root/'development'/a/f'h{h}';directory.mkdir(parents=True,exist_ok=True)
        if (directory/'selection.json').exists():continue
        dev=joblib.load(SOURCE/'data'/f'development_h{h}.joblib')
        old=joblib.load(SOURCE/f'h{h}'/a/'model.joblib')
        previous=json.loads((SOURCE/'development'/a/f'h{h}'/'selection.json').read_text())
        source_options=json.loads((SOURCE/'development'/a/f'h{h}'/'all_results.json').read_text())
        base_return=next(o for o in source_options if o['id']==previous['return']['selected'])
        trials=[];zero_errors=[];neutral_errors=[]
        common=dev.dropna(subset=['target','target_date','risk_scale'])
        for _,v in folds(common,protocol):
            zero_errors.append(return_errors(v,np.zeros(len(v)))['rmse'])
            neutral_errors.append(losses(v.target,np.full(len(v),.5))['log_loss'])
        trials.extend([dict(task='return',recipe='neutral',mix=0.,fold_errors=zero_errors),dict(task='direction',recipe='neutral',mix=0.,fold_errors=neutral_errors)])
        proposals=RECIPES if a!='lstm' else [RECIPES[0],RECIPES[1],dict(id='return_only',return_only=True),
            dict(id='compact_recent',compact=True,recent=True),dict(id='compact_recent_risk',compact=True,recent=True,risk=True)]
        for recipe in proposals:
            rd=directory/recipe['id'];rd.mkdir(exist_ok=True)
            cache=rd/'trials.json'
            if cache.exists():trials+=json.loads(cache.read_text());continue
            task_predictions={'return':[],'direction':[]};checkpoints={'return':[],'direction':[]};metadata={}
            columns=COMPACT if recipe.get('compact') else old['regression']['columns']
            if a=='lstm':
                cfg=dict(old['regression']['config']);cfg['direction_weight']=0. if recipe.get('return_only') else .25
                lookback=old['regression']['lookback']
            else:cfg=base_return['params']['return'];lookback=0
            for fold,(tr0,v0) in enumerate(folds(common,protocol),1):
                existing=joblib.load(SOURCE/'development'/a/f'h{h}'/previous['return']['selected']/f'fold{fold}.joblib')['return']
                dmodel=joblib.load(SOURCE/'development'/a/f'h{h}'/previous['direction']['selected']/f'fold{fold}.joblib')['direction']
                if recipe.get('reuse'):model=existing;used_span=span(tr0)
                else:
                    if a=='lstm':
                        from src.LSTM.model import sequences
                        full=sequences(dev,columns,lookback).dropna(subset=['target','target_date','risk_scale'])
                        tr,v=folds(full,protocol)[fold-1]
                    else:tr,v=tr0,v0
                    model,used_span=fit_recipe(a,'return',tr,v,columns,cfg,recipe)
                # Build sequences before date filtering; retain every matched validation key.
                rp=task_frame(dev,model);vp=rp.loc[(rp.index>=v0.index.min())&(rp.index<=v0.index.max())].dropna(subset=['target','target_date','risk_scale'])
                vp=vp.iloc[pd.Series(np.arange(len(vp)),index=keys(vp)).reindex(keys(v0)).astype(int).to_numpy()]
                ret=predict(model,vp)
                if a=='lstm' or recipe.get('reuse') or recipe.get('risk') or recipe.get('return_only'):
                    dm=dmodel
                else:
                    dcols=COMPACT if recipe.get('compact') else old['direction']['columns']
                    selected=next(o for o in source_options if o['id']==previous['direction']['selected'])
                    dm,_=fit_recipe(a,'direction',tr0,v0,dcols,selected['params']['direction'],recipe)
                dp=task_frame(dev,dm);dp=dp.iloc[pd.Series(np.arange(len(dp)),index=keys(dp)).reindex(keys(v0)).astype(int).to_numpy()]
                probability=predict(dm,dp)
                task_predictions['return'].append((v0,ret));task_predictions['direction'].append((v0,probability))
                checkpoints['return'].append(model['rounds']);checkpoints['direction'].append(dm['rounds'])
                joblib.dump(dict(regression=model,direction=dm),rd/f'fold{fold}.joblib',compress=3)
                metadata[str(fold)]=dict(training=used_span,validation=span(v0))
            local=[]
            for mix in [.25,.5,1.]:
                for task in ['return','direction']:
                    values=[];macro=[]
                    for v,p in task_predictions[task]:
                        pp=mix*p if task=='return' else .5+mix*(p-.5)
                        if task=='return':e=return_errors(v,pp);values.append(e['rmse']);macro.append(e['macro_rmse'])
                        else:values.append(losses(v.target,pp)['log_loss'])
                    local.append(dict(task=task,recipe=recipe['id'],mix=mix,fold_errors=values,macro_errors=macro,checkpoints=checkpoints[task],
                        columns=columns,params=cfg,lookback=lookback,settings=recipe,fold_spans=metadata))
            save_json(cache,local);trials+=local
            print(f'{a} h{h} {recipe["id"]}: return {min(np.mean(t["fold_errors"]) for t in local if t["task"]=="return"):.6f}',flush=True)
        selection={t:select(trials,t) for t in ['return','direction']}
        save_json(directory/'trials.json',trials);save_json(directory/'selection.json',selection)
        print(f'SELECTED {a} h{h}: '+str({t:s['selected']['recipe'] for t,s in selection.items()}),flush=True)


def freeze(root):
    paths=[root/'development'/a/f'h{h}'/'selection.json' for a in ['xgboost','lightgbm','lstm'] for h in [1,21,252]]
    if not all(p.exists() for p in paths):raise ValueError('All nine validation searches must finish before test access')
    data={str(p.relative_to(root)):digest(p) for p in (root/'development').rglob('*') if p.is_file()}
    file=root/'selection_frozen.json'
    if file.exists():assert json.loads(file.read_text())['sha256']==data
    else:save_json(file,dict(sha256=data,frozen_at=pd.Timestamp.now(tz='UTC').isoformat()))


def final(root,a):
    freeze(root);protocol=json.loads((SOURCE/'protocol.json').read_text());edges={k:pd.Timestamp(v) for k,v in protocol['boundaries'].items()}
    for h in [1,21,252]:
        out=root/f'h{h}'/a;out.mkdir(parents=True,exist_ok=True)
        if (out/'metrics.json').exists():continue
        dev=joblib.load(SOURCE/'data'/f'development_h{h}.joblib');old=joblib.load(SOURCE/f'h{h}'/a/'model.joblib')
        selected=json.loads((root/'development'/a/f'h{h}'/'selection.json').read_text())
        heads={};calframes={};choices={}
        for task,key in [('return','regression'),('direction','direction')]:
            choice=selected[task]['selected'];choices[task]=choice
            if choice['recipe']=='neutral':
                heads[key]=dict(old[key],output_shrinkage=0.) if task=='return' else old[key]
            elif choice['recipe']=='current' or (task=='direction' and (choice['settings'].get('risk') or choice['settings'].get('return_only'))):heads[key]=old[key]
            else:
                recipe=choice['settings'];columns=choice['columns'] if task=='return' or recipe.get('compact') else old[key]['columns']
                params=choice['params']
                if a!='lstm' and task=='direction':
                    opts=json.loads((SOURCE/'development'/a/f'h{h}'/'all_results.json').read_text())
                    parent=json.loads((SOURCE/'development'/a/f'h{h}'/'selection.json').read_text())
                    params=next(o for o in opts if o['id']==parent['direction']['selected'])['params']['direction']
                temporary=dict(old[key],columns=columns)
                full=task_frame(dev,temporary).dropna(subset=['target','target_date','risk_scale'])
                training=before(full,edges['calibration'])
                count=max(1,int(np.median(choice['checkpoints'])))
                heads[key],_=fit_recipe(a,task,training,None,columns,params,recipe,count)
            full=task_frame(dev,heads[key]).dropna(subset=['target','target_date','risk_scale'])
            calframes[task]=window(full,edges['calibration'],edges['test'])
        heads['regression']['output_shrinkage']=choices['return']['mix']
        rcal=calframes['return'];dcal=calframes['direction']
        rp=predict(heads['regression'],rcal);raw=predict(heads['direction'],dcal)
        dmix=choices['direction']['mix'];raw=.5+dmix*(raw-.5)
        calibrator,guard=guarded_calibrate(raw,dcal,h) if dmix else (None,dict(accepted=False,reason='validation_selected_neutral_probability'))
        bank=residual_bank(rcal.target,rp,rcal.risk_scale)
        prior_frame=before(full,edges['calibration'])
        if heads['direction'].get('fit_span'):prior_frame=prior_frame.loc[prior_frame.index>=pd.Timestamp(heads['direction']['fit_span']['first'])]
        prior=float((prior_frame.target>0).mean())
        bundle=dict(old,**heads,calibrator=calibrator,residual_bank=bank,repair_choices=choices,direction_mixture=dmix,probability_calibration_check=guard,
            prior_probability=prior,splits=dict(old['splits'],training=heads['regression'].get('fit_span',old['splits']['training']),
                direction_training=heads['direction'].get('fit_span',old['splits']['direction_training']),calibration=span(rcal)))
        joblib.dump(bundle,out/'model.joblib',compress=3)
        save_json(out/'test_access.json',dict(at=pd.Timestamp.now(tz='UTC').isoformat(),frozen_sha256=digest(root/'selection_frozen.json')))
        # First access to final-test outcomes happens only after all selections freeze.
        actual=joblib.load(SOURCE/'data'/f'evaluation_h{h}.joblib').dropna(subset=['target','target_date','risk_scale'])
        assert observation_hash(actual)==old['splits']['test_keys_sha256'],'Test observations changed'
        full=joblib.load(SOURCE/'data'/f'unlabeled_h{h}.joblib');result=actual.copy()
        for task,key,column in [('return','regression','regression'),('direction','direction','raw_probability')]:
            panel=task_frame(full,heads[key]);positions=pd.Series(np.arange(len(panel)),index=keys(panel)).reindex(keys(actual))
            assert not positions.isna().any();part=panel.iloc[positions.astype(int).to_numpy()]
            result[column]=predict(heads[key],part)
        result['raw_probability']=.5+dmix*(result.raw_probability-.5)
        result['probability_up']=result.raw_probability if calibrator is None else calibrator.predict_proba(logit(result.raw_probability.to_numpy()))[:,1]
        restored=joblib.load(out/'model.joblib')
        from src.feature_engineering_v2.inference import predict_pair
        again=predict_pair(restored,full)
        positions=pd.Series(np.arange(len(again)),index=keys(again)).reindex(keys(actual))
        again=again.iloc[positions.astype(int).to_numpy()]
        for c in ['regression','raw_probability','probability_up']:
            # PyTorch float32 CPU kernels can differ by one ULP when inference
            # batch shapes differ (matched-test subset versus full-history API).
            np.testing.assert_allclose(result[c],again[c],rtol=1e-6 if a=='lstm' else 1e-8,atol=1e-7 if a=='lstm' else 1e-9)
        result['group']=np.where(result.ticker.isin(protocol['held_out_companies']),'unseen','seen')
        for coverage in [.5,.8,.95]:result[f'lower_{coverage}'],result[f'upper_{coverage}']=interval(result.regression,result.risk_scale,bank,coverage)
        metrics={}
        for group in ['all','seen','unseen']:
            p=result if group=='all' else result.loc[result.group==group]
            metrics[group]=dict(regression=score(p,p.regression,'return'),zero=score(p,np.zeros(len(p)),'return'),
                direction=score(p,p.probability_up,'direction'),raw_direction=score(p,p.raw_probability,'direction'),
                coverage80=float(((p.target>=p['lower_0.8'])&(p.target<=p['upper_0.8'])).mean()))
            m=metrics[group]
            m.update(rows=len(p),dates=int(p.index.nunique()),classifier=m['direction'],classifier_raw=m['raw_direction'],
                prior_classifier=score(p,np.full(len(p),prior),'direction'),
                intervals={str(c):dict(nominal_coverage=c,observed_coverage=float(((p.target>=p[f'lower_{c}'])&(p.target<=p[f'upper_{c}'])).mean()),
                    mean_log_return_width=float((p[f'upper_{c}']-p[f'lower_{c}']).mean())) for c in [.5,.8,.95]})
        result.to_csv(out/'test_predictions.csv',index_label='Date',float_format='%.17g');save_json(out/'metrics.json',metrics)
        save_json(out/'verification.json',dict(test_observations_matched=True,reloaded_batch_and_inference_predictions_matched=True,
            test_access_after_all_selections_frozen=True,rows=len(result),inference_float_precision='float32' if a=='lstm' else 'native'))
        print(f'FINAL {a} h{h}: RMSE {metrics["all"]["regression"]["rmse"]:.6f} / zero {metrics["all"]["zero"]["rmse"]:.6f}',flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=DEFAULT);p.add_argument('--stage',choices=['develop','final','run'],default='run');p.add_argument('--algorithm',choices=['xgboost','lightgbm','lstm']);args=p.parse_args();root=args.output.resolve()
    if args.stage=='develop':develop(root,args.algorithm);return
    if args.stage=='final':final(root,args.algorithm);return
    root.mkdir(parents=True,exist_ok=True);(root/'logs').mkdir(exist_ok=True)
    if not (root/'design.json').exists():audit(root)
    for stage in ['develop','final']:
        if stage=='final':freeze(root)
        def worker(a):
            with (root/'logs'/f'{stage}_{a}.log').open('w',encoding='utf-8') as stream:
                process=subprocess.run([sys.executable,'-u','-m','src.repair_study.study','--stage',stage,'--algorithm',a,'--output',str(root)],stdout=stream,stderr=subprocess.STDOUT)
            if process.returncode:raise RuntimeError(f'{stage} {a} failed; inspect log')
        with ThreadPoolExecutor(max_workers=3) as pool:
            for task in as_completed([pool.submit(worker,a) for a in ['xgboost','lightgbm','lstm']]):task.result()
    from src.repair_study.report import generate
    generate(root)
    changed=[p for p,d in json.loads((root/'protected.json').read_text()).items() if digest(Path(p))!=d]
    assert not changed,changed[:3]
    save_json(root/'verification.json',dict(original_benchmark_unchanged=True,selections_frozen=True,models=9))
    print(f'Completed {root}',flush=True)


if __name__=='__main__':main()
