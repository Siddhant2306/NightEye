"""Complete development, test, interval and strategy tables plus offline dashboard."""
import argparse
import html
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.forecasting.train import save_json
from src.feature_engineering_v2.prepare import DEFAULT
from src.feature_engineering_v2.metrics import score
from src.feature_engineering_v2.models import predict
from src.forecasting.diagnostics import plotting,save_figure,price_frame,plot_split,plot_comparison


def feature_weights(model):
    columns=model["columns"]
    if model["algorithm"]=="xgboost":
        weights=model["model"].get_booster()[:model["rounds"]].get_score(importance_type="gain")
        values=np.array([weights.get(c,0.) for c in columns]);kind="Native split gain"
    elif model["algorithm"]=="lightgbm":
        values=model["model"].feature_importance(importance_type="gain",iteration=model["rounds"]);kind="Native split gain"
    else:
        matrix=np.abs(model["state"]["lstm.weight_ih_l0"])
        values=matrix[:,:len(columns)].sum(axis=0)+matrix[:,len(columns):].sum(axis=0)
        kind="Input/missing-mask weight magnitude; screening only, not causal importance"
    return pd.DataFrame(dict(feature=columns,importance=values,kind=kind))


def plot_importance(frame,title,path):
    plt,_=plotting();top=frame.sort_values("importance").tail(15)
    fig,ax=plt.subplots(figsize=(10,6));ax.barh(top.feature,top.importance,color="#0072b2")
    ax.set_xlabel(frame.kind.iloc[0]);ax.set_title(title);fig.tight_layout();save_figure(fig,path)


def plot_calibration(frame,algorithm,h,path):
    from src.feature_engineering_v2.metrics import score
    plt,_=plotting();fig,axes=plt.subplots(1,3,figsize=(14,4.5),sharex=True,sharey=True)
    for ax,group in zip(axes,["all","seen","unseen"]):
        part=frame if group=="all" else frame.loc[frame.group==group]
        ax.plot([0,1],[0,1],color="#555",linestyle="--",label="Perfect calibration")
        for column,label,color in [("raw_probability","Raw classifier","#0072b2"),("probability_up","Calibrated on earlier data","#d55e00")]:
            bins=score(part,part[column],"direction")["reliability_bins"]
            if bins:
                ax.plot([b["mean_probability"] for b in bins],[b["up_frequency"] for b in bins],marker="o",color=color,label=label)
        ax.set_title(group);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.set_xlabel("Predicted UP probability")
    axes[0].set_ylabel("Observed UP frequency");axes[-1].legend(fontsize=8)
    fig.suptitle(f"{algorithm} {h}: final-test probability reliability (diagnostic only)")
    fig.tight_layout(rect=(0,0,1,.94));save_figure(fig,path)


