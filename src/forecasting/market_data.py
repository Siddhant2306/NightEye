"""Read-only fresh market snapshots; preserve frozen research sources."""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import yfinance as yf
from src.pipeline import ROOT
from src.context_sources import SECTOR_FOR, INDEX_NAMES, ExchangeClient
from src.forecasting.train import save_json


def now_utc():
    return datetime.now(timezone.utc)


def completed_cutoff(now=None):
    local=(now or now_utc()).astimezone(ZoneInfo("Asia/Kolkata"))
    # Conservative EOD buffer; intraday bars are not accepted as completed sessions.
    return local.date() if local.hour>=17 else local.date()-timedelta(days=1)


def refresh_context(context, ticker, cutoff):
    client=ExchangeClient(context/"raw_refresh")
    records=[]
    for key,kind in [("market","prices"),(SECTOR_FOR[ticker],"prices"),("market","valuation")]:
        path=context/"indices"/f"{key}_{kind}.csv"
        old=pd.read_csv(path,parse_dates=["Date"])
        start=pd.Timestamp(old.Date.max()).date()-timedelta(days=10)
        name=INDEX_NAMES[key]
        payload="{'name':'%s','startDate':'%s','endDate':'%s','indexName':'%s'}" % (name,start.strftime("%d-%b-%Y"),cutoff.strftime("%d-%b-%Y"),name)
        endpoint="getHistoricaldatatabletoString" if kind=="prices" else "getpepbHistoricaldataDBtoString"
        try:
            content=client.get(f"{key}_{kind}_{cutoff}.json","https://www.niftyindices.com/BackPage/"+endpoint,{"cinfo":payload})
            data=json.loads(content)
            if isinstance(data,dict) and "d" in data:
                data=json.loads(data["d"]) if isinstance(data["d"],str) else data["d"]
            fresh=pd.DataFrame(data)
            if fresh.empty: raise ValueError("Empty index response")
            if kind=="prices":
                fresh["Date"]=pd.to_datetime(fresh.HistoricalDate,format="%d %b %Y")
                fresh["close"]=pd.to_numeric(fresh.CLOSE,errors="raise")
                fresh=fresh[["Date","close"]]
            else:
                fresh["Date"]=pd.to_datetime(fresh.DATE,format="%d %b %Y")
                for c in ["pe","pb","divYield"]: fresh[c]=pd.to_numeric(fresh[c],errors="coerce")
                fresh=fresh[["Date","pe","pb","divYield"]]
            fresh=fresh.loc[fresh.Date.dt.date<=cutoff]
            merged=pd.concat([old,fresh]).sort_values("Date").drop_duplicates("Date",keep="last")
            merged.to_csv(path,index=False)
            records.append(dict(series=f"{key}_{kind}",latest=str(merged.Date.max().date()),success=True))
        except Exception as exc:
            records.append(dict(series=f"{key}_{kind}",success=False,error=str(exc)))
    save_json(context/"refresh_audit.json",dict(records=records,requests=client.requests))
    return records


def freshness(history, context, ticker, retrieved_at, now=None):
    now=now or now_utc()
    bar=pd.Timestamp(history.index.max()).date()
    issues=[]
    if bar>completed_cutoff(now): issues.append("Contains an incomplete or future daily bar")
    age=(now.astimezone(ZoneInfo("Asia/Kolkata")).date()-bar).days
    if age>5: issues.append(f"Stock bar is {age} calendar days old")
    stamp=datetime.fromisoformat(retrieved_at)
    if stamp.tzinfo is None or not 0 <= (now-stamp).total_seconds() <= 12*3600:
        issues.append("Snapshot must have been retrieved in the last 12 hours")
    used={}
    for key,kind in [("market","prices"),(SECTOR_FOR[ticker],"prices"),("market","valuation")]:
        dates=pd.read_csv(context/"indices"/f"{key}_{kind}.csv",usecols=["Date"],parse_dates=["Date"]).Date
        eligible=dates.loc[dates.dt.date<bar]
        if eligible.empty:
            issues.append(f"No prior-session {key}_{kind} context")
            continue
        latest=eligible.max().date()
        used[f"{key}_{kind}"]=str(latest)
        if (bar-latest).days>4: issues.append(f"Stale {key}_{kind}: latest eligible source {latest}")
    return dict(ready=not issues,issues=issues,latest_stock_bar=str(bar),eligible_context_dates=used)


def snapshot(ticker, output, base_context):
    if ticker not in SECTOR_FOR: raise ValueError("Ticker requires an existing sector/context mapping")
    if output.exists(): raise FileExistsError("Use a new snapshot directory")
    output.mkdir(parents=True)
    retrieved=now_utc().isoformat()
    manifest=dict(ticker=ticker,retrieved_at=retrieved,provider="Yahoo Finance via yfinance; official Nifty context refresh",
        status="INCOMPLETE",fundamentals="Copied frozen as-published filings, not automatically refreshed; age/missingness retained",
        limitations=["Public EOD feed, not an exchange tick feed or broker execution price",
                    "Provider-adjusted historical series may be revised",
                    "No orders or account access"])
    try:
        cutoff=completed_cutoff()
        raw=yf.download(ticker,start="2016-01-01",end=str(cutoff+timedelta(days=1)),auto_adjust=False,
                        actions=True,progress=False,threads=False,timeout=20)
        if raw.empty: raise ValueError("Market provider returned no prices")
        if raw.columns.nlevels>1: raw.columns=raw.columns.get_level_values(0)
        raw.index=pd.to_datetime(raw.index).tz_localize(None)
        raw=raw.loc[raw.index.date<=cutoff].sort_index()
        required=["Open","High","Low","Close","Adj Close","Volume"]
        raw=raw.dropna(subset=required)
        if raw.empty or (raw[required[:5]]<=0).any().any() or (raw.Volume<0).any(): raise ValueError("Invalid market OHLCV")
        raw.index.name="Date"
        raw.to_csv(output/"provider_raw.csv")
        factor=raw["Adj Close"]/raw.Close
        adjusted=raw[["Open","High","Low","Close","Volume"]].copy()
        adjusted[["Open","High","Low","Close"]]=adjusted[["Open","High","Low","Close"]].mul(factor,axis=0)
        adjusted.to_csv(output/f"{ticker}.csv")
        context=output/"context"
        context.mkdir()
        for sub in ["indices","fundamentals"]:
            shutil.copytree(base_context/sub,context/sub)
        manifest["context_refresh"]=refresh_context(context,ticker,cutoff)
        adjusted.columns=[c.lower() for c in adjusted.columns]
        manifest["freshness"]=freshness(adjusted,context,ticker,retrieved)
        manifest["status"]="READY" if manifest["freshness"]["ready"] else "STALE_OR_INCOMPLETE"
        manifest["files_sha256"]={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in output.rglob("*.csv")}
    except Exception as exc:
        manifest["error"]=str(exc)
    save_json(output/"manifest.json",manifest)
    if manifest["status"]!="READY":
        raise RuntimeError(f"Fresh snapshot unavailable; see {output/'manifest.json'}: {manifest.get('error',manifest.get('freshness'))}")
    return manifest


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ticker",required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--context-dir",type=Path,default=ROOT/"data/context_v3")
    args=p.parse_args()
    print(json.dumps(snapshot(args.ticker,args.output,args.context_dir),indent=2))
