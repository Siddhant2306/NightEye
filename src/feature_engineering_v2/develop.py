"""Bounded development-only ablations, continuation and one-factor optimization."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.feature_engineering_v2.prepare import DEFAULT
from src.feature_engineering_v2.features import GROUPS,columns_for
from src.feature_engineering_v2.models import tree_fit,lstm_fit,predict
from src.feature_engineering_v2.metrics import score,primary,aggregate,choose
from src.forecasting.train import save_json
from src.forecasting.protocol import before,window,span
from src.helper.benchmark import observation_hash


def config(identifier,family,groups,columns,params,method="fresh",lookback=20,epochs=20,stage="ablation"):
    return dict(id=identifier,family=family,groups=groups,columns=columns,params=params,method=method,
                lookback=lookback,epochs=epochs,stage=stage)


def development_folds(panel,edges):
    labeled=panel.dropna(subset=["target","target_date","risk_scale"])
    return [(before(labeled,a),window(labeled,a,b)) for a,b in [(edges["fold1"],edges["fold2"]),(edges["fold2"],edges["calibration"])]]


def run_config(root,algorithm,horizon,proposal,frame,protocol,old_selection,parents):
    directory=root/"development"/algorithm/f"h{horizon}"/proposal["id"]
    signature=hashlib.sha256(json.dumps(proposal,sort_keys=True).encode()).hexdigest()
    result_path=directory/"result.json"
    if result_path.exists():
        result=json.loads(result_path.read_text())
        if result["signature"]!=signature: raise ValueError("Existing configuration fingerprint differs")
        return result
    directory.mkdir(parents=True,exist_ok=True)
    panel=frame
    if algorithm=="lstm":
        from src.LSTM.model import sequences
        cols=proposal["columns"]["return"]
        if cols!=proposal["columns"]["direction"]: raise ValueError("One LSTM run requires the same input columns for its two heads")
        panel=sequences(frame,cols,proposal["lookback"])
    edges={k:pd.Timestamp(v) for k,v in protocol["boundaries"].items()}
    # Calibration rows and masked future labels are never consumed by this worker.
    panel=panel.loc[panel.index<edges["calibration"]]
    folds=development_folds(panel,edges)
    records=[]
    print(f"{algorithm} h{horizon} {proposal['id']}: {proposal['family']} / {proposal['method']}",flush=True)
    for fold,(training,valid) in enumerate(folds,1):
        if training.empty or valid.empty or training.target_date.max()>=valid.index.min(): raise ValueError("Invalid chronological fold")
        original_parent=parents[fold-1]
        if algorithm=="lstm":
            if proposal["method"]=="reuse":
                models={"return":original_parent["regression"],"direction":original_parent["direction"]}
            else:
                models=lstm_fit(training,valid,proposal["columns"]["return"],proposal["params"],proposal["epochs"],
                    protocol["search_design"]["lstm_patience"],original_parent["regression"] if proposal["method"]=="warm" else None)
        else:
            models={}
            for task,columns in proposal["columns"].items():
                parent=original_parent["regression" if task=="return" else "direction"]
                if proposal["method"]=="reuse": models[task]=parent
                else:
                    limit=protocol["search_design"]["warm_additional_rounds" if proposal["method"]=="warm" else "tree_round_ceiling"]
                    models[task]=tree_fit(algorithm,task,training,columns,proposal["params"][task],limit,valid,
                        protocol["search_design"]["tree_patience"],parent if proposal["method"]=="warm" else None)
        record=dict(fold=fold,training={},validation={},checkpoints={},training_span=span(training),validation_span=span(valid),
                    validation_keys=observation_hash(valid),missing={})
        for task,model in models.items():
            record["training"][task]=score(training,predict(model,training),task)
            record["validation"][task]=score(valid,predict(model,valid),task)
            record["missing"][task]=float(training[model["columns"]].isna().to_numpy().mean())
            record["checkpoints"][task]=dict(total=model["rounds"],additional=model.get("additional_epochs",model.get("additional_rounds",0 if proposal["method"]=="reuse" else model["rounds"])),
                stopped_early=model.get("stopped_early"),observed_epochs=len(model.get("learning_curve",[])) if algorithm=="lstm" else None)
            if proposal["method"]=="reuse":
                expected=old_selection["regression" if task=="return" else "direction"]
                value=expected["folds"][fold-1]["rmse" if task=="return" else "log_loss"] if algorithm=="lstm" else expected["fold_losses"][fold-1]
                np.testing.assert_allclose(primary(record["validation"][task],task),value,rtol=1e-5)
        joblib.dump(models,directory/f"fold{fold}.joblib",compress=3)
        save_json(directory/f"fold{fold}_learning.json",{task:model["learning_curve"] for task,model in models.items()})
        records.append(record)
        print("  fold "+str(fold)+": "+", ".join(f"{task}={primary(value,task):.6f}" for task,value in record["validation"].items()),flush=True)
    result=dict(proposal,signature=signature,records=records,aggregate={task:aggregate(records,task) for task in records[0]["validation"]})
    save_json(result_path,result)
    return result


def alias(root,algorithm,horizon,identifier,source,family=None,epochs=None):
    result=copy.deepcopy(source);result.update(id=identifier,alias_of=source["id"],stage="deterministic_alias")
    if family: result["family"]=family
    if epochs: result["epochs"]=epochs
    directory=root/"development"/algorithm/f"h{horizon}"/identifier;directory.mkdir(parents=True,exist_ok=True)
    save_json(directory/"result.json",result)
    return result


def run_algorithm(root,algorithm,horizons=None):
    protocol=json.loads((root/"protocol.json").read_text())
    groups=json.loads((root/"feature_groups.json").read_text())
    bases=json.loads((root/"baseline_columns.json").read_text())
    output=root/"development"/algorithm;output.mkdir(parents=True,exist_ok=True)
    selected={}
    for h in (horizons or protocol["horizons"]):
        from filelock import FileLock
        lock=FileLock(str(output/f"h{h}.lock"));lock.acquire()
        if (output/f"h{h}"/"selection.json").exists() and (output/f"h{h}"/"all_results.json").exists():
            selected[str(h)]=json.loads((output/f"h{h}"/"selection.json").read_text());lock.release();continue
        # The worker never opens evaluation_h*.joblib or any final-test prediction file.
        frame=joblib.load(root/"data"/f"development_h{h}.joblib")
        if frame.ticker.isin(protocol["held_out_companies"]).any(): raise ValueError("Company holdout leaked into development")
        reference=Path(protocol["references"]["lstm" if algorithm=="lstm" else "trees"])
        old=json.loads((reference/f"h{h}"/algorithm/"selection.json").read_text())
        base=bases[str(h)][algorithm]
        parents=[joblib.load(Path(protocol["fold_cache"])/f"{algorithm}_h{h}"/f"validation_fold{k}_models.joblib") for k in [1,2]]
        default_lstm=dict(hidden=16,dropout=.1,learning_rate=.001,weight_decay=.001,batch_size=512,gradient_clip=1.,direction_weight=.25)
        parameters=default_lstm if algorithm=="lstm" else {task:old[key]["params"] for task,key in [("return","regression"),("direction","direction")]}
        options=[]
        def run(c):
            result=run_config(root,algorithm,h,c,frame,protocol,old,parents);options.append(result);return result
        f0=run(config("F0","F0",[],base,parameters,"fresh" if algorithm=="lstm" else "reuse"))
        if algorithm=="lstm": run(config("OLD","old_lstm",[],base,parameters,"reuse",stage="baseline"))
        for identifier,group in GROUPS.items():
            cols={task:columns_for(columns,groups,[group]) for task,columns in base.items()}
            run(config(identifier,identifier,[group],cols,parameters))
        cols={task:columns_for(columns,groups,list(groups)) for task,columns in base.items()}
        run(config("F8","F8",list(groups),cols,parameters))
        warm=copy.deepcopy(parameters)
        if algorithm=="lstm": warm["learning_rate"]=.0003
        else:
            for params in warm.values(): params["learning_rate"]=.003
        run(config("W0","F0",[],base,warm,"warm",stage="continuation"))
        # F9 uses only consistently improving marginal groups, at most three per objective.
        combinations=[]
        for task in ["return","direction"]:
            base_errors=np.asarray(f0["aggregate"][task]["fold_errors"])
            good=[o for o in options if o["id"] in GROUPS and np.all(np.asarray(o["aggregate"][task]["fold_errors"])<base_errors)]
            good=sorted(good,key=lambda o:o["aggregate"][task]["mean"])[:3]
            names=[o["groups"][0] for o in good]
            if not names:
                options.append(alias(root,algorithm,h,"F9_"+task,f0,"F9"));continue
            if names in combinations:
                source=next(o for o in options if o["family"]=="F9" and o["groups"]==names)
                options.append(alias(root,algorithm,h,"F9_"+task,source,"F9"));continue
            combinations.append(names)
            if algorithm=="lstm":
                cols={t:columns_for(base[t],groups,names) for t in base}
            else: cols={task:columns_for(base[task],groups,names)}
            run(config("F9_"+task,"F9",names,cols,parameters,stage="combination"))
        if algorithm!="lstm":
            for task in ["return","direction"]:
                winner,_=choose(options,task)
                for number in [1,2]:
                    params=copy.deepcopy(old["regression" if task=="return" else "direction"]["params"])
                    params.update(learning_rate=.015 if number==1 else .03,depth=1 if number==1 else 3,
                        leaf_min=150 if number==1 else 75,l2=100. if number==1 else 30.,alpha=1. if number==1 else .1,
                        gamma=.1 if number==1 else .01,sample=.8,colsample=.7 if number==1 else .8)
                    if algorithm=="lightgbm": params.update(leaves=2 if number==1 else 7,hessian_min=.1 if number==1 else .01)
                    run(config(f"H_{task}_{number}",winner["family"],winner["groups"],{task:winner["columns"][task]},
                               {task:params},stage="hyperparameter"))
        else:
            winner,_=choose(options,"return")
            cols=winner["columns"]
            # If a single-task F9 winner is ever present, both heads still use its return schema.
            cols={"return":cols["return"],"direction":cols.get("direction",cols["return"])}
            fresh_base=next((o for o in options if o["method"]=="fresh" and o["lookback"]==20 and o["params"]==default_lstm and o["columns"]==cols),None)
            if fresh_base is None: fresh_base=run(config("A_base",winner["family"],winner["groups"],cols,default_lstm,stage="architecture"))
            for lookback in [60,120]: run(config(f"A_sequence_{lookback}",winner["family"],winner["groups"],cols,default_lstm,lookback=lookback,stage="architecture"))
            for hidden in [32,64]: run(config(f"A_hidden_{hidden}",winner["family"],winner["groups"],cols,dict(default_lstm,hidden=hidden),stage="architecture"))
            for name,value in [("learning_rate",.0003),("weight_decay",.01),("dropout",.3),("batch_size",256),("gradient_clip",.5),("direction_weight",.1)]:
                run(config("O_"+name,winner["family"],winner["groups"],cols,dict(default_lstm,**{name:value}),stage="optimizer"))
            for ceiling in [40,60]:
                if all(r["checkpoints"]["return"]["stopped_early"] for r in fresh_base["records"]):
                    options.append(alias(root,algorithm,h,f"E_{ceiling}",fresh_base,epochs=ceiling))
                else: run(config(f"E_{ceiling}",winner["family"],winner["groups"],cols,default_lstm,epochs=ceiling,stage="epoch_ceiling"))
        chosen={}
        for task in ["return","direction"]:
            winner,absolute=choose(options,task)
            chosen[task]=dict(selected=winner["id"],absolute_minimum=absolute["id"],
                validation=winner["aggregate"][task],absolute_validation=absolute["aggregate"][task],
                columns=winner["columns"][task],family=winner["family"],groups=winner["groups"],method=winner["method"])
        selected[str(h)]=chosen
        save_json(output/f"h{h}"/"selection.json",chosen)
        save_json(output/f"h{h}"/"all_results.json",options)
        print(f"SELECTED {algorithm} h{h}: "+json.dumps({t:c["selected"] for t,c in chosen.items()}),flush=True)
        lock.release()
    if all((output/f"h{h}"/"selection.json").exists() for h in protocol["horizons"]):
        selected={str(h):json.loads((output/f"h{h}"/"selection.json").read_text()) for h in protocol["horizons"]}
        save_json(output/"complete.json",dict(algorithm=algorithm,selections=selected,final_test_read=False))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=DEFAULT)
    p.add_argument("--algorithm",choices=["xgboost","lightgbm","lstm"],required=True)
    p.add_argument("--horizons",type=int,nargs="+",choices=[1,21,252])
    args=p.parse_args();run_algorithm(args.output.resolve(),args.algorithm,args.horizons)