def plot_selected_curves(root,algorithm,h,selection,path):
    plt,_=plotting();fig,axes=plt.subplots(2,2,figsize=(13,8),squeeze=False)
    curve_rows=[]
    for fold in [1,2]:
        for task,j in [("return",0),("direction",1)]:
            identifier=selection[task]["selected"]
            model=joblib.load(root/"development"/algorithm/f"h{h}"/identifier/f"fold{fold}.joblib")[task]
            curve=model["learning_curve"];ax=axes[fold-1,j]
            if algorithm=="lstm" and curve and "training_return_rmse" in curve[0]:
                key="return_rmse" if task=="return" else "direction_log_loss"
                x=[r["additional_epoch"] for r in curve]
                train=[r[f"training_{key}"] for r in curve];valid=[r.get(f"validation_{key}") for r in curve]
                selected=model.get("additional_epochs",model["rounds"])
                joint=[r.get("training_joint") for r in curve]
                valjoint=[r.get("validation_joint") for r in curve]
            elif algorithm=="lstm":
                x=[r["epoch"] for r in curve];train=[r["training_loss"] for r in curve];valid=[r.get("validation_loss") for r in curve]
                selected=model["rounds"];joint=train;valjoint=valid
                ax.text(.02,.95,"Legacy joint loss; head-specific epoch loss was not saved",transform=ax.transAxes,va="top",fontsize=8)
            else:
                metric="rmse" if task=="return" else "logloss" if algorithm=="xgboost" else "binary_logloss"
                a,b=("validation_0","validation_1") if algorithm=="xgboost" else ("training","validation")
                train=curve[a][metric];valid=curve[b][metric]
                factor=model["scale"] if task=="return" else 1.
                train=np.asarray(train)*factor;valid=np.asarray(valid)*factor
                x=list(range(1,len(train)+1));selected=model.get("additional_rounds",model["rounds"])
                if model.get("reused") and model.get("initial_rounds",0):
                    # Native continuation logs start after the parent checkpoint.
                    selected=model.get("additional_rounds",0)
                    if "initial_validation_loss" in model:
                        x=[0]+x;train=[None]+list(train);valid=[model["initial_validation_loss"]]+list(valid)
                joint=[None]*len(x);valjoint=[None]*len(x)
            ax.plot(x,train,label="Training",color="#0072b2");ax.plot(x,valid,label="Validation",color="#d55e00")
            ax.axvline(selected,color="#444",linestyle="--",label="Selected checkpoint")
            ax.set_title(f"Fold {fold}: {task} ({identifier})");ax.set_xlabel("Additional epochs" if algorithm=="lstm" else "Boosting rounds / additional continuation rounds")
            ax.set_ylabel("Return RMSE" if task=="return" else "Binary log loss");ax.legend(fontsize=8)
            curve_rows += [dict(algorithm=algorithm,horizon=h,fold=fold,task=task,iteration=int(step),training=float(a) if a is not None else None,
                validation=float(b) if b is not None else None,training_joint=c,validation_joint=d,selected=int(selected))
                for step,a,b,c,d in zip(x,train,valid,joint,valjoint)]
    fig.suptitle(f"{algorithm} | {h} sessions | independently selected task checkpoints",fontsize=14)
    fig.tight_layout(rect=(0,0,1,.96));save_figure(fig,path)
    pd.DataFrame(curve_rows).to_csv(path.with_suffix(".csv"),index=False)


def original_validation(protocol,algorithm,h,task):
    ref=Path(protocol["references"]["lstm" if algorithm=="lstm" else "trees"])
    selection=json.loads((ref/f"h{h}"/algorithm/"selection.json").read_text())
    chosen=selection["regression" if task=="return" else "direction"]
    return [r["rmse" if task=="return" else "log_loss"] for r in chosen["folds"]] if algorithm=="lstm" else chosen["fold_losses"]


