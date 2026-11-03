import unittest
import numpy as np
import pandas as pd
from src.feature_engineering_v2.calibration import guarded_calibrate


class CalibrationGuardTests(unittest.TestCase):
    def frame(self,days=300,horizon=1):
        dates=pd.bdate_range('2018-01-01',periods=days+horizon)
        origins=dates[:days].repeat(5)
        x=np.tile(np.array([-2.,-1.,0.,1.,2.]),days)
        return pd.DataFrame(dict(target=np.where(x>0,.02,-.02),target_date=dates[horizon:].repeat(5)),index=origins),x

    def test_accepts_past_only_forward_probability_gain(self):
        frame,x=self.frame()
        model,report=guarded_calibrate(.55+.08*x,frame,1)
        self.assertIsNotNone(model)
        self.assertTrue(report['accepted'])
        boundary=pd.Timestamp(report['boundary'])
        expected=((frame.index<boundary)&(frame.target_date<boundary)).sum()
        self.assertEqual(report['fit_rows'],expected)
        self.assertLess(report['calibrated']['brier'],report['raw']['brier'])
        self.assertLess(report['calibrated']['log_loss'],report['prior']['log_loss'])

    def test_rejects_calibration_that_chases_an_earlier_base_rate(self):
        frame,x=self.frame()
        frame['target']=np.where(np.arange(len(frame))%10==0,-.02,.02)
        frame.loc[frame.index>=frame.index.unique()[210],'target']=np.where(x[-450:]>0,.02,-.02)
        model,report=guarded_calibrate(np.full(len(frame),.5),frame,1)
        self.assertIsNone(model)
        self.assertFalse(report['accepted'])
        self.assertEqual(report['reason'],'no_forward_gain_over_raw_and_prior')

    def test_many_overlapping_annual_rows_are_not_many_date_blocks(self):
        frame,_=self.frame(days=136,horizon=252)
        model,report=guarded_calibrate(np.full(len(frame),.5),frame,252)
        self.assertIsNone(model)
        self.assertEqual(report['fit_rows'],0)
        self.assertEqual(report['reason'],'insufficient_mature_forward_blocks')
        self.assertEqual(report['minimum_dates_per_part'],504)


if __name__=='__main__': unittest.main()
