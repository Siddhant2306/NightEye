"""Forecast return, UP probability, and Monte Carlo scenarios from a trusted bundle."""
import argparse
import html
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.helper.load_data import load_data
from src.forecasting import VERSION
from src.forecasting.features import build
from src.forecasting.models import raw_predict, probability
from src.forecasting.uncertainty import simulate, interval
from src.forecasting.train import save_json


def forecast(history, bundle, ticker, paths=5000, seed=42, context_dir=None):
    if bundle.get("version") != VERSION:
        raise ValueError("Unsupported forecast bundle")
    horizon = bundle["horizon"]
    frame, _ = build(history, horizon, ticker, context_dir or bundle["context_dir"], include_target=False)
    if bundle["algorithm"] == "lstm":
        from src.LSTM.model import sequences
        frame = sequences(frame, bundle["regression"]["columns"], bundle["regression"]["lookback"])
    if frame.empty or frame.index[-1] != history.index.max():
        raise ValueError("Latest stock row lacks eligible context/features; update stock and context together")
    row = frame.iloc[[-1]]
    estimate = float(raw_predict(bundle["regression"], row)[0])
    p = float(probability(bundle["direction"], row, bundle["calibrator"])[0])
    threshold = bundle["threshold"]
    signal = "UP" if p >= threshold else "NOT_UP" if p <= 1-threshold else "NO_SIGNAL"
    current, risk = float(row.close.iloc[0]), float(row.risk_scale.iloc[0])
    scenario, prices = simulate(current, estimate, risk, bundle["residual_bank"],
        np.log(history.close).diff().iloc[-756:].to_numpy(), horizon, paths, seed)
    intervals = {}
    for coverage in (.5, .8, .95):
        low, high = interval(estimate, risk, bundle["residual_bank"], coverage)
        intervals[str(coverage)] = dict(lower_adjusted_price=float(current*np.exp(low)),
                                       upper_adjusted_price=float(current*np.exp(high)))
    result = dict(ticker=ticker, algorithm=bundle["algorithm"], as_of=str(row.index[-1].date()),
        company_excluded_from_training=ticker in bundle["holdouts"],
        horizon_trading_sessions=horizon, current_adjusted_close=current,
        predicted_log_return=estimate, predicted_return_pct=float(np.expm1(estimate)*100),
        predicted_adjusted_price=float(current*np.exp(estimate)),
        point_direction="UP" if estimate>0 else "DOWN" if estimate<0 else "FLAT",
        heads_disagree=bool((signal=="UP" and estimate<0) or (signal=="NOT_UP" and estimate>0)),
        classifier_probability_up=p, direction_signal=signal, signal_threshold=threshold,
        empirical_price_intervals=intervals, monte_carlo=scenario,
        model_fit_latest_label=bundle["splits"]["training"]["latest_label"],
        calibration_latest_label=bundle["splits"]["calibration"]["latest_label"],
        scenario_calibration_rows=bundle["splits"]["calibration"]["rows"],
        scenario_calibration_origin_dates=bundle["splits"]["calibration"]["dates"],
        model_status="Historical evaluation model; not a latest-date production refit",
        probability_note="Classifier estimate and Monte Carlo frequency are different estimators; inspect test calibration/coverage before relying on either",
        price_basis="Vendor-adjusted OHLCV; adjusted-price estimate, not guaranteed future exchange quote",
        limitations=["No guarantee that nominal intervals attain coverage in a new regime",
                     "Finite historical residuals cannot represent every unseen crash or tail event",
                     "Monte Carlo does not add predictive information or improve model accuracy",
                     "Bridge paths/drawdowns are illustrative; terminal interval coverage is separately backtested",
                     "Annual test/calibration contain strongly overlapping outcomes",
                     "Only stocks with historical data and a configured sector/context mapping are supported"])
    return result, prices


