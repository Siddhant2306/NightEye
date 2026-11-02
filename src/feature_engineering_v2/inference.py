"""Saved v2 schemas, independent sequence heads and contemporaneous peer ranks."""
import contextlib
import io
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from src.forecasting.features import build
from src.forecasting.models import logit
from src.helper.load_data import load_data
from src.feature_engineering_v2.features import stock_features,context_features,cross_features
from src.feature_engineering_v2.models import predict
from src.feature_engineering_v2 import SCHEMA

CROSS_COLUMNS=["v2_momentum_rank","v2_volatility_rank","v2_volume_rank","v2_return_percentile","v2_sector_momentum_rank"]


def task_frame(panel,model):
    if model["algorithm"]!="lstm": return panel
    from src.LSTM.model import sequences
    return sequences(panel,model["columns"],model["lookback"])


def keys(frame): return pd.MultiIndex.from_arrays([frame.index,frame.ticker],names=["Date","ticker"])


def predict_pair(bundle,panel):
    r=task_frame(panel,bundle["regression"])
    d=task_frame(panel,bundle["direction"])
    ret=pd.Series(predict(bundle["regression"],r),index=keys(r))
    probability=pd.Series(predict(bundle["direction"],d),index=keys(d))
    wanted=keys(panel)
    valid=wanted.isin(ret.index)&wanted.isin(probability.index)
    result=panel.loc[valid].copy();wanted=wanted[valid]
    result["regression"]=ret.reindex(wanted).to_numpy()
    result["raw_probability"]=probability.reindex(wanted).to_numpy()
    result["raw_probability"]=.5+bundle.get("direction_mixture",1.)*(result.raw_probability-.5)
    calibrator=bundle.get("calibrator")
    result["probability_up"]=result.raw_probability if calibrator is None else calibrator.predict_proba(logit(result.raw_probability.to_numpy()))[:,1]
    return result


@lru_cache(maxsize=4)
def peer_histories(directory,as_of,reference_tickers):
    root=Path(directory);cutoff=pd.Timestamp(as_of)
    result={}
    for ticker in reference_tickers:
        matches=list(root.glob(f"{ticker}_*.csv"))+list(root.glob(f"{ticker}.csv"))
        if len(matches)!=1: raise ValueError(f"Need exactly one contemporaneous peer history for {ticker} in {root}")
        with contextlib.redirect_stdout(io.StringIO()): history=load_data(matches[0])
        history=history.loc[history.index<=cutoff]
        if history.empty or history.index[-1]!=cutoff:
            raise ValueError(f"Peer {ticker} has no close at {as_of}; refresh all reference peers instead of reusing stale ranks")
        result[ticker]=history
    return result


@lru_cache(maxsize=6)
def peer_inputs(directory,as_of,reference_tickers,horizon,context):
    pieces=[]
    for symbol,prices in peer_histories(directory,as_of,reference_tickers).items():
        with contextlib.redirect_stdout(io.StringIO()): eligible,_=build(prices,horizon,symbol,context,include_target=False)
        if eligible.empty or eligible.index[-1]!=pd.Timestamp(as_of):
            raise ValueError(f"Peer {symbol} is not eligible at {as_of}; refresh all sectors' context as well as peer prices")
        daily=np.log(prices.close).diff()
        part=pd.DataFrame({"v2_momentum_21":np.log(prices.close/prices.close.shift(21)),
            "v2_std_21":daily.rolling(21).std(),"v2_relative_volume_21":prices.volume/prices.volume.rolling(21).mean().replace(0,np.nan)-1,
            "v2_momentum_1":np.log(prices.close/prices.close.shift(1))},index=prices.index).reindex(eligible.index)
        part["ticker"]=symbol;pieces.append(part)
    return pd.concat(pieces).sort_index()


def build_one(history,bundle,ticker,context_dir=None,peer_data_dir=None):
    if bundle.get("feature_schema")!=SCHEMA: raise ValueError("Unsupported v2 feature schema")
    context=Path(context_dir or bundle["context_dir"])
    frame,_=build(history,bundle["horizon"],ticker,context,include_target=False)
    extra,_,_=stock_features(history)
    market,_,_=context_features(frame,history,context,ticker)
    frame=frame.join(extra).join(market)
    columns=bundle["regression"]["columns"]+bundle["direction"]["columns"]
    if any(c in CROSS_COLUMNS for c in columns):
        default_peer=context.parent/"peers"
        directory=Path(peer_data_dir) if peer_data_dir is not None else default_peer if default_peer.exists() else Path(bundle["peer_data_dir"])
        cutoff=str(history.index[-1].date())
        peer_panel=peer_inputs(str(directory.resolve()),cutoff,tuple(bundle["reference_tickers"]),bundle["horizon"],str(context.resolve()))
        peer_panel=peer_panel.loc[peer_panel.ticker!=ticker].copy()
        wanted=["v2_momentum_21","v2_std_21","v2_relative_volume_21","v2_momentum_1"]
        part=extra[wanted].reindex(frame.index).copy();part["ticker"]=ticker
        peer_panel=pd.concat([peer_panel,part]).sort_index()
        ranks,_=cross_features(peer_panel,bundle["holdouts"])
        ranks=ranks.loc[peer_panel.ticker==ticker]
        frame=frame.join(ranks)
    return frame
