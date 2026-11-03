"""Frozen OOF combinations evaluated on matched historical observations."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from src.feature_engineering_v2.calibration import guarded_calibrate
from src.feature_engineering_v2.inference import predict_pair
from src.feature_engineering_v2.metrics import score
from src.forecasting.backtest import run_strategy
from src.forecasting.models import logit
from src.forecasting.protocol import window
from src.forecasting.train import load_histories,save_json
from src.forecasting.uncertainty import residual_bank,interval,simulate
from src.helper.benchmark import observation_hash
from src.LightGBM.metrics import paired_uncertainty
from src.forecasting.stacking import meta
from src.forecasting.stacking.oof import aligned,audit
from src.forecasting.stacking.study import MODELS,SOURCE,REPAIR,PARAMS,predict_bases,slice_keys,hash_file


def predictions(bundles,fitted,panel,wanted):
    r,p=predict_bases(bundles,panel,wanted)
    return {**{name:(r[:,i],p[:,i]) for i,name in enumerate(MODELS)},**meta.combine(fitted,r,p)}


def scenario_selection(m,r,config):
    later=m.fold.to_numpy()==2
    target=m.target.to_numpy()[later]
    individual=min(range(len(MODELS)),key=lambda i:np.mean((r[later,i]-target)**2))
    candidates={'equal':float(np.mean((r[later].mean(axis=1)-target)**2)),
                'equal_without_tcn':float(np.mean((r[later,:3].mean(axis=1)-target)**2))}
    for name in ['weighted','linear_stack','lightgbm_stack']:
        trial=config.get('trials',{}).get(f'{name}_return')
        if trial:candidates[name]=trial['selected']['loss']
    return [MODELS[individual],min(candidates,key=candidates.get)]


def verify_freeze(root):
    path=root/'selection_frozen.json'
    if not path.exists():raise ValueError('Freeze every horizon before accessing test labels')
    frozen=json.loads(path.read_text())
    if any(hash_file(root/p)!=d for p,d in frozen['sha256'].items()):
        raise ValueError('A frozen selection or checkpoint changed')
    return frozen


def load_test(root,h):
    frozen=verify_freeze(root)
    access=root/f'h{h}'/'test_access.json'
    if not access.exists():
        save_json(access,dict(frozen_at=frozen['at'],first_label_access=pd.Timestamp.now(tz='UTC').isoformat()))
    return joblib.load(SOURCE/'data'/f'evaluation_h{h}.joblib').dropna(subset=['target','target_date','risk_scale'])


def calibration_bank(cal,returns,cutoff,test):
    if cal.index.min()<cutoff or cal.target_date.max()>=test or (cal.target_date.to_numpy()<=cal.index.to_numpy()).any():
        raise ValueError('Residual bank needs mature out-of-fit calibration observations')
    return residual_bank(cal.target,returns,cal.risk_scale)


def annotate_oof(root,frame,h):
    frame=frame.copy()
    frame['checkpoint_hash']=frame.model_configuration_hash
    for fold in [1,2]:
        bundles,_=joblib.load(root/f'h{h}'/f'fold{fold}.joblib')
        for name,bundle in bundles.items():
            if name=='tcn':
                config={k:bundle[k] for k in ['columns','config','best_epoch']}
            else:
                config={task:{k:model[k] for k in ['columns','rounds','config','lookback'] if k in model}
                        for task,model in bundle.items() if task in ['regression','direction']}
                if name in MODELS[:2]:config['params']=PARAMS
            encoded=json.dumps(config,sort_keys=True).encode()
            frame.loc[(frame.fold==fold)&(frame.model==name),'model_configuration_hash']=hashlib.sha256(encoded).hexdigest()
    return frame


def run(root):
    manifest=json.loads((root/'experiment_manifest.json').read_text())
    protocol=manifest['protocol']
    edges={k:pd.Timestamp(v) for k,v in protocol['boundaries'].items()}
    frozen=(root/'selection_frozen.json').exists()
    if frozen:verify_freeze(root)
    frames=[annotate_oof(root,pd.read_csv(root/f'h{h}'/'oof.csv',parse_dates=['origin','target_date']),h) for h in [1,21,252]]
    pd.concat(frames).to_csv(root/'oof_predictions.csv',index=False)
    pd.concat(frames).drop(columns='target').to_csv(root/'oof_audit.csv',index=False)
    validation=[]
    for frame in frames:
        for (h,fold,model),part in frame.groupby(['horizon','fold','model']):
            returns=score(part,part.regression,'return')
            direction=score(part,part.probability_up,'direction')
            validation.append(dict(horizon=h,fold=fold,model=model,rows=len(part),dates=part.origin.nunique(),
                                   rmse=returns['rmse'],mae=returns['mae'],log_loss=direction['log_loss'],
                                   balanced_accuracy=direction['balanced_accuracy'],brier=direction['brier'],
                                   data_version=manifest['data_version']))
    pd.DataFrame(validation).to_csv(root/'validation_metrics.csv',index=False)
    choices=json.loads((root/'stacking_config.json').read_text()) if frozen else {}
    configs=json.loads((root/'tcn_config.json').read_text()) if frozen else {}
    prepared={}
    for h,oof in zip([1,21,252],frames):
        d=root/f'h{h}'
        if frozen:
            bundles,_=joblib.load(d/'fold3.joblib')
            saved=joblib.load(d/'combinations.joblib')
            prepared[h]=(bundles,saved['fitted'],saved['calibrators'],saved['banks'],choices[str(h)]['scenario_models'])
            continue
        m,r,p=aligned(oof,MODELS)
        if set(m.index.get_level_values('ticker'))&set(protocol['held_out_companies']):
            raise ValueError('Held-out company in meta development')
        if pd.to_datetime(m.target_date).max()>=edges['calibration']:
            raise ValueError('Meta fitting labels must mature before calibration')
        fitted,config=meta.fit(m,r,p,h)
        config.update(origins=int(oof.origin.nunique()),base_rows=len(oof),matched_rows=len(m))
        choices[str(h)]=config
        bundles,training=joblib.load(d/'fold3.joblib')
        configs[str(h)]={k:bundles['tcn'][k] for k in ['config','best_epoch','seconds','device']}
        configs[str(h)]['training']=training['tcn']
        dev=joblib.load(SOURCE/'data'/f'development_h{h}.joblib')
        cal=window(dev.dropna(subset=['target','target_date','risk_scale']),edges['calibration'],edges['test'])
        candidates=predictions(bundles,fitted,dev,cal)
        selected=scenario_selection(m,r,config)
        choices[str(h)]['scenario_models']=selected
        calibrators={};banks={};checks={}
        for name,(returns,p) in candidates.items():
            calibrators[name],checks[name]=guarded_calibrate(p,cal,h)
            banks[name]=calibration_bank(cal,returns,edges['calibration'],edges['test'])
        provenance=dict(rows=len(cal),dates=int(cal.index.nunique()),latest_label=str(cal.target_date.max()),
                        earliest_origin=str(cal.index.min()),keys=observation_hash(cal),fit_cutoff=str(edges['calibration']))
        joblib.dump(dict(fitted=fitted,calibrators=calibrators,banks=banks,provenance=provenance),d/'combinations.joblib',compress=3)
        choices[str(h)]['calibration']=checks
        prepared[h]=(bundles,fitted,calibrators,banks,selected)
    if not frozen:
        save_json(root/'stacking_config.json',choices)
        save_json(root/'ensemble_weights.json',{h:{k:v for k,v in c.get('trials',{}).items() if k.startswith('weighted')} for h,c in choices.items()})
        save_json(root/'tcn_config.json',configs)
        frozen_paths=[root/'stacking_config.json',root/'tcn_config.json',root/'ensemble_weights.json',
                      root/'experiment_manifest.json',*root.glob('h*/oof.csv'),
                      *root.glob('h*/fold*.joblib'),*root.glob('h*/combinations.joblib')]
        save_json(root/'selection_frozen.json',dict(at=pd.Timestamp.now(tz='UTC').isoformat(),
                  sha256={str(p.relative_to(root)):hash_file(p) for p in frozen_paths}))
    histories,sources=load_histories(Path(protocol['source_prices'][0]['file']).parent)
    assert {s['ticker']:s['sha256'] for s in sources}=={s['ticker']:s['sha256'] for s in protocol['source_prices']}
    metrics=[];intervals=[];backtests=[];trade_stocks=[];stocks=[];years=[];regimes=[];tests=[];correlations=[];residuals=[];uncertainty=[];scenarios=[]
    back=root/'backtests';back.mkdir(exist_ok=True)
    with (root/'run_log.txt').open('a',encoding='utf-8') as log:
        log.write('Evaluation uses the frozen selections and checkpoints.\n')
    for h,(bundles,fitted,calibrators,banks,selected) in prepared.items():
        panel=joblib.load(SOURCE/'data'/f'unlabeled_h{h}.joblib')
        wanted=panel.loc[panel.index>=edges['test']]
        combined=predictions(bundles,fitted,panel,wanted)
        for a in MODELS[:3]:
            bundle=joblib.load(REPAIR/f'h{h}'/a/'model.joblib')
            p=slice_keys(predict_pair(bundle,panel),wanted)
            combined['repair_'+a]=(p.regression.to_numpy(),p.raw_probability.to_numpy())
            calibrators['repair_'+a]=bundle['calibrator']
            banks['repair_'+a]=bundle['residual_bank']
        actual=load_test(root,h)
        reference=pd.read_csv(SOURCE/f'h{h}/xgboost/test_predictions.csv',parse_dates=['Date','target_date']).set_index('Date')
        assert observation_hash(actual)==observation_hash(reference)
        previous=slice_keys(reference,actual)
        np.testing.assert_array_equal(actual.target_date,previous.target_date)
        np.testing.assert_allclose(actual.target,previous.target,rtol=1e-12,atol=1e-14)
        for a in MODELS[:3]:
            benchmark=pd.read_csv(REPAIR/f'h{h}'/a/'test_predictions.csv',parse_dates=['Date','target_date']).set_index('Date')
            assert observation_hash(benchmark)==observation_hash(actual)
            np.testing.assert_array_equal(actual.target_date,benchmark.target_date)
        original=joblib.load(SOURCE/f'h{h}/xgboost/model.joblib')
        prior=float(original['prior_probability'])
        indexed=pd.Series(np.arange(len(wanted)),index=pd.MultiIndex.from_arrays([wanted.index,wanted.ticker]))
        positions=indexed.reindex(pd.MultiIndex.from_arrays([actual.index,actual.ticker])).astype(int).to_numpy()
        target=actual.target.to_numpy()
        aligned_predictions={name:pair[0][positions] for name,pair in combined.items()}
        aligned_predictions.update(zero=np.zeros(len(actual)),historical_mean=previous.historical_mean.to_numpy(),matched_control=previous.control.to_numpy())
        for name,r in aligned_predictions.items():
            if name in combined:
                raw=combined[name][1]
                calibrator=calibrators.get(name)
                p=raw if calibrator is None else calibrator.predict_proba(logit(raw))[:,1]
                signal=wanted[['ticker']].copy()
                signal['regression'],signal['probability_up']=combined[name][0],p
                result,curve,trades=run_strategy(signal,histories,h,threshold=protocol['signal_threshold'])
                curve['drawdown']=curve.strategy/curve.strategy.cummax()-1
                curve.to_csv(back/f'{h}_{name}_equity.csv')
                trades.to_csv(back/f'{h}_{name}_trades.csv',index=False)
                strategy=result['strategy'].copy()
                enough=result['trades']>=30 and len(curve)>=2*max(21,h)
                if not enough:strategy['sharpe_zero_risk_free']=None
                backtests.append(dict(horizon=h,model=name,**strategy,buy_hold=result['buy_and_hold']['total_return'],
                    trades=result['trades'],exposure=result['mean_exposure'],win_rate=result['win_rate'],costs=result['cash_costs'],
                    mean_gain=trades.loc[trades.net_return>0,'net_return'].mean() if len(trades) else None,
                    mean_loss=trades.loc[trades.net_return<=0,'net_return'].mean() if len(trades) else None,
                    turnover=result['cash_costs']/.0015/100000,sharpe_support='descriptive' if enough else 'limited'))
                allocation=100000/wanted.ticker.nunique()
                for ticker in wanted.ticker.unique():
                    ledger=trades.loc[trades.ticker==ticker] if len(trades) else trades
                    opens=histories[ticker].loc[(histories[ticker].index>wanted.index.min())&
                                               (histories[ticker].index<=curve.index.max()),'open']
                    trade_stocks.append(dict(horizon=h,model=name,ticker=ticker,trades=len(ledger),
                        total_return=float(ledger.capital_after.iloc[-1]/allocation-1) if len(ledger) else 0.,
                        buy_hold=float(opens.iloc[-1]/opens.iloc[0]*(1-.0015)/(1+.0015)-1),
                        costs=float((ledger.entry_cost+ledger.exit_cost).sum()) if len(ledger) else 0.,
                        win_rate=float((ledger.net_return>0).mean()) if len(ledger) else None))
                raw,p=raw[positions],p[positions]
            else:
                p=np.full(len(actual),{'always_up':1.,'always_not_up':0.,'zero':.5}.get(name,prior));raw=p
            f=actual[['ticker','target','target_date','risk_scale']].copy()
            f['regression']=r;f['probability_up']=p;f['raw_probability']=raw;f['model']=name;f['horizon']=h
            f['group']=np.where(f.ticker.isin(protocol['held_out_companies']),'unseen','seen')
            for group,g in [('all',f),('unseen',f.loc[f.group=='unseen']),('seen',f.loc[f.group=='seen'])]:
                ret=score(g,g.regression,'return')
                ret['return_sign_accuracy']=ret.pop('direction_accuracy')
                direction=score(g,g.probability_up,'direction')
                zero=float(np.sqrt(np.mean(g.target**2)))
                metrics.append(dict(horizon=h,model=name,group=group,rows=len(g),**ret,zero_rmse=zero,
                    median_absolute_error=float(np.median(abs(g.target-g.regression))),rmse_difference=ret['rmse']-zero,
                    improvement_pct=100*(1-ret['rmse']/zero),
                    raw_brier=float(np.mean((g.raw_probability-(g.target>0))**2)),
                    roc_auc=roc_auc_score(g.target>0,g.probability_up) if (g.target>0).nunique()==2 else None,
                    **{f'direction_{k}':v for k,v in direction.items()}))
                if name in banks:
                    for coverage in [.5,.8,.95]:
                        lo,hi=interval(g.regression,g.risk_scale,banks[name],coverage)
                        intervals.append(dict(horizon=h,model=name,group=group,nominal=coverage,
                            observed=float(((g.target>=lo)&(g.target<=hi)).mean()),width=float(np.mean(hi-lo))))
                if name in combined and group in ['all','unseen']:
                    g=g.assign(zero=0.)
                    uncertainty.append(dict(horizon=h,model=name,group=group,**paired_uncertainty(g,'regression','zero',h)))
                    base=selected[0]
                    g=g.assign(oof_best_individual=aligned_predictions[base] if group=='all' else aligned_predictions[base][f.group=='unseen'])
                    uncertainty.append(dict(horizon=h,model=name,group=group,reference_model=base,
                        **paired_uncertainty(g,'regression','oof_best_individual',h)))
            if name in combined:
                for store,grouped in [(stocks,f.groupby('ticker')),(years,f.groupby(f.target_date.dt.year)),
                                      (regimes,f.groupby(previous.trend_regime.to_numpy()))]:
                    for key,g in grouped:
                        store.append(dict(horizon=h,model=name,segment=key,rows=len(g),**score(g,g.regression,'return'),
                                          **({'regime_type':'trend'} if store is regimes else {})))
                for key,g in f.groupby(previous.vol_regime.to_numpy()):
                    regimes.append(dict(horizon=h,model=name,segment=key,rows=len(g),regime_type='volatility',**score(g,g.regression,'return')))
            tests.append(f)
        for name,p in [('always_up',1.),('always_not_up',0.),('training_prevalence',prior)]:
            for group,g in [('all',actual),('unseen',actual.loc[actual.ticker.isin(protocol['held_out_companies'])]),
                            ('seen',actual.loc[~actual.ticker.isin(protocol['held_out_companies'])])]:
                direction=score(g,np.full(len(g),p),'direction')
                metrics.append(dict(horizon=h,model=name,group=group,rows=len(g),roc_auc=.5 if (g.target>0).nunique()==2 else None,
                    **{f'direction_{k}':v for k,v in direction.items()}))
        pm=pd.DataFrame({name:aligned_predictions[name] for name in combined})
        rm=pm.subtract(target,axis=0)
        tails=rm.abs().ge(rm.abs().quantile(.9))
        for a in pm:
            for b in pm:
                correlations.append(dict(horizon=h,first=a,second=b,correlation=pm[a].corr(pm[b])))
                residuals.append(dict(horizon=h,first=a,second=b,correlation=rm[a].corr(rm[b]),
                    same_error_sign=float((np.sign(rm[a])==np.sign(rm[b])).mean()),
                    large_error_jaccard=float((tails[a]&tails[b]).sum()/(tails[a]|tails[b]).sum())))
        # Same cached feature snapshot, at the latest common Reliance input origin.
        stock=wanted.loc[wanted.ticker=='RELIANCE.NS']
        last=stock.iloc[[-1]]
        last_position=int(indexed.loc[(last.index[0],'RELIANCE.NS')])
        close=float(last.close.iloc[0])
        daily=np.log(histories['RELIANCE.NS'].close.loc[:last.index[0]]).diff().iloc[-756:].to_numpy()
        for name in selected:
            r=float(combined[name][0][last_position]);risk=float(last.risk_scale.iloc[0])
            scenario,paths=simulate(close,r,risk,banks[name],daily,h,5000,42)
            pd.DataFrame(np.quantile(paths,[.025,.1,.5,.9,.975],axis=0).T,columns=['p025','p10','median','p90','p975']).to_csv(root/f'scenario_{h}_{name}.csv',index_label='session')
            pd.DataFrame(paths[:100].T).to_csv(root/f'paths_{h}_{name}.csv',index_label='session')
            scenarios.append(dict(horizon=h,model=name,as_of=str(last.index[0].date()),close=close,
                point=close*np.exp(r),**scenario))
        print(f'Evaluated {h} sessions',flush=True)
        with (root/'run_log.txt').open('a',encoding='utf-8') as log:log.write(f'Evaluated h{h}, {len(actual)} matched test rows.\n')
    summary=pd.DataFrame(metrics)
    summary['rmse_rank']=summary.groupby(['horizon','group']).rmse.rank(method='min')
    by_stock=pd.DataFrame(stocks)
    by_stock['rank']=by_stock.groupby(['horizon','segment']).rmse.rank(method='min')
    for name,data in [('metrics',summary),('metrics_by_horizon',summary),('model_comparison',summary),
                      ('metrics_by_stock',by_stock),('metrics_by_year',pd.DataFrame(years)),
                      ('metrics_by_regime',pd.DataFrame(regimes)),('backtest_metrics',pd.DataFrame(backtests)),('backtest_by_stock',pd.DataFrame(trade_stocks)),
                      ('monte_carlo_metrics',pd.DataFrame(intervals)),('prediction_correlations',pd.DataFrame(correlations)),
                      ('residual_correlations',pd.DataFrame(residuals)),('paired_intervals',pd.DataFrame(uncertainty)),
                      ('test_predictions',pd.concat(tests))]:
        data.assign(experiment=root.name,data_version=manifest['data_version']).to_csv(root/f'{name}.csv',index=name=='test_predictions')
    save_json(root/'scenarios.json',scenarios)
    from src.forecasting.stacking.report import render
    render(root)
    verify_results(root)


def verify_results(root):
    frozen=verify_freeze(root)
    saved=pd.read_csv(root/'test_predictions.csv',parse_dates=['Date','target_date']).set_index('Date')
    counts={}
    for h in [1,21,252]:
        first=json.loads((root/f'h{h}'/'test_access.json').read_text())
        if pd.Timestamp(first['first_label_access'])<pd.Timestamp(frozen['at']):
            raise ValueError('Test accessed before freeze')
        reference=saved.loc[(saved.horizon==h)&(saved.model=='zero')]
        counts[str(h)]=len(reference)
        for _,frame in saved.loc[saved.horizon==h].groupby('model'):
            if observation_hash(frame)!=observation_hash(reference):
                raise ValueError('Saved test keys changed')
            np.testing.assert_array_equal(frame.target_date,reference.target_date)
            np.testing.assert_array_equal(frame.target,reference.target)
    oof=pd.read_csv(root/'oof_predictions.csv')
    audit(oof)
    class LocalLinks(HTMLParser):
        def __init__(self):
            super().__init__()
            self.paths=[]

        def handle_starttag(self,tag,attrs):
            self.paths.extend(value for key,value in attrs if key in ['src','href'] and value)

    links=LocalLinks()
    links.feed((root/'index.html').read_text(encoding='utf-8'))
    for path in links.paths:
        if not (root/path).is_file():raise ValueError(f'Broken report link {path}')
    protected=json.loads((root/'protected.json').read_text())
    changed=[p for p,d in protected.items() if not Path(p).exists() or hash_file(Path(p))!=d]
    if changed:raise ValueError(f'Protected inputs changed: {changed[:5]}')
    result=dict(protected_files=len(protected),matched_keys=True,all_selections_before_test=True,
                test_rows_per_model=counts,oof_audit_rows=len(oof),report_links=len(links.paths))
    save_json(root/'verification.json',result)
    print(result,flush=True)
