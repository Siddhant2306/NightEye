import pandas as pd
import numpy as np
from src.forecasting.protocol import before, window


def inner_split(frame, cutoff, horizon):
    """Reserve a mature tail for checkpoint selection, then purge the fit."""
    available=before(frame,cutoff)
    dates=available.index.unique().sort_values()
    boundary=dates[int(.8*len(dates))]
    train=before(available,boundary)
    valid=window(available,boundary,cutoff)
    if min(len(train),len(valid))<100:
        raise ValueError(f'Insufficient inner support for horizon {horizon}')
    return train,valid


def audit(frame):
    origin=pd.to_datetime(frame['origin'])
    target=pd.to_datetime(frame['target_date'])
    if not ((pd.to_datetime(frame.training_start)<=pd.to_datetime(frame.training_end)) &
            (pd.to_datetime(frame.training_end)<origin) &
            (pd.to_datetime(frame.latest_training_label)<origin) &
            (pd.to_datetime(frame.selection_latest_label)<origin) &
            (pd.to_datetime(frame.prediction_timestamp)==origin) & (target>origin) &
            (frame.training_rows>0)).all():
        raise ValueError('OOF temporal ordering or label maturity violated')
    if frame.duplicated(['horizon','model','ticker','origin']).any():
        raise ValueError('Duplicate OOF prediction key')
    if not np.isfinite(frame[['regression','probability_up','target']].to_numpy()).all() or not frame.probability_up.between(0,1).all():
        raise ValueError('Invalid OOF forecast or target')


def aligned(frame, models):
    audit(frame)
    if frame.horizon.nunique()!=1 or set(frame.model)!=set(models):
        raise ValueError('Expected one horizon and the exact base-model set')
    group=frame.groupby(['origin','ticker'],sort=False)
    if (group.target_date.nunique()!=1).any() or (group.target.nunique()!=1).any():
        raise ValueError('Inconsistent OOF targets')
    keys=['origin','ticker']
    returns=frame.pivot(index=keys,columns='model',values='regression').reindex(columns=models)
    probs=frame.pivot(index=keys,columns='model',values='probability_up').reindex(columns=models)
    if returns.isna().any().any() or probs.isna().any().any():
        raise ValueError('Incomplete OOF model coverage')
    meta=frame.drop_duplicates(keys).set_index(keys).reindex(returns.index)
    return meta,returns.to_numpy(),probs.to_numpy()
