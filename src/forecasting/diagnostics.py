"""Training, reconstructed validation, calibration and test forecast plots.

Prices are aligned to TARGET dates, not origin dates. Validation uses past-only
fold estimators, never the final estimator that has seen the validation years.
"""
import argparse
import hashlib
import html
import json
from functools import lru_cache
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.pipeline import ROOT
from src.forecasting import VERSION
from src.forecasting.train import load_histories, prepare, macro_loss, save_json
from src.forecasting.protocol import partitions, span
from src.forecasting.models import fit, raw_predict
from src.forecasting.uncertainty import interval
from src.helper.benchmark import context_hashes, observation_hash

NAMES={"xgboost":"XGBoost","lightgbm":"LightGBM","lstm":"LSTM"}
SPLITS={"training":"Training · final model, in sample",
        "validation_fold1":"Validation fold 1 · past-only fold model",
        "validation_fold2":"Validation fold 2 · past-only fold model",
        "calibration":"Calibration · final return model, out of fit",
        "test":"Test · final model, held-out dates"}
COLORS={"xgboost":"#0072b2","lightgbm":"#009e73","lstm":"#cc79a7"}


def price_frame(frame,prediction,bank=None):
    prediction=np.asarray(prediction,dtype=float)
    if len(prediction)!=len(frame) or not np.isfinite(prediction).all():
        raise ValueError("Prediction length/values do not match observations")
    if frame.empty:
        return pd.DataFrame(columns=["origin_date","target_date","ticker","actual_price","predicted_price"])
    if frame.ticker.nunique()!=1 or frame.index.has_duplicates:
        raise ValueError("Price time-series charts require one stock and unique origin dates")
    if frame.target_date.isna().any() or (frame.target_date.to_numpy()<=frame.index.to_numpy()).any():
        raise ValueError("Every plotted outcome must have a known future target date")
    result=pd.DataFrame(dict(origin_date=frame.index.to_numpy(),target_date=frame.target_date.to_numpy(),
        ticker=frame.ticker.to_numpy(),origin_adjusted_close=frame.close.to_numpy(),
        actual_log_return=frame.target.to_numpy(),predicted_log_return=prediction,
        actual_price=frame.close.to_numpy()*np.exp(frame.target.to_numpy()),
        predicted_price=frame.close.to_numpy()*np.exp(prediction)))
    result["error_pct"]=(result.predicted_price/result.actual_price-1)*100
    if bank is not None:
        lo,hi=interval(prediction,frame.risk_scale,bank,.8)
        result["lower80"]=frame.close.to_numpy()*np.exp(lo)
        result["upper80"]=frame.close.to_numpy()*np.exp(hi)
    return result.sort_values("target_date").reset_index(drop=True)


def metrics(frame):
    if frame.empty: return dict(rows=0)
    actual=frame.actual_log_return.to_numpy()
    predicted=frame.predicted_log_return.to_numpy()
    return dict(rows=len(frame),price_mae=float(abs(frame.predicted_price-frame.actual_price).mean()),
        price_mape=float(abs(frame.error_pct).mean()/100),
        return_rmse=float(np.sqrt(np.mean((actual-predicted)**2))),
        unchanged_return_rmse=float(np.sqrt(np.mean(actual**2))),
        return_direction_accuracy=float(np.mean(np.sign(actual)==np.sign(predicted))),
        origin_start=str(frame.origin_date.min().date()),origin_end=str(frame.origin_date.max().date()),
        target_start=str(frame.target_date.min().date()),target_end=str(frame.target_date.max().date()))


@lru_cache(maxsize=1)
def plotting():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,
                         "axes.spines.right":False,"axes.grid":True,"grid.alpha":.18,
                         "figure.facecolor":"white","axes.facecolor":"white"})
    return plt,mdates


