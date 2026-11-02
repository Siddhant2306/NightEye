"""Development-date schema parity without opening final-test labels."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.helper.load_data import load_data
from src.forecasting.train import save_json
from src.feature_engineering_v2 import SCHEMA
from src.feature_engineering_v2.prepare import DEFAULT
from src.feature_engineering_v2.inference import build_one


def check(root):
    protocol=json.loads((root/"protocol.json").read_text())
    columns=list(json.loads((root/"feature_registry.json").read_text()))
    sources=protocol["source_prices"];source=next(s for s in sources if s["ticker"]=="RELIANCE.NS")
    with contextlib.redirect_stdout(io.StringIO()): all_history=load_data(Path(source["file"]))
    checks=[]
    for horizon in protocol["horizons"]:
        cached=joblib.load(root/"data"/f"development_h{horizon}.joblib")
        cutoff=pd.Timestamp(protocol["boundaries"]["calibration"])
        complete=cached.loc[cached.index<cutoff].groupby(level=0).size()
        asof=complete.loc[complete==len(set(s["ticker"] for s in sources)-set(protocol["held_out_companies"]))].index[-1]
        history=all_history.loc[all_history.index<=asof]
        bundle=dict(feature_schema=SCHEMA,horizon=horizon,context_dir=protocol["context_dir"],
            regression=dict(columns=columns),direction=dict(columns=columns),peer_data_dir=str(Path(source["file"]).parent),
            reference_tickers=sorted(s["ticker"] for s in sources if s["ticker"] not in protocol["held_out_companies"]),holdouts=protocol["held_out_companies"])
        fresh=build_one(history,bundle,"RELIANCE.NS")
        original=cached.loc[(cached.ticker=="RELIANCE.NS")&(cached.index<=asof)]
        dates=original.index[-126:]
        np.testing.assert_allclose(fresh.reindex(dates)[columns],original.loc[dates,columns],rtol=1e-7,atol=1e-8,equal_nan=True)
        checks.append(dict(horizon=horizon,as_of=str(asof.date()),features=len(columns),checked_origins=len(dates),all_feature_families_match=True))
        print(f"All-family live/cache parity h{horizon}: {len(columns)} features x {len(dates)} development dates",flush=True)
    save_json(root/"feature_parity_development.json",dict(final_test_read=False,checks=checks))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,default=DEFAULT)
    check(p.parse_args().output.resolve())