def write_html(path, result, prices):
    """Standalone local report; no external scripts, requests or browser dependencies."""
    lo, hi = float(prices.min()), float(prices.max())
    width, height = 900, 360
    def polyline(values, color, opacity, stroke=1):
        x = np.linspace(40, width-20, len(values))
        y = height-30-(values-lo)/max(hi-lo, 1e-8)*(height-55)
        points = " ".join(f"{a:.1f},{b:.1f}" for a,b in zip(x,y))
        return f'<polyline points="{points}" fill="none" stroke="{color}" stroke-opacity="{opacity}" stroke-width="{stroke}"/>'
    lines = "".join(polyline(p, "#68a9df", .12) for p in prices[:60])
    for q in [.1, .5, .9]:
        lines += polyline(np.quantile(prices, q, axis=0), "#ffba49" if q == .5 else "#eee", 1, 2)
    s = result
    table = "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>" for k,v in {
        "As of":s["as_of"], "Algorithm":s["algorithm"], "Trading sessions":s["horizon_trading_sessions"],
        "Starting adjusted price":f'{s["current_adjusted_close"]:.2f}',
        "Point estimate":f'{s["predicted_adjusted_price"]:.2f}',
        "Estimated return":f'{s["predicted_return_pct"]:.2f}%',
        "Classifier P(UP)":f'{s["classifier_probability_up"]:.1%}',
        "Signal":s["direction_signal"],
        "Scenario P(UP)":f'{s["monte_carlo"]["scenario_probability_up"]:.1%}',
        "80% empirical interval":f'{s["empirical_price_intervals"]["0.8"]["lower_adjusted_price"]:.2f} – {s["empirical_price_intervals"]["0.8"]["upper_adjusted_price"]:.2f}'}.items())
    warnings = " ".join(result.get("reliability_warnings", []))
    text = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NightEye forecast</title><style>body{{font:16px system-ui;background:#101923;color:#ecf1f7;max-width:1000px;margin:32px auto;padding:20px}}td{{padding:8px 20px 8px 0;border-bottom:1px solid #354354}}svg{{width:100%;background:#172533;margin-top:24px}}p{{line-height:1.6;color:#c8d3e0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}</style>
<h1>{html.escape(s['ticker'])} · {s['horizon_trading_sessions']} sessions</h1>
<p>Historical evaluation model · input date {html.escape(s['as_of'])}. Scenario ranges depend on assumptions and are not guaranteed.</p>
<p><strong>Reliability:</strong> {html.escape(warnings or 'Inspect the historical evaluation before relying on this output.')}</p>
<table>{table}</table><svg viewBox="0 0 {width} {height}" role="img" aria-label="Illustrative Monte Carlo adjusted price paths">{lines}<text x="40" y="18" fill="white">{hi:.2f}</text><text x="40" y="{height-8}" fill="white">{lo:.2f} · Session 0 → {s['horizon_trading_sessions']}</text></svg>
<p>Blue: sample paths. White: scenario 10th/90th percentiles. Gold: scenario median. Path behavior is illustrative; inspect test interval coverage and probability calibration in the experiment report.</p>
<p>{html.escape(s['probability_note'])}</p><details><summary>Full output and limitations</summary><pre>{html.escape(json.dumps(s, indent=2))}</pre></details></html>'''
    path.write_text(text, encoding="utf-8")


def add_diagnostics(result, model_path):
    metrics_path = model_path.parent/"metrics.json"
    warnings = []
    if result.get("heads_disagree"):
        warnings.append("The point-return estimate and classifier signal differ; they optimize different objectives.")
    if metrics_path.exists():
        groups = json.loads(metrics_path.read_text())
        group = "unseen" if result["company_excluded_from_training"] else "seen"
        test = groups[group]
        cls = test["classifier"]
        result["historical_diagnostic_group"] = group
        result["historical_test"] = dict(rows=test["rows"], dates=test["dates"],
            direction_accuracy=cls["accuracy"], always_up_accuracy=cls["always_up_accuracy"],
            balanced_accuracy=cls["balanced_accuracy"], brier=cls["brier"],
            baseline_brier=test["prior_classifier"]["brier"],
            signal_coverage=cls["signal_coverage"], up_signal_precision=cls["up_signal_precision"],
            signal_count=cls["signal_count"], up_signal_count=cls["up_signal_count"],
            price_mape=test["regression"]["price_mape"], interval_coverage=test["intervals"])
        result["all_stock_test_interval_coverage"] = groups["all"]["intervals"]
        if cls["balanced_accuracy"] is None or cls["balanced_accuracy"] <= .51:
            warnings.append("No demonstrated directional edge: test balanced accuracy is near 50%.")
        if cls["brier"] >= test["prior_classifier"]["brier"]:
            warnings.append("UP probability estimates did not beat the constant-probability baseline on this test.")
        if cls["up_signal_count"] < 100:
            warnings.append("Too few high-confidence UP signals to establish precision reliably.")
        if test["intervals"]["0.8"]["observed_coverage"] < .75:
            warnings.append("The nominal 80% interval undercovered the historical test for this company group.")
        if test["dates"] < 2*result["horizon_trading_sessions"]:
            warnings.append("Fewer than two horizon-sized test blocks; long-horizon reliability is unresolved.")
    else:
        warnings.append("Historical test diagnostics are missing.")
    result["reliability_warnings"] = warnings
    result["forecast_status"] = "EXPERIMENTAL" if warnings else "RESEARCH_EVALUATION_ONLY"
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--history", type=Path, required=True)
    p.add_argument("--ticker", required=True)
    p.add_argument("--context-dir", type=Path)
    p.add_argument("--paths", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", type=Path, required=True, help="New output folder for JSON/HTML/CSV")
    args = p.parse_args()
    if args.output.exists():
        p.error("Choose a new forecast output directory")
    result, prices = forecast(load_data(args.history), joblib.load(args.model), args.ticker,
                              args.paths, args.seed, args.context_dir)
    add_diagnostics(result, args.model)
    args.output.mkdir(parents=True)
    save_json(args.output/"forecast.json", result)
    pd.DataFrame(np.quantile(prices, [.025, .1, .5, .9, .975], axis=0).T,
                 columns=["p2_5", "p10", "p50", "p90", "p97_5"]).to_csv(args.output/"path_quantiles.csv", index_label="session")
    pd.DataFrame(prices[:100].T).to_csv(args.output/"sample_paths.csv", index_label="session")
    write_html(args.output/"forecast.html", result, prices)
    print(json.dumps(result, indent=2))
    print(f"Report: {(args.output/'forecast.html').resolve()}")


if __name__ == "__main__":
    main()
