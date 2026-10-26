import unittest
import numpy as np
import pandas as pd
from src.XGBoost.feature_eng import create_features
from src.pipeline import purged_split


def history(seed=5):
    rng = np.random.default_rng(seed)
    close = 100*np.exp(np.cumsum(rng.normal(0, .01, 1000)))
    return pd.DataFrame(dict(open=close*.999, high=close*1.01, low=close*.99,
                             close=close, volume=rng.integers(100, 10000, 1000)),
                        index=pd.bdate_range('2010-01-01', periods=1000))


class PipelineTests(unittest.TestCase):
    def test_features_do_not_see_future(self):
        raw = history()
        full, columns = create_features(raw, 21, include_target=False)
        prefix, _ = create_features(raw.iloc[:700], 21, include_target=False)
        pd.testing.assert_frame_equal(full.loc[prefix.index, columns], prefix[columns])
        self.assertEqual(prefix.index[-1], raw.index[699])

    def test_labels_and_purge(self):
        raw = history()
        data, _ = create_features(raw, 21)
        self.assertAlmostEqual(data.target.iloc[0], np.log(raw.close.loc[data.target_date.iloc[0]]/data.close.iloc[0]))
        train, valid = purged_split(data, raw.index[700], raw.index[900])
        self.assertLess(train.target_date.max(), valid.index.min())
        self.assertLess(valid.target_date.max(), raw.index[900])

    def test_price_scale_invariance(self):
        raw = history()
        scaled = raw.copy()
        scaled[['open', 'high', 'low', 'close']] *= 100
        a, cols = create_features(raw)
        b, _ = create_features(scaled)
        np.testing.assert_allclose(a[cols], b[cols], atol=1e-9)

    def test_constant_price_rsi(self):
        raw = history()
        raw[['open', 'high', 'low', 'close']] = 100.
        data, _ = create_features(raw, include_target=False, extended=False)
        self.assertTrue((data.rsi_14d == 50).all())
        self.assertGreater(len(data), 0)

if __name__ == '__main__':
    unittest.main()
