import unittest
import numpy as np
import pandas as pd
from src.forecasting.diagnostics import price_frame,metrics,learning_rows
from src.forecasting.models import fit,raw_predict,candidates


class DiagnosticTests(unittest.TestCase):
    def test_prices_are_aligned_to_future_target_dates(self):
        frame=pd.DataFrame(dict(ticker=["A","A"],close=[100.,110.],target=np.log([1.1,.9]),
            target_date=pd.to_datetime(["2025-02-03","2025-02-04"])),index=pd.to_datetime(["2025-01-02","2025-01-03"]))
        result=price_frame(frame,np.log([1.05,.95]))
        np.testing.assert_allclose(result.actual_price,[110.,99.])
        np.testing.assert_allclose(result.predicted_price,[105.,104.5])
        np.testing.assert_array_equal(result.target_date,frame.target_date)
        self.assertAlmostEqual(metrics(result)["price_mae"],5.25)
        self.assertTrue((result.target_date>result.origin_date).all())

    def test_unknown_targets_and_mixed_stocks_are_rejected(self):
        frame=pd.DataFrame(dict(ticker=["A","B"],close=[100.,200.],target=[.01,.02],
            target_date=pd.to_datetime(["2025-01-03","2025-01-06"])),index=pd.to_datetime(["2025-01-02","2025-01-03"]))
        with self.assertRaises(ValueError): price_frame(frame,[0.,0.])
        frame["ticker"]="A"
        frame["target_date"]=pd.NaT
        with self.assertRaises(ValueError): price_frame(frame,[0.,0.])
        self.assertEqual(metrics(price_frame(frame.iloc[:0],[])),{"rows":0})

    def test_logging_training_metrics_preserves_selected_predictions(self):
        rng=np.random.default_rng(42)
        x=rng.normal(size=300)
        frame=pd.DataFrame(dict(ticker="A",x=x,target=.02*x+rng.normal(0,.005,300)))
        training,valid=frame.iloc[:220],frame.iloc[220:]
        params=dict(candidates(1)[0],leaf_min=5)
        for algorithm in ["xgboost","lightgbm"]:
            for task in ["return","direction"]:
                a=fit(algorithm,task,training,["x"],params,12,valid,3)
                b=fit(algorithm,task,training,["x"],params,12,valid,3,record_training=True)
                self.assertEqual(a["rounds"],b["rounds"])
                np.testing.assert_allclose(raw_predict(a,valid),raw_predict(b,valid),atol=1e-8)
                curves=learning_rows(b,1)
                self.assertGreater(len(curves),0)
                self.assertTrue(all(np.isfinite(r["training"]) and np.isfinite(r["validation"]) for r in curves))


if __name__=="__main__": unittest.main()
