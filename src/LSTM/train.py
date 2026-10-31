"""Fit sequence models on the frozen forecasting reference's exact date protocol."""
import argparse
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import torch
from src.pipeline import ROOT
from src.forecasting import VERSION
from src.forecasting.train import load_histories, prepare, macro_loss, evaluate, save_json
from src.forecasting.protocol import partitions, span
from src.forecasting.models import raw_predict, calibrate, probability, direction_metrics
from src.forecasting.uncertainty import residual_bank, interval, interval_metrics
from src.forecasting.report import generate
from src.helper.benchmark import observation_hash, context_hashes
from src.LightGBM.train import protected_hashes
from src.LSTM.model import sequences, fit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reference", type=Path, default=ROOT/"artifacts/forecasting/intensive_v1")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--patience", type=int, default=3)
    p.add_argument("--lookback", type=int, default=20)
    p.add_argument("--trials", type=int, choices=[1,2], default=1)
    p.add_argument("--horizons", type=int, nargs="+", choices=[1,21,252], default=[1,21,252])
    args = p.parse_args()
    allowed = (ROOT/"artifacts/forecasting").resolve()
    args.output = args.output.resolve()
    if args.output.exists() or not args.output.is_relative_to(allowed) or args.output == allowed:
        p.error("Choose a new child of artifacts/forecasting")
    if not 1 <= args.epochs <= 200 or not 2 <= args.lookback <= 126 or args.patience < 1 or len(set(args.horizons)) != len(args.horizons):
        p.error("Use 1..200 epochs, 2..126 lookback, positive patience and unique horizons")
    ref = json.loads((args.reference/"protocol.json").read_text())
    if ref["version"] != VERSION:
        raise ValueError("Use the completed forecasting reference")
    old = protected_hashes()
    source_dir = Path(ref["source_prices"][0]["file"]).parent
    histories, sources = load_histories(source_dir)
    if {s["ticker"]:s["sha256"] for s in sources} != {s["ticker"]:s["sha256"] for s in ref["source_prices"]}:
        raise ValueError("Price data no longer matches reference")
    edges = {k:pd.Timestamp(v) for k,v in ref["boundaries"].items()}
    configs = [dict(hidden=16, dropout=.1, learning_rate=.001, weight_decay=.001, batch_size=512),
               dict(hidden=32, dropout=.2, learning_rate=.0005, weight_decay=.001, batch_size=512)][:args.trials]
    protocol = dict(ref, algorithms=["lstm"], horizons=args.horizons, candidates=configs,
        max_epochs=args.epochs, early_stopping_patience=args.patience, lookback=args.lookback,
        architecture="One unidirectional LSTM layer, dropout, shared return and UP-logit heads; loss = standardized MSE + .25 binary cross entropy",
        epoch_selection="Best validation joint loss per fold; median best epoch for final fit; feature family fixed to existing",
        torch_version=torch.__version__, reference=str(args.reference.resolve()),
        warmup="First lookback-1 feature dates per stock excluded; test keys remain identical to tree reference")
    args.output.mkdir(parents=True)
    save_json(args.output/"protocol.json", protocol)
    save_json(args.output/"protected_before.json", old)
    summaries, selections = [], {}
    for h in args.horizons:
        reference_model = args.reference/f"h{h}/xgboost/model.joblib"
        frozen = joblib.load(reference_model)
        context = Path(frozen["context_dir"])
        if context_hashes(context) != ref["context_hashes"]:
            raise ValueError("Context no longer matches reference")
        panel, families = prepare(histories, h, context)
        columns = families["existing"]
        panel = sequences(panel, columns, args.lookback).dropna(subset=["target", "target_date", "risk_scale"])
        folds, training, cal, test = partitions(panel, edges, ref["held_out_companies"])
        if observation_hash(test) != frozen["splits"]["test_keys_sha256"]:
            raise ValueError("Sequence test rows must exactly match tree experiment")
        root = args.output/f"h{h}"
        directory = root/"lstm"
        directory.mkdir(parents=True)
        splits = dict(training=span(training), calibration=span(cal), test=span(test),
            folds=[dict(training=span(a), validation=span(b)) for a,b in folds], test_keys_sha256=observation_hash(test))
        save_json(root/"splits.json", splits)
        options = []
        for number, config in enumerate(configs):
            records = []
            for fold_number, (tr, va) in enumerate(folds):
                print(f"h{h} config {number+1} fold {fold_number+1}; rows={len(tr)}/{len(va)}", flush=True)
                reg, cls = fit(tr, va, columns, config, args.epochs, args.patience)
                rmse = macro_loss(va, raw_predict(reg, va), "return")
                ll = macro_loss(va, raw_predict(cls, va), "direction")
                records.append(dict(rmse=rmse, log_loss=ll, normalized_joint=rmse/reg["scale"]+.25*ll,
                                    epochs=reg["rounds"], learning_curve=reg["learning_curve"]))
            options.append(dict(trial=number, params=config, family="existing", folds=records,
                validation_loss=float(np.mean([r["normalized_joint"] for r in records])),
                rounds=max(1,int(np.median([r["epochs"] for r in records])))))
        chosen = min(options, key=lambda o:o["validation_loss"])
        print(f"Final h{h}: {chosen['rounds']} epochs", flush=True)
        reg, cls = fit(training, None, columns, chosen["params"], chosen["rounds"])
        regression_trials, direction_trials = [], []
        for option in options:
            for task, metric, target in [("return", "rmse", regression_trials), ("direction", "log_loss", direction_trials)]:
                target.append(dict(option, validation_loss=float(np.mean([f[metric] for f in option["folds"]]))))
        selection = dict(regression=regression_trials[chosen["trial"]], direction=direction_trials[chosen["trial"]],
            regression_trials=regression_trials, direction_trials=direction_trials,
            selection="Configuration and checkpoint by predeclared joint validation objective; no test selection")
        save_json(directory/"selection.json", selection)
        cal_pred = raw_predict(reg, cal)
        bank = residual_bank(cal.target, cal_pred, cal.risk_scale)
        calibrator = calibrate(raw_predict(cls, cal), cal.target)
        bundle = dict(version=VERSION, algorithm="lstm", horizon=h, regression=reg, direction=cls,
            control=frozen["control"], calibrator=calibrator, residual_bank=bank,
            threshold=ref["signal_threshold"], context_dir=str(context), splits=splits,
            holdouts=ref["held_out_companies"], prior_probability=float((training.target>0).mean()),
            training_mean=float(training.target.mean()), boundaries=ref["boundaries"],
            regression_family="existing", direction_family="existing", seed=42,
            calibration_intervals=interval_metrics(cal.target.to_numpy(),cal_pred,cal.risk_scale,bank),
            target="After-close cumulative adjusted-price log return", reference_model_sha256=hashlib.sha256(reference_model.read_bytes()).hexdigest())
        joblib.dump(bundle, directory/"model.joblib")
        restored = joblib.load(directory/"model.joblib")
        frame = test[["ticker","target","target_date","close","risk_scale"]].copy()
        frame["group"] = np.where(frame.ticker.isin(ref["held_out_companies"]),"unseen","seen")
        frame["regression"] = raw_predict(reg, test)
        frame["control"] = raw_predict(bundle["control"],test)
        frame["raw_probability"] = raw_predict(cls,test)
        frame["probability_up"] = probability(cls,test,calibrator)
        frame["prior_probability"] = bundle["prior_probability"]
        frame["zero_return"], frame["historical_mean"] = 0., bundle["training_mean"]
        for coverage in [.5,.8,.95]:
            frame[f"lower_{coverage}"], frame[f"upper_{coverage}"] = interval(frame.regression,frame.risk_scale,bank,coverage)
        np.testing.assert_allclose(frame.regression,raw_predict(restored["regression"],test),rtol=1e-7,atol=1e-9)
        np.testing.assert_allclose(frame.probability_up,probability(restored["direction"],test,restored["calibrator"]),rtol=1e-7)
        frame.to_csv(directory/"test_predictions.csv",index_label="Date",float_format="%.17g")
        metrics = evaluate(frame,bundle["threshold"],h)
        save_json(directory/"metrics.json",metrics)
        per_stock = []
        for ticker, part in frame.groupby("ticker"):
            d = direction_metrics(part.target,part.probability_up,bundle["threshold"])
            per_stock.append(dict(ticker=ticker,group=part.group.iloc[0],balanced_accuracy=d["balanced_accuracy"],
                                  direction_accuracy=d["accuracy"],up_precision=d["up_precision"],signal_coverage=d["signal_coverage"]))
        pd.DataFrame(per_stock).to_csv(directory/"per_stock.csv",index=False)
        for group, m in metrics.items():
            d,r = m["classifier"],m["regression"]
            summaries.append(dict(horizon=h,algorithm="lstm",group=group,regression_family="existing",direction_family="existing",
                regression_rounds=reg["rounds"],direction_rounds=cls["rounds"],rmse=r["rmse"],control_rmse=m["control"]["rmse"],
                zero_rmse=m["zero_return"]["rmse"],price_mape=r["price_mape"],regression_direction=r["direction"]["accuracy"],
                classifier_accuracy=d["accuracy"],balanced_accuracy=d["balanced_accuracy"],up_precision=d["up_precision"],
                up_recall=d["up_recall"],not_up_recall=d["not_up_recall"],always_up=d["always_up_accuracy"],
                brier=d["brier"],prior_brier=m["prior_classifier"]["brier"],signal_coverage=d["signal_coverage"],
                up_signal_precision=d["up_signal_precision"],signal_count=d["signal_count"],up_signal_count=d["up_signal_count"],
                interval80_coverage=m["intervals"]["0.8"]["observed_coverage"],rows=m["rows"],dates=m["dates"]))
        pd.DataFrame(summaries).to_csv(args.output/"summary.csv",index=False)
        selections[str(h)] = dict(regression="lstm",direction="lstm")
        save_json(args.output/"selected.json",selections)
        print(f"Saved LSTM h{h}: unseen RMSE={metrics['unseen']['regression']['rmse']:.6f}",flush=True)
    tree = pd.read_csv(args.reference/"summary.csv")
    pd.concat([tree.loc[tree.horizon.isin(args.horizons)],pd.DataFrame(summaries)]).to_csv(args.output/"comparison_all_algorithms.csv",index=False)
    if old != protected_hashes():
        raise ValueError("Protected reference source changed")
    save_json(args.output/"verification.json",dict(protected_unchanged=True,saved_bundles_reloaded=len(args.horizons),
        source_prices_unchanged=all(hashlib.sha256(Path(s["file"]).read_bytes()).hexdigest()==s["sha256"] for s in sources)))
    generate(args.output)


if __name__ == "__main__":
    main()
