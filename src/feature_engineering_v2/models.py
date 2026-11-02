"""Native continuation and independent RMSE/log-loss LSTM checkpoints."""
import copy
import numpy as np
import lightgbm as lgb
from xgboost import XGBRegressor,XGBClassifier
from sklearn.metrics import log_loss
from src.pipeline import weights
from src.helper.benchmark import ordered_features
from src.forecasting.models import raw_predict
from src.feature_engineering_v2.metrics import score,primary


def predict(model,frame):
    if model["algorithm"]=="lightgbm":
        result=np.asarray(model["model"].predict(ordered_features(frame,model["columns"]),num_threads=2))*model["scale"]+model["center"]
    else: result=raw_predict(model,frame)
    if model.get("output_risk_scaled",False): result=result*frame.risk_scale.to_numpy()
    if model.get("task")=="return": result=result*model.get("output_shrinkage",1.)
    if not np.isfinite(result).all(): raise ValueError("Nonfinite prediction")
    return result


def native_loss(frame,prediction,task):
    return float(np.sqrt(np.mean((frame.target.to_numpy()-prediction)**2))) if task=="return" else float(log_loss((frame.target>0).astype(int),np.clip(prediction,1e-7,1-1e-7),labels=[0,1]))


def tree_fit(algorithm,task,training,columns,params,rounds,valid=None,patience=50,parent=None):
    if parent is not None:
        if parent["columns"]!=columns or parent["algorithm"]!=algorithm or parent["task"]!=task: raise ValueError("Continuation requires identical ordered feature schema, algorithm and task")
        if rounds==0: return dict(parent,additional_rounds=0,reused=True)
    classification=task=="direction"
    center=0. if classification else float(training.target.mean())
    scale=1. if classification else max(float(training.target.std()),1e-8)
    if parent is not None and not np.allclose([center,scale],[parent["center"],parent["scale"]],rtol=1e-8,atol=1e-10):
        raise ValueError("Continuation target preprocessing differs; parent may have a different fitting window")
    X=ordered_features(training,columns)
    y=(training.target>0).astype(int) if classification else (training.target-center)/scale
    vy=None if valid is None else ((valid.target>0).astype(int) if classification else (valid.target-center)/scale)
    init_count=0
    common=dict(learning_rate=params["learning_rate"],max_depth=params["depth"],subsample=params.get("sample",.8),
        colsample_bytree=params.get("colsample",.8),reg_lambda=params["l2"],reg_alpha=params.get("alpha",.1),random_state=42,n_jobs=2)
    if algorithm=="xgboost":
        ctor=XGBClassifier if classification else XGBRegressor
        model=ctor(**common,n_estimators=rounds,tree_method="hist",min_child_weight=params["leaf_min"],gamma=params.get("gamma",0.),
            objective="binary:logistic" if classification else "reg:squarederror",eval_metric="logloss" if classification else "rmse",
            early_stopping_rounds=patience if valid is not None else None)
        kw=dict(sample_weight=weights(training),verbose=False)
        if valid is not None: kw["eval_set"]=[(X,y),(ordered_features(valid,columns),vy)]
        if parent is not None:
            initial=parent["model"].get_booster()[:parent["rounds"]]
            init_count=initial.num_boosted_rounds();kw["xgb_model"]=initial
        model.fit(X,y,**kw)
        best=model.best_iteration+1 if valid is not None else init_count+rounds
        curves=model.evals_result() if valid is not None else {}
    else:
        config=dict(**common,objective="binary" if classification else "regression",metric="binary_logloss" if classification else "rmse",
            verbosity=-1,num_leaves=params.get("leaves",2**params["depth"]),min_child_samples=params["leaf_min"],
            min_child_weight=params.get("hessian_min",.001),min_split_gain=params.get("gamma",0.),subsample_freq=1,
            deterministic=True,force_col_wise=True)
        data=lgb.Dataset(X,label=y,weight=weights(training),free_raw_data=False)
        curves={};callbacks=[lgb.log_evaluation(0),lgb.record_evaluation(curves)]
        kw={}
        if valid is not None:
            kw.update(valid_sets=[data,lgb.Dataset(ordered_features(valid,columns),label=vy,reference=data)],valid_names=["training","validation"])
            callbacks.append(lgb.early_stopping(patience,first_metric_only=True,verbose=False))
        if parent is not None:
            initial=lgb.Booster(model_str=parent["model"].model_to_string(num_iteration=parent["rounds"]))
            init_count=initial.current_iteration();kw["init_model"]=initial
        model=lgb.train(config,data,num_boost_round=rounds,callbacks=callbacks,keep_training_booster=True,**kw)
        best=model.best_iteration if valid is not None else model.current_iteration()
        # Persist only the selected checkpoint, not the patience tail.
        model=lgb.Booster(model_str=model.model_to_string(num_iteration=max(1,best)))
    result=dict(model=model,algorithm=algorithm,task=task,columns=columns,center=center,scale=scale,
        rounds=int(max(1,best)),additional_rounds=int(max(0,best-init_count)),learning_curve=curves,params=params,
        reused=parent is not None,initial_rounds=init_count)
    if parent is not None and valid is not None:
        old_loss=native_loss(valid,predict(parent,valid),task)
        new_loss=native_loss(valid,predict(result,valid),task)
        result["initial_validation_loss"]=old_loss
        if new_loss>=old_loss:
            result=dict(parent,additional_rounds=0,reused=True,initial_rounds=parent["rounds"],
                learning_curve=curves,initial_validation_loss=old_loss,params=params)
    return result


