import io
import importlib.util
import unittest
import joblib
import numpy as np
import pandas as pd
HAS_TORCH=importlib.util.find_spec("torch") is not None
if HAS_TORCH:
    from src.LSTM.model import sequences, preprocessing, fit, predict
from src.forecasting.backtest import run_strategy


class LSTMBacktestTests(unittest.TestCase):
    @unittest.skipUnless(HAS_TORCH,"Install requirements-lstm.txt for optional LSTM tests")
    def test_sequences_never_mix_stocks_or_use_future_rows(self):
        index=pd.bdate_range("2020-01-01",periods=30)
        frame=pd.concat([pd.DataFrame(dict(ticker=t,x=np.arange(30)+offset),index=index)
                         for t,offset in [("A",0),("B",1000)]]).sort_index()
        result=sequences(frame,["x"],5)
        # Preserve reference row order, including stock ties within each date.
        expected_keys=frame.loc[frame.index>=index[4]].reset_index()[["index","ticker"]]
        actual_keys=result.reset_index()[["index","ticker"]]
        pd.testing.assert_frame_equal(actual_keys,expected_keys)
        for date,row in result.iterrows():
            expected=frame.loc[frame.ticker==row.ticker].loc[:date].x.iloc[-5:].to_numpy()
            np.testing.assert_array_equal(row._sequence[:,0],expected)
            self.assertLessEqual(row._sequence_start,date)
        shortened=sequences(frame.loc[frame.index<=index[15]],["x"],5)
        for ticker in ["A","B"]:
            a=result.loc[(result.ticker==ticker)&(result.index<=index[15])]
            b=shortened.loc[shortened.ticker==ticker]
            for x,y in zip(a._sequence,b._sequence): np.testing.assert_array_equal(x,y)

    @unittest.skipUnless(HAS_TORCH,"Install requirements-lstm.txt for optional LSTM tests")
    def test_train_only_scaling_missing_values_and_model_reload(self):
        n=260
        f=pd.DataFrame(dict(ticker="A",x=np.sin(np.arange(n)),missing=np.nan,
                            target=np.cos(np.arange(n))*.02),index=pd.bdate_range("2020-01-01",periods=n))
        f=sequences(f,["x","missing"],5)
        tr,va=f.iloc[:160],f.iloc[160:]
        center,spread=preprocessing(tr,["x","missing"])
        self.assertEqual(center[1],0.)
        self.assertEqual(spread[1],1.)
        cfg=dict(hidden=4,dropout=.1,learning_rate=.001,weight_decay=.001,batch_size=64)
        reg,cls=fit(tr,va,["x","missing"],cfg,epochs=2,patience=1)
        self.assertAlmostEqual(reg["center"],tr.target.mean())
        for bundle in [reg,cls]:
            buf=io.BytesIO(); joblib.dump(bundle,buf); buf.seek(0)
            np.testing.assert_allclose(predict(bundle,va),predict(joblib.load(buf),va))
        self.assertTrue(((predict(cls,va)>=0)&(predict(cls,va)<=1)).all())
        with self.assertRaises(ValueError): predict(reg,va.drop(columns="_sequence"))

    def market(self):
        index=pd.bdate_range("2024-01-01",periods=12)
        history=pd.DataFrame(dict(open=np.arange(12)+100.,close=np.arange(12)+100.),index=index)
        prediction=pd.DataFrame(dict(ticker="A",probability_up=.9,regression=.02),index=index[:8])
        prediction.index.name="Date"
        return history,prediction

    def test_next_open_execution_non_overlap_and_costs(self):
        history,prediction=self.market()
        metrics,curve,trades=run_strategy(prediction,{"A":history},2,cost_bps=10,slippage_bps=5)
        self.assertEqual(trades.iloc[0].entry,history.index[1])
        self.assertEqual(trades.iloc[0].exit,history.index[3])
        self.assertGreater(trades.iloc[0].entry,trades.iloc[0].origin)
        self.assertGreater(metrics["cash_costs"],0)
        self.assertTrue((trades.entry.iloc[1:].to_numpy()>=trades.exit.iloc[:-1].to_numpy()).all())
        expected=(history.open.iloc[3]/history.open.iloc[1])*(1-.0015)/(1+.0015)-1
        self.assertAlmostEqual(trades.net_return.iloc[0],expected)
        self.assertEqual(curve.strategy.iloc[0],100000)

    def test_uncertain_forecasts_stay_cash(self):
        history,prediction=self.market()
        prediction["probability_up"]=.5
        metrics,curve,trades=run_strategy(prediction,{"A":history},1)
        self.assertEqual(metrics["trades"],0)
        self.assertEqual(metrics["strategy"]["total_return"],0.)
        self.assertIsNone(metrics["win_rate"])
        self.assertTrue((curve.strategy==100000).all())

    def test_unmatured_positions_are_liquidated_at_predeclared_end(self):
        history,prediction=self.market()
        metrics,curve,trades=run_strategy(prediction,{"A":history},252,cost_bps=0,slippage_bps=0)
        self.assertEqual(len(trades),1)
        self.assertTrue(trades.truncated_at_end.iloc[0])
        self.assertEqual(trades.exit.iloc[0],history.index[-1])
        self.assertGreater(metrics["strategy"]["total_return"],0)
        self.assertAlmostEqual(curve.strategy.iloc[-1]/100000,history.open.iloc[-1]/history.open.iloc[1])


if __name__=="__main__": unittest.main()
