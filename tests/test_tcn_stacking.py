import tempfile
import unittest
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import torch
from src.LSTM.model import preprocessing,sequences
from src.forecasting.tcn.model import TCN,CONFIGS,fit,predict
from src.forecasting.stacking.oof import aligned,audit,inner_split
from src.forecasting.stacking.meta import inputs,fit as fit_meta
from src.forecasting.ensemble import weights
from src.forecasting.stacking.evaluate import calibration_bank,load_test


class TcnStackingTests(unittest.TestCase):
    def test_causal_temporal_axis(self):
        torch.manual_seed(42)
        model=TCN(3,16,3,[1,2,4],.2).eval()
        x=torch.randn(2,35,6)
        modified=x.clone();modified[:,19:]+=50
        with torch.inference_mode():
            torch.testing.assert_close(model.temporal(x)[:,:19],model.temporal(modified)[:,:19],rtol=0,atol=0)
            self.assertEqual(model(x).shape,(2,2))

    def test_purge_sequences_and_training_only_scaling(self):
        dates=pd.bdate_range('2019-01-01',periods=700)
        frame=pd.DataFrame(dict(ticker='A',x=np.arange(700,dtype=float),target=.01,target_date=dates+pd.offsets.BDay(21)),index=dates)
        tr,va=inner_split(frame,dates[-1],21)
        self.assertLess(tr.target_date.max(),va.index.min())
        self.assertLess(va.target_date.max(),dates[-1])
        seq=sequences(frame,['x'],20)
        np.testing.assert_array_equal(seq._sequence.iloc[0][:,0],np.arange(20))
        self.assertEqual(seq.target_date.iloc[0],frame.target_date.iloc[19])
        self.assertLess(preprocessing(tr,['x'])[0][0],preprocessing(frame,['x'])[0][0])

    def test_oof_audit_and_target_alignment(self):
        row=dict(origin='2020-01-10',target_date='2020-01-13',prediction_timestamp='2020-01-10',
                 training_start='2019-01-01',training_end='2020-01-06',latest_training_label='2020-01-08',
                 selection_latest_label='2020-01-09',training_rows=100,horizon=1,ticker='A',target=.01,
                 regression=.005,probability_up=.6)
        panel=pd.DataFrame([dict(row,model='A'),dict(row,model='B')])
        m,r,p=aligned(panel,['A','B'])
        self.assertEqual(inputs(r,p).shape,(1,7))
        self.assertEqual(m.target.iloc[0],.01)
        for column in ['latest_training_label','selection_latest_label','training_end']:
            bad=panel.copy();bad.loc[0,column]=row['origin']
            with self.assertRaises(ValueError):audit(bad)
        bad=panel.copy();bad.loc[1,'target_date']='2020-01-14'
        with self.assertRaises(ValueError):aligned(bad,['A','B'])
        with self.assertRaises(ValueError):aligned(panel,['A','B','C'])

    def test_meta_insufficient_support_and_weight_constraints(self):
        origins=pd.bdate_range('2020-01-01',periods=10)
        m=pd.DataFrame(dict(fold=[1]*5+[2]*5,target_date=origins+pd.offsets.BDay(1),target=np.linspace(-.1,.1,10)),
                       index=pd.MultiIndex.from_arrays([origins,['A']*10],names=['origin','ticker']))
        x=np.column_stack([m.target,np.zeros(len(m))])
        result,report=fit_meta(m,x,np.full_like(x,.5),252)
        self.assertFalse(result);self.assertEqual(report['fit_dates'],4)
        w=weights(x,m.target.to_numpy(),'return',.1)
        self.assertTrue((w>=0).all());self.assertAlmostEqual(w.sum(),1.)

    def test_checkpoint_reproducibility(self):
        dates=pd.bdate_range('2020-01-01',periods=105)
        y=np.sin(np.arange(len(dates))/3)
        frame=pd.DataFrame(dict(ticker='A',x=y,target=y*.01),index=dates)
        seq=sequences(frame,['x'],20);tr,va=seq.iloc[:60],seq.iloc[60:]
        model=fit(tr,va,['x'],CONFIGS[0])
        other=fit(tr,va,['x'],CONFIGS[0])
        np.testing.assert_allclose(predict(model,va),predict(other,va))
        import io
        buffer=io.BytesIO();joblib.dump(model,buffer);buffer.seek(0)
        np.testing.assert_array_equal(predict(joblib.load(buffer),va),predict(model,va))

    def test_test_access_requires_frozen_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'Freeze every horizon'):
                load_test(Path(directory),1)

    def test_residual_bank_only_accepts_mature_out_of_fit_rows(self):
        dates=pd.bdate_range('2022-01-03',periods=150)
        cal=pd.DataFrame(dict(target=.02,risk_scale=.01,target_date=dates+pd.offsets.BDay(1)),index=dates)
        bank=calibration_bank(cal,np.zeros(len(cal)),dates[0],dates[-1]+pd.offsets.BDay(2))
        np.testing.assert_array_equal(bank,np.full(len(cal),2.))
        with self.assertRaises(ValueError):
            calibration_bank(cal,np.zeros(len(cal)),dates[1],dates[-1]+pd.offsets.BDay(2))
        with self.assertRaises(ValueError):
            calibration_bank(cal,np.zeros(len(cal)),dates[0],dates[-1])
