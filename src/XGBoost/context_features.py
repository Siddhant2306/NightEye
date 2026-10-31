"""Causal, previous-session market/sector context and published annual financial ratios."""
from pathlib import Path
import numpy as np
import pandas as pd
from src.context_sources import SECTOR_FOR
from src.XGBoost.reduced_features import make_reduced_features

MARKET = ['market_return_1','market_return_21','market_return_63','market_std_21','market_std_63',
          'relative_market_21','relative_market_63']
SECTOR = ['sector_return_21','sector_return_63','sector_std_63','relative_sector_21','relative_sector_63']
VALUATION = ['market_earnings_yield','market_book_yield','market_dividend_yield']
COMPANY = ['reported_net_margin','reported_income_growth','reported_profit_growth','financial_age_days']
FAMILIES = ['price_only','market','market_sector','market_sector_valuation','market_sector_fundamentals']


def lagged_join(index, source, date_column='Date', max_age=7):
    """Make a daily published observation available on the next calendar day, then as-of join.

    A Friday publication can first be used at the next Monday stock session. This never
    backfills future observations and does not assume that today's final EOD data were
    available for a trade at today's close.
    """
    source=source.copy().sort_values(date_column)
    source['source_date']=pd.to_datetime(source[date_column])
    source['eligible_date']=source.source_date+pd.Timedelta(days=1)
    source=source.drop(columns=[date_column])
    if source.eligible_date.duplicated().any():
        raise ValueError('Duplicate context observation dates')
    left=pd.DataFrame({'decision_date':index})
    joined=pd.merge_asof(left,source.sort_values('eligible_date'),left_on='decision_date',right_on='eligible_date',direction='backward')
    age=(joined.decision_date-joined.source_date).dt.days
    columns=[c for c in source if c not in ['source_date','eligible_date']]
    joined.loc[age>max_age,columns]=np.nan
    joined.index=index
    return joined[columns]


def index_signals(path, prefix):
    prices=pd.read_csv(path,parse_dates=['Date']).set_index('Date').sort_index()
    if prices.index.has_duplicates or (prices.close<=0).any():
        raise ValueError(f'Invalid index history {path}')
    result=pd.DataFrame(index=prices.index)
    daily=np.log(prices.close).diff()
    windows=[1,21,63] if prefix=='market' else [21,63]
    for window in windows:
        result[f'{prefix}_return_{window}']=np.log(prices.close/prices.close.shift(window))
    for window in ([21,63] if prefix=='market' else [63]):
        result[f'{prefix}_std_{window}']=daily.rolling(window).std()
    return result.reset_index()


def published_financials(index, path):
    empty=pd.DataFrame(np.nan,index=index,columns=COMPANY)
    if not Path(path).exists(): return empty
    facts=pd.read_csv(path)
    facts['release']=pd.to_datetime(facts.available_at,utc=True).dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
    facts['period_end']=pd.to_datetime(facts.period_end)
    if (facts.release<facts.period_end).any() or facts.release.duplicated().any():
        raise ValueError('Invalid financial publication timestamps')
    facts=facts.sort_values('release')
    income_growth, profit_growth=[],[]
    for _, row in facts.iterrows():
        previous=facts.loc[(facts.release<row.release) & ((row.period_end-facts.period_end).dt.days.between(350,380))]
        if previous.empty:
            income_growth.append(np.nan); profit_growth.append(np.nan)
        else:
            previous=previous.iloc[-1]
            # Bounded symmetric growth handles profits that change sign without division explosions.
            income_growth.append(2*(row.income-previous.income)/(abs(row.income)+abs(previous.income)) if abs(row.income)+abs(previous.income)>0 else np.nan)
            profit_growth.append(2*(row.profit-previous.profit)/(abs(row.profit)+abs(previous.profit)) if abs(row.profit)+abs(previous.profit)>0 else np.nan)
    facts['reported_net_margin']=facts.net_margin
    facts['reported_income_growth']=income_growth
    facts['reported_profit_growth']=profit_growth
    facts['eligible_date']=facts.release.dt.normalize()+pd.Timedelta(days=1)
    facts=facts.sort_values('release').drop_duplicates('eligible_date',keep='last')
    joined=pd.merge_asof(pd.DataFrame({'decision_date':index}),facts[['eligible_date','release']+COMPANY[:3]].sort_values('eligible_date'),
                         left_on='decision_date',right_on='eligible_date',direction='backward')
    joined['financial_age_days']=(joined.decision_date-joined.release.dt.normalize()).dt.days
    joined.loc[joined.financial_age_days>550,COMPANY]=np.nan
    joined.index=index
    return joined[COMPANY]


def make_context_features(history,horizon,ticker,context_dir,family,include_target=True):
    if family not in FAMILIES: raise ValueError(f'Unknown context family {family}')
    context_dir=Path(context_dir)
    if ticker not in SECTOR_FOR: raise ValueError(f'No predeclared sector proxy for {ticker}')
    base='core' if horizon==1 else 'original'
    frame, columns=make_reduced_features(history,horizon,base,include_target=include_target)
    # This sample constraint is common to every family, including the price-only control.
    market=lagged_join(frame.index,index_signals(context_dir/'indices'/'market_prices.csv','market'))
    sector_key=SECTOR_FOR[ticker]
    sector=lagged_join(frame.index,index_signals(context_dir/'indices'/f'{sector_key}_prices.csv','sector'))
    frame=frame.join(market).join(sector)
    for window in [21,63]:
        previous_stock=np.log(history.close/history.close.shift(window)).shift(1).reindex(frame.index)
        frame[f'relative_market_{window}']=previous_stock-frame[f'market_return_{window}']
        frame[f'relative_sector_{window}']=previous_stock-frame[f'sector_return_{window}']
    values=pd.read_csv(context_dir/'indices'/'market_valuation.csv',parse_dates=['Date'])
    values['market_earnings_yield']=1/values.pe.where(values.pe>0)
    values['market_book_yield']=1/values.pb.where(values.pb>0)
    values['market_dividend_yield']=values.divYield/100
    frame=frame.join(lagged_join(frame.index,values[['Date']+VALUATION]))
    frame=frame.join(published_financials(frame.index,context_dir/'fundamentals'/f'{ticker}.csv'))
    frame=frame.loc[frame.index>=pd.Timestamp('2017-01-01')].replace([np.inf,-np.inf],np.nan)
    # No zero substitution for missing valuation or corporate disclosures. XGBoost handles missing inputs.
    frame=frame.dropna(subset=MARKET+SECTOR)
    additions={
        'price_only':[], 'market':MARKET, 'market_sector':MARKET+SECTOR,
        'market_sector_valuation':MARKET+SECTOR+VALUATION,
        'market_sector_fundamentals':MARKET+SECTOR+VALUATION+COMPANY,
    }
    return frame, columns+additions[family]
