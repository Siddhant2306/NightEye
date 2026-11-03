import unittest
from unittest.mock import patch
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from src.forecasting.market_data import completed_cutoff,freshness
from src.forecasting.paper import outcome,next_weekday_open


class PaperTests(unittest.TestCase):
    def fixture(self):
        history=pd.DataFrame(dict(close=[100.,102.,101.,103.]),index=pd.bdate_range("2026-01-05",periods=4))
        record=dict(as_of="2026-01-05",recorded_at="2026-01-05T12:00:00+00:00",horizon_trading_sessions=1,
            predicted_log_return=.01,classifier_probability_up=.6,current_adjusted_close=100.,
            empirical_price_intervals={"0.8":dict(lower_adjusted_price=95.,upper_adjusted_price=105.)})
        return history,record

    def test_no_outcomes_until_horizon_matures(self):
        h,r=self.fixture()
        result=outcome(r,h.iloc[:1],"2026-01-06T12:00:00+00:00")
        self.assertEqual(result["status"],"PENDING")
        self.assertEqual(result["observed_future_sessions"],0)

    def test_adjusted_return_uses_one_consistent_new_price_basis(self):
        h,r=self.fixture()
        result=outcome(r,h,"2026-01-08T12:00:00+00:00")
        revised=outcome(r,h*.5,"2026-01-08T12:00:00+00:00")
        self.assertAlmostEqual(result["actual_log_return"],np.log(1.02))
        self.assertAlmostEqual(result["actual_log_return"],revised["actual_log_return"])
        self.assertTrue(revised["adjusted_origin_revised"])
        self.assertTrue(result["interval80_covered"])

    def test_cannot_score_backdated_forecast_as_prospective(self):
        h,r=self.fixture()
        r["recorded_at"]="2026-01-07T12:00:00+00:00"
        self.assertEqual(outcome(r,h,"2026-01-08T12:00:00+00:00")["status"],"INVALID_LATE_RECORD")
        r["recorded_at"]="2026-01-09T12:00:00+00:00"
        self.assertEqual(outcome(r,h,"2026-01-08T12:00:00+00:00")["status"],"PENDING")

    def test_completed_bar_cutoff_and_weekend_recording(self):
        before=datetime(2026,11,2,10,0,tzinfo=timezone.utc) # 15:30 IST, EOD buffer not elapsed
        after=datetime(2026,11,2,12,0,tzinfo=timezone.utc)
        self.assertEqual(str(completed_cutoff(before)),"2026-11-01")
        self.assertEqual(str(completed_cutoff(after)),"2026-11-02")
        self.assertEqual(str(next_weekday_open("2026-10-30")),"2026-11-02 09:15:00+05:30")

    def test_stale_snapshots_and_context_cannot_start_fresh_market_tests(self):
        now=datetime(2026,11,1,0,0,tzinfo=timezone.utc)
        history=pd.DataFrame(dict(close=[100.]),index=pd.to_datetime(["2026-10-30"]))
        with patch("src.forecasting.market_data.pd.read_csv",return_value=pd.DataFrame({"Date":pd.to_datetime(["2026-10-29"])})):
            self.assertTrue(freshness(history,Path("."),"RELIANCE.NS",now.isoformat(),now)["ready"])
            stale="2026-10-30T00:00:00+00:00"
            self.assertFalse(freshness(history,Path("."),"RELIANCE.NS",stale,now)["ready"])
        with patch("src.forecasting.market_data.pd.read_csv",return_value=pd.DataFrame({"Date":pd.to_datetime(["2026-10-20"])})):
            self.assertFalse(freshness(history,Path("."),"RELIANCE.NS",now.isoformat(),now)["ready"])


if __name__=="__main__": unittest.main()
