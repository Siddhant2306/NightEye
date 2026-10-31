"""Matched 80/20 chronological experiments for XGBoost and LightGBM."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import platform
import joblib
import numpy as np
import pandas as pd
import lightgbm
import xgboost
import sklearn
from sklearn.metrics import log_loss
from src.pipeline import ROOT
from src.fetch_research_data import NEW_HOLDOUTS
from src.helper.load_data import load_data
from src.helper.benchmark import context_hashes, observation_hash
from src.LightGBM.train import protected_hashes
from src.LightGBM.metrics import summary_metrics, paired_uncertainty
from src.forecasting import VERSION
from src.forecasting.features import build
from src.forecasting.protocol import boundaries, partitions, span
from src.forecasting.models import candidates, fit, raw_predict, calibrate, probability, direction_metrics
from src.forecasting.uncertainty import residual_bank, interval, interval_metrics


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False, default=str), encoding="utf-8")


def macro_loss(frame, prediction, task):
    errors = []
    for ticker in frame.ticker.unique():
        mask = (frame.ticker == ticker).to_numpy()
        if task == "direction":
            errors.append(log_loss((frame.target.to_numpy()[mask] > 0).astype(int),
                                   np.clip(prediction[mask], 1e-6, 1-1e-6), labels=[0, 1]))
        else:
            errors.append(np.sqrt(np.mean((frame.target.to_numpy()[mask]-prediction[mask])**2)))
    return float(np.mean(errors))


def search(algorithm, task, folds, families, params, rounds, patience):
    trials = []
    for family, columns in families.items():
        for number, config in enumerate(params):
            scores, trees, curves = [], [], []
            for training, valid in folds:
                model = fit(algorithm, task, training, columns, config, rounds, valid, patience)
                scores.append(macro_loss(valid, raw_predict(model, valid), task))
                trees.append(model["rounds"])
                curves.append(model["learning_curve"])
            trial = dict(family=family, trial=number, params=config, validation_loss=float(np.mean(scores)),
                         fold_losses=scores, fold_rounds=trees, rounds=max(1, int(np.median(trees))),
                         learning_curves=curves)
            trials.append(trial)
            print(f"  {algorithm} {task} {family} trial {number+1}/{len(params)}: validation={trial['validation_loss']:.6f}, rounds={trees}", flush=True)
    return min(trials, key=lambda x: x["validation_loss"]), trials


def evaluate(frame, threshold, horizon):
    out = {}
    for group in ("seen", "unseen", "all"):
        part = frame if group == "all" else frame.loc[frame.group == group]
        if part.empty:
            continue
        metrics = dict(rows=len(part), dates=int(part.index.nunique()), stocks=int(part.ticker.nunique()))
        for name in ("regression", "control", "zero_return", "historical_mean"):
            metrics[name] = summary_metrics(part, name)
        metrics["classifier_raw"] = direction_metrics(part.target, part.raw_probability, threshold)
        metrics["classifier"] = direction_metrics(part.target, part.probability_up, threshold)
        metrics["prior_classifier"] = direction_metrics(part.target, part.prior_probability, threshold)
        metrics["intervals"] = {str(c): dict(nominal_coverage=c,
            observed_coverage=float(((part.target >= part[f"lower_{c}"]) & (part.target <= part[f"upper_{c}"])).mean()),
            mean_log_return_width=float((part[f"upper_{c}"]-part[f"lower_{c}"]).mean())) for c in (.5, .8, .95)}
        metrics["paired_vs_control"] = paired_uncertainty(part, "regression", "control", horizon)
        out[group] = metrics
    return out


def load_histories(directory):
    histories, sources = {}, []
    for path in sorted(directory.glob("*.csv")):
        ticker = path.stem.split("_")[0]
        if ticker in histories:
            raise ValueError(f"Duplicate stock snapshot: {ticker}")
        with contextlib.redirect_stdout(io.StringIO()):
            histories[ticker] = load_data(path)
        sources.append(dict(ticker=ticker, file=str(path.resolve()), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    if not histories or not set(NEW_HOLDOUTS).issubset(histories):
        raise ValueError("Use the research_v2 snapshot including all five company holdouts")
    return histories, sources


def prepare(histories, horizon, context):
    frames = []
    for ticker, history in histories.items():
        with contextlib.redirect_stdout(io.StringIO()):
            frame, families = build(history, horizon, ticker, context, include_target=False)
        frames.append(frame)
    panel = pd.concat(frames).sort_index()
    if panel.reset_index().duplicated([panel.index.name or "index", "ticker"]).any():
        raise ValueError("Duplicate stock/date observations")
    return panel, families


def train_horizon(args, panel, families, edges, horizon):
    labeled = panel.dropna(subset=["target", "target_date", "risk_scale"])
    folds, training, cal, test = partitions(labeled, edges, NEW_HOLDOUTS)
    split_info = dict(training=span(training), calibration=span(cal), test=span(test),
                      folds=[dict(training=span(a), validation=span(b)) for a, b in folds],
                      test_keys_sha256=observation_hash(test),
                      calibration_overlap_warning="Annual labels overlap; calibration count overstates independent outcomes")
    root = args.output/f"h{horizon}"
    root.mkdir()
    save_json(root/"splits.json", split_info)
    summaries = []
    for algorithm in args.algorithms:
        print(f"Horizon {horizon}: {algorithm}; train={len(training)}, calibration={len(cal)}, test={len(test)}", flush=True)
        directory = root/algorithm
        directory.mkdir()
        reg_choice, reg_trials = search(algorithm, "return", folds, families, candidates(args.trials), args.max_rounds, args.patience)
        cls_choice, cls_trials = search(algorithm, "direction", folds, families, candidates(args.trials), args.max_rounds, args.patience)
        # Every choice, including rounds, is frozen before any final-test prediction.
        save_json(directory/"selection.json", dict(regression=reg_choice, direction=cls_choice,
                  regression_trials=reg_trials, direction_trials=cls_trials,
                  selection="Mean macro-stock RMSE for return; mean macro-stock log loss for direction"))
        def final(choice, task):
            return fit(algorithm, task, training, families[choice["family"]], choice["params"], choice["rounds"])
        reg = final(reg_choice, "return")
        classifier = final(cls_choice, "direction")
        baseline_choice = next(t for t in reg_trials if t["family"] == "existing" and t["trial"] == 0)
        control = reg if reg_choice is baseline_choice else final(baseline_choice, "return")
        cal_pred = raw_predict(reg, cal)
        bank = residual_bank(cal.target, cal_pred, cal.risk_scale)
        calibrator = calibrate(raw_predict(classifier, cal), cal.target)
        prior = float((training.target > 0).mean())
        bundle = dict(version=VERSION, algorithm=algorithm, horizon=horizon, regression=reg,
                      direction=classifier, control=control, calibrator=calibrator,
                      residual_bank=bank, threshold=args.signal_threshold,
                      feature_families=families, regression_family=reg_choice["family"],
                      direction_family=cls_choice["family"], context_dir=str(args.context_dir.resolve()),
                      prior_probability=prior, training_mean=float(training.target.mean()),
                      boundaries={k:str(v.date()) for k,v in edges.items()}, splits=split_info,
                      target="log(adjusted_close[t+h]/adjusted_close[t]); after-close information",
                      holdouts=NEW_HOLDOUTS, seed=42, calibration_is_out_of_fit=True,
                      calibration_intervals=interval_metrics(cal.target.to_numpy(), cal_pred, cal.risk_scale, bank))
        joblib.dump(bundle, directory/"model.joblib")
        restored = joblib.load(directory/"model.joblib")
        frame = test[["ticker", "target", "target_date", "close", "risk_scale"]].copy()
        frame["group"] = np.where(frame.ticker.isin(NEW_HOLDOUTS), "unseen", "seen")
        frame["regression"] = raw_predict(reg, test)
        frame["control"] = raw_predict(control, test)
        frame["raw_probability"] = raw_predict(classifier, test)
        frame["probability_up"] = probability(classifier, test, calibrator)
        frame["prior_probability"] = prior
        frame["zero_return"] = 0.
        frame["historical_mean"] = float(training.target.mean())
        for coverage in (.5, .8, .95):
            frame[f"lower_{coverage}"], frame[f"upper_{coverage}"] = interval(frame.regression, frame.risk_scale, bank, coverage)
        np.testing.assert_allclose(raw_predict(restored["regression"], test), frame.regression, rtol=1e-10)
        np.testing.assert_allclose(probability(restored["direction"], test, restored["calibrator"]), frame.probability_up, rtol=1e-10)
        frame.to_csv(directory/"test_predictions.csv", index_label="Date", float_format="%.17g")
        reports = evaluate(frame, args.signal_threshold, horizon)
        save_json(directory/"metrics.json", reports)
        # Per-stock results make aggregate success/failure inspectable.
        per_stock = []
        for ticker, part in frame.groupby("ticker"):
            d = direction_metrics(part.target, part.probability_up, args.signal_threshold)
            r = summary_metrics(part, "regression")
            per_stock.append(dict(ticker=ticker, group=part.group.iloc[0], rows=len(part), rmse=r["rmse"],
                price_mape=r["price_mape"], direction_accuracy=d["accuracy"], up_precision=d["up_precision"],
                balanced_accuracy=d["balanced_accuracy"], signal_coverage=d["signal_coverage"],
                signal_up_precision=d["up_signal_precision"]))
        pd.DataFrame(per_stock).to_csv(directory/"per_stock.csv", index=False)
        for group, values in reports.items():
            d, r, b = values["classifier"], values["regression"], values["control"]
            summaries.append(dict(horizon=horizon, algorithm=algorithm, group=group,
                regression_family=reg_choice["family"], direction_family=cls_choice["family"],
                regression_rounds=reg["rounds"], direction_rounds=classifier["rounds"],
                rmse=r["rmse"], control_rmse=b["rmse"], zero_rmse=values["zero_return"]["rmse"],
                price_mape=r["price_mape"], regression_direction=r["direction"]["accuracy"],
                classifier_accuracy=d["accuracy"], balanced_accuracy=d["balanced_accuracy"],
                up_precision=d["up_precision"], up_recall=d["up_recall"], not_up_recall=d["not_up_recall"],
                always_up=d["always_up_accuracy"], brier=d["brier"], prior_brier=values["prior_classifier"]["brier"],
                signal_coverage=d["signal_coverage"], up_signal_precision=d["up_signal_precision"],
                signal_count=d["signal_count"], up_signal_count=d["up_signal_count"],
                interval80_coverage=values["intervals"]["0.8"]["observed_coverage"], rows=values["rows"], dates=values["dates"]))
        print(f"  Saved/reloaded {algorithm} h{horizon}: unseen classifier accuracy={reports['unseen']['classifier']['accuracy']:.3%}", flush=True)
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT/"data/research_v2")
    parser.add_argument("--context-dir", type=Path, default=ROOT/"data/context_v3")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--algorithms", nargs="+", choices=["xgboost", "lightgbm"], default=["xgboost", "lightgbm"])
    parser.add_argument("--horizons", nargs="+", type=int, choices=[1, 21, 252], default=[1, 21, 252])
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--max-rounds", "--epochs", dest="max_rounds", type=int, default=500,
                        help="Maximum boosting rounds (epochs is a convenience alias), not repeated fits")
    parser.add_argument("--patience", type=int, default=40)
    parser.add_argument("--signal-threshold", type=float, default=.60)
    args = parser.parse_args()
    if len(set(args.horizons)) != len(args.horizons) or len(set(args.algorithms)) != len(args.algorithms):
        parser.error("Do not repeat algorithms or horizons")
    candidates(args.trials)
    if not 1 <= args.max_rounds <= 5000 or args.patience < 1 or not .5 < args.signal_threshold < 1:
        parser.error("Use 1..5000 rounds, positive patience, and a signal threshold between .5 and 1")
    args.output = args.output.resolve()
    allowed = (ROOT/"artifacts/forecasting").resolve()
    if not args.output.is_relative_to(allowed) or args.output == allowed or args.output.exists():
        parser.error("Choose a new child directory under artifacts/forecasting")
    old_hashes = protected_hashes()
    histories, sources = load_histories(args.data_dir)
    reference, reference_families = prepare(histories, 1, args.context_dir)
    edges = boundaries(reference.index)
    args.output.mkdir(parents=True)
    protocol = dict(version=VERSION, boundaries={k:str(v.date()) for k,v in edges.items()},
        date_split="First 80% development, last 20% test; 64..80% calibration; expanding validation folds at 40..52% and 52..64%",
        percentages="Unique eligible daily origin dates, shared by every horizon; counts change after label maturity/purging",
        source_prices=sources, context_hashes=context_hashes(args.context_dir), held_out_companies=NEW_HOLDOUTS,
        max_boosting_rounds=args.max_rounds, early_stopping_patience=args.patience, candidates=candidates(args.trials),
        signal_threshold=args.signal_threshold, algorithms=args.algorithms, horizons=args.horizons,
        libraries=dict(python=platform.python_version(), xgboost=xgboost.__version__, lightgbm=lightgbm.__version__, sklearn=sklearn.__version__),
        caveats=["Reused historical data, not a new prospective holdout", "No random splitting or test-based model selection",
                 "Adjusted OHLCV basis; context archives may be retrospective/revised; fixed sector proxies",
                 "Company holdouts excluded from fitting, tuning and calibration", "No guarantee of improvement or live profitability",
                 "Annual overlapping labels provide few independent outcomes", "Simulation paths are conditional illustrative scenarios"])
    save_json(args.output/"protocol.json", protocol)
    save_json(args.output/"protected_before.json", old_hashes)
    rows = []
    for horizon in args.horizons:
        panel, families = (reference, reference_families) if horizon == 1 else prepare(histories, horizon, args.context_dir)
        rows += train_horizon(args, panel, families, edges, horizon)
        pd.DataFrame(rows).to_csv(args.output/"summary.csv", index=False)
    # Algorithm preference is frozen by validation; final test never chooses a winner.
    selection = {}
    for h in args.horizons:
        options = {a:json.loads((args.output/f"h{h}"/a/"selection.json").read_text()) for a in args.algorithms}
        selection[str(h)] = {task:min(options, key=lambda a:options[a][task]["validation_loss"]) for task in ["regression", "direction"]}
    save_json(args.output/"selected.json", selection)
    unchanged = old_hashes == protected_hashes()
    prices_unchanged = all(hashlib.sha256(Path(s["file"]).read_bytes()).hexdigest() == s["sha256"] for s in sources)
    context_unchanged = context_hashes(args.context_dir) == protocol["context_hashes"]
    save_json(args.output/"verification.json", dict(protected_files=len(old_hashes), protected_unchanged=unchanged,
        source_prices_unchanged=prices_unchanged, context_unchanged=context_unchanged,
        saved_bundles_reloaded=len(args.horizons)*len(args.algorithms)))
    if not (unchanged and prices_unchanged and context_unchanged):
        raise RuntimeError("Source/reference changed during experiment")
    from src.forecasting.report import generate
    generate(args.output)
    print(f"Completed: {args.output}; see summary.csv and selected.json", flush=True)


if __name__ == "__main__":
    main()
