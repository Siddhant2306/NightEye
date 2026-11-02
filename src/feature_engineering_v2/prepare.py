"""Freeze design, sources and separated development/evaluation files before search."""
import argparse
import hashlib
import json
from pathlib import Path
import joblib
import pandas as pd
from src.pipeline import ROOT
from src.forecasting import VERSION
from src.forecasting.train import load_histories,prepare,save_json
from src.helper.benchmark import context_hashes,observation_hash
from src.feature_engineering_v2.features import stock_features,context_features,cross_features
from src.feature_engineering_v2 import SCHEMA

DEFAULT=ROOT/"artifacts/forecasting/feature_engineering_v2"


def protected_files(output):
    roots=[ROOT/"data",ROOT/"artifacts",ROOT/"src/XGBoost",ROOT/"src/LightGBM",ROOT/"src/LSTM"]
    result={}
    for root in roots:
        if not root.exists(): continue
        for file in root.rglob("*"):
            if file.is_file() and not file.resolve().is_relative_to(output.resolve()) and "__pycache__" not in file.parts and "test_temp" not in file.parts:
                result[str(file.resolve())]=hashlib.sha256(file.read_bytes()).hexdigest()
    return result


def check_protected(output):
    before=json.loads((output/"protected_originals.json").read_text())
    changed=[path for path,digest in before.items() if not Path(path).exists() or hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest]
    if changed: raise ValueError(f"Original files changed: {changed[:5]}")
    return len(before)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=DEFAULT)
    args=p.parse_args();out=args.output.resolve()
    if out.exists() or not out.is_relative_to((ROOT/"artifacts/forecasting").resolve()): p.error("Use a new forecasting experiment directory")
    references={"trees":ROOT/"artifacts/forecasting/intensive_v1","lstm":ROOT/"artifacts/forecasting/lstm_sequence_v1"}
    original=json.loads((references["trees"]/"protocol.json").read_text())
    lstm=json.loads((references["lstm"]/"protocol.json").read_text())
    if original["boundaries"]!=lstm["boundaries"]: raise ValueError("Reference boundaries differ")
    before=protected_files(out)
    out.mkdir(parents=True);(out/"data").mkdir();(out/"logs").mkdir()
    histories,sources=load_histories(Path(original["source_prices"][0]["file"]).parent)
    if {s["ticker"]:s["sha256"] for s in sources}!={s["ticker"]:s["sha256"] for s in original["source_prices"]}: raise ValueError("Frozen price source mismatch")
    context=ROOT/"data/context_v3"
    if context_hashes(context)!=original["context_hashes"]: raise ValueError("Frozen context mismatch")
    protocol=dict(original,feature_schema=SCHEMA,algorithms=["xgboost","lightgbm","lstm"],horizons=[1,21,252],
        references={k:str(v.resolve()) for k,v in references.items()},context_dir=str(context.resolve()),
        fold_cache=str((ROOT/"artifacts/diagnostics/reliance_v1").resolve()),
        search_design=dict(feature_families="F0 current selected columns per algorithm/task; F1..F7 marginal groups; F8 all groups including calendar; F9 top-three consistent groups selected in development",
            tree_round_ceiling=1500,tree_patience=50,warm_additional_rounds=200,
            lstm_epoch_ceiling=20,lstm_patience=3,lstm_sequences=[20,60,120],lstm_hidden=[16,32,64],epoch_ceiling_checks=[20,40,60],
            hyperparameters="Two regularization alternatives per tree task after ablation; bounded one-factor LSTM changes on best return family",
            selection="Minimum mean macro-stock validation RMSE / log loss; reject >0.5% worst-fold deterioration vs F0; within 0.1% of best mean prefer smaller worst baseline ratio and fewer features",
            f9="At most three marginal groups that improve both folds for the corresponding task; no final-test access",
            epoch_alias="If training stops naturally before 20, ceilings 40/60 share the same deterministic stopped trajectory; otherwise run them",
            warm_start="Only same ordered schema and past-only fold parents; tree continuation and LSTM weight fine-tuning with reset optimizer; never warm-start a validation fold from final-model weights"),
        evaluation_policy="No evaluation_h*.joblib, final test reports or strategy outcomes read by development workers. Freeze all algorithm/task/horizon selections before evaluation.",
        cross_section="Training-company reference peers only; excluded-company prices never enter training ranks. Fresh inference requires contemporaneous reference peers.",
        caveat="Historical final test has been repeatedly inspected in earlier studies; process isolation does not make it a new prospective test")
    save_json(out/"protocol.json",protocol);save_json(out/"protected_originals.json",before)
    stock_cache={};groups=None;registry={}
    for ticker,history in histories.items():
        values,groups,meta=stock_features(history);stock_cache[ticker]=values;registry.update(meta)
    baseline_columns={}
    for h in [1,21,252]:
        print(f"Preparing causal features h{h}",flush=True)
        panel,_=prepare(histories,h,context)
        frames=[]
        context_groups=None
        for ticker,part in panel.groupby("ticker",sort=False):
            part=part.copy()
            extra,cg,meta=context_features(part,histories[ticker],context,ticker)
            part=part.join(stock_cache[ticker]).join(extra)
            frames.append(part);context_groups=cg;registry.update(meta)
        # Restore the reference panel's exact row order after per-company feature joins.
        enriched=pd.concat(frames)
        keys=pd.MultiIndex.from_arrays([enriched.index,enriched.ticker])
        lookup=pd.Series(range(len(enriched)),index=keys)
        wanted=pd.MultiIndex.from_arrays([panel.index,panel.ticker])
        enriched=enriched.iloc[lookup.reindex(wanted).to_numpy()].copy()
        cross,meta=cross_features(enriched,protocol["held_out_companies"])
        enriched=pd.concat([enriched,cross],axis=1);registry.update(meta)
        all_groups=dict(groups,**context_groups,cross_section=list(cross.columns))
        baseline_columns[str(h)]={}
        for algorithm in protocol["algorithms"]:
            ref=references["lstm" if algorithm=="lstm" else "trees"]
            bundle=joblib.load(ref/f"h{h}"/algorithm/"model.joblib")
            baseline_columns[str(h)][algorithm]={task:bundle[key]["columns"] for task,key in [("return","regression"),("direction","direction")]}
            test=enriched.loc[(enriched.index>=pd.Timestamp(protocol["boundaries"]["test"]))&enriched.target.notna()]
            if observation_hash(test)!=bundle["splits"]["test_keys_sha256"]: raise ValueError("New features changed final-test observation keys")
        boundary=pd.Timestamp(protocol["boundaries"]["test"])
        dev=enriched.loc[(enriched.index<boundary)&~enriched.ticker.isin(protocol["held_out_companies"])].copy()
        # Features needed for sequences are retained; future test-period outcomes are not.
        dev.loc[dev.target_date>=boundary,"target"]=float("nan")
        joblib.dump(dev,out/"data"/f"development_h{h}.joblib",compress=3)
        joblib.dump(enriched.loc[enriched.index>=boundary,["ticker","target","target_date","close","risk_scale"]],out/"data"/f"evaluation_h{h}.joblib",compress=3)
        joblib.dump(enriched.drop(columns="target"),out/"data"/f"unlabeled_h{h}.joblib",compress=3)
    save_json(out/"feature_groups.json",all_groups);save_json(out/"feature_registry.json",registry)
    save_json(out/"baseline_columns.json",baseline_columns)
    check_protected(out)
    print(f"Prepared isolated experiment: {out}",flush=True)


if __name__=="__main__": main()
