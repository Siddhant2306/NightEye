import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import joblib
import lightgbm
import numpy as np
import pandas as pd
from test_pipeline import history
from src.XGBoost.feature_eng import create_features
from src.helper.benchmark import ordered_features, development_split, validation_folds, context_hashes
from src.LightGBM import MODEL_VERSION
from src.LightGBM.config import baseline_params, candidate_params
from src.LightGBM.model import fit_model, predict_returns
from src.LightGBM.predict import predict_features, return_to_price
from src.LightGBM.metrics import directional_metrics, summary_metrics, paired_uncertainty, ranking_metrics
from src.LightGBM.train import validate_snapshot


def training_frame():
    rng=np.random.default_rng(7)
    dates=pd.bdate_range("2015-01-01",periods=1500)
    frame=pd.DataFrame(dict(x=rng.normal(size=len(dates)),other=rng.normal(size=len(dates)),
                            ticker=np.where(np.arange(len(dates))%3==0,"HOLDOUT","TRAIN")),index=dates)
    frame["target"] = .01*frame.x + rng.normal(0,.01,len(frame))
    frame["target_date"] = pd.Series(dates,index=dates).shift(-21)
    return frame.dropna(subset=["target_date"])


class LightGBMTests(unittest.TestCase):
    def setUp(self):
        self.params=dict(baseline_params(),n_estimators=12,num_leaves=3,max_depth=2,
                         min_child_samples=5,n_jobs=1)
        self.frame=training_frame()

    def test_target_correct_for_all_three_horizons(self):
        raw=history()
        for horizon in [1,21,252]:
            frame,_=create_features(raw,horizon,extended=False)
            row=frame.iloc[0]; date=frame.index[0]
            i=raw.index.get_loc(date)
            self.assertEqual(row.target_date,raw.index[i+horizon])
            self.assertAlmostEqual(row.target,np.log(raw.close.iloc[i+horizon]/raw.close.iloc[i]))

    def test_all_horizons_reload_and_feature_order(self):
        for horizon in [1,21,252]:
            train=self.frame.iloc[:250]
            model,center,scale=fit_model(train,["x","other"],self.params)
            artifact=dict(model=model,algorithm="lightgbm",model_version=MODEL_VERSION,
                          horizon=horizon,feature_cols=["x","other"],target_center=center,target_scale=scale)
            expected=predict_returns(model,self.frame.tail(10),["x","other"],center,scale)
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
                path=Path(directory)/"model.joblib"
                joblib.dump(artifact,path)
                loaded=joblib.load(path)
                reordered=self.frame.tail(10)[["other","x"]]
                np.testing.assert_allclose(predict_features(loaded,reordered),expected,atol=1e-12)
                model.booster_.save_model(str(Path(directory)/"model.txt"))
                native=lightgbm.Booster(model_file=str(Path(directory)/"model.txt"))
                np.testing.assert_allclose(native.predict(reordered[["x","other"]])*scale+center,expected,atol=1e-12)

    def test_missing_values_native_but_missing_columns_rejected(self):
        frame=self.frame.iloc[:250].copy(); frame.loc[frame.index[:20],"other"]=np.nan
        model,center,scale=fit_model(frame,["x","other"],self.params)
        test=self.frame.tail(5).copy(); test["other"]=np.nan
        self.assertTrue(np.isfinite(predict_returns(model,test,["x","other"],center,scale)).all())
        with self.assertRaises(ValueError): ordered_features(test.drop(columns="x"),["x","other"])
        test["x"]=np.inf
        with self.assertRaises(ValueError): ordered_features(test,["x","other"])
        duplicated=pd.DataFrame([[1.,2.]],columns=["x","x"])
        with self.assertRaises(ValueError): ordered_features(duplicated,["x"])

    def test_target_scaling_excludes_validation_labels(self):
        train=self.frame.iloc[:250]; valid=self.frame.iloc[300:350].copy()
        valid["target"]=999.
        _,center,scale=fit_model(train,["x","other"],self.params,valid,stopping_rounds=3)
        self.assertAlmostEqual(center,train.target.mean())
        self.assertAlmostEqual(scale,train.target.std())

    def test_chronology_purging_and_company_exclusion(self):
        train,test=development_split(self.frame,"2020-01-01",["HOLDOUT"])
        self.assertNotIn("HOLDOUT",set(train.ticker))
        self.assertLess(train.target_date.max(),test.index.min())
        for fit,valid,metadata in validation_folds(train,["2017-01-01","2019-01-01","2020-01-01"]):
            self.assertLess(fit.target_date.max(),valid.index.min())
            self.assertLess(valid.target_date.max(),pd.Timestamp(metadata["end"]))
            self.assertTrue((fit.index<pd.Timestamp(metadata["start"])).all())

    def test_tuning_is_bounded_seeded_and_contains_baseline(self):
        base=baseline_params()
        self.assertEqual(candidate_params(base,8),candidate_params(base,8))
        self.assertEqual(candidate_params(base,8)[0],base)
        with self.assertRaises(ValueError): candidate_params(base,17)
        self.assertEqual(base["subsample_freq"],1)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/"invalid.json"; path.write_text(json.dumps({"metric":"l1"}))
            with self.assertRaises(ValueError): baseline_params(path)

    def test_price_conversion_and_no_probability(self):
        self.assertAlmostEqual(return_to_price(100.,np.log(1.1)),110.)
        for price,value in [(0.,.1),(100.,np.nan),(100.,1000.)]:
            with self.assertRaises(ValueError): return_to_price(price,value)

    def test_all_up_is_not_balanced_skill(self):
        result=directional_metrics(np.array([.1,-.1,.2,-.2]),np.array([.1,.1,.1,.1]))
        self.assertEqual(result["collapse"],"all_UP")
        self.assertEqual(result["balanced_accuracy_nonflat"],.5)
        self.assertEqual(result["classes"]["DOWN"]["recall"],0.)
        self.assertFalse(result["classes"]["DOWN"]["precision_defined"])
        self.assertEqual(result["confusion_matrix"],[[0,0,2],[0,0,0],[0,0,2]])

    def test_flat_outcomes_and_predictions_are_explicit(self):
        result=directional_metrics(np.array([-.1,0.,.1]),np.array([0.,0.,.1]))
        self.assertEqual(result["flat_actual_count"],1)
        self.assertEqual(result["flat_prediction_count"],2)
        self.assertAlmostEqual(result["accuracy"],2/3)

    def test_constant_correlations_not_invented(self):
        frame=self.frame.tail(20).copy(); frame["prediction"]=.01
        metrics=summary_metrics(frame,"prediction")
        self.assertIsNone(metrics["pearson"]); self.assertIsNone(metrics["spearman"])

    def test_insufficient_annual_history_has_no_interval(self):
        frame=self.frame.tail(100).copy(); frame["a"]=.01; frame["b"]=.02
        self.assertIsNone(paired_uncertainty(frame,"a","b",252)["rmse_difference_ci95"])

    def test_cross_sectional_rank_metric(self):
        frame=pd.DataFrame(dict(ticker=list("ABCDE"),target=[1.,2.,3.,4.,5.],prediction=[1.,2.,3.,4.,5.]),
                           index=pd.to_datetime(["2025-01-01"]*5))
        self.assertAlmostEqual(ranking_metrics(frame,"prediction",21)["mean_rank_ic"],1.)
        later=frame.copy(); later.index=pd.to_datetime(["2025-01-02"]*5); later["prediction"]=1.
        result=ranking_metrics(pd.concat([frame,later]),"prediction",21)
        self.assertEqual(result["total_dates"],2)
        self.assertEqual(result["evaluated_date_fraction"],.5)

    def test_snapshot_mismatch_fails(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            directory=Path(directory); (directory/"indices").mkdir(); (directory/"fundamentals").mkdir()
            path=directory/"indices"/"market.csv"; path.write_text("a\n1\n")
            protocol=dict(context_hashes=context_hashes(directory),training_start="2017-01-01",test_start="2025-01-01",validation_edges=["2021-01-01","2023-01-01","2025-01-01"])
            path.write_text("a\n2\n")
            with self.assertRaises(ValueError): validate_snapshot(protocol,directory)

    def test_cannot_write_under_xgboost_reference(self):
        from src.LightGBM.train import main
        for protected in [Path.cwd()/"artifacts"/"context_v3",Path.cwd()/"src"/"XGBoost",Path.cwd()/"src"/"models"]:
            with patch("sys.argv",["train","--output",str(protected/"forbidden")]):
                with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
                    main()
            self.assertEqual(error.exception.code,2)

    def test_report_rejects_other_algorithm_without_writing(self):
        from src.LightGBM.model_report import generate_report
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            directory=Path(directory)
            (directory/"protocol.json").write_text(json.dumps(dict(algorithm="xgboost")))
            with self.assertRaises(ValueError): generate_report(directory)
            self.assertFalse((directory/"comparisons").exists())


if __name__=="__main__": unittest.main()
