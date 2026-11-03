import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor,LGBMClassifier
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from src.forecasting.ensemble import weights,loss


def inputs(returns,probabilities):
    return np.column_stack([returns,probabilities,returns.std(axis=1),probabilities.std(axis=1),
                            np.abs(probabilities-.5).mean(axis=1)])


def fit_one(method,task,x,y,regularization):
    if method=='linear_stack':
        model=Ridge(alpha=regularization) if task=='return' else LogisticRegression(C=1/regularization,max_iter=300)
        model=make_pipeline(StandardScaler(),model)
    else:
        cls=LGBMRegressor if task=='return' else LGBMClassifier
        model=cls(n_estimators=int(regularization),max_depth=2,num_leaves=4,min_child_samples=150,
                  reg_lambda=25,learning_rate=.03,n_jobs=2,verbosity=-1,random_state=42)
    return model.fit(x,y if task=='return' else y>0)


def predict_one(model,x,task):
    return model.predict(x) if task=='return' else model.predict_proba(x)[:,1]


def fit(meta,returns,probabilities,horizon):
    origin=pd.DatetimeIndex(meta.index.get_level_values('origin'))
    second=meta.fold.to_numpy()==2
    boundary=origin[second].min()
    first=(meta.fold.to_numpy()==1)&(pd.to_datetime(meta.target_date).to_numpy()<boundary.to_datetime64())
    support=[origin[mask].nunique() for mask in [first,second]]
    minimum=max(42,2*horizon)
    report=dict(fit_dates=support[0],validation_dates=support[1],minimum_per_part=minimum,
                validation_start=str(boundary.date()),fit_latest_label=str(pd.to_datetime(meta.target_date[first]).max().date()),
                oof_rows=len(meta))
    if min(support)<minimum:
        return {},dict(report,status='insufficient chronological OOF support')
    y=meta.target.to_numpy()
    features=inputs(returns,probabilities)
    fitted={};details={}
    for task,matrix in [('return',returns),('direction',probabilities)]:
        for method,values in [('weighted',[0.,.1,1.]),('linear_stack',[100.,1000.]),('lightgbm_stack',[20,50])]:
            def train(mask,value):
                return weights(matrix[mask],y[mask],task,value) if method=='weighted' else fit_one(method,task,features[mask],y[mask],value)
            trials=[]
            for value in values:
                model=train(first,value)
                p=matrix[second]@model if method=='weighted' else predict_one(model,features[second],task)
                trials.append(dict(parameter=value,loss=loss(y[second],p,task),
                                   weights=model.tolist() if method=='weighted' else None))
            best=min(trials,key=lambda t:t['loss'])
            fitted.setdefault(method,{})[task]=train(np.ones(len(y),dtype=bool),best['parameter'])
            details[f'{method}_{task}']=dict(selected=best,trials=trials,
                equal_loss=loss(y[second],matrix[second].mean(axis=1),task),
                final_weights=fitted[method][task].tolist() if method=='weighted' else None)
    return fitted,dict(report,status='fitted',trials=details)


def combine(fitted,returns,probabilities):
    output={'equal':(returns.mean(axis=1),probabilities.mean(axis=1)),
            'equal_without_tcn':(returns[:,:3].mean(axis=1),probabilities[:,:3].mean(axis=1))}
    x=inputs(returns,probabilities)
    for name,models in fitted.items():
        if name=='weighted':
            output[name]=(returns@models['return'],probabilities@models['direction'])
        else:
            output[name]=tuple(predict_one(models[task],x,task) for task in ['return','direction'])
    return output
