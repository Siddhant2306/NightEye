import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from src.feature_engineering_v2.models import predict
from src.feature_engineering_v2.inference import predict_pair
from src.repair_study.study import select


class RepairTests(unittest.TestCase):
    def test_output_transform_applies_once_and_keeps_direction_unchanged(self):
        frame=pd.DataFrame({'risk_scale':[.01,.02]})
        model=dict(algorithm='xgboost',task='return',output_risk_scaled=True,output_shrinkage=.5)
        with patch('src.feature_engineering_v2.models.raw_predict',return_value=np.array([1.,2.])):
            np.testing.assert_allclose(predict(model,frame),[.005,.02])
            np.testing.assert_array_equal(predict(dict(algorithm='xgboost',task='return'),frame),[1.,2.])
            np.testing.assert_array_equal(predict(dict(algorithm='xgboost',task='direction',output_shrinkage=0.),frame),[1.,2.])

    def test_neutral_mixture_is_applied_before_probability_calibration(self):
        frame=pd.DataFrame(dict(ticker=['A','A'],risk_scale=.01),index=pd.bdate_range('2020-01-01',periods=2))
        bundle=dict(regression=dict(algorithm='xgboost',task='return'),direction=dict(algorithm='xgboost',task='direction'),direction_mixture=0.,calibrator=None)
        def prediction(model,part):return np.full(len(part),.01 if model['task']=='return' else .99)
        with patch('src.feature_engineering_v2.inference.predict',side_effect=prediction):
            result=predict_pair(bundle,frame)
        np.testing.assert_array_equal(result.probability_up,[.5,.5])
        np.testing.assert_array_equal(result.regression,[.01,.01])

    def test_validation_rejects_one_fold_gain_and_retains_neutral_fallback(self):
        neutral=dict(task='return',recipe='neutral',mix=0.,fold_errors=[1.,1.])
        lucky=dict(task='return',recipe='lucky',mix=1.,fold_errors=[.1,1.1])
        safe=dict(task='return',recipe='safe',mix=.5,fold_errors=[.9,.9])
        self.assertEqual(select([neutral,lucky],'return')['selected']['recipe'],'neutral')
        self.assertEqual(select([neutral,lucky,safe],'return')['selected']['recipe'],'safe')
        self.assertEqual(select([neutral,lucky,safe],'return')['absolute_minimum']['recipe'],'lucky')


if __name__=='__main__':unittest.main()
