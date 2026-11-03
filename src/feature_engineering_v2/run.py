"""Resumable full study: development -> freeze -> final fit/test -> charts/backtest."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import subprocess
import sys
from src.feature_engineering_v2.prepare import DEFAULT


def execute(module,arguments,log):
    log.parent.mkdir(parents=True,exist_ok=True)
    with log.open("w",encoding="utf-8") as stream:
        result=subprocess.run([sys.executable,"-u","-m",module,*map(str,arguments)],stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode: raise RuntimeError(f"{module} failed; see {log}")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=DEFAULT)
    p.add_argument("--resume",action="store_true")
    p.add_argument("--market",action="store_true",help="Fetch fresh Reliance/peer snapshot and record a new, separate prospective journal")
    p.add_argument("--workers",type=int,default=6)
    args=p.parse_args();root=args.output.resolve()
    if not 1<=args.workers<=6: p.error("Use 1..6 independent CPU worker processes")
    if root.exists() and not args.resume: p.error("Choose a new output or pass --resume for this same frozen study")
    if not root.exists(): execute("src.feature_engineering_v2.prepare",["--output",root],root.parent/(root.name+"_prepare.log"))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs=[pool.submit(execute,"src.feature_engineering_v2.develop",["--output",root,"--algorithm",a,"--horizons",h],root/"logs"/f"develop_{a}_h{h}.log") for a in ["xgboost","lightgbm","lstm"] for h in [1,21,252]]
        for job in as_completed(jobs): job.result()
    execute("src.feature_engineering_v2.finalize",["--output",root,"--freeze-only"],root/"logs/freeze.log")
    with ThreadPoolExecutor(max_workers=min(3,args.workers)) as pool:
        jobs=[pool.submit(execute,"src.feature_engineering_v2.finalize",["--output",root,"--algorithm",a],root/"logs"/f"final_{a}.log") for a in ["xgboost","lightgbm","lstm"]]
        for job in as_completed(jobs): job.result()
    execute("src.feature_engineering_v2.verify",["--output",root],root/"logs/verification.log")
    if not (root/"backtest/summary.csv").exists():
        execute("src.forecasting.backtest",["--experiments",root,"--output",root/"backtest"],root/"logs/backtest.log")
    execute("src.forecasting.backtest_verify",["--directory",root/"backtest","--experiments",root],root/"logs/backtest_verification.log")
    execute("src.feature_engineering_v2.report",["--output",root],root/"logs/report.log")
    if not (root/"lstm_validation_permutation_importance.csv").exists(): execute("src.feature_engineering_v2.importance",["--output",root],root/"logs/permutation_importance.log")
    import json
    protocol=json.loads((root/"protocol.json").read_text())
    history=next(s["file"] for s in protocol["source_prices"] if s["ticker"]=="RELIANCE.NS")
    if args.market:
        if not (root/"market_snapshot/manifest.json").exists(): execute("src.feature_engineering_v2.market",["--experiment",root,"--output",root/"market_snapshot"],root/"logs/market_snapshot.log")
        history=root/"market_snapshot/RELIANCE.NS.csv"
    if not (root/"forecasts/index.html").exists():
        if args.market:
            # Batch prediction already accepts the bundle's stored context; use the
            # dedicated forecast command below to override context without modifying bundles.
            execute("src.feature_engineering_v2.forecast",["--experiment",root,"--snapshot",root/"market_snapshot","--output",root/"forecasts"],root/"logs/forecasts.log")
        else: execute("src.forecasting.batch_predict",["--experiment",root,"--history",history,"--ticker","RELIANCE.NS","--paths",5000,"--output",root/"forecasts"],root/"logs/forecasts.log")
    if args.market:
        execute("src.forecasting.paper",["record","--experiments",root,"--snapshot",root/"market_snapshot","--journal",root/"paper_journal_v2"],root/"logs/paper_record.log")
        execute("src.forecasting.paper",["score","--snapshot",root/"market_snapshot","--journal",root/"paper_journal_v2"],root/"logs/paper_status.log")
    execute("src.feature_engineering_v2.verify",["--output",root],root/"logs/verification_final.log")
    execute("src.feature_engineering_v2.conclusions",["--output",root],root/"logs/conclusions.log")
    print(f"Study complete: {root/'index.html'}",flush=True)


if __name__=="__main__": main()