def save_figure(fig,path):
    plt,_=plotting()
    fig.savefig(path.with_suffix(".png"),dpi=150,bbox_inches="tight")
    fig.savefig(path.with_suffix(".svg"),bbox_inches="tight")
    plt.close(fig)


def plot_split(frame,algorithm,horizon,ticker,split,path):
    plt,mdates=plotting()
    fig,axes=plt.subplots(3,1,figsize=(12,8.5),sharex=True,gridspec_kw={"height_ratios":[2.2,1.1,1]})
    fig.suptitle(f"{NAMES[algorithm]} | {ticker} | {horizon} trading sessions\n{SPLITS[split]}",fontsize=15,fontweight="bold",y=.985)
    if frame.empty:
        for ax in axes:
            ax.text(.5,.5,"This stock was excluded from this fitting/validation block.\nNo in-sample curve is claimed.",ha="center",va="center",transform=ax.transAxes)
        fig.tight_layout(rect=(0,.03,1,.92)); save_figure(fig,path); return
    x=frame.target_date
    axes[0].plot(x,frame.actual_price,color="#202a35",label="Actual future adjusted price",linewidth=1.5)
    axes[0].plot(x,frame.predicted_price,color=COLORS[algorithm],label="Predicted future adjusted price",linewidth=1.25,alpha=.9)
    axes[0].plot(x,frame.origin_adjusted_close,color="#92989f",label="Unchanged-price baseline (origin close)",linewidth=.85,linestyle="--",alpha=.8)
    if "lower80" in frame:
        axes[0].fill_between(x,frame.lower80,frame.upper80,color=COLORS[algorithm],alpha=.10,label="Empirical 80% interval (coverage not guaranteed)")
    axes[0].set_ylabel("Adjusted price (INR)")
    axes[0].legend(loc="best",fontsize=8)
    axes[1].plot(x,np.expm1(frame.actual_log_return)*100,color="#202a35",label="Actual horizon return",linewidth=.9)
    axes[1].plot(x,np.expm1(frame.predicted_log_return)*100,color=COLORS[algorithm],label="Predicted horizon return",linewidth=1.1)
    axes[1].axhline(0,color="#777",linewidth=.7)
    axes[1].set_ylabel("Horizon return (%)")
    axes[1].legend(loc="best",fontsize=8)
    axes[2].plot(x,frame.error_pct,color="#c44e52",linewidth=.9)
    axes[2].axhline(0,color="#202a35",linewidth=.8)
    axes[2].set_ylabel("Price error (%)\n(predicted / actual − 1)")
    axes[2].set_xlabel("Target date — when the forecast outcome is observed")
    locator=mdates.AutoDateLocator(minticks=4,maxticks=9)
    axes[2].xaxis.set_major_locator(locator)
    axes[2].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    m=metrics(frame)
    text=f"{len(frame):,} forecasts | price MAE INR {m['price_mae']:.2f} | MAPE {m['price_mape']:.2%} | return RMSE {m['return_rmse']:.5f} | sign accuracy {m['return_direction_accuracy']:.2%}"
    fig.text(.5,.018,text,ha="center",fontsize=9)
    fig.tight_layout(rect=(0,.045,1,.985))
    save_figure(fig,path)


def learning_rows(model,fold):
    curves=model["learning_curve"]
    if model["algorithm"]=="lstm":
        return [dict(fold=fold,task="joint",iteration=r["epoch"],training=r["training_loss"],
                     validation=r.get("validation_loss"),best_iteration=model["rounds"],
                     metric="standardized MSE + 0.25 BCE (stock weighted)") for r in curves]
    metric="rmse" if model["task"]=="return" else "logloss"
    if model["algorithm"]=="xgboost":
        train=curves["validation_0"][metric]
        valid=curves["validation_1"][metric]
        label="Unweighted cumulative log-return RMSE" if model["task"]=="return" else "Unweighted binary log loss"
    else:
        key="rmse" if model["task"]=="return" else "binary_logloss"
        train=curves["training"][key]
        valid=curves["validation"][key]
        label="Train stock-weighted / validation unweighted RMSE" if model["task"]=="return" else "Train stock-weighted / validation unweighted log loss"
    factor=model["scale"] if model["task"]=="return" else 1.
    return [dict(fold=fold,task=model["task"],iteration=i+1,training=float(a)*factor,validation=float(b)*factor,
                 best_iteration=model["rounds"],metric=label) for i,(a,b) in enumerate(zip(train,valid))]


