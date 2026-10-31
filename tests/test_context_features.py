import tempfile
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
from test_pipeline import history
from src.context_sources import parse_annual_filing
from src.XGBoost.context_features import lagged_join, published_financials, make_context_features
from src.report_reduced import paired_intervals


class ContextTests(unittest.TestCase):
    def test_short_annual_history_has_no_bootstrap_interval(self):
        frame=pd.DataFrame(dict(Date=pd.bdate_range('2025-01-01',periods=100),
                                target=.1,xgboost=.05,price_only=.02))
        result=paired_intervals(frame,252,'price_only')
        self.assertIsNone(result['approximate_mse_difference_ci95'])
    def test_index_observation_is_lagged_and_expires(self):
        source=pd.DataFrame({'Date':pd.to_datetime(['2020-01-03']),'value':[7.]})
        dates=pd.to_datetime(['2020-01-03','2020-01-06','2020-01-13'])
        joined=lagged_join(dates,source)
        self.assertTrue(pd.isna(joined.value.iloc[0]))
        self.assertEqual(joined.value.iloc[1],7.)
        self.assertTrue(pd.isna(joined.value.iloc[2]))

    def test_publication_and_revision_do_not_backfill(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/'facts.csv'
            pd.DataFrame(dict(period_end=['2020-03-31','2020-03-31'],
                              available_at=['2020-05-05T18:00:00+05:30','2020-06-05T18:00:00+05:30'],
                              income=[100.,100.],profit=[10.,20.],net_margin=[.1,.2])).to_csv(path,index=False)
            dates=pd.to_datetime(['2020-05-05','2020-05-06','2020-06-05','2020-06-08','2022-01-01'])
            values=published_financials(dates,path)
            self.assertTrue(pd.isna(values.reported_net_margin.iloc[0]))
            self.assertEqual(values.reported_net_margin.iloc[1],.1)
            self.assertEqual(values.reported_net_margin.iloc[2],.1)
            self.assertEqual(values.reported_net_margin.iloc[3],.2)
            self.assertTrue(pd.isna(values.reported_net_margin.iloc[4]))

    def test_growth_uses_only_prior_published_year(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/'facts.csv'
            pd.DataFrame(dict(period_end=['2019-03-31','2020-03-31'],
                              available_at=['2019-05-01T18:00:00+05:30','2020-05-01T18:00:00+05:30'],
                              income=[100.,120.],profit=[10.,-5.],net_margin=[.1,-5/120])).to_csv(path,index=False)
            values=published_financials(pd.to_datetime(['2020-05-04']),path)
            self.assertAlmostEqual(values.reported_income_growth.iloc[0],40/220)
            self.assertEqual(values.reported_profit_growth.iloc[0],-2.)

    def test_annual_parser_selects_current_period_and_units(self):
        xml=b'''<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:f="urn:finance">
        <context id="annual"><period><startDate>2019-04-01</startDate><endDate>2020-03-31</endDate></period></context>
        <context id="prior"><period><startDate>2018-04-01</startDate><endDate>2019-03-31</endDate></period></context>
        <f:Income contextRef="prior" unitRef="INR">900</f:Income>
        <f:ProfitLossForPeriod contextRef="prior" unitRef="INR">800</f:ProfitLossForPeriod>
        <f:Income contextRef="annual" unitRef="INR">100</f:Income>
        <f:ProfitLossForPeriod contextRef="annual" unitRef="INR">12</f:ProfitLossForPeriod></xbrl>'''
        meta=dict(toDate='31-Mar-2020',period='Annual',broadCastDate='05-May-2020 18:00:00',
                  exchdisstime='05-May-2020 18:01:00',xbrl='https://example.test/fixture.xml')
        facts=parse_annual_filing(xml,meta)
        self.assertEqual(facts['net_margin'],.12)
        self.assertEqual(facts['context'],'annual')
        self.assertFalse(facts['context_inferred_from_annual_template'])
        with self.assertRaises(ValueError):
            parse_annual_filing(xml.replace(b'unitRef="INR">12',b'unitRef="USD">12'),meta)

    def test_context_features_never_see_future(self):
        raw=history()
        raw.index=pd.bdate_range('2016-01-01',periods=len(raw))
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            directory=Path(directory)
            (directory/'indices').mkdir(); (directory/'fundamentals').mkdir()
            prices=pd.DataFrame({'Date':raw.index,'close':raw.close})
            prices.to_csv(directory/'indices'/'market_prices.csv',index=False)
            prices.to_csv(directory/'indices'/'energy_prices.csv',index=False)
            pd.DataFrame({'Date':raw.index,'pe':20.,'pb':3.,'divYield':1.}).to_csv(directory/'indices'/'market_valuation.csv',index=False)
            full,columns=make_context_features(raw,21,'RELIANCE.NS',directory,'market_sector_fundamentals',include_target=False)
            prefix,_=make_context_features(raw.iloc[:700],21,'RELIANCE.NS',directory,'market_sector_fundamentals',include_target=False)
            pd.testing.assert_frame_equal(full.loc[prefix.index,columns],prefix[columns])
            self.assertEqual(prefix.index[-1],raw.index[699])
            self.assertTrue(full.reported_net_margin.isna().all())

if __name__=='__main__': unittest.main()
