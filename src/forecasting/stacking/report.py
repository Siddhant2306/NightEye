"""Local report built from experiment outputs."""
import html
import json
import numpy as np
import pandas as pd
from src.forecasting.diagnostics import plotting,save_figure


def render(root):
    plt,_=plotting()
    charts=root/'charts';charts.mkdir(exist_ok=True)
    metrics=pd.read_csv(root/'metrics.csv')
    back=pd.read_csv(root/'backtest_metrics.csv')
    intervals=pd.read_csv(root/'monte_carlo_metrics.csv')
    prediction=pd.read_csv(root/'test_predictions.csv')
    configs=json.loads((root/'stacking_config.json').read_text())
    tcn=json.loads((root/'tcn_config.json').read_text())
    manifest=json.loads((root/'experiment_manifest.json').read_text())
    models=back.model.unique()
    show=metrics.loc[metrics.model.isin(models)&(metrics.group=='all')]
    images=[]
    def save(fig,name):
        fig.tight_layout();save_figure(fig,charts/name);images.append(name)
    for h in [1,21,252]:
        sub=show.loc[show.horizon==h].sort_values('rmse')
        fig,axes=plt.subplots(1,2,figsize=(13,5))
        axes[0].barh(sub.model,sub.rmse);axes[0].axvline(sub.zero_rmse.iloc[0],color='black',ls='--');axes[0].set_title('RMSE and unchanged price')
        axes[1].barh(sub.model,sub.improvement_pct);axes[1].axvline(0,color='black');axes[1].set_title('RMSE improvement over zero (%)')
        fig.suptitle(f'{h} sessions · full test');save(fig,f'rmse_{h}')
        for metric in ['prediction','residual']:
            table=pd.read_csv(root/f'{metric}_correlations.csv')
            matrix=table.loc[table.horizon==h].pivot(index='first',columns='second',values='correlation')
            fig,ax=plt.subplots(figsize=(9,7));im=ax.imshow(matrix,vmin=-1,vmax=1,cmap='coolwarm')
            ax.set_xticks(range(len(matrix.columns)),matrix.columns,rotation=60,ha='right')
            ax.set_yticks(range(len(matrix)),matrix.index);fig.colorbar(im,ax=ax);ax.set_title(f'{metric.capitalize()} correlation · {h} sessions')
            save(fig,f'{metric}_correlation_{h}')
        fig,axes=plt.subplots(2,2,figsize=(13,9))
        for name in sub.model:
            g=prediction.loc[(prediction.horizon==h)&(prediction.model==name)]
            if name in ['tcn','equal','linear_stack','lightgbm_stack','weighted']:
                axes[0,0].hist(g.regression-g.target,bins=60,density=True,histtype='step',label=name)
                if name=='tcn':axes[0,1].scatter(g.target,g.regression,s=3,alpha=.2)
                bins=pd.cut(g.probability_up,np.linspace(0,1,11),include_lowest=True)
                reliability=g.assign(up=g.target>0).groupby(bins,observed=True)[['probability_up','up']].mean()
                axes[1,0].plot(reliability.probability_up,reliability.up,'o-',label=name)
            c=intervals.loc[(intervals.horizon==h)&(intervals.model==name)&(intervals.group=='all')]
            axes[1,1].plot(c.nominal,c.observed,'o-',label=name,alpha=.75)
        axes[0,0].set_title('Residual distributions');axes[0,0].legend(fontsize=7)
        axes[0,1].set_title('TCN actual vs predicted return');axes[0,1].set_xlabel('Actual');axes[0,1].set_ylabel('Predicted')
        for ax,title in [(axes[1,0],'Direction reliability'),(axes[1,1],'Interval coverage')]:
            ax.plot([0,1],[0,1],'k--');ax.set_title(title);ax.legend(fontsize=6)
        save(fig,f'errors_and_calibration_{h}')
        fig,ax=plt.subplots(figsize=(10,4))
        distribution=prediction.loc[prediction.horizon==h]
        actual=distribution.loc[distribution.model=='tcn','target']
        bins=np.linspace(actual.quantile(.01),actual.quantile(.99),65)
        ax.hist(actual,bins=bins,density=True,histtype='step',color='black',label='Actual')
        for name in ['tcn','equal','weighted','linear_stack','lightgbm_stack']:
            values=distribution.loc[distribution.model==name,'regression']
            if len(values):ax.hist(values,bins=bins,density=True,histtype='step',label=name)
        ax.set(title=f'Forecast and outcome distributions · {h} sessions',xlabel='Log return',ylabel='Density')
        ax.legend(fontsize=8)
        save(fig,f'prediction_distribution_{h}')
        fig,axes=plt.subplots(1,2,figsize=(13,5))
        for name in sub.model:
            equity=pd.read_csv(root/'backtests'/f'{h}_{name}_equity.csv',parse_dates=['Date'])
            axes[0].plot(equity.Date,equity.strategy,label=name)
            axes[1].plot(equity.Date,equity.drawdown,label=name)
        axes[0].plot(equity.Date,equity.buy_and_hold,'k--',label='buy and hold')
        axes[0].set_title('Net equity');axes[1].set_title('Drawdown');axes[0].legend(fontsize=7)
        save(fig,f'backtest_{h}')
        fig,axes=plt.subplots(1,3,figsize=(14,4))
        for fold,ax in enumerate(axes,1):
            trials=json.loads((root/f'h{h}'/f'tcn_fold{fold}_trials.json').read_text())
            for trial in trials:
                c=pd.DataFrame(trial['curves']);n=trial['config']['lookback']
                ax.plot(c.epoch,c.training_loss,'--',label=f'{n} train')
                ax.plot(c.epoch,c.validation_loss,label=f'{n} valid')
            ax.set_title(f'Fit {fold}');ax.set_xlabel('Epoch');ax.legend(fontsize=7)
        fig.suptitle(f'TCN joint loss · {h} sessions');save(fig,f'tcn_learning_{h}')
        support=configs[str(h)]
        if support['status']=='fitted':
            fig,ax=plt.subplots(figsize=(8,4))
            for i,task in enumerate(['return','direction']):
                values=support['trials'][f'weighted_{task}']['final_weights']
                ax.bar(np.arange(4)+.25*i,values,width=.25,label=task)
            ax.set_xticks(np.arange(4)+.125,['XGBoost','LightGBM','LSTM','TCN']);ax.legend();ax.set_title(f'OOF weights · {h} sessions')
            save(fig,f'weights_{h}')
        fig,axes=plt.subplots(1,2,figsize=(13,5))
        g=prediction.loc[(prediction.horizon==h)&(prediction.model=='tcn')]
        matrix=pd.crosstab(g.target>0,g.probability_up>=.5).reindex(index=[False,True],columns=[False,True],fill_value=0)
        axes[0].imshow(matrix,cmap='Blues')
        for i in range(2):
            for j in range(2):axes[0].text(j,i,str(matrix.iloc[i,j]),ha='center')
        axes[0].set(xlabel='Predicted UP',ylabel='Actual UP',title='TCN confusion matrix')
        stocks=pd.read_csv(root/'metrics_by_stock.csv')
        s=stocks.loc[(stocks.horizon==h)&stocks.model.isin(['tcn','equal','weighted','linear_stack','lightgbm_stack'])]
        grid=s.pivot(index='model',columns='segment',values='rmse')
        im=axes[1].imshow(grid,aspect='auto');axes[1].set_yticks(range(len(grid)),grid.index)
        axes[1].set_xticks(range(len(grid.columns)),grid.columns,rotation=90,fontsize=5);fig.colorbar(im,ax=axes[1]);axes[1].set_title('Stock RMSE')
        save(fig,f'confusion_and_stocks_{h}')
    scenarios=json.loads((root/'scenarios.json').read_text())
    for item in scenarios:
        h,name=item['horizon'],item['model']
        p=pd.read_csv(root/f'scenario_{h}_{name}.csv')
        fig,ax=plt.subplots(figsize=(9,4))
        sample_path=root/f'paths_{h}_{name}.csv'
        if sample_path.exists():
            sample=pd.read_csv(sample_path)
            ax.plot(sample.session,sample.iloc[:,1:41],color='#0072b2',alpha=.06)
        ax.fill_between(p.session,p.p10,p.p90,alpha=.25,label='10th–90th scenario percentiles')
        ax.plot(p.session,p['median'],label='Scenario median');ax.scatter([h],[item['point']],label='Point forecast')
        ax.set(title=f'Reliance · {name} · {item["as_of"]}',xlabel='Future sessions',ylabel='Adjusted price');ax.legend()
        save(fig,f'scenario_{h}_{name}')
    columns=['horizon','model','rmse','zero_rmse','improvement_pct','direction_balanced_accuracy','direction_brier']
    def table(frame):return frame.to_html(index=False,float_format=lambda v:f'{v:.6f}')
    findings=[]
    individuals=['xgboost','lightgbm','lstm','tcn','repair_xgboost','repair_lightgbm','repair_lstm']
    stock_scores=pd.read_csv(root/'metrics_by_stock.csv')
    for h in [1,21,252]:
        for group in ['all','unseen']:
            g=metrics.loc[(metrics.horizon==h)&(metrics.group==group)].set_index('model')
            base=g.loc[individuals,'rmse'].idxmin()
            effects='; '.join(f'{n} {g.loc[n,"rmse"]-g.loc[base,"rmse"]:+.6f}' for n in ['equal','weighted','linear_stack','lightgbm_stack'] if n in g.index)
            findings.append(f'{h} sessions, {group}. Lowest individual RMSE was {base}. Combination RMSE differences from it are {effects}. Adding TCN to the equal average changed RMSE by {g.loc["equal","rmse"]-g.loc["equal_without_tcn","rmse"]:+.6f}. TCN minus LSTM {g.loc["tcn","rmse"]-g.loc["lstm","rmse"]:+.6f}, versus XGBoost {g.loc["tcn","rmse"]-g.loc["xgboost","rmse"]:+.6f}, versus LightGBM {g.loc["tcn","rmse"]-g.loc["lightgbm","rmse"]:+.6f}.')
        s=stock_scores.loc[stock_scores.horizon==h].pivot(index='segment',columns='model',values='rmse')
        reference=s[individuals].min(axis=1)
        breadth=', '.join(f'{n} {int((s[n]<reference).sum())}/{len(s)}' for n in
                          ['equal','weighted','linear_stack','lightgbm_stack'] if n in s)
        findings.append(f'{h} sessions. Stocks where each combination beat that stock’s lowest individual RMSE are {breadth}.')
    links=' · '.join(f'<a href="{p.name}">{p.stem}</a>' for p in sorted(root.glob('*.csv')))
    scenario_rows=[dict(horizon=s['horizon'],model=s['model'],as_of=s['as_of'],close=s['close'],point=s['point'],
                        p10=s['terminal_price_quantiles']['p10'],p90=s['terminal_price_quantiles']['p90']) for s in scenarios]
    def subset(names):return table(show.loc[show.model.isin(names),columns])
    accepted=sum(check['accepted'] for c in configs.values() for check in c['calibration'].values())
    coverage=intervals.loc[(intervals.nominal==.8)&(intervals.group=='all')].groupby('horizon')['observed'].agg(['min','max'])
    coverage_note='; '.join(f'{h} sessions {row["min"]:.1%} to {row["max"]:.1%}' for h,row in coverage.iterrows())
    sections=[('Executive summary',''.join(f'<p>{html.escape(x)}</p>' for x in findings)),
              ('Experiment protocol',f'<pre>{html.escape(json.dumps(manifest["protocol"]["boundaries"],indent=2))}</pre><p>Fixed compact inputs and independent inner checkpoint splits for fresh base fits. Saved repair models are separate comparisons.</p>'),
              ('Data and split audit',table(pd.DataFrame([dict(horizon=h,**{k:c[k] for k in ["matched_rows","origins","fit_dates","validation_dates","status"]}) for h,c in configs.items()]))+'<p><a href="oof_audit.csv">Row-level OOF audit</a></p>'),
              ('TCN architecture and checkpoints',f'<pre>{html.escape(json.dumps(tcn,indent=2))}</pre>'),
              ('TCN training curves',''.join(f'<img loading="lazy" src="charts/tcn_learning_{h}.png" alt="TCN loss curves for {h} sessions">' for h in [1,21,252])),
              ('Individual models',subset(individuals)),
              ('Equal weights',subset(['equal','equal_without_tcn'])),
              ('Learned weights',subset(['weighted'])+'<p><a href="ensemble_weights.json">Weights and selection losses</a></p>'),
              ('Linear stacking',subset(['linear_stack'])),
              ('LightGBM stacking',subset(['lightgbm_stack'])),
              ('Held-out companies',table(metrics.loc[metrics.model.isin(models)&(metrics.group=='unseen'),columns])),
              ('Direction classification and calibration',table(show[['horizon','model','direction_accuracy','direction_balanced_accuracy','raw_brier','direction_brier','roc_auc']])+f'<p>The forward calibration check accepted {accepted} new model and horizon combinations. Reliability bins, recall, precision and confusion counts are in metrics.csv.</p>'),
              ('Residual and error analysis','<p><a href="test_predictions.csv">Matched forecasts and actual returns</a> · <a href="paired_intervals.csv">Date-block confidence intervals</a></p>'),
              ('Prediction correlation and diversity','<p><a href="prediction_correlations.csv">Prediction correlations</a> · <a href="residual_correlations.csv">Residual correlations and tail error overlap</a></p>'),
              ('Monte Carlo interval calibration',f'<p>Observed full-test coverage of nominal 80% intervals ranged by horizon as follows. {coverage_note}.</p>'+table(pd.DataFrame(scenario_rows))+table(intervals.loc[intervals.group.isin(['all','unseen'])])),
              ('Cost-aware backtest',table(back)),
              ('Per-stock results','<p><a href="metrics_by_stock.csv">Errors and ranks by stock</a> · <a href="backtest_by_stock.csv">Stock-level strategy results</a></p>'),
              ('Per-year and market-regime results','<p><a href="metrics_by_year.csv">Target-year errors</a> · <a href="metrics_by_regime.csv">Trend and volatility regime errors</a></p>'),
              ('Limitations','<p>Previously inspected historical test. Annual OOF support may preclude learned combinations. Date-block intervals are withheld when fewer than two blocks exist. Residual-bank scenarios inherit calibration regime shifts. Backtests with few trades have limited support. Comparisons use historical adjusted prices.</p>'),
              ('Charts and files',f'<p>{links}</p>'+''.join(f'<figure><img loading="lazy" src="charts/{name}.png" alt="{name}"></figure>' for name in images if not name.startswith('tcn_learning_')))]
    body=''.join(f'<section><h2>{heading}</h2>{content}</section>' for heading,content in sections)
    (root/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>NightEye TCN and stacking</title><style>body{font:15px system-ui;max-width:1350px;margin:auto;padding:25px}section{overflow:auto;margin:28px 0}img{max-width:100%}td,th{padding:6px}figure{margin:20px 0}</style><h1>NightEye TCN and stacking</h1>'+body,encoding='utf-8')
