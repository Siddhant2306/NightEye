"""Pre-test-only, purged forward gate for optional probability calibration."""
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss,log_loss
from src.forecasting.models import calibrate,logit


def losses(actual, probability):
    y=np.asarray(actual)>0;p=np.clip(np.asarray(probability,dtype=float),1e-7,1-1e-7)
    return dict(brier=float(brier_score_loss(y,p)),log_loss=float(log_loss(y,p,labels=[False,True])))


def guarded_calibrate(raw,frame,horizon):
    """Keep raw unless calibration wins on a later, label-purged calibration tail.

    The 70/30 origin-date split and two horizon-sized blocks per part are fixed
    safeguards, not claims of independent samples or statistical significance.
    No final-test inputs belong in this function. Accepted calibration refits on
    the complete calibration block only after this forward check.
    """
    p=np.asarray(raw,dtype=float)
    if len(p)!=len(frame) or not np.isfinite(p).all(): raise ValueError("Invalid calibration alignment")
    dates=pd.DatetimeIndex(frame.index).unique().sort_values()
    report=dict(policy="purged-70-30-forward-v1",accepted=False,horizon=int(horizon),rows=len(frame),origin_dates=len(dates),
                minimum_dates_per_part=2*max(21,horizon))
    if len(dates)<2:
        return None,dict(report,reason="insufficient_origin_dates")
    boundary=dates[min(len(dates)-1,int(.7*len(dates)))]
    fit=(frame.index<boundary)&(frame.target_date<boundary)
    valid=frame.index>=boundary
    report.update(boundary=str(boundary.date()),fit_rows=int(fit.sum()),validation_rows=int(valid.sum()),
                  fit_dates=int(frame.index[fit].nunique()),validation_dates=int(frame.index[valid].nunique()))
    if min(report['fit_dates'],report['validation_dates'])<report['minimum_dates_per_part']:
        return None,dict(report,reason="insufficient_mature_forward_blocks")
    if min(int(fit.sum()),int(valid.sum()))<100:
        return None,dict(report,reason="insufficient_rows")
    candidate=calibrate(p[fit],frame.target.to_numpy()[fit])
    if candidate is None: return None,dict(report,reason="insufficient_fit_classes")
    adjusted=candidate.predict_proba(logit(p[valid]))[:,1]
    y=frame.target.to_numpy()[valid]
    prior=float((frame.target.to_numpy()[fit]>0).mean())
    report.update(raw=losses(y,p[valid]),calibrated=losses(y,adjusted),prior=losses(y,np.full(len(y),prior)))
    accepted=all(report['calibrated'][key]<min(report['raw'][key],report['prior'][key]) for key in ['brier','log_loss'])
    report.update(accepted=accepted,reason="forward_gain_over_raw_and_prior" if accepted else "no_forward_gain_over_raw_and_prior")
    return (calibrate(p,frame.target.to_numpy()) if accepted else None),report
