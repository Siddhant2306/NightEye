"""Fresh v2 snapshot with complete eligible peer prices/context when ranks are used."""
import argparse
import hashlib
import json
import shutil
from datetime import timedelta
from pathlib import Path
import pandas as pd
import yfinance as yf
import joblib
from src.forecasting.market_data import snapshot,refresh_context,completed_cutoff
from src.forecasting.train import save_json
from src.context_sources import SECTOR_FOR
from src.feature_engineering_v2.inference import CROSS_COLUMNS
from src.feature_engineering_v2.prepare import DEFAULT


def create(root,ticker,output):
    protocol=json.loads((root/"protocol.json").read_text())
    models=[joblib.load(root/f"h{h}"/a/"model.joblib") for a in protocol["algorithms"] for h in protocol["horizons"]]
    need_peers=any(any(c in CROSS_COLUMNS for c in m[t]["columns"]) for m in models for t in ["regression","direction"])
    manifest=snapshot(ticker,output,Path(protocol["context_dir"]))
    if need_peers:
        try:
            peers=output/"peers";peers.mkdir()
            required=models[0]["reference_tickers"]
            origin=pd.read_csv(output/f"{ticker}.csv",usecols=["Date"]).Date.iloc[-1]
            cutoff=completed_cutoff()
            for symbol in required:
                destination=peers/f"{symbol}.csv"
                if symbol==ticker: shutil.copy2(output/f"{ticker}.csv",destination)
                else:
                    data=yf.download(symbol,start="2016-01-01",end=str(cutoff+timedelta(days=1)),auto_adjust=False,actions=True,progress=False,threads=False,timeout=20)
                    if data.empty: raise ValueError(f"No peer data for {symbol}")
                    if data.columns.nlevels>1: data.columns=data.columns.get_level_values(0)
                    data.index=pd.to_datetime(data.index).tz_localize(None)
                    data=data.loc[data.index.date<=cutoff].sort_index().dropna(subset=["Open","High","Low","Close","Adj Close","Volume"])
                    factor=data["Adj Close"]/data.Close
                    adjusted=data[["Open","High","Low","Close","Volume"]].copy()
                    adjusted[["Open","High","Low","Close"]]=adjusted[["Open","High","Low","Close"]].mul(factor,axis=0)
                    adjusted.index.name="Date";adjusted.to_csv(destination)
                last=pd.read_csv(destination,usecols=["Date"]).Date.iloc[-1]
                if last!=origin: raise ValueError(f"Peer {symbol} last date {last} differs from target {origin}")
                print(f"Peer snapshot {symbol}: {last}",flush=True)
            # Training ranks use the same eligible company definition as the original
            # context pipeline, so every reference sector must be current as well.
            representatives={}
            for symbol in required: representatives.setdefault(SECTOR_FOR[symbol],symbol)
            for representative in representatives.values(): refresh_context(output/"context",representative,cutoff)
            manifest["peer_reference_tickers"]=required
            manifest["peer_source"]="Fresh contemporaneous training-company peers; held-out companies excluded"
        except Exception as exc:
            manifest["status"]="INCOMPLETE_PEERS";manifest["error"]=str(exc)
    manifest["files_sha256"]={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob("*.csv")}
    save_json(output/"manifest.json",manifest)
    if manifest["status"]!="READY": raise RuntimeError(manifest.get("error","Snapshot incomplete"))
    return manifest


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--experiment",type=Path,default=DEFAULT)
    p.add_argument("--ticker",default="RELIANCE.NS")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args();print(json.dumps(create(args.experiment,args.ticker,args.output),indent=2))
