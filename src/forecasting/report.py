"""Regenerate a readable comparison without fitting or choosing on test results."""
import argparse
import html
import json
from pathlib import Path
import pandas as pd
from src.forecasting import VERSION


def generate(directory):
    protocol = json.loads((directory/"protocol.json").read_text())
    if protocol.get("version") != VERSION:
        raise ValueError("Not a forecasting experiment")
    frame = pd.read_csv(directory/"summary.csv")
    unseen = frame.loc[frame.group == "unseen"]
    lines = ["# NightEye chronological experiment", "",
        "80% development / 20% test by unique origin dates. All horizons share the same date boundaries.",
        "64% model development (two expanding validation folds); 16% separate probability/interval calibration; final 20% test.",
        "Training and calibration labels must mature before the next boundary. Five companies are excluded from all fitting, tuning and calibration.", "",
        "## Unseen-company final test", "",
        "| Sessions | Algorithm | Price MAPE | Return RMSE | Control RMSE | Classifier accuracy | Always UP | Balanced accuracy | UP precision | Signal coverage | UP signals | UP signal precision | 80% interval coverage |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    def pct(x):
        return "undefined" if pd.isna(x) else f"{x:.2%}"
    for _, r in unseen.iterrows():
        count = json.loads((directory/f"h{int(r.horizon)}"/r.algorithm/"metrics.json").read_text())["unseen"]["classifier"]["up_signal_count"]
        lines.append(f"| {r.horizon} | {r.algorithm} | {pct(r.price_mape)} | {r.rmse:.6f} | {r.control_rmse:.6f} | {pct(r.classifier_accuracy)} | {pct(r.always_up)} | {pct(r.balanced_accuracy)} | {pct(r.up_precision)} | {pct(r.signal_coverage)} | {count} | {pct(r.up_signal_precision)} | {pct(r.interval80_coverage)} |")
    lines += ["", "## All-stock final test (seen plus unseen companies)", "",
        "| Sessions | Algorithm | Price MAPE | Return RMSE | Classifier accuracy | Always UP | 80% interval coverage |",
        "|---|---|---|---|---|---|---|"]
    for _, r in frame.loc[frame.group == "all"].iterrows():
        lines.append(f"| {r.horizon} | {r.algorithm} | {pct(r.price_mape)} | {r.rmse:.6f} | {pct(r.classifier_accuracy)} | {pct(r.always_up)} | {pct(r.interval80_coverage)} |")
    lines += ["", "Control = existing feature family, first conservative configuration, retrained on exactly the same dates.",
        "Price MAPE is mean absolute percentage error, not probability or a guaranteed range. Return RMSE is on log returns.",
        "Classifier labels are UP (>0 return) and NOT_UP (<=0). UP signal precision refers only to probabilities >= the predeclared threshold; no-signal cases are included in coverage.",
        "The threshold was fixed before training, not chosen on test performance. Undefined precision means no UP signals.", "",
        "A high precision with only one or a few UP signals is not evidence of reliability; inspect the count and coverage.", "",
        "## Validation choices and feature experiment", ""]
    for horizon in protocol["horizons"]:
        for algorithm in protocol["algorithms"]:
            selection = json.loads((directory/f"h{horizon}"/algorithm/"selection.json").read_text())
            for task in ["regression", "direction"]:
                chosen = selection[task]
                trials = selection[f"{task}_trials"]
                scores = {family:min(t["validation_loss"] for t in trials if t["family"] == family)
                          for family in dict.fromkeys(t["family"] for t in trials)}
                losses = ", ".join(f"{name}={value:.6f}" for name,value in scores.items())
                unit = "epochs" if algorithm == "lstm" else "rounds"
                lines.append(f"- {horizon} / {algorithm} / {task}: selected **{chosen['family']}**, {chosen['rounds']} {unit}. Validation losses: {losses}.")
    lines += ["", "## Limits", "",
        "- For LSTM experiments, the control is the frozen matched XGBoost control. LSTM uses shared return/direction heads and train-only median imputation/scaling; sequence warmup removes early training origins, but final-test keys must match.",
        "- These are reused historical observations, not a fresh prospective test. Metrics are not directly comparable to older experiments with different boundaries.",
        "- High UP accuracy in a rising period can match an always-UP model. Check balanced accuracy, NOT_UP recall, calibration and signal coverage.",
        "- Calibration is pooled across training companies; it can fail for unseen companies or market regimes. No guarantee of nominal interval coverage is claimed.",
        "- Annual outcomes overlap. See metrics.json paired_vs_control: confidence intervals are withheld if fewer than two horizon-sized date blocks exist.",
        "- Monte Carlo uses later-calibration residuals and volatility scaling for endpoints. Bridge paths and drawdowns are illustrative, not validated path-risk forecasts.",
        "- Classifier P(UP) and simulation P(UP) are separate estimates and may disagree; neither is automatically a trustworthy probability.",
        "- Added features, more rounds, 80/20 splitting and simulation do not guarantee improvements.",
        "- Vendor-adjusted historical prices and retrospective index/financial archives retain source limitations.", "",
        "See per-algorithm metrics.json, per_stock.csv, test_predictions.csv and selection.json for full results and learning curves."]
    (directory/"comparison.md").write_text("\n".join(lines), encoding="utf-8")
    # A simple offline report, with no additional package dependency.
    table = frame.to_html(index=False, float_format=lambda v:f"{v:.5f}", escape=True)
    doc = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>NightEye experiment results</title>
<style>body{{font:15px system-ui;margin:32px;background:#111b25;color:#e6edf5}}table{{border-collapse:collapse;white-space:nowrap}}td,th{{padding:8px;border:1px solid #405060}}pre{{white-space:pre-wrap;line-height:1.6}}section{{overflow:auto}}</style>
<h1>NightEye experiment results</h1><p>Seen, unseen and all-company results. All proportions below use 0..1. Read the interpretation and limits below.</p>
<section>{table}</section><pre>{html.escape(chr(10).join(lines))}</pre></html>'''
    (directory/"comparison.html").write_text(doc, encoding="utf-8")
    return directory/"comparison.md"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    print(generate(parser.parse_args().directory))
