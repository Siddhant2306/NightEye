"""Reconstruct frozen splits and reproduce every saved test prediction, without fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.forecasting import VERSION
from src.forecasting.train import load_histories, prepare, evaluate, save_json
from src.forecasting.protocol import partitions, span
from src.forecasting.models import raw_predict, probability, direction_metrics
from src.forecasting.uncertainty import residual_bank, interval
from src.forecasting.report import generate
from src.helper.benchmark import context_hashes, observation_hash
from src.LightGBM.train import protected_hashes


def verify(directory):
    protocol = json.loads((directory/"protocol.json").read_text())
    if protocol.get("version") != VERSION:
        raise ValueError("Wrong experiment version")
    for source in protocol["source_prices"]:
        if hashlib.sha256(Path(source["file"]).read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Changed price source")
    old = json.loads((directory/"protected_before.json").read_text())
    if old != protected_hashes():
        raise ValueError("Protected old source/artifacts changed")
    data_dir = Path(protocol["source_prices"][0]["file"]).parent
    histories, _ = load_histories(data_dir)
    edges = {k:pd.Timestamp(v) for k,v in protocol["boundaries"].items()}
    checked = []
    for horizon in protocol["horizons"]:
        first = directory/f"h{horizon}"/protocol["algorithms"][0]/"model.joblib"
        context = Path(joblib.load(first)["context_dir"])
        if context_hashes(context) != protocol["context_hashes"]:
            raise ValueError("Changed context source")
        panel, _ = prepare(histories, horizon, context)
        if "lstm" in protocol["algorithms"]:
            from src.LSTM.model import sequences
            first_bundle = joblib.load(first)
            panel = sequences(panel, first_bundle["regression"]["columns"], first_bundle["regression"]["lookback"])
        folds, training, cal, test = partitions(panel.dropna(subset=["target", "target_date", "risk_scale"]), edges, protocol["held_out_companies"])
        for algorithm in protocol["algorithms"]:
            folder = directory/f"h{horizon}"/algorithm
            bundle = joblib.load(folder/"model.joblib")
            if bundle["version"] != VERSION or bundle["splits"]["test_keys_sha256"] != observation_hash(test):
                raise ValueError("Mismatched model or test observations")
            if bundle["splits"]["training"] != span(training) or bundle["splits"]["calibration"] != span(cal):
                raise ValueError("Mismatched training/calibration dates")
            saved = pd.read_csv(folder/"test_predictions.csv", parse_dates=["Date", "target_date"]).set_index("Date")
            if observation_hash(saved) != observation_hash(test):
                raise ValueError("Saved CSV observation mismatch")
            np.testing.assert_allclose(saved.target, test.target, rtol=1e-10, atol=1e-12)
            if not np.array_equal(saved.target_date.to_numpy(), test.target_date.to_numpy()):
                raise ValueError("Target date mismatch")
            reproduced = {}
            for name in ["regression", "control"]:
                reproduced[name] = raw_predict(bundle[name], test)
                # XGBoost outputs float32; older CSVs used pandas' float32 display precision.
                np.testing.assert_allclose(saved[name], reproduced[name], rtol=1e-6, atol=1e-9)
            np.testing.assert_allclose(saved.raw_probability, raw_predict(bundle["direction"], test), rtol=1e-6, atol=1e-9)
            np.testing.assert_allclose(saved.probability_up, probability(bundle["direction"], test, bundle["calibrator"]), rtol=1e-6, atol=1e-9)
            expected_bank = residual_bank(cal.target, raw_predict(bundle["regression"], cal), cal.risk_scale)
            np.testing.assert_allclose(bundle["residual_bank"], expected_bank, rtol=1e-9)
            for coverage in [.5,.8,.95]:
                low, high = interval(reproduced["regression"], test.risk_scale, expected_bank, coverage)
                np.testing.assert_allclose(saved[f"lower_{coverage}"], low, rtol=1e-9, atol=1e-12)
                np.testing.assert_allclose(saved[f"upper_{coverage}"], high, rtol=1e-9, atol=1e-12)
            # Recompute diagnostics only; never refit/select from the test.
            save_json(folder/"metrics.json", evaluate(saved, bundle["threshold"], horizon))
            stocks = pd.read_csv(folder/"per_stock.csv")
            for index, row in stocks.iterrows():
                part = saved.loc[saved.ticker == row.ticker]
                d = direction_metrics(part.target, part.probability_up, bundle["threshold"])
                stocks.loc[index, "balanced_accuracy"] = d["balanced_accuracy"] if d["balanced_accuracy"] is not None else np.nan
            stocks.to_csv(folder/"per_stock.csv", index=False)
            checked.append(dict(horizon=horizon, algorithm=algorithm, full_test_rows=len(test),
                                train_labels_before_calibration=True, calibration_labels_before_test=True,
                                joblib_predictions_reproduced=True, residual_bank_reproduced=True,
                                interval_predictions_reproduced=True))
            print(f"Verified {algorithm} h{horizon}: {len(test)} test predictions", flush=True)
    result = dict(protected_files=len(old), protected_unchanged=True, source_prices_unchanged=True,
                  context_unchanged=True, saved_bundles_reloaded=len(checked), checks=checked)
    save_json(directory/"verification.json", result)
    generate(directory)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory", type=Path, required=True)
    print(json.dumps(verify(p.parse_args().directory), indent=2))
