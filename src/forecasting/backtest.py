"""Fixed-rule, next-open long/cash backtests on saved out-of-sample forecasts."""
import argparse
import html
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from src.forecasting import VERSION
from src.forecasting.train import load_histories, save_json, prepare
from src.forecasting.models import raw_predict, probability
from src.helper.benchmark import observation_hash, context_hashes


def statistics(equity, initial):
    returns = equity.pct_change().dropna()
    std = float(returns.std()) if len(returns)>1 else 0.
    return dict(total_return=float(equity.iloc[-1]/initial-1),
        cagr=float((equity.iloc[-1]/initial)**(252/max(len(returns),1))-1),
        annualized_volatility=std*np.sqrt(252),
        sharpe_zero_risk_free=float(returns.mean()/std*np.sqrt(252)) if std>1e-12 else None,
        max_drawdown=float((equity/equity.cummax()-1).min()))


def run_strategy(predictions, histories, horizon, initial=100000., cost_bps=10., slippage_bps=5., threshold=.60):
    if horizon<1 or initial<=0 or min(cost_bps,slippage_bps)<0 or not .5<threshold<1:
        raise ValueError("Invalid backtest settings")
    if predictions.reset_index().duplicated([predictions.index.name or "index","ticker"]).any():
        raise ValueError("Duplicate forecast key")
    tickers = sorted(predictions.ticker.unique())
    start = predictions.index.min()
    end = min(histories[t].index.max() for t in tickers)
    dates = pd.DatetimeIndex(sorted(set(d for t in tickers for d in histories[t].index if start<=d<=end)))
    if len(dates)<2:
        raise ValueError("Insufficient test sessions")
    charge = (cost_bps+slippage_bps)/10000
    if charge>=.1:
        raise ValueError("Per-side costs must be below 1000 basis points")
    portfolio, benchmark, exposure = np.zeros(len(dates)), np.zeros(len(dates)), np.zeros(len(dates))
    trades, skipped = [], 0
    allocation = initial/len(tickers)
    for ticker in tickers:
        history = histories[ticker].sort_index()
        scheduled = []
        next_free = -1
        for origin, row in predictions.loc[predictions.ticker==ticker].sort_index().iterrows():
            if not np.isfinite([row.probability_up,row.regression]).all():
                raise ValueError("Nonfinite forecast")
            if row.probability_up<threshold or row.regression<=0:
                continue
            origin_pos = history.index.get_indexer([origin])[0]
            if origin_pos<0:
                raise ValueError("Forecast date absent from execution history")
            entry, desired_exit = origin_pos+1, origin_pos+horizon+1
            # The end date is predeclared: mark/close remaining positions, rather than
            # using unavailable labels to stop admitting forecasts near the tail.
            exit = min(desired_exit,len(history)-1)
            if entry<next_free:
                continue
            while exit>=0 and history.index[exit]>end: exit-=1
            if entry>=exit:
                skipped += 1
                continue
            scheduled.append(dict(origin=origin, entry=history.index[entry], exit=history.index[exit],
                entry_open=float(history.open.iloc[entry]), exit_open=float(history.open.iloc[exit]),
                truncated_at_end=exit<desired_exit,
                probability_up=float(row.probability_up), predicted_log_return=float(row.regression)))
            next_free = exit
        entries = {t["entry"]:t for t in scheduled}
        exits = {t["exit"]:t for t in scheduled}
        cash, shares, active = allocation, 0., None
        observed_close = history.close.reindex(dates).ffill()
        account, benchmark_account = [], []
        first_open_dates = history.index[(history.index>start)&(history.index<=end)]
        if first_open_dates.empty:
            raise ValueError("No execution session after forecast")
        first, last = first_open_dates[0], first_open_dates[-1]
        bench_shares = allocation/(float(history.loc[first,"open"])*(1+charge))
        bench_exit = bench_shares*float(history.loc[last,"open"])*(1-charge)
        for i, date in enumerate(dates):
            if date in exits and active is not None:
                event = exits[date]
                cash = shares*event["exit_open"]*(1-charge)
                net = cash/active["capital_before"]-1
                trades.append(dict(ticker=ticker,**event,capital_before=active["capital_before"],capital_after=cash,
                    net_return=net,entry_cost=active["entry_cost"],exit_cost=shares*event["exit_open"]*charge))
                shares, active = 0., None
            if date in entries:
                if active is not None:
                    raise AssertionError("Overlapping position")
                event = entries[date]
                shares = cash/(event["entry_open"]*(1+charge))
                active = dict(capital_before=cash,entry_cost=shares*event["entry_open"]*charge)
                cash = 0.
            close = float(observed_close.loc[date]) if pd.notna(observed_close.loc[date]) else 0.
            value = cash+shares*close
            account.append(value)
            if shares:
                exposure[i] += 1/len(tickers)
            benchmark_account.append(allocation if date<first else bench_exit if date>=last else bench_shares*close)
        if active is not None:
            raise AssertionError("Every accepted trade must have matured")
        portfolio += account
        benchmark += benchmark_account
    curve = pd.DataFrame(dict(strategy=portfolio,buy_and_hold=benchmark,cash=initial,exposure=exposure),index=dates)
    curve.index.name="Date"
    metrics = dict(strategy=statistics(curve.strategy,initial),buy_and_hold=statistics(curve.buy_and_hold,initial),
        cash=statistics(curve.cash,initial),trades=len(trades),
        win_rate=float(np.mean([t["net_return"]>0 for t in trades])) if trades else None,
        mean_exposure=float(exposure.mean()),cash_costs=float(sum(t["entry_cost"]+t["exit_cost"] for t in trades)),
        unable_to_enter_before_end=skipped,truncated_trades=sum(t["truncated_at_end"] for t in trades),
        stocks=len(tickers),first_date=str(dates[0].date()),last_date=str(dates[-1].date()))
    return metrics,curve,pd.DataFrame(trades)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--experiments",type=Path,nargs="+",required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--tickers",nargs="+")
    p.add_argument("--initial-cash",type=float,default=100000.)
    p.add_argument("--cost-bps",type=float,default=10.)
    p.add_argument("--slippage-bps",type=float,default=5.)
    args=p.parse_args()
    if args.output.exists(): p.error("Use a new backtest directory")
    manifests=[json.loads((e/"protocol.json").read_text()) for e in args.experiments]
    if any(m.get("version")!=VERSION for m in manifests): raise ValueError("Wrong experiment version")
    directory=Path(manifests[0]["source_prices"][0]["file"]).parent
    histories,sources=load_histories(directory)
    actual_hashes={s["ticker"]:s["sha256"] for s in sources}
    if any(actual_hashes!={s["ticker"]:s["sha256"] for s in m["source_prices"]} for m in manifests):
        raise ValueError("Backtest history must match all frozen forecasting snapshots")
    if args.tickers and set(args.tickers)-set(histories): raise ValueError("Unknown requested stock")
    inference_histories={t:h for t,h in histories.items() if not args.tickers or t in args.tickers}
    args.output.mkdir(parents=True)
    rules=dict(strategy="Long/cash: P(UP)>=experiment threshold AND predicted return>0",
        model_hashes={str(file.resolve()):hashlib.sha256(file.read_bytes()).hexdigest()
            for experiment in args.experiments for file in sorted(experiment.glob("h*/*/model.joblib"))},
        execution="After-close signal, next-session open entry, exit open after horizon sessions; no overlapping positions per stock; final-date open liquidation of remaining positions",
        prediction_eligibility="All eligible test-origin feature rows, including origins whose target labels are not yet available; no target is required to trade",
        allocation="Equal initial capital per stock; each account compounds independently; idle accounts hold cash, no leverage",
        cost_bps_per_side=args.cost_bps,slippage_bps_per_side=args.slippage_bps,initial_cash=args.initial_cash,
        benchmark="Same stocks, equal initial capital, buy next open and hold until final open; same costs",
        limitations=["Historical research test was reused; not prospective trading evidence",
            "Adjusted OHLCV are a total-return proxy, not executable exchange quotes or literal share accounting",
            "Fractional adjusted-price units; no integer share/lot constraints",
            "Execution open-to-open outcomes differ from the model's close-to-close label",
            "No liquidity/market-impact constraints, taxes, interest on cash or exchange-specific fee schedule",
            "No shorting or real orders; costs are assumptions, not actual broker fees",
            "Annual test supports very few independent trades; do not infer robustness from win rate"])
    save_json(args.output/"rules.json",rules)
    summaries, keys, panels = [], {}, {}
    for experiment, manifest in zip(args.experiments,manifests):
        for h in manifest["horizons"]:
            for algorithm in manifest["algorithms"]:
                name=f"{experiment.name}_h{h}_{algorithm}"
                model=joblib.load(experiment/f"h{h}"/algorithm/"model.joblib")
                if context_hashes(Path(model["context_dir"]))!=manifest["context_hashes"]:
                    raise ValueError("Context snapshot no longer matches experiment")
                is_v2=model.get("feature_schema","").startswith("nighteye-features-v2")
                cache_key=(h,str(experiment.resolve()) if is_v2 else "legacy")
                if cache_key not in panels:
                    if is_v2:
                        panels[cache_key]=joblib.load(experiment/"data"/f"unlabeled_h{h}.joblib")
                    else: panels[cache_key]=prepare(inference_histories,h,Path(model["context_dir"]))[0]
                panel=panels[cache_key]
                if is_v2:
                    from src.feature_engineering_v2.inference import predict_pair
                    panel=predict_pair(model,panel)
                elif algorithm=="lstm":
                    from src.LSTM.model import sequences
                    panel=sequences(panel,model["regression"]["columns"],model["regression"]["lookback"])
                frame=panel.loc[panel.index>=pd.Timestamp(manifest["boundaries"]["test"])].copy()
                if not is_v2:
                    frame["regression"]=raw_predict(model["regression"],frame)
                    frame["probability_up"]=probability(model["direction"],frame,model["calibrator"])
                if args.tickers:
                    if set(args.tickers)-set(frame.ticker): raise ValueError("Requested ticker not in test")
                    frame=frame.loc[frame.ticker.isin(args.tickers)]
                key=observation_hash(frame)
                if h in keys and keys[h]!=key: raise ValueError("Algorithms have different test keys")
                keys[h]=key
                frame[["ticker","regression","probability_up","target_date"]].to_csv(args.output/f"{name}_signals.csv",index_label="Date")
                metrics,curve,trades=run_strategy(frame,histories,h,args.initial_cash,args.cost_bps,args.slippage_bps,manifest["signal_threshold"])
                curve.to_csv(args.output/f"{name}_equity.csv")
                trades.to_csv(args.output/f"{name}_trades.csv",index=False)
                save_json(args.output/f"{name}_metrics.json",metrics)
                summaries.append(dict(experiment=experiment.name,horizon=h,algorithm=algorithm,
                    total_return=metrics["strategy"]["total_return"],buy_hold_return=metrics["buy_and_hold"]["total_return"],
                    sharpe=metrics["strategy"]["sharpe_zero_risk_free"],max_drawdown=metrics["strategy"]["max_drawdown"],
                    trades=metrics["trades"],truncated_trades=metrics["truncated_trades"],win_rate=metrics["win_rate"],exposure=metrics["mean_exposure"],cash_costs=metrics["cash_costs"]))
                print(f"{name}: return={metrics['strategy']['total_return']:.2%}, trades={metrics['trades']}",flush=True)
    summary=pd.DataFrame(summaries)
    summary.to_csv(args.output/"summary.csv",index=False)
    text=f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>NightEye historical backtest</title>
<style>body{{font:16px system-ui;margin:32px}}td,th{{padding:8px;border-bottom:1px solid #bbb}}pre{{white-space:pre-wrap}}</style>
<h1>Historical long/cash backtest</h1><p>Research simulation with next-open execution and costs. Values are proportions; this is not evidence of live profitability.</p>
{summary.to_html(index=False,float_format=lambda x:f'{x:.4f}')}<pre>{html.escape(json.dumps(rules,indent=2))}</pre></html>'''
    (args.output/"report.html").write_text(text,encoding="utf-8")


if __name__=="__main__": main()
