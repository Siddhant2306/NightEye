"""Frozen-feature LightGBM baseline and optional bounded tuning for three horizons."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from types import SimpleNamespace
import joblib
import lightgbm
import numpy as np
import pandas as pd
from src.pipeline import ROOT, score
from src.research_context import prepare
from src.helper.benchmark import (context_hashes, development_split, validation_folds,
                                  observation_hash, align_reference, ordered_features)
from src.LightGBM import MODEL_VERSION
from src.LightGBM.config import HORIZON_NAMES, baseline_params, candidate_params
from src.LightGBM.model import fit_model, predict_returns
from src.LightGBM.metrics import summary_metrics


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def protected_hashes(reference_dir=None):
    roots = [ROOT/"src"/"XGBoost", ROOT/"src"/"models", ROOT/"artifacts"/"context_v3"]
    if reference_dir is not None and Path(reference_dir) not in roots:
        roots.append(Path(reference_dir))
    paths = [p for root in roots if root.exists() for p in root.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts]
    paths += [ROOT/name for name in ["src/pipeline.py", "src/research_v2.py", "src/research_context.py"]]
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def validate_snapshot(protocol, directory):
    if protocol["context_hashes"] != context_hashes(directory):
        raise ValueError("Context source snapshot differs from XGBoost; no comparable benchmark is possible")
    if protocol["training_start"] != "2017-01-01" or protocol["test_start"] != protocol["validation_edges"][-1]:
        raise ValueError("Unsupported reference date protocol")


def validate_training_reference(data, columns, sources, report, protocol):
    expected = {s["ticker"]: s["price_sha256"] for s in report["sources"]}
    actual = {s["ticker"]: s["price_sha256"] for s in sources}
    if expected != actual or columns != report["feature_cols"]:
        raise ValueError("Price source hashes or feature definitions differ from XGBoost")
    development, test = development_split(data, protocol["test_start"], protocol["held_out_tickers"])
    if len(development) != report["training_rows"] or observation_hash(test) != report["test_keys_sha256"]:
        raise ValueError("Training/test observations differ from XGBoost")
    folds = list(validation_folds(development, protocol["validation_edges"]))
    reference_folds = report["best_trial"]["folds"]
    if len(folds) != len(reference_folds):
        raise ValueError("Validation fold count differs")
    for (_, _, metadata), reference in zip(folds, reference_folds):
        for key in ["start", "end", "train_rows", "validation_rows", "max_train_target", "max_validation_target"]:
            if metadata[key] != reference[key]:
                raise ValueError(f"Validation observations differ: {key}")
    ordered_features(data, columns)
    return development, test, folds


def cross_validate(folds, columns, params, stopping_rounds):
    results = []
    for fit, valid, metadata in folds:
        model, center, scale = fit_model(fit, columns, params, valid, stopping_rounds)
        pred = predict_returns(model, valid, columns, center, scale)
        macro = float(np.mean([score(group.target, pred[valid.ticker.to_numpy()==ticker])["rmse"]
                               for ticker, group in valid.groupby("ticker")]))
        results.append(dict(metadata, macro_rmse=macro, trees=int(model.best_iteration_ or model.n_estimators_),
                            target_center=center, target_scale=scale))
    return dict(params=params, folds=results, cv_rmse=float(np.mean([r["macro_rmse"] for r in results])),
                trees=int(np.median([r["trees"] for r in results])))


def evaluate_horizon(args, protocol, horizon, configs):
    reference_family = protocol["reference_selections"][str(horizon)]["family"]
    reference_dir = args.xgboost_dir/reference_family/f"h{horizon}"
    reference_report = json.loads((reference_dir/"report.json").read_text())
    columns = reference_report["feature_cols"]
    data, _, sources = prepare(SimpleNamespace(data_dir=args.data_dir, context_dir=args.context_dir), horizon)
    development, test, folds = validate_training_reference(data, columns, sources, reference_report, protocol)
    trials = []
    for index, params in enumerate(configs):
        result = cross_validate(folds, columns, params, args.early_stopping_rounds)
        trials.append(result)
        print(f"h={horizon} candidate={index+1}/{len(configs)} validation RMSE={result['cv_rmse']:.6f}", flush=True)
    # Model selection is complete before test predictions/reference outcomes are evaluated.
    choices = {"baseline": trials[0]}
    if args.tune:
        choices["tuned"] = min(trials, key=lambda t:t["cv_rmse"])
    test["group"] = np.where(test.ticker.isin(protocol["held_out_tickers"]), "unseen", "seen")
    test = align_reference(test, pd.read_csv(reference_dir/"test_predictions.csv", parse_dates=["Date", "target_date"]))
    price_dir = args.xgboost_dir/"price_only"/f"h{horizon}"
    price_report = json.loads((price_dir/"report.json").read_text())
    expected = {s["ticker"]:s["price_sha256"] for s in sources}
    if {s["ticker"]:s["price_sha256"] for s in price_report["sources"]} != expected:
        raise ValueError("Price-only reference source mismatch")
    test = align_reference(test, pd.read_csv(price_dir/"test_predictions.csv", parse_dates=["Date", "target_date"]), "price_only")
    test["zero_return"] = 0.
    test["historical_mean"] = float(development.target.mean())
    test["stock_mean"] = test.ticker.map(development.groupby("ticker").target.mean()).fillna(development.target.mean())
    reports = {}
    for stage, selected in choices.items():
        model, center, scale = fit_model(development, columns, selected["params"], trees=selected["trees"])
        name = "lightgbm_"+stage
        test[name] = predict_returns(model, test, columns, center, scale)
        out = args.output/stage/f"h{horizon}"
        out.mkdir(parents=True)
        metrics = {label:summary_metrics(group, name) for label, group in test.groupby("group")}
        metrics["all"] = summary_metrics(test, name)
        date_ranges = dict(train_origin_start=str(development.index.min()), train_origin_end=str(development.index.max()),
                           max_train_target=str(development.target_date.max()), test_start=protocol["test_start"],
                           test_origin_end=str(test.index.max()), validation=selected["folds"])
        artifact = dict(algorithm="lightgbm", model_version=MODEL_VERSION, model=model,
                        feature_cols=columns, feature_family=reference_family, horizon=horizon, stage=stage,
                        target="log(adjusted_close[t+H] / adjusted_close[t])", target_center=center, target_scale=scale,
                        context_dir=str(args.context_dir.resolve()), random_seed=selected["params"]["random_state"],
                        training_config=selected["params"], final_tree_limit=selected["trees"],
                        fitted_trees=model.booster_.current_iteration(), date_ranges=date_ranges, metrics=metrics,
                        source_snapshot=protocol["context_hashes"], library_version=lightgbm.__version__)
        filename="lightgbm_"+HORIZON_NAMES[horizon]+".joblib"
        joblib.dump(artifact, out/filename)
        model.booster_.save_model(str(out/"model.txt"))
        reloaded=joblib.load(out/filename)
        np.testing.assert_allclose(predict_returns(reloaded["model"], test, columns, center, scale), test[name], atol=1e-12)
        native=lightgbm.Booster(model_file=str(out/"model.txt"))
        np.testing.assert_allclose(native.predict(ordered_features(test, columns))*scale+center, test[name], atol=1e-12)
        pd.DataFrame(dict(feature=columns, gain=model.booster_.feature_importance(importance_type="gain"),
                          splits=model.booster_.feature_importance(importance_type="split"))).to_csv(out/"feature_importance.csv",index=False)
        report = dict(horizon=horizon, stage=stage, feature_family=reference_family, feature_cols=columns,
                      selected=selected, trials=trials if stage=="tuned" else trials[:1], date_ranges=date_ranges,
                      metrics=metrics, training_rows=len(development), test_rows=len(test),
                      train_tickers=sorted(development.ticker.unique()), held_out_tickers=protocol["held_out_tickers"],
                      test_keys_sha256=observation_hash(test), sources=sources,
                      model_path=str((out/filename).resolve()), model_reload_verified=True, native_reload_verified=True,
                      extra_embargo_sessions=0, xgboost_reference_cv=reference_report["best_trial"],
                      target_scaling="training-label mean/std only, matching XGBoost; no feature scaling/imputation")
        write_json(out/"report.json",report)
        reports[stage]=report
    report_dir=args.output/"reports"
    report_dir.mkdir(exist_ok=True)
    names=list("lightgbm_"+s for s in choices)+["xgboost","price_only","zero_return","historical_mean","stock_mean"]
    test[["ticker","group","close","target","target_date"]+names].to_csv(report_dir/(HORIZON_NAMES[horizon]+"_predictions.csv"),index_label="Date")
    metadata=dict(horizon=horizon, reports=reports, training_majority_direction=1 if (development.target>0).sum()>=(development.target<0).sum() else -1)
    write_json(report_dir/(HORIZON_NAMES[horizon]+"_metadata.json"),metadata)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,default=ROOT/"data"/"research_v2")
    parser.add_argument("--context-dir",type=Path,default=ROOT/"data"/"context_v3")
    parser.add_argument("--xgboost-dir",type=Path,default=ROOT/"artifacts"/"context_v3")
    parser.add_argument("--output",type=Path,default=ROOT/"artifacts"/"lightgbm"/"benchmark")
    parser.add_argument("--horizons",type=int,nargs="+",default=[1,21,252])
    parser.add_argument("--config",type=Path,help="JSON overrides of baseline LightGBM parameters")
    parser.add_argument("--tune",action="store_true",help="Optional bounded validation-only search; saves baseline separately")
    parser.add_argument("--trials",type=int,default=8,help="Includes baseline; 1–16 candidates when --tune")
    parser.add_argument("--early-stopping-rounds",type=int,default=50)
    args=parser.parse_args()
    if len(args.horizons)!=len(set(args.horizons)) or any(h not in HORIZON_NAMES for h in args.horizons):
        parser.error("Choose distinct supported horizons: 1, 21, 252")
    if args.early_stopping_rounds<1:
        parser.error("Early stopping rounds must be positive")
    protected_outputs=[args.xgboost_dir,ROOT/"src"/"XGBoost",ROOT/"src"/"models"]
    if args.output.exists() or any(args.output.resolve().is_relative_to(p.resolve()) for p in protected_outputs):
        parser.error("Choose a new output directory outside the XGBoost reference")
    reference=json.loads((args.xgboost_dir/"protocol.json").read_text())
    validate_snapshot(reference,args.context_dir)
    selections=json.loads((args.xgboost_dir/"selected.json").read_text())
    base=baseline_params(args.config)
    configs=candidate_params(base,args.trials if args.tune else 1)
    before=protected_hashes(args.xgboost_dir)
    args.output.mkdir(parents=True)
    protocol=dict(reference, reference_selections=selections, reference_directory=str(args.xgboost_dir.resolve()),
                  algorithm="lightgbm", model_version=MODEL_VERSION, baseline_params=base,
                  candidates=configs, tune=args.tune, horizons=args.horizons, early_stopping_rounds=args.early_stopping_rounds,
                  extra_embargo_sessions=0, feature_selection="Fixed to validation-selected XGBoost family per horizon",
                  created_at=datetime.now(timezone.utc).isoformat(),
                  data_directory=str(args.data_dir.resolve()), context_directory=str(args.context_dir.resolve()),
                  versions=dict(python=platform.python_version(),lightgbm=lightgbm.__version__,pandas=pd.__version__),
                  caveat="Historical test already inspected; models/configurations are not selected using its metrics")
    write_json(args.output/"protocol.json",protocol)
    write_json(args.output/"xgboost_before.json",before)
    try:
        for horizon in args.horizons:
            evaluate_horizon(args,protocol,horizon,configs)
        from src.LightGBM.model_report import generate_report
        generate_report(args.output)
    finally:
        after=protected_hashes(args.xgboost_dir)
        write_json(args.output/"xgboost_integrity.json",dict(unchanged=before==after,checked_files=len(before)))
        if before!=after:
            raise RuntimeError("Protected XGBoost source/artifacts changed during the benchmark")
    print(f"Saved independent models and comparison report: {args.output}",flush=True)


if __name__=="__main__": main()
