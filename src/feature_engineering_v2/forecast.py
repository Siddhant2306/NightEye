"""Nine selected v2 Monte Carlo forecasts with an explicit fresh context snapshot."""
import argparse
import html
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.forecasting.paper import read_snapshot
from src.forecasting.predict import forecast,add_diagnostics,write_html
from src.forecasting.train import save_json
from src.forecasting.diagnostics import plotting,save_figure
from src.feature_engineering_v2.prepare import DEFAULT

SCENARIO_NOTE="Scenario endpoints include historical calibration residuals, which may be biased. Their median can differ substantially from the model point estimate, and a central scenario interval can even exclude that estimate. Neither the path median nor the scenario UP fraction is an independently validated forecast."


def path_plot(result,prices,path):
    plt,_=plotting();fig,ax=plt.subplots(figsize=(11,6))
    x=np.arange(prices.shape[1])
    for series in prices[:70]: ax.plot(x,series,color="#0072b2",alpha=.06,linewidth=.7)
    lower,median,upper=np.quantile(prices,[.1,.5,.9],axis=0)
    ax.fill_between(x,lower,upper,color="#0072b2",alpha=.13,label="Scenario 10th–90th percentiles (not guaranteed)")
    ax.plot(x,median,color="#0072b2",linewidth=2,label="Scenario median")
    ax.axhline(result["current_adjusted_close"],color="#555",linestyle="--",label="Starting adjusted close")
    ax.scatter([x[-1]],[result["predicted_adjusted_price"]],color="#d55e00",s=65,label="Model point estimate",zorder=5)
    ax.set_xlabel("Future trading sessions");ax.set_ylabel("Adjusted price (INR)")
    ax.set_title(f"{result['ticker']} | {result['algorithm']} | {result['horizon_trading_sessions']} sessions\nAs of {result['as_of']} · experimental conditional scenarios")
    ax.legend(fontsize=8)
    fig.text(.5,.015,"Monte Carlo does not improve prediction accuracy. Historical coverage/probability warnings remain applicable; paths are illustrative.",ha="center",fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1));save_figure(fig,path)


def generate(root,snapshot,output,paths=5000):
    if output.exists(): raise FileExistsError("Use a new forecast output directory")
    manifest,history=read_snapshot(snapshot)
    protocol=json.loads((root/"protocol.json").read_text())
    output.mkdir(parents=True)
    rows=[];links=[]
    for h in protocol["horizons"]:
        for algorithm in protocol["algorithms"]:
            model_path=root/f"h{h}"/algorithm/"model.joblib";bundle=joblib.load(model_path)
            result,prices=forecast(history,bundle,manifest["ticker"],paths,42,snapshot/"context")
            add_diagnostics(result,model_path)
            result["scenario_interpretation"]=SCENARIO_NOTE
            result["feature_configurations"]={task:s["selected"] for task,s in bundle["selections"].items()}
            folder=output/f"{algorithm}_h{h}";folder.mkdir()
            save_json(folder/"forecast.json",result);write_html(folder/"forecast.html",result,prices)
            path_plot(result,prices,folder/"monte_carlo_paths")
            pd.DataFrame(prices[:100].T).to_csv(folder/"sample_paths.csv",index_label="session")
            pd.DataFrame(np.quantile(prices,[.025,.1,.5,.9,.975],axis=0).T,
                columns=["p2_5","p10","p50","p90","p97_5"]).to_csv(folder/"path_quantiles.csv",index_label="session")
            limits=result["empirical_price_intervals"]["0.8"]
            rows.append(dict(algorithm=algorithm,horizon=h,as_of=result["as_of"],current_price=result["current_adjusted_close"],
                point_estimate=result["predicted_adjusted_price"],return_pct=result["predicted_return_pct"],
                probability_up=result["classifier_probability_up"],signal=result["direction_signal"],
                lower80=limits["lower_adjusted_price"],upper80=limits["upper_adjusted_price"],
                scenario_probability_up=result["monte_carlo"]["scenario_probability_up"],status=result["forecast_status"]))
            links.append(f'<section><h2><a href="{folder.name}/forecast.html">{algorithm} · {h} sessions</a></h2><img loading="lazy" src="{folder.name}/monte_carlo_paths.png" alt="Monte Carlo paths"><a href="{folder.name}/sample_paths.csv">Sample paths CSV</a> · <a href="{folder.name}/forecast.json">Full output JSON</a></section>')
            print(f"v2 forecast {algorithm} h{h}: {result['predicted_adjusted_price']:.2f}",flush=True)
    summary=pd.DataFrame(rows);summary.to_csv(output/"forecast_summary.csv",index=False)
    doc=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NightEye v2 price paths</title>
<style>body{{font:16px system-ui;max-width:1200px;margin:30px auto;padding:20px;background:#f5f7fa}}section{{background:white;padding:20px;margin:20px 0}}img{{max-width:100%}}td,th{{padding:7px;border-bottom:1px solid #ddd}}.scroll{{overflow:auto}}</style>
<h1>{html.escape(manifest['ticker'])} · v2 Monte Carlo price paths</h1><p>As of {history.index[-1].date()}. Conditional scenarios from validation-selected historical models. Read reliability warnings; probabilities and annual ranges are not automatically calibrated.</p><p>{html.escape(SCENARIO_NOTE)}</p>
<a href="../index.html">Experiment results</a><div class="scroll">{summary.to_html(index=False,float_format=lambda x:f'{x:.4f}')}</div>{''.join(links)}</html>'''
    (output/"index.html").write_text(doc,encoding="utf-8")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--experiment",type=Path,default=DEFAULT)
    p.add_argument("--snapshot",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--paths",type=int,default=5000)
    args=p.parse_args();generate(args.experiment.resolve(),args.snapshot.resolve(),args.output.resolve(),args.paths)