def generate(root):
    protocol=json.loads((root/"protocol.json").read_text());frozen=json.loads((root/"selection_frozen.json").read_text())
    charts=root/"charts";charts.mkdir(exist_ok=True)
    ablation,hyper,validation,comparison,directions,intervals,regimes,importance=[],[],[],[],[],[],[],[]
    narrative=[];test_tables={h:{} for h in protocol["horizons"]}
    for algorithm in protocol["algorithms"]:
        for h in protocol["horizons"]:
            results=json.loads((root/"development"/algorithm/f"h{h}"/"all_results.json").read_text())
            f0=next(o for o in results if o["id"]=="F0")
            selection=frozen["selections"][algorithm][str(h)]
            for option in results:
                for task,a in option["aggregate"].items():
                    base=f0["aggregate"][task]
                    row=dict(algorithm=algorithm,horizon=h,task=task,configuration=option["id"],family=option["family"],groups="|".join(option["groups"]),
                        stage=option["stage"],method=option["method"],features=len(option["columns"][task]),
                        mean_validation_error=a["mean"],median_validation_error=a["median"],std_validation_error=a["std"],worst_fold_error=a["worst"],
                        training_error=a["training_mean"],training_validation_gap=a["gap"],
                        mean_validation_mae=a.get("mean_mae"),mean_prediction_bias=a.get("mean_bias"),
                        fold1_error=a["fold_errors"][0],fold2_error=a["fold_errors"][1],
                        improved_folds=int(np.sum(np.asarray(a["fold_errors"])<np.asarray(base["fold_errors"]))),
                        relative_improvement_vs_F0=(base["mean"]-a["mean"])/base["mean"],
                        missing_fraction=float(np.mean([r["missing"][task] for r in option["records"]])),
                        selected=selection[task]["selected"]==option["id"],alias_of=option.get("alias_of"),
                        lookback=option["lookback"],epoch_ceiling=option["epochs"],parameters=json.dumps(option["params"],sort_keys=True))
                    hyper.append(row)
                    if option["family"].startswith("F") and option["stage"]!="hyperparameter": ablation.append(row)
                if not option.get("alias_of"):
                    for fold in [1,2]:
                        fold_models=joblib.load(root/"development"/algorithm/f"h{h}"/option["id"]/f"fold{fold}.joblib")
                        for task,model in fold_models.items():
                            weight=feature_weights(model)
                            weight["algorithm"],weight["horizon"],weight["configuration"],weight["task"],weight["fold"]=algorithm,h,option["id"],task,fold
                            importance.extend(weight.to_dict("records"))
            for task,s in selection.items():
                chosen=next(o for o in results if o["id"]==s["selected"])
                old=original_validation(protocol,algorithm,h,task)
                row=dict(algorithm=algorithm,horizon=h,task=task,selected=s["selected"],absolute_minimum=s["absolute_minimum"],
                    validation_error=s["validation"]["mean"],absolute_minimum_error=s["absolute_validation"]["mean"],
                    F0_error=f0["aggregate"][task]["mean"],old_selected_error=float(np.mean(old)),
                    fold1_error=s["validation"]["fold_errors"][0],fold2_error=s["validation"]["fold_errors"][1],
                    std=s["validation"]["std"],worst=s["validation"]["worst"],
                    features=len(s["columns"]),consistent_improvement_vs_F0=bool(np.all(np.asarray(s["validation"]["fold_errors"])<np.asarray(f0["aggregate"][task]["fold_errors"]))),
                    gap_change=s["validation"]["gap"]-f0["aggregate"][task]["gap"],
                    selected_checkpoints="|".join(str(r["checkpoints"][task]["total"]) for r in chosen["records"]))
                for baseline_algorithm in ["xgboost","lightgbm","lstm"]:
                    row[f"old_{baseline_algorithm}_error"]=float(np.mean(original_validation(protocol,baseline_algorithm,h,task)))
                if task=="return":
                    dev=joblib.load(root/"data"/f"development_h{h}.joblib")
                    from src.feature_engineering_v2.develop import development_folds
                    edges={k:pd.Timestamp(v) for k,v in protocol["boundaries"].items()}
                    row["zero_return_error"]=float(np.mean([score(v,np.zeros(len(v)),"return")["macro_rmse"] for _,v in development_folds(dev,edges)]))
                    tree_reference=Path(protocol["references"]["trees"])
                    ctrl=json.loads((tree_reference/f"h{h}"/(algorithm if algorithm!="lstm" else "xgboost")/"selection.json").read_text())
                    control=next(o for o in ctrl["regression_trials"] if o["family"]=="existing" and o["trial"]==0)
                    row["matched_control_error"]=control["validation_loss"]
                validation.append(row)
            directory=root/f"h{h}"/algorithm
            model=joblib.load(directory/"model.joblib")
            frame=pd.read_csv(directory/"test_predictions.csv",parse_dates=["Date","target_date"]).set_index("Date")
            scores=json.loads((directory/"metrics.json").read_text())
            ref=Path(protocol["references"]["lstm" if algorithm=="lstm" else "trees"])
            old_frame=pd.read_csv(ref/f"h{h}"/algorithm/"test_predictions.csv",parse_dates=["Date","target_date"]).set_index("Date")
            for version,values in [("v2",frame),("previous",old_frame)]:
                for group in ["seen","unseen","all"]:
                    part=values if group=="all" else values.loc[values.group==group]
                    r=score(part,part.regression,"return");d=score(part,part.probability_up,"direction")
                    comparison.append(dict(algorithm=algorithm,horizon=h,version=version,group=group,rows=len(part),**r))
                    directions.append(dict(algorithm=algorithm,horizon=h,version=version,group=group,
                        **{k:v for k,v in d.items() if not isinstance(v,(dict,list))},confusion_matrix=json.dumps(d["confusion_matrix"])))
                    if version=="v2":
                        for name,p in [("raw",part.raw_probability),("calibrated",part.probability_up)]:
                            pd.DataFrame(score(part,p,"direction")["reliability_bins"]).to_csv(directory/f"calibration_curve_{group}_{name}.csv",index=False)
                for level,part in values.groupby("ticker"):
                    for coverage in [.5,.8,.95]:
                        low,high=part[f"lower_{coverage}"],part[f"upper_{coverage}"]
                        intervals.append(dict(algorithm=algorithm,horizon=h,version=version,scope="company",name=level,rows=len(part),nominal=coverage,
                            observed=float(((part.target>=low)&(part.target<=high)).mean()),mean_log_width=float((high-low).mean()),mean_width_pct_of_origin=float((np.exp(high)-np.exp(low)).mean()*100)))
                for group in ["seen","unseen","all"]:
                    part=values if group=="all" else values.loc[values.group==group]
                    for coverage in [.5,.8,.95]:
                        low,high=part[f"lower_{coverage}"],part[f"upper_{coverage}"]
                        intervals.append(dict(algorithm=algorithm,horizon=h,version=version,scope="group",name=group,rows=len(part),nominal=coverage,
                            observed=float(((part.target>=low)&(part.target<=high)).mean()),mean_log_width=float((high-low).mean()),mean_width_pct_of_origin=float((np.exp(high)-np.exp(low)).mean()*100)))
            for column in ["vol_regime","trend_regime"]: old_frame[column]=frame[column].to_numpy()
            for version,values in [("v2",frame),("previous",old_frame)]:
                for kind in ["vol_regime","trend_regime"]:
                    for name,part in values.groupby(kind):
                        r=score(part,part.regression,"return");d=score(part,part.probability_up,"direction")
                        row=dict(algorithm=algorithm,horizon=h,version=version,regime_type=kind,regime=name,rows=len(part),**r,
                            classifier_accuracy=d["accuracy"],balanced_accuracy=d["balanced_accuracy"],brier=d["brier"])
                        for coverage in [.5,.8,.95]: row[f"coverage_{coverage}"]=float(((part.target>=part[f"lower_{coverage}"])&(part.target<=part[f"upper_{coverage}"])).mean())
                        regimes.append(row)
            w=feature_weights(model["regression"]);w.to_csv(directory/"feature_importance.csv",index=False)
            plot_importance(w,f"{algorithm} {h}: selected return model",charts/f"importance_{algorithm}_h{h}")
            plot_selected_curves(root,algorithm,h,selection,charts/f"learning_{algorithm}_h{h}")
            plot_calibration(frame,algorithm,h,charts/f"calibration_{algorithm}_h{h}")
            stock=frame.loc[frame.ticker=="RELIANCE.NS"]
            prices=price_frame(stock,stock.regression.to_numpy(),model["residual_bank"])
            plot_split(prices,algorithm,h,"RELIANCE.NS","test",charts/f"forecast_{algorithm}_h{h}")
            test_tables[h][algorithm]=prices
    for name,rows in [("feature_ablation_results",ablation),("hyperparameter_results",hyper),("validation_error_comparison",validation),
                      ("model_comparison",comparison),("direction_metrics",directions),("interval_metrics",intervals),("regime_metrics",regimes),
                      ("feature_importance_all_configs",importance)]:
        pd.DataFrame(rows).to_csv(root/f"{name}.csv",index=False)
    for h,tables in test_tables.items(): plot_comparison(tables,h,"RELIANCE.NS",charts/f"comparison_h{h}")
    backtest=root/"backtest"/"summary.csv"
    strategy=[]
    if backtest.exists():
        new=pd.read_csv(backtest);new["version"]="v2";strategy.append(new)
        old_path=Path("artifacts/backtests/all_algorithms_v2/summary.csv")
        old=pd.read_csv(old_path);old["version"]="previous";strategy.append(old)
        combined=pd.concat(strategy,ignore_index=True)
        turnover=[]
        for _,row in combined.iterrows():
            folder=root/"backtest" if row.version=="v2" else old_path.parent
            rules=json.loads((folder/"rules.json").read_text());charge=(rules["cost_bps_per_side"]+rules["slippage_bps_per_side"])/10000
            path=folder/f"{row.experiment}_h{int(row.horizon)}_{row.algorithm}_trades.csv"
            try:
                trades=pd.read_csv(path)
                value=float((trades.capital_before/(1+charge)+trades.capital_after/(1-charge)).sum()/rules["initial_cash"])
            except pd.errors.EmptyDataError: value=0.
            turnover.append(value)
        combined["gross_traded_notional_over_initial_cash"]=turnover
        combined.to_csv(root/"backtest_comparison.csv",index=False)
    validation=pd.DataFrame(validation)
    comparisons=pd.DataFrame(comparison)
    clean_validation=validation.astype(object).where(pd.notna(validation),None)
    clean_comparisons=comparisons.astype(object).where(pd.notna(comparisons),None)
    summary=dict(selection=frozen["selections"],selected_validation=clean_validation.to_dict("records"),
        regression_tests=clean_comparisons.loc[comparisons.group=="unseen"].to_dict("records"),
        caveats=["Reused historical test, not pristine prospective evidence","LSTM weight magnitudes are screening only; see separate validation permutation importance",
            "No maximum achievable accuracy claim","Native tree weights reused only with an identical schema; new schemas fit fresh",
            "Annual overlapping labels and limited independent outcomes still constrain probability/interval validation"])
    save_json(root/"experiment_summary.json",summary)
    css="body{font:16px system-ui;max-width:1400px;margin:30px auto;padding:20px;background:#f6f8fa;color:#182434}section{background:white;padding:20px;margin:20px 0}img{max-width:100%;height:auto}table{border-collapse:collapse;font-size:13px}td,th{padding:7px;border-bottom:1px solid #ddd}.scroll{overflow:auto}a{color:#0065a8}p{line-height:1.6}"
    links=" · ".join(f'<a href="{name}.csv">{label}</a>' for name,label in [("feature_ablation_results","Feature ablations"),("hyperparameter_results","All configurations"),
        ("validation_error_comparison","Validation comparison"),("model_comparison","Final test"),("direction_metrics","Direction"),("interval_metrics","Intervals"),("regime_metrics","Regimes"),("backtest_comparison","Backtests")])
    plots="".join(f'<section><h2>{h}-session price forecasts</h2><img loading="lazy" src="charts/comparison_h{h}.png"></section>' for h in protocol["horizons"])
    plots+="".join(f'<section><h2>{algorithm} · {h} sessions</h2><img loading="lazy" src="charts/learning_{algorithm}_h{h}.png"><img loading="lazy" src="charts/calibration_{algorithm}_h{h}.png"><img loading="lazy" src="charts/importance_{algorithm}_h{h}.png">'+(f'<img loading="lazy" src="charts/permutation_lstm_h{h}.png">' if algorithm=="lstm" else '')+f'<a href="charts/forecast_{algorithm}_h{h}.png">Detailed return/error chart</a></section>' for algorithm in protocol["algorithms"] for h in protocol["horizons"])
    body=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NightEye feature engineering v2</title><style>{css}</style>