def lstm_fit(training,valid,columns,config,epochs=20,patience=3,parent=None,final_checkpoints=None):
    import torch
    from torch import nn
    from src.LSTM.model import Network,preprocessing,tensor_batch,infer
    torch.set_num_threads(2);torch.manual_seed(42);torch.use_deterministic_algorithms(True)
    rng=np.random.default_rng(42)
    feature_center,feature_spread=preprocessing(training,columns)
    center=float(training.target.mean());scale=max(float(training.target.std()),1e-8)
    model=Network(len(columns),config["hidden"],config["dropout"])
    start_epoch=0
    if parent is not None:
        if parent["columns"]!=columns or parent["config"]["hidden"]!=config["hidden"]: raise ValueError("LSTM fine-tuning requires a compatible input/hidden schema")
        if not np.allclose([center,scale],[parent["center"],parent["scale"]],rtol=1e-8): raise ValueError("Warm LSTM target window changed")
        np.testing.assert_allclose(feature_center,parent["feature_center"],rtol=1e-6,atol=1e-7)
        np.testing.assert_allclose(feature_spread,parent["feature_spread"],rtol=1e-6,atol=1e-7)
        model.load_state_dict({k:torch.from_numpy(v.copy()) for k,v in parent["state"].items()})
        start_epoch=parent["rounds"]
    optimizer=torch.optim.AdamW(model.parameters(),lr=config["learning_rate"],weight_decay=config["weight_decay"])
    y=torch.tensor((training.target.to_numpy()-center)/scale,dtype=torch.float32)
    labels=torch.tensor((training.target.to_numpy()>0).astype(np.float32))
    w=torch.tensor(weights(training),dtype=torch.float32)
    batch=config.get("batch_size",512);direction_weight=config.get("direction_weight",.25)
    curves=[];best={"return":float("inf"),"direction":float("inf")};states={};selected={};stale={"return":0,"direction":0}
    def snapshot(): return {k:v.detach().cpu().numpy().copy() for k,v in model.state_dict().items()}
    def record(epoch,train_joint):
        tr,tp=infer(model,training,feature_center,feature_spread)
        tr=tr.astype(float)*scale+center
        tm={"return":score(training,tr,"return"),"direction":score(training,tp,"direction")}
        row=dict(epoch=epoch+start_epoch,additional_epoch=epoch,training_joint=train_joint,
            training_return_rmse=tm["return"]["macro_rmse"],training_direction_log_loss=tm["direction"]["macro_log_loss"])
        if valid is not None:
            vr,vp=infer(model,valid,feature_center,feature_spread);vr=vr.astype(float)*scale+center
            vm={"return":score(valid,vr,"return"),"direction":score(valid,vp,"direction")}
            pv=np.clip(vp,1e-7,1-1e-7);truth=(valid.target.to_numpy()>0).astype(float)
            row.update(validation_joint=float(np.average(((vr-valid.target.to_numpy())/scale)**2+direction_weight*(-truth*np.log(pv)-(1-truth)*np.log(1-pv)),weights=weights(valid))),
                validation_return_rmse=vm["return"]["macro_rmse"],validation_direction_log_loss=vm["direction"]["macro_log_loss"])
            for task in best:
                value=primary(vm[task],task)
                if value<best[task]-1e-7:
                    best[task]=value;selected[task]=epoch;states[task]=snapshot();stale[task]=0
                else: stale[task]+=1
        elif final_checkpoints is not None:
            for task,checkpoint in final_checkpoints.items():
                if epoch==checkpoint: selected[task]=epoch;states[task]=snapshot()
        curves.append(row)
        print(f"    LSTM epoch +{epoch}/{epochs}: train RMSE {row['training_return_rmse']:.5f}"+(f", val RMSE {row['validation_return_rmse']:.5f}, val logloss {row['validation_direction_log_loss']:.5f}" if valid is not None else ""),flush=True)
    if parent is not None: record(0,None)
    for epoch in range(1,epochs+1):
        model.train();order=rng.permutation(len(training));total=0.
        for start in range(0,len(order),batch):
            indices=order[start:start+batch]
            optimizer.zero_grad();prediction,logits=model(tensor_batch(training,indices,feature_center,feature_spread))
            each=(prediction-y[indices])**2+direction_weight*nn.functional.binary_cross_entropy_with_logits(logits,labels[indices],reduction="none")
            loss=(each*w[indices]).mean()
            if not torch.isfinite(loss): raise ValueError("Nonfinite LSTM loss")
            loss.backward();nn.utils.clip_grad_norm_(model.parameters(),config.get("gradient_clip",1.));optimizer.step()
            total+=float(loss.detach())*len(indices)
        record(epoch,total/len(training))
        if valid is not None and all(n>=patience for n in stale.values()): break
    for task in best:
        if task not in states: selected[task]=epochs;states[task]=snapshot()
    models={}
    for task in best:
        models[task]=dict(algorithm="lstm",task=task,columns=columns,config=config,
            lookback=int(training._sequence.iloc[0].shape[0]),feature_center=feature_center,feature_spread=feature_spread,
            state=states[task],rounds=start_epoch+selected[task],additional_epochs=selected[task],
            center=center if task=="return" else 0.,scale=scale if task=="return" else 1.,
            learning_curve=curves,reused=parent is not None,initial_epochs=start_epoch,
            stopped_early=len(curves)-(1 if parent is not None else 0)<epochs,
            checkpoint_metric="validation macro-stock RMSE" if task=="return" else "validation macro-stock binary log loss")
    return models