def plot_learning(rows,algorithm,horizon,path):
    plt,_=plotting()
    tasks=["joint"] if algorithm=="lstm" else ["return","direction"]
    fig,axes=plt.subplots(2,len(tasks),figsize=(12,7),squeeze=False)
    data=pd.DataFrame(rows)
    for i,fold in enumerate([1,2]):
        for j,task in enumerate(tasks):
            part=data.loc[(data.fold==fold)&(data.task==task)]
            ax=axes[i,j]
            ax.plot(part.iteration,part.training,label="Training",color="#0072b2")
            ax.plot(part.iteration,part.validation,label="Validation",color="#d55e00")
            ax.axvline(part.best_iteration.iloc[0],linestyle="--",color="#555",linewidth=1,label="Selected checkpoint")
            ax.set_title(f"Fold {fold} | {task}")
            ax.set_xlabel("Epoch" if algorithm=="lstm" else "Boosting round")
            ax.set_ylabel("Joint MSE + 0.25 BCE" if task=="joint" else "Log-return RMSE" if task=="return" else "Binary log loss",fontsize=9)
            ax.legend(fontsize=8)
    fig.suptitle(f"{NAMES[algorithm]} | {horizon} sessions | fold learning curves\nAll fitting companies; reconstructed selected settings; no test loss used",fontsize=13)
    fig.text(.5,.012,"Native losses: LightGBM training is stock weighted; tree validation is unweighted. LSTM joint losses are stock weighted.",ha="center",fontsize=8)
    fig.tight_layout(rect=(0,.035,1,.985))
    save_figure(fig,path)


