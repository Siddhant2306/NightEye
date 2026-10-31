"""Reproduce every saved forecast, latest-row inference and protected-source check."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import joblib
import lightgbm
import numpy as np
import pandas as pd
from src.pipeline import ROOT
from src.research_context import prepare
from src.helper.load_data import load_data
from src.helper.benchmark import context_hashes, ordered_features, observation_hash
from src.LightGBM.config import HORIZON_NAMES
from src.LightGBM.predict import predict, predict_features
from src.LightGBM.train import protected_hashes


def verify(directory):
    directory=Path(directory)
    protocol=json.loads((directory/"protocol.json").read_text())
    before=json.loads((directory/"xgboost_before.json").read_text())
    if before!=protected_hashes(protocol["reference_directory"]):
        raise ValueError("Protected XGBoost files changed")
    data_dir=Path(protocol.get("data_directory",ROOT/"data"/"research_v2"))
    context_dir=Path(protocol.get("context_directory",ROOT/"data"/"context_v3"))
    if context_hashes(context_dir)!=protocol["context_hashes"]:
        raise ValueError("Context source snapshot changed")
    checked=0
    history=load_data(next(data_dir.glob("RELIANCE.NS_*.csv")))
    for horizon in protocol["horizons"]:
        label=HORIZON_NAMES[horizon]
        data,_,sources=prepare(SimpleNamespace(data_dir=data_dir,context_dir=context_dir),horizon)
        indexed=data.reset_index(names="Date").set_index(["Date","ticker"])
        saved=pd.read_csv(directory/"reports"/(label+"_predictions.csv"),parse_dates=["Date","target_date"])
        x=indexed.reindex(pd.MultiIndex.from_frame(saved[["Date","ticker"]]))
        for stage in (["baseline","tuned"] if protocol["tune"] else ["baseline"]):
            path=directory/stage/f"h{horizon}"
            report=json.loads((path/"report.json").read_text())
            expected={s["ticker"]:s["price_sha256"] for s in report["sources"]}
            if expected!={s["ticker"]:s["price_sha256"] for s in sources}:
                raise ValueError("Price source snapshot changed")
            if set(report["train_tickers"]).intersection(report["held_out_tickers"]):
                raise ValueError("Held-out company entered training")
            for trial in report["trials"]:
                for fold in trial["folds"]:
                    if not (pd.Timestamp(fold["max_train_target"])<pd.Timestamp(fold["start"])
                            and pd.Timestamp(fold["max_validation_target"])<pd.Timestamp(fold["end"])):
                        raise ValueError("Leaking label boundary")
            dated=saved.set_index("Date")
            if observation_hash(dated)!=report["test_keys_sha256"]:
                raise ValueError("Test observations changed")
            model_path=path/("lightgbm_"+label+".joblib")
            artifact=joblib.load(model_path)
            np.testing.assert_allclose(predict_features(artifact,x),saved["lightgbm_"+stage],rtol=1e-10,atol=1e-12)
            native=lightgbm.Booster(model_file=str(path/"model.txt"))
            native_prediction=native.predict(ordered_features(x,artifact["feature_cols"]))*artifact["target_scale"]+artifact["target_center"]
            np.testing.assert_allclose(native_prediction,saved["lightgbm_"+stage],rtol=1e-10,atol=1e-12)
            latest=predict(history,model_path,"RELIANCE.NS",context_dir)
            if latest["as_of"]!=str(history.index.max().date()) or "probability" in latest:
                raise ValueError("Incorrect inference date/schema")
            checked+=1
            print(f"{stage} h={horizon}: all predictions, native reload and latest inference verified",flush=True)
    result=dict(models_verified=checked,all_predictions_reproduced=True,native_reload=True,
                latest_inference_all_horizons=True,purged_boundaries=True,held_out_exclusion=True,
                frozen_sources=True,xgboost_unchanged=True,protected_files=len(before))
    (directory/"verification.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory",type=Path,required=True)
    verify(parser.parse_args().directory)
