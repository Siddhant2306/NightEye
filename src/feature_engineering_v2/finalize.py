"""Freeze every development decision, fit selected models, then evaluate once."""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.forecasting import VERSION
from src.forecasting.train import save_json,evaluate
from src.forecasting.protocol import before,window,span
from src.feature_engineering_v2.calibration import guarded_calibrate
from src.forecasting.uncertainty import residual_bank,interval,interval_metrics
from src.helper.benchmark import observation_hash,align_reference
from src.feature_engineering_v2 import SCHEMA
from src.feature_engineering_v2.prepare import DEFAULT,check_protected
from src.feature_engineering_v2.models import tree_fit,lstm_fit,predict
from src.feature_engineering_v2.inference import task_frame,predict_pair,keys
from src.feature_engineering_v2.metrics import score


def freeze(root):
    protocol=json.loads((root/"protocol.json").read_text())
    chosen={};digests={}
    for algorithm in protocol["algorithms"]:
        chosen[algorithm]={}
        for h in protocol["horizons"]:
            directory=root/"development"/algorithm/f"h{h}"
            if not (directory/"selection.json").exists() or not (directory/"all_results.json").exists():
                raise ValueError(f"Development incomplete: {algorithm} h{h}; final test remains closed")
            chosen[algorithm][str(h)]=json.loads((directory/"selection.json").read_text())
            for file in directory.rglob("*"):
                if file.is_file(): digests[str(file.relative_to(root))]=hashlib.sha256(file.read_bytes()).hexdigest()
    path=root/"selection_frozen.json"
    if path.exists():
        previous=json.loads(path.read_text())
        if previous["development_files_sha256"]!=digests: raise ValueError("Development changed after freeze")
        return previous
    result=dict(frozen_at=datetime.now(timezone.utc).isoformat(),selections=chosen,development_files_sha256=digests,
                selection_data="Only first-64%-period purged development folds; final test and calibration metrics did not select configurations")
    save_json(path,result);return result


def train_selected(root,algorithm,h,protocol,selections):
    frame=joblib.load(root/"data"/f"development_h{h}.joblib")
    reference=Path(protocol["references"]["lstm" if algorithm=="lstm" else "trees"])
    old=joblib.load(reference/f"h{h}"/algorithm/"model.joblib")
    edges={k:pd.Timestamp(v) for k,v in protocol["boundaries"].items()}
    all_results=json.loads((root/"development"/algorithm/f"h{h}"/"all_results.json").read_text())
    options={o["id"]:o for o in all_results}
    fitted={};training_frames={};cal_frames={};final_trace={}
    ids={task:selections[task]["selected"] for task in ["return","direction"]}
    for identifier in dict.fromkeys(ids.values()):
        option=options[identifier];tasks=[task for task in ids if ids[task]==identifier]
        if algorithm=="lstm":
            from src.LSTM.model import sequences
            panel=sequences(frame,option["columns"]["return"],option["lookback"])
        else: panel=frame
        labeled=panel.dropna(subset=["target","target_date","risk_scale"])
        training=before(labeled,edges["calibration"])
        cal=window(labeled,edges["calibration"],edges["test"])
        for task in tasks: training_frames[task]=training;cal_frames[task]=cal
        if option["method"]=="reuse":
            for task in tasks:
                fitted[task]=old["regression" if task=="return" else "direction"]
                if span(training)!=old["splits"]["training"]: raise ValueError("Reused final fitting window differs")
            final_trace[identifier]=dict(method="reused existing weights",additional_training=0)
            continue
        counts={task:max(0,int(np.median([record["checkpoints"][task]["additional" if option["method"]=="warm" else "total"] for record in option["records"]]))) for task in tasks}
        if algorithm=="lstm":
            parent=old["regression"] if option["method"]=="warm" else None
            if max(counts.values())==0:
                models={task:old["regression" if task=="return" else "direction"] for task in tasks}
            else:
                models=lstm_fit(training,None,option["columns"]["return"],option["params"],max(counts.values()),
                    protocol["search_design"]["lstm_patience"],parent=parent,final_checkpoints=counts)
            for task in tasks: fitted[task]=models[task]
        else:
            for task in tasks:
                fitted[task]=tree_fit(algorithm,task,training,option["columns"][task],option["params"][task],counts[task],
                    parent=old["regression" if task=="return" else "direction"] if option["method"]=="warm" else None)
        final_trace[identifier]=dict(method=option["method"],selected_counts=counts,
            learning_curves={task:fitted[task].get("learning_curve",{}) for task in tasks})
    reg,cls=fitted["return"],fitted["direction"]
    cal=cal_frames["return"];dircal=cal_frames["direction"]
    if not keys(cal).equals(keys(dircal)): raise ValueError("Calibration head observation keys differ")
    calpred=predict(reg,cal);calraw=predict(cls,dircal)
    bank=residual_bank(cal.target,calpred,cal.risk_scale)
    calibrator,calibration_check=guarded_calibrate(calraw,dircal,h)
    bundle=dict(version=VERSION,feature_schema=SCHEMA,algorithm=algorithm,horizon=h,regression=reg,direction=cls,
        control=old["control"],calibrator=calibrator,probability_calibration_check=calibration_check,residual_bank=bank,threshold=protocol["signal_threshold"],
        context_dir=protocol["context_dir"],peer_data_dir=str(Path(protocol["source_prices"][0]["file"]).parent),
        reference_tickers=sorted(s["ticker"] for s in protocol["source_prices"] if s["ticker"] not in protocol["held_out_companies"]),
        holdouts=protocol["held_out_companies"],boundaries=protocol["boundaries"],seed=42,
        training_mean=float(training_frames["return"].target.mean()),prior_probability=float((training_frames["direction"].target>0).mean()),
        selections=selections,feature_registry_sha256=hashlib.sha256((root/"feature_registry.json").read_bytes()).hexdigest(),
        splits=dict(training=span(training_frames["return"]),direction_training=span(training_frames["direction"]),calibration=span(cal)),
        calibration_intervals=interval_metrics(cal.target.to_numpy(),calpred,cal.risk_scale,bank),
        target="After-close cumulative adjusted-price log return; independent task-selected feature/checkpoint configurations")
    return bundle,final_trace