def plot_comparison(tables,horizon,ticker,path):
    plt,mdates=plotting()
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True,gridspec_kw={"height_ratios":[2,1]})
    first=next(iter(tables.values()))
    axes[0].plot(first.target_date,first.actual_price,color="#202a35",linewidth=1.6,label="Actual future adjusted price")
    for algorithm,frame in tables.items():
        if not np.array_equal(frame.target_date,first.target_date) or not np.allclose(frame.actual_price,first.actual_price):
            raise ValueError("Comparison charts must use identical target dates and outcomes")
        axes[0].plot(frame.target_date,frame.predicted_price,color=COLORS[algorithm],linewidth=1.2,label=NAMES[algorithm])
        axes[1].plot(frame.target_date,frame.error_pct,color=COLORS[algorithm],linewidth=1,label=NAMES[algorithm])
    axes[0].set_ylabel("Adjusted price (INR)")
    axes[1].set_ylabel("Price error (%)")
    axes[1].set_xlabel("Target date")
    axes[1].axhline(0,color="#555",linewidth=.8)
    for ax in axes: ax.legend(fontsize=9)
    locator=mdates.AutoDateLocator(minticks=4,maxticks=9)
    axes[1].xaxis.set_major_locator(locator)
    axes[1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    fig.suptitle(f"{ticker} | {horizon} trading sessions | held-out test forecasts",fontsize=15,fontweight="bold")
    fig.tight_layout(rect=(0,0,1,.95));save_figure(fig,path)


def write_pages(output,cards,ticker,summary):
    css="body{font:16px system-ui;max-width:1280px;margin:30px auto;padding:20px;color:#182434;background:#f5f7fa}img{max-width:100%;height:auto;background:white}section{background:white;padding:20px;margin:20px 0;border-radius:12px}a{color:#0066a5}p{line-height:1.6}table{border-collapse:collapse;font-size:13px}td,th{padding:7px;border-bottom:1px solid #ddd}.scroll{overflow:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}"
    note="Price charts use target dates. Training is in sample; validation uses reconstructed past-only fold models. Validation was used to select settings and is not an untouched test. Price tracking can come from the starting price alone: compare the unchanged-price baseline and the return/error panels. Historical labeled data ends 23 October 2026; current paper forecasts may still be pending."
    links=[]
    for card in cards:
        directory=output/card["folder"]
        sections=[]
        for split,title in SPLITS.items():
            sections.append(f'<section id="{split}"><h2>{html.escape(title)}</h2><p><a href="{split}.png">PNG</a> · <a href="{split}.svg">SVG</a> · <a href="{split}.csv">Underlying forecasts CSV</a></p><img loading="lazy" src="{split}.png" alt="{html.escape(title)} actual versus predicted"></section>')
        sections.append('<section id="learning"><h2>Training and validation learning curves</h2><p>These are fold training curves, not repeated test evaluation. LSTM uses a joint loss; tree objectives have separate curves.</p><a href="learning_curves.csv">Loss data CSV</a><img loading="lazy" src="learning_curves.png" alt="Fold training and validation learning curves"></section>')
        title=f"{NAMES[card['algorithm']]} · {card['horizon']} sessions · {ticker}"
        doc=f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{css}</style><a href="../index.html">All models</a><h1>{html.escape(title)}</h1><p>{note}</p><nav>'+" · ".join(f'<a href="#{key}">{html.escape(label.split(" · ")[0])}</a>' for key,label in SPLITS.items())+' · <a href="#learning">Learning curves</a></nav>'+"".join(sections)+"</html>"
        (directory/"index.html").write_text(doc,encoding="utf-8")
        links.append(f'<section><h2><a href="{card["folder"]}/index.html">{html.escape(title)}</a></h2><a href="{card["folder"]}/index.html"><img loading="lazy" src="{card["folder"]}/test.png" alt="{html.escape(title)} test chart"></a></section>')
    comparisons="".join(f'<section><h2>{h}-session test comparison</h2><a href="test_comparison_h{h}.png">PNG</a> · <a href="test_comparison_h{h}.svg">SVG</a><img loading="lazy" src="test_comparison_h{h}.png" alt="All-model {h}-session test comparison"></section>' for h in sorted(set(c["horizon"] for c in cards)))
    doc=f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NightEye model diagnostics</title><style>{css}</style><h1>{html.escape(ticker)} · model diagnostics</h1><p>{note}</p><p>Each model has separate training, two validation folds, calibration, test and learning-curve graphs. All price graphs include returns and signed errors. <a href="summary.csv">Metrics CSV</a> · <a href="verification.json">Verification</a></p>'+comparisons+'<h2>Every model and split</h2><div class="grid">'+"".join(links)+'</div><section><h2>Per-stock split metrics</h2><div class="scroll">'+summary.to_html(index=False,float_format=lambda x:f"{x:.5f}")+"</div></section></html>"
    (output/"index.html").write_text(doc,encoding="utf-8")


def render_saved(output):
    """Refresh presentation from saved chart data without any additional fitting."""
    protocol=json.loads((output/"protocol.json").read_text())
    if not protocol.get("price_alignment","").startswith("Target date; actual="):
        raise ValueError("Not a diagnostics output directory")
    ticker=protocol["ticker"]
    cards,rows,tables=[],[],{}
    for directory in sorted(output.iterdir()):
        if not directory.is_dir() or not (directory/"learning_curves.csv").exists(): continue
        algorithm,number=directory.name.rsplit("_h",1)
        h=int(number)
        if algorithm not in NAMES: raise ValueError("Unsupported chart algorithm")
        for split in SPLITS:
            frame=pd.read_csv(directory/f"{split}.csv",parse_dates=["origin_date","target_date"])
            plot_split(frame,algorithm,h,ticker,split,directory/split)
            rows.append(dict(algorithm=algorithm,horizon=h,ticker=ticker,split=split,**metrics(frame)))
            if split=="test": tables.setdefault(h,{})[algorithm]=frame
        curves=pd.read_csv(directory/"learning_curves.csv").to_dict("records")
        plot_learning(curves,algorithm,h,directory/"learning_curves")
        cards.append(dict(algorithm=algorithm,horizon=h,folder=directory.name))
    summary=pd.DataFrame(rows)
    for h,comparison in tables.items(): plot_comparison(comparison,h,ticker,output/f"test_comparison_h{h}")
    write_pages(output,cards,ticker,summary)
    return len(cards)


def verify_saved_data(output):
    protocol=json.loads((output/"protocol.json").read_text())
    experiment=Path(protocol["experiments"][0])
    source=json.loads((experiment/"protocol.json").read_text())
    price_source=next(s for s in source["source_prices"] if s["ticker"]==protocol["ticker"])
    if hashlib.sha256(Path(price_source["file"]).read_bytes()).hexdigest()!=price_source["sha256"]:
        raise ValueError("Chart source prices changed")
    from src.helper.load_data import load_data
    history=load_data(Path(price_source["file"]))
    edges={k:pd.Timestamp(v) for k,v in source["boundaries"].items()}
    total=0
    checks=[]
    for directory in sorted(output.iterdir()):
        if not directory.is_dir() or not (directory/"learning_curves.csv").exists(): continue
        for split in SPLITS:
            frame=pd.read_csv(directory/f"{split}.csv",parse_dates=["origin_date","target_date"])
            if frame.empty: continue
            if not (frame.target_date>frame.origin_date).all(): raise ValueError("Invalid target-date alignment")
            np.testing.assert_allclose(frame.actual_price,history.close.reindex(pd.DatetimeIndex(frame.target_date)).to_numpy(),rtol=1e-10)
            np.testing.assert_allclose(frame.origin_adjusted_close,history.close.reindex(pd.DatetimeIndex(frame.origin_date)).to_numpy(),rtol=1e-10)
            np.testing.assert_allclose(frame.predicted_price,frame.origin_adjusted_close*np.exp(frame.predicted_log_return),rtol=1e-10)
            if split=="training": assert (frame.target_date<edges["calibration"]).all()
            elif split=="validation_fold1": assert (frame.origin_date>=edges["fold1"]).all() and (frame.target_date<edges["fold2"]).all()
            elif split=="validation_fold2": assert (frame.origin_date>=edges["fold2"]).all() and (frame.target_date<edges["calibration"]).all()
            elif split=="calibration": assert (frame.origin_date>=edges["calibration"]).all() and (frame.target_date<edges["test"]).all()
            else: assert (frame.origin_date>=edges["test"]).all()
            checks.append(dict(model=directory.name,split=split,forecasts=len(frame),target_prices_match_source=True,split_boundaries_verified=True))
            total+=len(frame)
    result=dict(checked_forecasts=total,checks=checks,source_price_hash_unchanged=True)
    save_json(output/"price_data_verification.json",result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--experiments",type=Path,nargs="+",default=[ROOT/"artifacts/forecasting/intensive_v1",ROOT/"artifacts/forecasting/lstm_sequence_v1"])
    p.add_argument("--ticker",default="RELIANCE.NS")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--render-only",action="store_true",help="Re-render an existing diagnostics folder; no model fitting")
    args=p.parse_args()
    args.output=args.output.resolve()
    allowed=(ROOT/"artifacts/diagnostics").resolve()
    if args.output==allowed or not args.output.is_relative_to(allowed):
        p.error("Use a child directory under artifacts/diagnostics")
    if args.render_only:
        verify_saved_data(args.output)
        print(f"Rendered {render_saved(args.output)} models: {args.output/'index.html'}")
        return
    if args.output.exists():
        p.error("Choose a new child directory under artifacts/diagnostics")
    protocols=[json.loads((e/"protocol.json").read_text()) for e in args.experiments]
    if any(m.get("version")!=VERSION for m in protocols): raise ValueError("Unsupported experiment")
    first=protocols[0]
    if any(m["boundaries"]!=first["boundaries"] or m["context_hashes"]!=first["context_hashes"] for m in protocols):
        raise ValueError("Experiments need identical date and context protocols")
    histories,sources=load_histories(Path(first["source_prices"][0]["file"]).parent)
    if args.ticker not in histories: raise ValueError("Ticker absent from frozen training snapshot")
    hashes={s["ticker"]:s["sha256"] for s in sources}
    if any(hashes!={s["ticker"]:s["sha256"] for s in m["source_prices"]} for m in protocols): raise ValueError("Price source mismatch")
    protected={str(file.resolve()):hashlib.sha256(file.read_bytes()).hexdigest() for exp in args.experiments for file in exp.rglob("*") if file.is_file()}
    args.output.mkdir(parents=True)
    save_json(args.output/"protocol.json",dict(ticker=args.ticker,experiments=[str(e.resolve()) for e in args.experiments],
        validation="Refit selected fold settings only, preserving chronology and purged boundaries; final saved models not refitted or modified",
        price_alignment="Target date; actual=origin adjusted close*exp(actual log return); predicted=origin adjusted close*exp(predicted log return)",
        caveat="In-sample training is optimistic; validation was used for selection; price-level tracking is not proof of return skill"))
    edges={k:pd.Timestamp(v) for k,v in first["boundaries"].items()}
    cards,summary,checks,test_tables=[],[],[],{}
    horizons=sorted(set(h for m in protocols for h in m["horizons"]))
    for h in horizons:
        matching=[(exp,m,a) for exp,m in zip(args.experiments,protocols) if h in m["horizons"] for a in m["algorithms"]]
        probe=joblib.load(matching[0][0]/f"h{h}"/matching[0][2]/"model.joblib")
        context=Path(probe["context_dir"])
        if context_hashes(context)!=first["context_hashes"]: raise ValueError("Context sources changed")
        base,families=prepare(histories,h,context)
        test_tables[h]={}
        for exp,protocol,algorithm in matching:
            print(f"Plotting {algorithm} h{h}; reconstructing selected validation folds",flush=True)
            bundle=joblib.load(exp/f"h{h}"/algorithm/"model.joblib")
            selection=json.loads((exp/f"h{h}"/algorithm/"selection.json").read_text())
            panel=base
            if algorithm=="lstm":
                from src.LSTM.model import sequences,fit as fit_lstm
                panel=sequences(base,bundle["regression"]["columns"],bundle["regression"]["lookback"])
            labeled=panel.dropna(subset=["target","target_date","risk_scale"])
            folds,training,cal,test=partitions(labeled,edges,protocol["held_out_companies"])
            if span(training)!=bundle["splits"]["training"] or observation_hash(test)!=bundle["splits"]["test_keys_sha256"]:
                raise ValueError("Reconstructed model partitions do not match saved model")
            folder=f"{algorithm}_h{h}"
            destination=args.output/folder
            destination.mkdir()
            tables={}
            for name,frame in [("training",training),("calibration",cal),("test",test)]:
                stock=frame.loc[frame.ticker==args.ticker]
                pred=raw_predict(bundle["regression"],stock) if len(stock) else np.array([])
                tables[name]=price_frame(stock,pred,bundle["residual_bank"] if name=="test" else None)
            # Test output must reproduce the already saved forecasts, not a diagnostic refit.
            saved=pd.read_csv(exp/f"h{h}"/algorithm/"test_predictions.csv",parse_dates=["Date"]).set_index("Date")
            saved=saved.loc[saved.ticker==args.ticker]
            np.testing.assert_array_equal(tables["test"].origin_date.to_numpy(),saved.index.to_numpy())
            np.testing.assert_allclose(tables["test"].predicted_log_return,saved.regression,rtol=1e-6,atol=1e-9)
            learning=[]
            for fold,(tr,va) in enumerate(folds,1):
                if tr.target_date.max()>=va.index.min(): raise ValueError("Validation label leakage")
                if algorithm=="lstm":
                    reg,cls=fit_lstm(tr,va,bundle["regression"]["columns"],selection["regression"]["params"],
                        protocol["max_epochs"],protocol["early_stopping_patience"])
                    expected=selection["regression"]["folds"][fold-1]
                    if reg["rounds"]!=expected["epochs"]: raise ValueError("LSTM validation checkpoint did not reproduce")
                    np.testing.assert_allclose(macro_loss(va,raw_predict(reg,va),"return"),expected["rmse"],rtol=1e-5)
                    learning+=learning_rows(reg,fold)
                else:
                    fitted={}
                    for task,key in [("return","regression"),("direction","direction")]:
                        choice=selection[key]
                        model=fit(algorithm,task,tr,families[choice["family"]],choice["params"],protocol["max_boosting_rounds"],
                            va,protocol["early_stopping_patience"],record_training=True)
                        if model["rounds"]!=choice["fold_rounds"][fold-1]: raise ValueError("Tree validation checkpoint did not reproduce")
                        np.testing.assert_allclose(macro_loss(va,raw_predict(model,va),task),choice["fold_losses"][fold-1],rtol=1e-5)
                        fitted[task]=model
                        learning+=learning_rows(model,fold)
                    reg,cls=fitted["return"],fitted["direction"]
                joblib.dump(dict(regression=reg,direction=cls),destination/f"validation_fold{fold}_models.joblib")
                stock=va.loc[va.ticker==args.ticker]
                pred=raw_predict(reg,stock) if len(stock) else np.array([])
                tables[f"validation_fold{fold}"]=price_frame(stock,pred)
                checks.append(dict(algorithm=algorithm,horizon=h,fold=fold,
                    train_labels_before_validation=True,best_checkpoint_reproduced=True,original_validation_loss_reproduced=True))
            for split in SPLITS:
                table=tables[split]
                if len(table):
                    np.testing.assert_allclose(table.actual_price,histories[args.ticker].close.reindex(pd.DatetimeIndex(table.target_date)).to_numpy(),rtol=1e-10)
                table.to_csv(destination/f"{split}.csv",index=False,float_format="%.17g")
                plot_split(table,algorithm,h,args.ticker,split,destination/split)
                summary.append(dict(algorithm=algorithm,horizon=h,ticker=args.ticker,split=split,**metrics(table)))
            pd.DataFrame(learning).to_csv(destination/"learning_curves.csv",index=False)
            plot_learning(learning,algorithm,h,destination/"learning_curves")
            save_json(destination/"metrics.json",{s:metrics(t) for s,t in tables.items()})
            test_tables[h][algorithm]=tables["test"]
            cards.append(dict(algorithm=algorithm,horizon=h,folder=folder))
        plot_comparison(test_tables[h],h,args.ticker,args.output/f"test_comparison_h{h}")
    summary=pd.DataFrame(summary)
    summary.to_csv(args.output/"summary.csv",index=False)
    if any(hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest for path,digest in protected.items()):
        raise ValueError("An existing model/result artifact changed")
    save_json(args.output/"verification.json",dict(original_artifacts_unchanged=True,protected_artifact_files=len(protected),
        validation_reconstruction=checks,test_predictions_reproduced=True,models=len(cards),
        split_charts=len(cards)*len(SPLITS),learning_curve_charts=len(cards),test_comparison_charts=len(horizons)))
    write_pages(args.output,cards,args.ticker,summary)
    print(f"Charts: {args.output/'index.html'}",flush=True)


if __name__=="__main__": main()
