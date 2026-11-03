"""Full selected-model prediction, preprocessing, source and journal integrity audit."""
import argparse
import hashlib
import io
import contextlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.forecasting.train import save_json
from src.forecasting.protocol import before,window,span
from src.helper.load_data import load_data
from src.helper.benchmark import observation_hash
from src.feature_engineering_v2.prepare import DEFAULT,check_protected
from src.feature_engineering_v2.finalize import freeze
from src.feature_engineering_v2.inference import task_frame,predict_pair,keys,build_one
from src.feature_engineering_v2.models import predict
from src.forecasting.uncertainty import residual_bank,interval


def verify(root):
    frozen=freeze(root);protocol=json.loads((root/"protocol.json").read_text())
    edges={k:pd.Timestamp(v) for k,v in protocol["boundaries"].items()}
    checks=[];registry_hash=hashlib.sha256((root/"feature_registry.json").read_bytes()).hexdigest()
    source=next(s for s in protocol["source_prices"] if s["ticker"]=="RELIANCE.NS")
    with contextlib.redirect_stdout(io.StringIO()): history=load_data(Path(source["file"]))
    for h in protocol["horizons"]:
        full=joblib.load(root/"data"/f"unlabeled_h{h}.joblib")
        development=joblib.load(root/"data"/f"development_h{h}.joblib")
        if development.ticker.isin(protocol["held_out_companies"]).any(): raise ValueError("Held-out companies in development")
        for algorithm in protocol["algorithms"]:
            directory=root/f"h{h}"/algorithm
            bundle=joblib.load(directory/"model.joblib")
            if bundle["feature_registry_sha256"]!=registry_hash: raise ValueError("Feature schema registry changed")
            access=json.loads((directory/"test_access.json").read_text())
            if pd.Timestamp(access["first_label_access"])<pd.Timestamp(frozen["frozen_at"]): raise ValueError("Test accessed before selections froze")
            for task,key in [("return","regression"),("direction","direction")]:
                model=bundle[key];panel=task_frame(development,model)
                labeled=panel.dropna(subset=["target","target_date","risk_scale"])
                training=before(labeled,edges["calibration"]);cal=window(labeled,edges["calibration"],edges["test"])
                expected=bundle["splits"]["training" if task=="return" else "direction_training"]
                if span(training)!=expected or span(cal)!=bundle["splits"]["calibration"]: raise ValueError("Fitting/calibration boundary mismatch")
                if task=="return":
                    np.testing.assert_allclose([model["center"],model["scale"]],[training.target.mean(),max(training.target.std(),1e-8)],rtol=1e-8)
                    bank=residual_bank(cal.target,predict(model,cal),cal.risk_scale)
                    np.testing.assert_allclose(bank,bundle["residual_bank"],rtol=1e-8,atol=1e-9)
                if algorithm=="lstm":
                    from src.LSTM.model import preprocessing
                    c,s=preprocessing(training,model["columns"])
                    np.testing.assert_allclose(c,model["feature_center"],rtol=1e-6,atol=1e-7)
                    np.testing.assert_allclose(s,model["feature_spread"],rtol=1e-6,atol=1e-7)
            saved=pd.read_csv(directory/"test_predictions.csv",parse_dates=["Date","target_date"]).set_index("Date")
            if observation_hash(saved)!=bundle["splits"]["test_keys_sha256"]: raise ValueError("Saved observation keys changed")
            predicted=predict_pair(bundle,full)
            positions=pd.Series(np.arange(len(predicted)),index=keys(predicted)).reindex(keys(saved))
            predicted=predicted.iloc[positions.astype(int).to_numpy()]
            for name in ["regression","raw_probability","probability_up"]:
                np.testing.assert_allclose(saved[name],predicted[name],rtol=1e-8,atol=1e-9)
            for coverage in [.5,.8,.95]:
                low,high=interval(saved.regression,saved.risk_scale,bundle["residual_bank"],coverage)
                np.testing.assert_allclose(saved[f"lower_{coverage}"],low,rtol=1e-8,atol=1e-9)
                np.testing.assert_allclose(saved[f"upper_{coverage}"],high,rtol=1e-8,atol=1e-9)
            # Historical as-of inference must generate the same selected feature vectors
            # as the frozen cache, including independent head windows and peer ranks.
            fresh=build_one(history,bundle,"RELIANCE.NS")
            cached=full.loc[full.ticker=="RELIANCE.NS"]
            columns=list(dict.fromkeys(bundle["regression"]["columns"]+bundle["direction"]["columns"]))
            dates=cached.index[-126:]
            np.testing.assert_allclose(fresh.reindex(dates)[columns],cached.loc[dates,columns],rtol=1e-7,atol=1e-8,equal_nan=True)
            checks.append(dict(algorithm=algorithm,horizon=h,full_test_rows=len(saved),preprocessing_training_only=True,
                source_features_reproduced=True,independent_task_windows_reproduced=True,calibration_bank_reproduced=True,
                saved_predictions_reproduced=True,test_after_selection_freeze=True))
            print(f"Verified v2 {algorithm} h{h}: {len(saved)} observations",flush=True)
    result=dict(protected_original_files=check_protected(root),original_artifacts_data_and_nine_forecasts_unchanged=True,
        selections_frozen_before_final_test=True,models_verified=len(checks),checks=checks)
    save_json(root/"verification.json",result);return result


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,default=DEFAULT)
    print(json.dumps(verify(p.parse_args().output.resolve()),indent=2))