def run(root,algorithm,horizons):
    frozen=json.loads((root/"selection_frozen.json").read_text())
    protocol=json.loads((root/"protocol.json").read_text())
    # Recheck selected metadata before opening any test labels; all algorithms must have finished.
    freeze(root)
    for h in horizons or protocol["horizons"]:
        directory=root/f"h{h}"/algorithm
        if (directory/"metrics.json").exists(): continue
        print(f"Final selected fit {algorithm} h{h}",flush=True)
        selection=frozen["selections"][algorithm][str(h)]
        bundle,trace=train_selected(root,algorithm,h,protocol,selection)
        full=joblib.load(root/"data"/f"unlabeled_h{h}.joblib")
        predictions=predict_pair(bundle,full)
        predictions=predictions.loc[predictions.index>=pd.Timestamp(protocol["boundaries"]["test"])]
        directory.mkdir(parents=True,exist_ok=True)
        save_json(directory/"test_access.json",dict(selection_frozen_at=frozen["frozen_at"],
            selection_sha256=hashlib.sha256((root/"selection_frozen.json").read_bytes()).hexdigest(),
            first_label_access=datetime.now(timezone.utc).isoformat()))
        actual=joblib.load(root/"data"/f"evaluation_h{h}.joblib")
        actual=actual.dropna(subset=["target","target_date","risk_scale"])
        wanted=keys(actual)
        lookup=pd.Series(np.arange(len(predictions)),index=keys(predictions))
        positions=lookup.reindex(wanted)
        if positions.isna().any(): raise ValueError("Final-test observation keys changed")
        features=predictions.iloc[positions.astype(int).to_numpy()].copy()
        frame=actual.copy()
        for c in ["regression","raw_probability","probability_up"]: frame[c]=features[c].to_numpy()
        frame["control"]=predict(bundle["control"],features)
        frame["group"]=np.where(frame.ticker.isin(protocol["held_out_companies"]),"unseen","seen")
        frame["zero_return"],frame["historical_mean"]=0.,bundle["training_mean"]
        frame["prior_probability"]=bundle["prior_probability"]
        frame["vol_regime"]=features.v2_market_vol_state.map({0.:"low",1.:"medium",2.:"high"}).fillna("unknown").to_numpy()
        frame["trend_regime"]=features.v2_market_trend_state.map({-1.:"bear",0.:"sideways",1.:"bull"}).fillna("unknown").to_numpy()
        for coverage in [.5,.8,.95]:
            frame[f"lower_{coverage}"],frame[f"upper_{coverage}"]=interval(frame.regression,frame.risk_scale,bundle["residual_bank"],coverage)
        old_reference=Path(protocol["references"]["lstm" if algorithm=="lstm" else "trees"])
        old_bundle=joblib.load(old_reference/f"h{h}"/algorithm/"model.joblib")
        if observation_hash(frame)!=old_bundle["splits"]["test_keys_sha256"]: raise ValueError("Unmatched frozen test")
        bundle["splits"].update(test=span(frame),test_keys_sha256=observation_hash(frame))
        joblib.dump(bundle,directory/"model.joblib",compress=3)
        restored=joblib.load(directory/"model.joblib")
        again=predict_pair(restored,full)
        again=again.iloc[pd.Series(np.arange(len(again)),index=keys(again)).reindex(wanted).astype(int).to_numpy()]
        np.testing.assert_allclose(frame.regression,again.regression,rtol=1e-8,atol=1e-9)
        np.testing.assert_allclose(frame.probability_up,again.probability_up,rtol=1e-8,atol=1e-9)
        frame.to_csv(directory/"test_predictions.csv",index_label="Date",float_format="%.17g")
        metrics=evaluate(frame,bundle["threshold"],h)
        for group,m in metrics.items():
            part=frame if group=="all" else frame.loc[frame.group==group]
            m["regression_v2"]=score(part,part.regression,"return")
            m["classifier_v2"]=score(part,part.probability_up,"direction")
        save_json(directory/"metrics.json",metrics);save_json(directory/"final_training.json",trace)
        save_json(directory/"selection.json",selection)
        pd.DataFrame([dict(ticker=t,**score(p,p.regression,"return")) for t,p in frame.groupby("ticker")]).to_csv(directory/"per_stock.csv",index=False)
        print(f"Evaluated {algorithm} h{h}: unseen RMSE {metrics['unseen']['regression']['rmse']:.6f}",flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=DEFAULT)
    p.add_argument("--freeze-only",action="store_true")
    p.add_argument("--algorithm",choices=["xgboost","lightgbm","lstm"])
    p.add_argument("--horizons",type=int,nargs="+",choices=[1,21,252])
    args=p.parse_args();root=args.output.resolve()
    if args.freeze_only: freeze(root)
    elif args.algorithm: run(root,args.algorithm,args.horizons)
    else: p.error("Specify --freeze-only or --algorithm")
