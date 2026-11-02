"""Consistent regression/probability metrics and stability-based selection."""
import numpy as np
from sklearn.metrics import confusion_matrix,f1_score,log_loss
from src.forecasting.models import direction_metrics
from src.LightGBM.metrics import correlation


def score(frame,prediction,task):
    y=frame.target.to_numpy();p=np.asarray(prediction,dtype=float)
    if not np.isfinite(p).all(): raise ValueError("Nonfinite prediction")
    if task=="return":
        error=p-y
        return dict(rmse=float(np.sqrt(np.mean(error**2))),mae=float(np.mean(abs(error))),bias=float(error.mean()),
            r2=float(1-np.sum(error**2)/np.sum((y-y.mean())**2)) if np.var(y)>0 else None,
            macro_rmse=float(np.mean([np.sqrt(np.mean(error[(frame.ticker==t).to_numpy()]**2)) for t in frame.ticker.unique()])),
            pearson=correlation(y,p),spearman=correlation(y,p,True),
            price_mape=float(np.mean(abs(np.expm1(error)))),direction_accuracy=float(np.mean(np.sign(y)==np.sign(p))))
    result=direction_metrics(y,np.clip(p,1e-7,1-1e-7))
    result.update(macro_log_loss=float(np.mean([log_loss((g.target>0).astype(int),np.clip(p[(frame.ticker==t).to_numpy()],1e-7,1-1e-7),labels=[0,1]) for t,g in frame.groupby("ticker")])),
        f1=float(f1_score(y>0,p>=.5,zero_division=0)),confusion_matrix=confusion_matrix(y>0,p>=.5,labels=[False,True]).tolist(),
        confusion_labels=["NOT_UP","UP"],up_predictions=int((p>=.5).sum()),not_up_predictions=int((p<.5).sum()))
    return result


def primary(metrics,task): return metrics["macro_rmse" if task=="return" else "macro_log_loss"]


def aggregate(records,task):
    values=np.array([primary(r["validation"][task],task) for r in records])
    train=np.array([primary(r["training"][task],task) for r in records])
    result=dict(mean=float(values.mean()),median=float(np.median(values)),std=float(values.std()),worst=float(values.max()),
        fold_errors=values.tolist(),training_mean=float(train.mean()),gap=float((values-train).mean()))
    if task=="return":
        result.update(mean_mae=float(np.mean([r["validation"][task]["mae"] for r in records])),
            mean_bias=float(np.mean([r["validation"][task]["bias"] for r in records])))
    return result


def choose(options,task):
    available=[o for o in options if task in o["aggregate"] and not o.get("alias_of")]
    baseline=next(o for o in available if o["id"]=="F0")
    base=np.asarray(baseline["aggregate"][task]["fold_errors"])
    absolute=min(available,key=lambda o:o["aggregate"][task]["mean"])
    eligible=[o for o in available if np.all(np.asarray(o["aggregate"][task]["fold_errors"])<=base*1.005)]
    minimum=min(o["aggregate"][task]["mean"] for o in eligible)
    near=[o for o in eligible if o["aggregate"][task]["mean"]<=minimum*1.001]
    selected=min(near,key=lambda o:(float(np.max(np.asarray(o["aggregate"][task]["fold_errors"])/base)),len(o["columns"][task]),o["id"]))
    return selected,absolute
