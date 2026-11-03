"""Independent execution/ledger/equity audit of an existing backtest, no refitting."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.forecasting.train import load_histories,save_json
from src.helper.benchmark import context_hashes,observation_hash


def verify(directory,experiments):
    summary=pd.read_csv(directory/"summary.csv")
    rules=json.loads((directory/"rules.json").read_text())
    manifests={e.name:json.loads((e/"protocol.json").read_text()) for e in experiments}
    lookup={e.name:e for e in experiments}
    manifest=next(iter(manifests.values()))
    histories,sources=load_histories(Path(manifest["source_prices"][0]["file"]).parent)
    hashes={s["ticker"]:s["sha256"] for s in sources}
    for m in manifests.values():
        if hashes!={s["ticker"]:s["sha256"] for s in m["source_prices"]}: raise ValueError("Changed source history")
    charge=(rules["cost_bps_per_side"]+rules["slippage_bps_per_side"])/10000
    checks,keys,model_hashes=[],{},{}
    for _,row in summary.iterrows():
        h=int(row.horizon)
        name=f"{row.experiment}_h{h}_{row.algorithm}"
        folder=lookup[row.experiment]
        import joblib
        model_path=folder/f"h{h}"/row.algorithm/"model.joblib"
        model=joblib.load(model_path)
        model_hashes[str(model_path.resolve())]=hashlib.sha256(model_path.read_bytes()).hexdigest()
        if context_hashes(Path(model["context_dir"]))!=manifests[row.experiment]["context_hashes"]: raise ValueError("Changed context")
        signals=pd.read_csv(directory/f"{name}_signals.csv",parse_dates=["Date"]).set_index("Date")
        key=observation_hash(signals)
        if h in keys and keys[h]!=key: raise ValueError("Mismatched algorithm signal keys")
        keys[h]=key
        curve=pd.read_csv(directory/f"{name}_equity.csv",parse_dates=["Date"]).set_index("Date")
        try:
            trades=pd.read_csv(directory/f"{name}_trades.csv",parse_dates=["origin","entry","exit"])
        except pd.errors.EmptyDataError:
            trades=pd.DataFrame(columns=["ticker","origin","entry","exit"])
        assets=sorted(signals.ticker.unique())
        expected=np.zeros(len(curve))
        allocation=rules["initial_cash"]/len(assets)
        for ticker in assets:
            price=histories[ticker]
            close=price.close.reindex(curve.index).ffill()
            account=np.full(len(curve),allocation)
            capital=allocation
            last_exit=None
            for _,trade in trades.loc[trades.ticker==ticker].sort_values("entry").iterrows():
                oi=price.index.get_loc(trade.origin)
                ei=price.index.get_loc(trade.entry)
                xi=price.index.get_loc(trade.exit)
                assert ei==oi+1 and trade.entry>trade.origin
                expected_exit=min(oi+h+1,price.index.get_indexer([curve.index[-1]])[0])
                assert xi==expected_exit and trade.exit>trade.entry
                if last_exit is not None: assert trade.entry>=last_exit
                last_exit=trade.exit
                signal=signals.loc[(signals.index==trade.origin)&(signals.ticker==ticker)].iloc[0]
                assert signal.probability_up>=manifests[row.experiment]["signal_threshold"] and signal.regression>0
                np.testing.assert_allclose([trade.entry_open,trade.exit_open],[price.open.iloc[ei],price.open.iloc[xi]],rtol=1e-12)
                np.testing.assert_allclose(trade.capital_before,capital,rtol=1e-12)
                shares=capital/(trade.entry_open*(1+charge))
                active=(curve.index>=trade.entry)&(curve.index<trade.exit)
                account[active]=shares*close.loc[active].to_numpy()
                capital=shares*trade.exit_open*(1-charge)
                np.testing.assert_allclose(trade.capital_after,capital,rtol=1e-12)
                np.testing.assert_allclose(trade.net_return,(trade.exit_open/trade.entry_open)*(1-charge)/(1+charge)-1,rtol=1e-10,atol=1e-12)
                account[curve.index>=trade.exit]=capital
            expected+=account
        np.testing.assert_allclose(curve.strategy,expected,rtol=1e-10,atol=1e-7)
        np.testing.assert_allclose(row.total_return,expected[-1]/rules["initial_cash"]-1,atol=1e-12)
        checks.append(dict(experiment=row.experiment,horizon=h,algorithm=row.algorithm,signal_rows=len(signals),
            trades=len(trades),next_open_execution_verified=True,no_overlap_verified=True,costs_and_equity_verified=True))
        print(f"Audited {name}: {len(trades)} trades",flush=True)
    result=dict(checks=checks,model_sha256=model_hashes,matching_signal_keys=keys,source_hashes_unchanged=True)
    save_json(directory/"verification.json",result)
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory",type=Path,required=True)
    p.add_argument("--experiments",type=Path,nargs="+",required=True)
    args=p.parse_args()
    verify(args.directory,args.experiments)
