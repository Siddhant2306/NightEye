"""Repair comparisons, actual/predicted charts and explicitly dated scenarios."""
import html
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.repair_study.study import SOURCE,folds,digest
from src.feature_engineering_v2.inference import task_frame
from src.feature_engineering_v2.models import predict
from src.feature_engineering_v2.conclusions import table
from src.feature_engineering_v2.forecast import path_plot,SCENARIO_NOTE
from src.forecasting.diagnostics import plotting,save_figure,price_frame,plot_split,plot_comparison,SPLITS
from src.forecasting.protocol import before
from src.forecasting.predict import forecast,write_html
from src.forecasting.train import save_json
from src.helper.load_data import load_data


def data_checks(root,protocol):
    volumes={};quality=[];extremes=[]
    for item in protocol['source_prices']:
        f=pd.read_csv(item['file']);f.columns=f.columns.str.lower();f['date']=pd.to_datetime(f.date)
        volumes[item['ticker']]=f.set_index('date').volume
        tolerance=1e-5*f.close
        quality.append(dict(ticker=item['ticker'],rows=len(f),first=str(f.date.min().date()),last=str(f.date.max().date()),
            duplicate_dates=int(f.date.duplicated().sum()),missing_ohlcv=int(f[['open','high','low','close','volume']].isna().any(axis=1).sum()),
            bad_ohlc=int(((f.high+tolerance<np.maximum(f.open,f.close))|(f.low-tolerance>np.minimum(f.open,f.close))|(f.high<f.low)).sum()),
            zero_volume=int((f.volume==0).sum()),active_zero_volume=int(((f.volume==0)&(f.date>=pd.Timestamp('2017-01-01'))).sum()),
            max_abs_daily_log_return=float(np.log(f.close).diff().abs().max())))
        returns=np.log(f.close).diff()
        for i in np.flatnonzero(returns.abs().to_numpy()>.4):
            extremes.append(dict(ticker=item['ticker'],date=str(f.date.iloc[i].date()),log_return=float(returns.iloc[i]),previous_close=float(f.close.iloc[i-1]),close=float(f.close.iloc[i]),volume=float(f.volume.iloc[i])))
    pd.DataFrame(quality).to_csv(root/'data_quality.csv',index=False);pd.DataFrame(extremes).to_csv(root/'large_return_audit.csv',index=False)
    sensitivity=[]
    for path in root.glob('h*/*/test_predictions.csv'):
        f=pd.read_csv(path,parse_dates=['Date','target_date']);valid=np.ones(len(f),dtype=bool)
        for ticker,positions in f.groupby('ticker').groups.items():
            positions=np.asarray(list(positions));volume=volumes[ticker]
            valid[positions]=(volume.reindex(f.loc[positions,'Date']).to_numpy()>0)&(volume.reindex(f.loc[positions,'target_date']).to_numpy()>0)
        part=f.loc[valid];rmse=float(np.sqrt(np.mean((part.regression-part.target)**2)));zero=float(np.sqrt(np.mean(part.target**2)))
        sensitivity.append(dict(algorithm=path.parent.name,horizon=int(path.parent.parent.name[1:]),rows=len(part),excluded=len(f)-len(part),rmse=rmse,zero_rmse=zero,improvement_vs_zero=1-rmse/zero))
    pd.DataFrame(sensitivity).sort_values(['horizon','algorithm']).to_csv(root/'zero_volume_sensitivity.csv',index=False)


def learning_plot(root,a,h,selection,path):
    plt,_=plotting();fig,axes=plt.subplots(2,2,figsize=(12,7))
    for i,fold in enumerate([1,2]):
        for j,(task,key) in enumerate([('return','regression'),('direction','direction')]):
            ax=axes[i,j];choice=selection[task]['selected'];recipe=choice['recipe']
            if recipe=='neutral':
                ax.text(.5,.5,'Validation selected a fixed neutral baseline',ha='center',transform=ax.transAxes);continue
            model=joblib.load(root/'development'/a/f'h{h}'/recipe/f'fold{fold}.joblib')[key];curve=model['learning_curve']
            if a=='lstm':
                metric='return_rmse' if task=='return' else 'direction_log_loss'
                tr=[r['training_'+metric] for r in curve];va=[r['validation_'+metric] for r in curve];x=[r['additional_epoch'] for r in curve]
                ylabel='Risk-normalized RMSE' if task=='return' and model.get('output_risk_scaled') else 'Return RMSE' if task=='return' else 'Binary log loss'
            else:
                metric='rmse' if task=='return' else 'logloss' if a=='xgboost' else 'binary_logloss'
                names=('validation_0','validation_1') if a=='xgboost' else ('training','validation')
                scale=model['scale'] if task=='return' else 1.
                tr=np.asarray(curve[names[0]][metric])*scale;va=np.asarray(curve[names[1]][metric])*scale;x=np.arange(1,len(tr)+1)
                ylabel='Risk-normalized RMSE' if task=='return' and model.get('output_risk_scaled') else 'Return RMSE' if task=='return' else 'Binary log loss'
            ax.plot(x,tr,label='Training');ax.plot(x,va,label='Validation');ax.axvline(model.get('additional_epochs',model['rounds']),color='#555',linestyle='--',label='Estimator checkpoint')
            ax.set_title(f'Fold {fold}: {task} · {recipe}');ax.set_xlabel('Epoch / boosting round');ax.set_ylabel(ylabel);ax.legend(fontsize=7)
    fig.suptitle(f'{a} · {h} sessions · underlying estimator before output shrinkage');fig.tight_layout(rect=(0,0,1,.94));save_figure(fig,path)


