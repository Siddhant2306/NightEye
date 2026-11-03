import io
import unittest
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.forecasting.features import technical_features
from src.forecasting.protocol import boundaries, partitions
from src.forecasting.models import fit, raw_predict, calibrate, probability, direction_metrics, candidates
from src.forecasting.uncertainty import residual_bank, interval, simulate


class ForecastingTests(unittest.TestCase):
    def history(self, n=2000):
        rng = np.random.default_rng(42)
        c = 100*np.exp(np.cumsum(rng.normal(.0001, .015, n)))
        return pd.DataFrame(dict(close=c, open=c*.999, high=c*1.01, low=c*.99,
                                 volume=rng.integers(100, 10000, n)), index=pd.bdate_range("2010-01-01", periods=n))

    def test_technical_features_are_causal_and_scale_free(self):
        h = self.history()
        whole, truncated = technical_features(h), technical_features(h.iloc[:1000])
        pd.testing.assert_frame_equal(whole.iloc[:1000], truncated)
        scaled = h.copy()
        scaled[["open", "high", "low", "close"]] *= 10
        np.testing.assert_allclose(whole, technical_features(scaled), atol=1e-10, equal_nan=True)
        self.assertNotIn("insider_shares", whole)
        self.assertNotIn("sentiment", whole)

    def test_shared_chronological_edges_and_horizon_purging(self):
        h = self.history(3000)
        edges = boundaries(h.index)
        self.assertEqual(edges["test"], h.index[2400])
        for horizon in [1, 21, 252]:
            f = h.copy()
            f["target"] = np.log(f.close.shift(-horizon)/f.close)
            f["target_date"] = pd.Series(f.index, index=f.index).shift(-horizon)
            f["ticker"] = "FIT"
            f = pd.concat([f, f.assign(ticker="HOLD")]).sort_index().dropna()
            folds, training, calibration, test = partitions(f, edges, ["HOLD"])
            self.assertTrue((training.target_date < edges["calibration"]).all())
            self.assertTrue((calibration.target_date < edges["test"]).all())
            self.assertNotIn("HOLD", training.ticker.unique())
            self.assertNotIn("HOLD", calibration.ticker.unique())
            self.assertIn("HOLD", test.ticker.unique())
            for tr, va in folds:
                self.assertLess(tr.target_date.max(), va.index.min())

    def test_both_algorithms_and_tasks_reload_and_keep_feature_order(self):
        f = technical_features(self.history(450)).iloc[70:].copy()
        f["ticker"] = "A"
        f["target"] = np.sin(np.arange(len(f)))*.02
        columns = ["tech_momentum_5", "tech_rsi", "tech_relative_volume"]
        train, valid = f.iloc[:250], f.iloc[250:]
        for algorithm in ["xgboost", "lightgbm"]:
            for task in ["return", "direction"]:
                model = fit(algorithm, task, train, columns, candidates(1)[0], 12, valid, 3)
                pred = raw_predict(model, valid)
                buffer = io.BytesIO()
                joblib.dump(model, buffer)
                buffer.seek(0)
                reload = joblib.load(buffer)
                np.testing.assert_allclose(pred, raw_predict(reload, valid[list(reversed(valid.columns))]))
                self.assertTrue(np.isfinite(pred).all())
                self.assertGreaterEqual(model["rounds"], 1)
                if task == "direction":
                    self.assertTrue(((pred >= 0) & (pred <= 1)).all())
                    cal = calibrate(pred, valid.target)
                    self.assertIsNotNone(cal)
                    self.assertTrue(np.isfinite(probability(model, valid, cal)).all())

    def test_no_signal_does_not_fake_precision(self):
        metrics = direction_metrics(np.array([.1, -.1]*100), np.repeat(.51, 200))
        self.assertEqual(metrics["signal_coverage"], 0)
        self.assertIsNone(metrics["up_signal_precision"])
        self.assertIsNone(metrics["signal_accuracy"])
        self.assertEqual(metrics["balanced_accuracy"], .5)
        self.assertIsNone(direction_metrics(np.ones(200), np.repeat(.8, 200))["balanced_accuracy"])

    def test_empirical_intervals_and_scenario_paths(self):
        bank = residual_bank(np.linspace(-.1, .1, 200), np.zeros(200), np.ones(200)*.02)
        low, high = interval(0., .02, bank)
        self.assertLess(low, 0)
        self.assertGreater(high, 0)
        for horizon in [1, 21, 252]:
            args = (100., .02, .02, bank, np.linspace(-.02, .02, 100), horizon)
            result, paths = simulate(*args, paths=200)
            result2, paths2 = simulate(*args, paths=200)
            np.testing.assert_array_equal(paths, paths2)
            self.assertEqual(paths.shape, (200, horizon+1))
            self.assertTrue((paths[:, 0] == 100).all())
            self.assertTrue((paths > 0).all())
            self.assertEqual(result, result2)
            terminal = np.log(paths[:, -1]/100)
            # Endpoint samples really follow the calibration residual distribution.
            self.assertGreaterEqual(terminal.min(), .02+.02*bank.min()-1e-10)
            self.assertLessEqual(terminal.max(), .02+.02*bank.max()+1e-10)
        with self.assertRaises(ValueError):
            simulate(100, 0, .02, bank, np.zeros(100), 21, paths=1)


if __name__ == "__main__":
    unittest.main()
