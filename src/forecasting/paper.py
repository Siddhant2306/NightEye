"""Immutable timestamped forecast journal and delayed actual-outcome scoring; no orders."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.helper.load_data import load_data
from src.forecasting import VERSION
from src.forecasting.train import save_json
from src.forecasting.predict import forecast,add_diagnostics,write_html
from src.forecasting.market_data import freshness,now_utc


def next_weekday_open(origin):
    day=pd.Timestamp(origin).normalize()+pd.Timedelta(days=1)
    while day.day_of_week>=5: day+=pd.Timedelta(days=1)
    return day.tz_localize("Asia/Kolkata")+pd.Timedelta(hours=9,minutes=15)


def journal_index(journal):
    rows=[]
    for file in sorted((journal/"forecasts").glob("*.json")):
        record=json.loads(file.read_text())
        outcome_path=journal/"outcomes"/file.name
        status=json.loads(outcome_path.read_text())["status"] if outcome_path.exists() else "PENDING"
        rows.append(dict(ticker=record["ticker"],origin=record["as_of"],algorithm=record["algorithm"],
            horizon=record["horizon_trading_sessions"],predicted_return_pct=record["predicted_return_pct"],
            probability_up=record["classifier_probability_up"],signal=record["direction_signal"],status=status,
            report=f'<a href="forecasts/{html.escape(file.stem)}.html">Forecast</a>'))
    frame=pd.DataFrame(rows)
    if len(frame): frame=frame.sort_values(["ticker","origin","algorithm","horizon"])
    # All free text is escaped before inserting the controlled report links.
    safe=frame.copy()
    for column in ["ticker","origin","algorithm","signal","status"]:
        if column in safe: safe[column]=safe[column].map(html.escape)
    text=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>NightEye paper forecast journal</title>
<style>body{{font:16px system-ui;margin:32px}}td,th{{padding:8px;border-bottom:1px solid #ccc}}</style>
<h1>Prospective paper forecasts</h1><p>Timestamped EOD predictions, no orders. Pending forecasts have no measured future accuracy yet. All probability estimates remain experimental.</p>
{safe.to_html(index=False,escape=False,float_format=lambda x:f'{x:.4f}') if len(safe) else '<p>No forecasts recorded.</p>'}</html>'''
    (journal/"index.html").write_text(text,encoding="utf-8")


def read_snapshot(directory,require_fresh=True):
    manifest=json.loads((directory/"manifest.json").read_text())
    if manifest.get("status")!="READY": raise ValueError("Snapshot is not marked ready")
    for relative,digest in manifest["files_sha256"].items():
        target=(directory/relative).resolve()
        if not target.is_relative_to(directory.resolve()): raise ValueError("Invalid snapshot file path")
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest: raise ValueError("Snapshot was modified")
    history=load_data(directory/f"{manifest['ticker']}.csv")
    if require_fresh:
        check=freshness(history,directory/"context",manifest["ticker"],manifest["retrieved_at"])
        if not check["ready"]: raise ValueError(f"Stale snapshot: {check['issues']}")
    return manifest,history


def record(experiments,snapshot_dir,journal,paths=2000):
    manifest,history=read_snapshot(snapshot_dir)
    if pd.Timestamp(now_utc())>=next_weekday_open(history.index[-1]):
        raise ValueError("The next weekday session has started since this bar; retrieve a completed newer bar before recording. This conservative check may reject exchange holidays.")
    journal.mkdir(parents=True,exist_ok=True)
    (journal/"forecasts").mkdir(exist_ok=True)
    records=[]
    for experiment in experiments:
        protocol=json.loads((experiment/"protocol.json").read_text())
        if protocol["version"]!=VERSION: raise ValueError("Unsupported experiment")
        for horizon in protocol["horizons"]:
            for algorithm in protocol["algorithms"]:
                model_path=experiment/f"h{horizon}"/algorithm/"model.joblib"
                model_hash=hashlib.sha256(model_path.read_bytes()).hexdigest()
                identity=f"{manifest['ticker']}|{history.index[-1].date()}|{horizon}|{algorithm}|{model_hash}"
                key=hashlib.sha256(identity.encode()).hexdigest()[:24]
                destination=journal/"forecasts"/f"{key}.json"
                if destination.exists():
                    print(f"Already recorded {key}; preserving original timestamp",flush=True)
                    continue
                result,prices=forecast(history,joblib.load(model_path),manifest["ticker"],paths,42,snapshot_dir/"context")
                if max(pd.Timestamp(result["model_fit_latest_label"]),pd.Timestamp(result["calibration_latest_label"]))>pd.Timestamp(result["as_of"]):
                    raise ValueError("Model fitting/calibration uses labels later than this forecast origin")
                add_diagnostics(result,model_path)
                result.update(paper_id=key,recorded_at=now_utc().isoformat(),model_sha256=model_hash,
                    snapshot=str(snapshot_dir.resolve()),snapshot_manifest_sha256=hashlib.sha256((snapshot_dir/"manifest.json").read_bytes()).hexdigest(),
                    purpose="Prospective EOD forecast tracking only; not an order or live strategy",
                    target_maturity="Count actual subsequent stock sessions; no outcome until h sessions exist")
                # Exclusive creation protects the original prediction even across concurrent invocations.
                with destination.open("x",encoding="utf-8") as stream:
                    json.dump(result,stream,indent=2,allow_nan=False)
                write_html(journal/"forecasts"/f"{key}.html",result,prices)
                records.append(result)
                print(f"Recorded {key}: {algorithm} / {horizon} sessions / {result['as_of']}",flush=True)
    journal_index(journal)
    return records


def outcome(forecast_record,history,snapshot_retrieved):
    origin=pd.Timestamp(forecast_record["as_of"])
    created=pd.Timestamp(forecast_record["recorded_at"])
    if created>=pd.Timestamp(snapshot_retrieved): return dict(status="PENDING",reason="Need a snapshot retrieved after the forecast")
    if origin not in history.index: return dict(status="PENDING",reason="Origin absent from current price history")
    position=history.index.get_loc(origin)
    horizon=forecast_record["horizon_trading_sessions"]
    if position+horizon>=len(history):
        return dict(status="PENDING",observed_future_sessions=len(history)-position-1,required_sessions=horizon)
    target=history.index[position+horizon]
    target_close=pd.Timestamp(target).tz_localize("Asia/Kolkata")+pd.Timedelta(hours=15,minutes=30)
    if created>=target_close:
        return dict(status="INVALID_LATE_RECORD",reason="Target session closed before the prediction was recorded")
    # Both closes come from the same new adjusted snapshot so split/dividend revisions do not mix price bases.
    actual=float(np.log(history.close.iloc[position+horizon]/history.close.iloc[position]))
    predicted=forecast_record["predicted_log_return"]
    p=forecast_record["classifier_probability_up"]
    lower=forecast_record["empirical_price_intervals"]["0.8"]["lower_adjusted_price"]
    upper=forecast_record["empirical_price_intervals"]["0.8"]["upper_adjusted_price"]
    start=forecast_record["current_adjusted_close"]
    return dict(status="MATURED",target_date=str(target.date()),actual_log_return=actual,
        actual_return_pct=float(np.expm1(actual)*100),predicted_log_return=predicted,
        absolute_log_return_error=abs(actual-predicted),squared_log_return_error=(actual-predicted)**2,
        return_direction_correct=bool(np.sign(actual)==np.sign(predicted)),
        classifier_correct=bool((p>=.5)==(actual>0)),brier=(p-float(actual>0))**2,
        interval80_covered=bool(np.log(lower/start)<=actual<=np.log(upper/start)),
        adjusted_origin_revised=not np.isclose(history.close.iloc[position],start,rtol=1e-6),
        caveat="Actual return uses one consistent, newly retrieved vendor-adjusted series; original forecast is unchanged")


def score(snapshot_dir,journal):
    manifest,history=read_snapshot(snapshot_dir)
    folder=journal/"outcomes"
    folder.mkdir(parents=True,exist_ok=True)
    rows=[]
    for file in sorted((journal/"forecasts").glob("*.json")):
        record=json.loads(file.read_text())
        if record["ticker"]!=manifest["ticker"]: continue
        destination=folder/file.name
        if destination.exists():
            result=json.loads(destination.read_text())
        else:
            result=outcome(record,history,manifest["retrieved_at"])
            result.update(paper_id=record["paper_id"],ticker=record["ticker"],algorithm=record["algorithm"],
                horizon=record["horizon_trading_sessions"],origin=record["as_of"],scored_at=now_utc().isoformat(),
                outcome_snapshot_sha256=hashlib.sha256((snapshot_dir/"manifest.json").read_bytes()).hexdigest())
            if result["status"]=="MATURED":
                with destination.open("x",encoding="utf-8") as stream: json.dump(result,stream,indent=2,allow_nan=False)
        rows.append(result)
    pd.DataFrame(rows).to_csv(journal/"status.csv",index=False)
    mature=[r for r in rows if r["status"]=="MATURED"]
    groups=[]
    for algorithm,horizon in sorted(set((r["algorithm"],r["horizon"]) for r in mature)):
        part=[r for r in mature if r["algorithm"]==algorithm and r["horizon"]==horizon]
        groups.append(dict(algorithm=algorithm,horizon=horizon,count=len(part),
            rmse=float(np.sqrt(np.mean([r["squared_log_return_error"] for r in part]))),
            classifier_accuracy=float(np.mean([r["classifier_correct"] for r in part])),
            interval80_coverage=float(np.mean([r["interval80_covered"] for r in part])),
            brier=float(np.mean([r["brier"] for r in part]))))
    pd.DataFrame(groups,columns=["algorithm","horizon","count","rmse","classifier_accuracy","interval80_coverage","brier"]).to_csv(journal/"group_summary.csv",index=False)
    summary=dict(forecasts=len(rows),matured=len(mature),pending=sum(r["status"]=="PENDING" for r in rows),
        invalid=sum(r["status"]=="INVALID_LATE_RECORD" for r in rows),by_algorithm_horizon=groups,
        rmse=float(np.sqrt(np.mean([r["squared_log_return_error"] for r in mature]))) if mature else None,
        direction_accuracy=float(np.mean([r["classifier_correct"] for r in mature])) if mature else None,
        caveat="Pooled summary is descriptive; compare horizons/algorithms separately, and do not treat overlapping outcomes as independent")
    save_json(journal/"status.json",summary)
    journal_index(journal)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    r=sub.add_parser("record")
    r.add_argument("--experiments",type=Path,nargs="+",required=True)
    r.add_argument("--snapshot",type=Path,required=True)
    r.add_argument("--journal",type=Path,required=True)
    r.add_argument("--paths",type=int,default=2000)
    s=sub.add_parser("score")
    s.add_argument("--snapshot",type=Path,required=True)
    s.add_argument("--journal",type=Path,required=True)
    args=p.parse_args()
    if args.command=="record": record(args.experiments,args.snapshot,args.journal,args.paths)
    else: print(json.dumps(score(args.snapshot,args.journal),indent=2))


if __name__=="__main__": main()