<h1>NightEye v2 · validation-selected feature study</h1><p>All choices were frozen before this run opened the final test. This historical test has been inspected in earlier research. Improvements must beat baselines across folds; no live-market edge is implied.</p>
<p>{links}</p><p><a href="FINAL_REPORT.md">Research conclusions</a> · <a href="forecasts/index.html">Monte Carlo price paths</a> · <a href="backtest/report.html">Cost-aware backtest</a> · <a href="paper_journal_v2/index.html">New prospective journal</a> · <a href="verification.json">Verification</a></p>
<section><h2>Validation decisions</h2><div class="scroll">{validation.to_html(index=False,float_format=lambda x:f'{x:.6f}')}</div></section>
<section><h2>Unseen-company regression errors</h2><div class="scroll">{comparisons.loc[comparisons.group=='unseen'].to_html(index=False,float_format=lambda x:f'{x:.6f}')}</div></section>
<p>Price tracking can be explained by the starting price. Inspect return/error panels and unchanged-price baselines. LSTM return/direction checkpoints are chosen independently. Loss units differ by task and horizon. Annual uncertainty remains limited; inspect coverage.</p>{plots}</html>'''
    (root/"index.html").write_text(body,encoding="utf-8")
    return summary


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,default=DEFAULT)
    generate(p.parse_args().output.resolve())
