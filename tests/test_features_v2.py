import io
import unittest
import importlib.util
import joblib
import numpy as np
import pandas as pd
import tempfile
from pathlib import Path
import json
from src.feature_engineering_v2.features import stock_features,cross_features,columns_for
from src.feature_engineering_v2.models import tree_fit,predict
from src.feature_engineering_v2.metrics import choose


class V2Tests(unittest.TestCase):
    def history(self,n=600):
        rng=np.random.default_rng(42);close=100*np.exp(np.cumsum(rng.normal(0,.01,n)))
        return pd.DataFrame(dict(close=close,open=close*.999,high=close*1.01,low=close*.99,volume=rng.integers(100,10000,n)),index=pd.bdate_range("2015-01-01",periods=n))

    def test_feature_formula_causality_and_scale(self):
        h=self.history();full,groups,registry=stock_features(h)
        truncated,_,_=stock_features(h.iloc[:400])
        pd.testing.assert_frame_equal(full.iloc[:400],truncated)
        self.assertAlmostEqual(full.v2_momentum_21.iloc[-1],np.log(h.close.iloc[-1]/h.close.iloc[-22]))
        scaled=h.copy();scaled[["open","high","low","close"]]*=10
        np.testing.assert_allclose(full,stock_features(scaled)[0],atol=1e-8,equal_nan=True)
        self.assertTrue(all(name in registry for names in groups.values() for name in names))
        self.assertNotIn("v2_momentum_21",columns_for(["tech_momentum_21"],groups,["momentum"]))

    def test_cross_section_excludes_held_out_peers_and_future_dates(self):
        index=pd.to_datetime(["2025-01-02"]*6+["2025-01-03"]*6)
        tickers=["RELIANCE.NS","NTPC.NS","ONGC.NS","BPCL.NS","GAIL.NS","POWERGRID.NS"]*2
        frame=pd.DataFrame(dict(ticker=tickers,v2_momentum_21=np.arange(12,dtype=float),v2_std_21=.01,v2_relative_volume_21=.1,v2_momentum_1=.01),index=index)
        a,_=cross_features(frame,["NTPC.NS"])
        modified=frame.copy();modified.loc[modified.ticker=="NTPC.NS","v2_momentum_21"]=100000
        b,_=cross_features(modified,["NTPC.NS"])
        np.testing.assert_allclose(a.loc[frame.ticker!="NTPC.NS"],b.loc[frame.ticker!="NTPC.NS"],equal_nan=True)
        short,_=cross_features(frame.iloc[:6],["NTPC.NS"])
        np.testing.assert_allclose(a.iloc[:6],short,equal_nan=True)

    def test_new_context_features_ignore_future_source_revisions(self):
        from src.feature_engineering_v2.features import context_features
        from src.context_sources import SECTOR_FOR
        h=self.history();dates=h.index
        returns=np.log(h.close).diff().shift(1)
        frame=pd.DataFrame(dict(market_return_1=returns,market_std_21=returns.rolling(21).std(),market_std_63=returns.rolling(63).std()),index=dates)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/"indices").mkdir()
            paths=[]
            for name in ["market",SECTOR_FOR["RELIANCE.NS"]]:
                path=root/"indices"/f"{name}_prices.csv";paths.append(path)
                pd.DataFrame(dict(Date=dates,close=h.close.to_numpy())).to_csv(path,index=False)
            before=context_features(frame.iloc[:400],h.iloc[:400],root,"RELIANCE.NS")[0]
            for path in paths:
                source=pd.read_csv(path);source.loc[400:,"close"]*=100;source.to_csv(path,index=False)
            after=context_features(frame.iloc[:400],h.iloc[:400],root,"RELIANCE.NS")[0]
            pd.testing.assert_frame_equal(before,after)
            self.assertTrue(np.isfinite(before.v2_market_beta_63.iloc[-1]))

    def test_schema_guard_and_reloaded_tree_continuation(self):
        rng=np.random.default_rng(42);x=rng.normal(size=350)
        frame=pd.DataFrame(dict(ticker="A",x=x,target=.02*x+rng.normal(0,.01,len(x))))
        tr,va=frame.iloc[:250],frame.iloc[250:]
        params=dict(depth=2,leaf_min=5,l2=10.,learning_rate=.03,sample=.8)
        for algorithm in ["xgboost","lightgbm"]:
            for task in ["return","direction"]:
                parent=tree_fit(algorithm,task,tr,["x"],params,10,va,3)
                child=tree_fit(algorithm,task,tr,["x"],dict(params,learning_rate=.005),5,va,3,parent)
                buf=io.BytesIO();joblib.dump(child,buf);buf.seek(0)
                np.testing.assert_allclose(predict(child,va),predict(joblib.load(buf),va))
                with self.assertRaises(ValueError): tree_fit(algorithm,task,tr,["wrong"],params,3,va,3,parent)

    def test_stability_rule_rejects_one_fold_lucky_candidate(self):
        def option(name,values):
            return dict(id=name,columns={"return":["x"]},aggregate={"return":dict(mean=float(np.mean(values)),fold_errors=values)})
        baseline=option("F0",[1.,1.])
        lucky=option("F1",[.1,1.5])
        stable=option("F2",[.9,.9])
        selected,absolute=choose([baseline,lucky,stable],"return")
        self.assertEqual(selected["id"],"F2")
        self.assertEqual(absolute["id"],"F1")

    def test_test_is_closed_until_all_selections_are_frozen(self):
        from src.feature_engineering_v2.finalize import freeze
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"protocol.json").write_text(json.dumps(dict(algorithms=["xgboost","lstm"],horizons=[1])))
            with self.assertRaises(ValueError): freeze(root)
            for algorithm in ["xgboost","lstm"]:
                d=root/"development"/algorithm/"h1";d.mkdir(parents=True)
                (d/"selection.json").write_text("{}")
                (d/"all_results.json").write_text("[]")
            freeze(root)
            (root/"development/lstm/h1/all_results.json").write_text("[{}]")
            with self.assertRaises(ValueError): freeze(root)

    @unittest.skipUnless(importlib.util.find_spec("torch"),"Optional PyTorch")
    def test_lstm_checkpoint_metrics_scaling_and_reload(self):
        from src.LSTM.model import sequences
        from src.feature_engineering_v2.models import lstm_fit
        from src.feature_engineering_v2.metrics import score
        n=240
        frame=pd.DataFrame(dict(ticker="A",x=np.sin(np.arange(n)),missing=np.nan,target=np.cos(np.arange(n))*.02),index=pd.bdate_range("2020-01-01",periods=n))
        frame=sequences(frame,["x","missing"],5);training,valid=frame.iloc[:150],frame.iloc[150:]
        cfg=dict(hidden=4,dropout=.1,learning_rate=.001,weight_decay=.001,batch_size=64)
        models=lstm_fit(training,valid,["x","missing"],cfg,epochs=3,patience=2)
        for task,model in models.items():
            field="validation_return_rmse" if task=="return" else "validation_direction_log_loss"
            expected=min(model["learning_curve"],key=lambda r:r[field])
            self.assertEqual(model["additional_epochs"],expected["additional_epoch"])
            got=score(valid,predict(model,valid),task)["macro_rmse" if task=="return" else "macro_log_loss"]
            self.assertAlmostEqual(got,expected[field],places=7)
            buf=io.BytesIO();joblib.dump(model,buf);buf.seek(0)
            np.testing.assert_allclose(predict(model,valid),predict(joblib.load(buf),valid))
        self.assertAlmostEqual(models["return"]["center"],training.target.mean())
        child=lstm_fit(training,valid,["x","missing"],dict(cfg,learning_rate=.0003),epochs=1,patience=1,parent=models["return"])
        self.assertTrue(child["return"]["reused"])
        with self.assertRaises(ValueError): lstm_fit(training.iloc[:-1],valid,["x","missing"],cfg,1,1,models["return"])

    @unittest.skipUnless(importlib.util.find_spec("torch"),"Optional PyTorch")
    def test_independent_lstm_head_sequences_align_by_keys(self):
        import torch
        from src.LSTM.model import Network
        from src.feature_engineering_v2.inference import predict_pair
        def bundle(task,columns,lookback):
            torch.manual_seed(42);model=Network(len(columns),4,.1)
            return dict(algorithm="lstm",task=task,columns=columns,lookback=lookback,config=dict(hidden=4,dropout=.1),
                feature_center=np.zeros(len(columns),dtype=np.float32),feature_spread=np.ones(len(columns),dtype=np.float32),
                center=0.,scale=1.,state={k:v.detach().numpy().copy() for k,v in model.state_dict().items()})
        frame=pd.DataFrame(dict(ticker="A",x=np.arange(30)/30,z=.5),index=pd.bdate_range("2025-01-01",periods=30))
        result=predict_pair(dict(regression=bundle("return",["x"],5),direction=bundle("direction",["z","x"],10),calibrator=None),frame)
        self.assertEqual(result.index.min(),frame.index[9])
        self.assertEqual(len(result),21)
        self.assertTrue(np.isfinite(result.regression).all())


if __name__=="__main__": unittest.main()
