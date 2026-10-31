"""One command produces all available algorithm/horizon forecast reports."""
import argparse
import html
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.helper.load_data import load_data
from src.forecasting import VERSION
from src.forecasting.predict import forecast, write_html, add_diagnostics
from src.forecasting.train import save_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--experiment", type=Path, required=True)
    p.add_argument("--history", type=Path, required=True)
    p.add_argument("--ticker", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--paths", type=int, default=5000)
    args = p.parse_args()
    protocol = json.loads((args.experiment/"protocol.json").read_text())
    if protocol.get("version") != VERSION or args.output.exists():
        p.error("Use a forecasting experiment and a new output directory")
    history = load_data(args.history)
    args.output.mkdir(parents=True)
    rows, links = [], []
    for horizon in protocol["horizons"]:
        for algorithm in protocol["algorithms"]:
            model_path = args.experiment/f"h{horizon}"/algorithm/"model.joblib"
            result, prices = forecast(history, joblib.load(model_path), args.ticker, args.paths)
            add_diagnostics(result, model_path)
            relative = Path(f"h{horizon}_{algorithm}")
            folder = args.output/relative
            folder.mkdir()
            save_json(folder/"forecast.json", result)
            write_html(folder/"forecast.html", result, prices)
            pd.DataFrame(np.quantile(prices, [.025,.1,.5,.9,.975], axis=0).T,
                columns=["p2_5","p10","p50","p90","p97_5"]).to_csv(folder/"path_quantiles.csv", index_label="session")
            pd.DataFrame(prices[:100].T).to_csv(folder/"sample_paths.csv", index_label="session")
            limits = result["empirical_price_intervals"]["0.8"]
            rows.append(dict(algorithm=algorithm, horizon=horizon, as_of=result["as_of"],
                current=result["current_adjusted_close"], predicted=result["predicted_adjusted_price"],
                return_pct=result["predicted_return_pct"], probability_up=result["classifier_probability_up"],
                signal=result["direction_signal"], lower80=limits["lower_adjusted_price"], upper80=limits["upper_adjusted_price"],
                scenario_probability_up=result["monte_carlo"]["scenario_probability_up"], status=result["forecast_status"]))
            links.append(f'<li><a href="{relative.as_posix()}/forecast.html">{horizon} sessions · {algorithm}</a></li>')
            print(f"Saved {horizon} / {algorithm}: {result['predicted_adjusted_price']:.2f}, {result['direction_signal']}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(args.output/"forecast_summary.csv", index=False)
    doc = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>NightEye stock overview</title>
<style>body{{font:16px system-ui;margin:32px}}td,th{{padding:8px;border-bottom:1px solid #ccc}}section{{overflow:auto}}</style>
<h1>{html.escape(args.ticker)} forecast overview</h1><p>Experimental historical models. All prices are adjusted prices; probabilities and intervals require validation. Read reliability warnings in each report.</p>
<section>{frame.to_html(index=False, float_format=lambda x:f'{x:.3f}')}</section><ul>{''.join(links)}</ul></html>'''
    (args.output/"index.html").write_text(doc, encoding="utf-8")
    print(f"Overview: {(args.output/'index.html').resolve()}")


if __name__ == "__main__":
    main()
