import tempfile
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
from test_pipeline import history
from src.XGBoost.reduced_features import binned_mode, make_reduced_features, point_in_time_valuation


class ReducedFeatureTests(unittest.TestCase):
    def test_feature_families_are_causal(self):
        raw = history()
        actions = pd.DataFrame({'raw_close': raw.close, 'dividend': 0.}, index=raw.index)
        actions.iloc[600, 1] = 2.
        for family in ['core', 'statistics', 'statistics_mode', 'statistics_dividends']:
            full, columns = make_reduced_features(raw, 21, family, actions, include_target=False)
            prefix, _ = make_reduced_features(raw.iloc[:700], 21, family, actions.iloc[:700], include_target=False)
            pd.testing.assert_frame_equal(full.loc[prefix.index, columns], prefix[columns])
            self.assertEqual(prefix.index[-1], raw.index[699])

    def test_dividend_yield_uses_observed_raw_cash(self):
        raw = history()
        actions = pd.DataFrame({'raw_close': 200., 'dividend': 0.}, index=raw.index)
        actions.iloc[600, 1] = 4.
        features, _ = make_reduced_features(raw, 1, 'statistics_dividends', actions)
        self.assertEqual(features.loc[raw.index[599], 'dividend_yield_365'], 0.)
        self.assertEqual(features.loc[raw.index[600], 'dividend_yield_365'], .02)
        self.assertEqual(features.loc[raw.index[600], 'dividend_events_365'], 1.)
        with self.assertRaises(ValueError):
            make_reduced_features(raw, 1, 'statistics_dividends', actions.iloc[1:])

    def test_mode_is_binned_and_ties_are_deterministic(self):
        self.assertAlmostEqual(binned_mode([.00101, .00102, -.02]), .001)
        self.assertEqual(binned_mode([-.002, .001]), .001)
        self.assertEqual(binned_mode([-.001, .001]), -.001)

    def test_earnings_available_only_after_publication(self):
        dates = pd.bdate_range('2020-05-04', periods=3)
        frame = pd.DataFrame({'close': 100.}, index=dates)
        # May 5 at 16:30 IST: after close, unavailable until May 6.
        facts = pd.DataFrame(dict(available_at=['2020-05-05T11:00:00Z'], period_end=['2020-03-31'],
                                  eps_ttm=[5.], source=['synthetic unit test'], currency=['INR'],
                                  share_basis=['matches_raw_close']))
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            path = Path(directory)/'facts.csv'
            facts.to_csv(path, index=False)
            result = point_in_time_valuation(frame, frame.close, path)
            self.assertTrue(result.pe_ttm.iloc[:2].isna().all())
            self.assertEqual(result.pe_ttm.iloc[2], 20.)
            self.assertEqual(result.earnings_yield_ttm.iloc[2], .05)

    def test_mean_and_std_are_not_future_statistics(self):
        raw = history()
        features, _ = make_reduced_features(raw, 21, 'statistics')
        returns = np.log(raw.close).diff()
        date = features.index[0]
        self.assertAlmostEqual(features.loc[date, 'mean_21'], returns.loc[:date].tail(21).mean())
        self.assertAlmostEqual(features.loc[date, 'std_21'], returns.loc[:date].tail(21).std())

if __name__ == '__main__':
    unittest.main()