def generate(root):
    SPLITS['validation']='Validation · two past-only fold models'
    protocol=json.loads((SOURCE/'protocol.json').read_text());charts=root/'charts';charts.mkdir(exist_ok=True)
    data_checks(root,protocol)
    output=root/'forecasts';output.mkdir(exist_ok=True);summary=[];validation=[];future=[];links=[];attribution=[]
    history=load_data(SOURCE/'market_snapshot/RELIANCE.NS.csv')
    for h in [1,21,252]:
        dev=joblib.load(SOURCE/'data'/f'development_h{h}.joblib');test_tables={}
        for a in ['xgboost','lightgbm','lstm']:
            directory=root/f'h{h}'/a;bundle=joblib.load(directory/'model.joblib')
            saved=pd.read_csv(directory/'test_predictions.csv',parse_dates=['Date','target_date']).set_index('Date')
            metrics=json.loads((directory/'metrics.json').read_text())
            old=json.loads((SOURCE/f'h{h}'/a/'metrics.json').read_text())
            sel=json.loads((root/'development'/a/f'h{h}'/'selection.json').read_text())
            trials=json.loads((root/'development'/a/f'h{h}'/'trials.json').read_text())
            learning_plot(root,a,h,sel,charts/f'learning_{a}_h{h}')
            returns=[t for t in trials if t['task']=='return' and t['recipe']!='neutral']
            control=float(np.mean(next(t for t in returns if t['recipe']=='current' and t['mix']==1.)['fold_errors']))
            for recipe_id in dict.fromkeys(t['recipe'] for t in returns):
                group=[t for t in returns if t['recipe']==recipe_id]
                unshrunk=float(np.mean(next(t for t in group if t['mix']==1.)['fold_errors']))
                best=min(float(np.mean(t['fold_errors'])) for t in group)
                attribution.append(dict(algorithm=a,horizon=h,recipe=recipe_id,unshrunk_validation_rmse=unshrunk,
                    best_shrunk_validation_rmse=best,change_gain_before_shrinkage=control-unshrunk,shrinkage_gain=unshrunk-best))
            for task,s in sel.items():
                for t in [x for x in trials if x['task']==task]:
                    validation.append(dict(algorithm=a,horizon=h,task=task,recipe=t['recipe'],mix=t['mix'],
                        mean_error=float(np.mean(t['fold_errors'])),fold1=t['fold_errors'][0],fold2=t['fold_errors'][1],
                        selected=t['recipe']==s['selected']['recipe'] and t['mix']==s['selected']['mix']))
            for group,m in metrics.items():
                summary.append(dict(algorithm=a,horizon=h,group=group,recipe=sel['return']['selected']['recipe'],shrinkage=sel['return']['selected']['mix'],
                    old_rmse=old[group]['regression']['rmse'],rmse=m['regression']['rmse'],zero_rmse=m['zero']['rmse'],
                    control_rmse=old[group]['control']['rmse'],historical_mean_rmse=old[group]['historical_mean']['rmse'],
                    improvement_vs_zero=1-m['regression']['rmse']/m['zero']['rmse'],macro_rmse=m['regression']['macro_rmse'],
                    direction_accuracy=m['direction']['accuracy'],balanced_accuracy=m['direction']['balanced_accuracy'],
                    brier=m['direction']['brier'],old_brier=old[group]['classifier']['brier'],coverage80=m['coverage80']))
            stock=saved.loc[saved.ticker=='RELIANCE.NS'];prices=price_frame(stock,stock.regression.to_numpy(),bundle['residual_bank'])
            test_tables[a]=prices;plot_split(prices,a,h,'RELIANCE.NS','test',charts/f'test_{a}_h{h}')
            training=before(task_frame(dev,bundle['regression']).dropna(subset=['target','target_date','risk_scale']),pd.Timestamp(protocol['boundaries']['calibration']))
            recipe=sel['return']['selected'];fit_span=bundle['regression'].get('fit_span')
            if fit_span:training=training.loc[training.index>=pd.Timestamp(fit_span['first'])]
            elif recipe.get('settings',{}).get('recent'):training=training.loc[training.index>=training.index.max()-pd.DateOffset(years=3)]
            training=training.loc[training.ticker=='RELIANCE.NS']
            plot_split(price_frame(training,predict(bundle['regression'],training)),a,h,'RELIANCE.NS','training',charts/f'training_{a}_h{h}')
            vparts=[]
            for fold,(_,valid) in enumerate(folds(dev.dropna(subset=['target','target_date','risk_scale']),protocol),1):
                if recipe['recipe']=='neutral':v=valid.loc[valid.ticker=='RELIANCE.NS'].copy();p=np.zeros(len(v))
                else:
                    model=joblib.load(root/'development'/a/f'h{h}'/recipe['recipe']/f'fold{fold}.joblib')['regression']
                    panel=task_frame(dev,model);v=panel.loc[(panel.index>=valid.index.min())&(panel.index<=valid.index.max())&(panel.ticker=='RELIANCE.NS')].dropna(subset=['target','target_date'])
                    p=predict(model,v)*recipe['mix']
                vparts.append(price_frame(v,p))
            vprices=pd.concat(vparts,ignore_index=True)
            plot_split(vprices,a,h,'RELIANCE.NS','validation',charts/f'validation_{a}_h{h}')
            result,paths=forecast(history,bundle,'RELIANCE.NS',5000,42,SOURCE/'market_snapshot/context')
            result['forecast_status']='EXPLORATORY_HISTORICAL_INPUT'
            result['scenario_interpretation']=SCENARIO_NOTE
            result['reliability_warnings']=['Previously inspected historical test; repaired results are exploratory.',
                'Input snapshot is dated '+result['as_of']+'; this is not a live quote or latest-date production refit.',
                f"Full-test balanced direction accuracy {metrics['all']['direction']['balanced_accuracy']:.1%}; nominal 80% interval coverage {metrics['all']['coverage80']:.1%}.",
                'Monte Carlo does not improve price accuracy; annual intervals remain unvalidated.']
            path=output/f'{a}_h{h}';path.mkdir(exist_ok=True)
            save_json(path/'forecast.json',result);write_html(path/'forecast.html',result,paths);path_plot(result,paths,path/'monte_carlo_paths')
            pd.DataFrame(paths[:100].T).to_csv(path/'sample_paths.csv',index_label='session')
            interval80=result['empirical_price_intervals']['0.8']
            future.append(dict(algorithm=a,horizon=h,as_of=result['as_of'],current=result['current_adjusted_close'],point=result['predicted_adjusted_price'],
                probability_up=result['classifier_probability_up'],signal=result['direction_signal'],lower80=interval80['lower_adjusted_price'],upper80=interval80['upper_adjusted_price']))
            links.append(f'<section><h2>{a} · {h} sessions</h2><a href="{a}_h{h}/forecast.html">Full forecast</a><img src="{a}_h{h}/monte_carlo_paths.png"></section>')
            print(f'Reported {a} h{h}',flush=True)
        plot_comparison(test_tables,h,'RELIANCE.NS',charts/f'comparison_h{h}')
    summary=pd.DataFrame(summary);validation=pd.DataFrame(validation);future=pd.DataFrame(future)
    summary.to_csv(root/'results.csv',index=False);validation.to_csv(root/'validation_trials.csv',index=False);future.to_csv(output/'summary.csv',index=False)
    pd.DataFrame(attribution).to_csv(root/'attribution.csv',index=False)
    plt,_=plotting();fig,axes=plt.subplots(1,3,figsize=(15,5))
    for ax,h in zip(axes,[1,21,252]):
        p=summary.loc[(summary.group=='all')&(summary.horizon==h)]
        x=np.arange(3);ax.bar(x-.2,p.old_rmse,width=.2,label='Previous');ax.bar(x,p.rmse,width=.2,label='Repair');ax.bar(x+.2,p.zero_rmse,width=.2,label='Unchanged price')
        ax.set_xticks(x,p.algorithm,rotation=20);ax.set_title(f'{h} sessions');ax.set_ylabel('Full-test log-return RMSE');ax.legend(fontsize=8)
    fig.suptitle('Frozen validation-selected repairs · reused historical test · lower is better');fig.tight_layout();save_figure(fig,charts/'baseline_comparison')
    selected=validation.loc[validation.selected]
    lines=['# Controlled repair study — results','',
        'The historical test was already inspected. Repairs were selected only from the original two purged validation folds, and all nine choices were frozen before this run read test labels. These are exploratory retrospective results, not independent evidence of a market edge.','',
        '## Selected validation results','',table(selected,['algorithm','horizon','task','recipe','mix','mean_error','fold1','fold2']),
        '', '## Full-universe final test','',table(summary.loc[summary.group=='all'],['algorithm','horizon','recipe','shrinkage','old_rmse','rmse','zero_rmse','control_rmse','historical_mean_rmse','improvement_vs_zero','direction_accuracy','balanced_accuracy','brier','coverage80']),
        '', 'Positive improvement_vs_zero means lower RMSE than unchanged price. Direction accuracy is a separate classifier metric, not price accuracy. Neutral probability gives no confidence signal even when threshold-at-0.5 accuracy follows the UP prevalence.','',
        '## Held-out-company test','',table(summary.loc[summary.group=='unseen'],['algorithm','horizon','rmse','zero_rmse','direction_accuracy','balanced_accuracy','coverage80']),
        '', '## Where a change helped','',
        'validation_trials.csv preserves every recipe and shrinkage value, including failures. The current recipe with mix below one isolates output shrinkage without changing any feature or estimator weight. A selected risk_target changes the target/loss scaling; compact changes only the input subset; recent changes only the fitting window. Combined recipes do not establish which individual factor caused a gain unless their one-factor controls agree.','',
        'The fixed neutral/unchanged-price controls compete during validation. The selector requires both-fold non-deterioration versus that control. We do not replace a losing selected model using its test result. Native tree early stopping and risk-normalized loss operate in estimator target units; final selection uses original-return pooled RMSE. LSTM risk-loss curves likewise use normalized units.','',
        '## Dated Reliance predictions','',table(future,['algorithm','horizon','as_of','current','point','probability_up','signal','lower80','upper80']),
        '', 'The input is the existing 30 October 2026 snapshot. These are historical-input scenario outputs, not current market forecasts. Annual empirical intervals retain known coverage limitations. Models are benchmark fits before the original test, not refitted using test labels.','',
        '## Charts and files','',
        'index.html contains actual/predicted training, past-fold validation and final-test plots for every algorithm/horizon. Training plots are in-sample; validation uses saved past-only fold weights; test points use frozen final weights. forecasts/index.html contains nine sets of 5,000 Monte Carlo paths and sample-path CSVs.','']
    (root/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    css='body{font:16px system-ui;max-width:1400px;margin:25px auto;padding:20px;background:#f6f8fa}section{background:white;padding:16px;margin:20px 0}img{max-width:100%}td,th{padding:8px;border-bottom:1px solid #ddd}.scroll{overflow:auto}'
    plots=''.join(f'<section><h2>{a} · {h} sessions</h2>'+''.join(f'<h3>{part}</h3><img loading="lazy" src="charts/{part}_{a}_h{h}.png">' for part in ['learning','training','validation','test'])+'</section>' for h in [1,21,252] for a in ['xgboost','lightgbm','lstm'])
    (root/'index.html').write_text(f'<!doctype html><meta charset="utf-8"><title>NightEye controlled repairs</title><style>{css}</style><h1>Controlled repair study</h1><p>Exploratory reused historical test. Price error and direction accuracy are different measurements.</p><p><a href="RESULTS.md">Results and limits</a> · <a href="forecasts/index.html">Monte Carlo forecasts</a> · <a href="validation_trials.csv">Every validation trial</a> · <a href="code_review.md">Code/feature review</a></p><img src="charts/baseline_comparison.png"><div class="scroll">{summary.loc[summary.group=="all"].to_html(index=False,float_format=lambda v:f"{v:.5f}")}</div>{plots}',encoding='utf-8')
    (output/'index.html').write_text(f'<!doctype html><meta charset="utf-8"><title>Repair scenarios</title><style>{css}</style><h1>Reliance scenarios · historical input as of 30 October 2026</h1><p>{html.escape(SCENARIO_NOTE)}</p><p>Not live quotes or validated future probability ranges.</p><div class="scroll">{future.to_html(index=False,float_format=lambda v:f"{v:.4f}")}</div>'+''.join(links),encoding='utf-8')
