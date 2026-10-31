"""Frozen exchange-sourced market, sector and as-published company financial inputs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import requests
from src.pipeline import ROOT

CONTEXT_DIR = ROOT/'data'/'context_v3'
SECTORS = {
    'bank': ['HDFCBANK','ICICIBANK','SBIN','AXISBANK','INDUSINDBK'],
    'financial': ['BAJFINANCE','BAJAJFINSV'],
    'it': ['TCS','INFY','WIPRO','HCLTECH','TECHM'],
    'fmcg': ['ITC','HINDUNILVR','BRITANNIA','DABUR'],
    'auto': ['MARUTI','EICHERMOT','HEROMOTOCO'],
    'pharma': ['SUNPHARMA','CIPLA','DRREDDY'],
    'metal': ['TATASTEEL','JSWSTEEL','HINDALCO'],
    'energy': ['RELIANCE','NTPC','COALINDIA','POWERGRID','ONGC','BPCL','GAIL'],
    'infra': ['LT','BHARTIARTL'],
    'materials': ['ULTRACEMCO','GRASIM','SHREECEM'],
    'consumer': ['TITAN','ASIANPAINT','PIDILITIND'],
}
SECTOR_FOR = {symbol+'.NS':sector for sector, names in SECTORS.items() for symbol in names}
INDEX_NAMES = dict(market='NIFTY 50', bank='NIFTY BANK', financial='NIFTY FINANCIAL SERVICES',
                   it='NIFTY IT', fmcg='NIFTY FMCG', auto='NIFTY AUTO', pharma='NIFTY PHARMA',
                   metal='NIFTY METAL', energy='NIFTY ENERGY', infra='NIFTY INFRASTRUCTURE', materials='NIFTY COMMODITIES',
                   consumer='NIFTY INDIA CONSUMPTION')


def local(tag):
    return tag.split('}')[-1]


def parse_annual_filing(content, metadata):
    """Extract same-period ratios, not P/E, from the original published annual filing.

    Older NSE/BSE annual templates use FourD for current annual/YTD facts and sometimes
    omit that context definition. Accept that documented template only for Annual
    records; otherwise require an explicit matching 300–380 day context. Never read
    comparative-period facts backward into prior prediction dates.
    """
    root = ET.fromstring(content)
    end = pd.to_datetime(metadata['toDate'], format='%d-%b-%Y')
    contexts = []
    for element in root.iter():
        if local(element.tag) != 'context':
            continue
        fields = {local(e.tag):e.text for e in element.iter() if local(e.tag) in ['startDate','endDate']}
        members = [e for e in element.iter() if local(e.tag) in ['explicitMember','typedMember']]
        if any('Segment' in (e.text or '') or 'Segment' in str(e.attrib) or 'Expenses' in str(e.attrib) for e in members):
            continue
        if 'startDate' in fields and 'endDate' in fields:
            start, stop = pd.Timestamp(fields['startDate']), pd.Timestamp(fields['endDate'])
            if stop == end and 300 <= (stop-start).days <= 380:
                contexts.append(element.attrib['id'])
    context_ids = contexts or (['FourD'] if metadata.get('period') == 'Annual' else [])
    if not context_ids:
        raise ValueError('No current annual context')
    profit_names = ['ProfitLossForPeriod','ProfitLossForThePeriod','NetProfitLossForThePeriod','NetProfitLossForPeriod','ProfitAfterTax']
    income_names = ['Income','TotalIncome','TotalIncomeFromOperations','RevenueFromOperations','Revenue']
    for context_id in context_ids:
        values = {}
        for element in root.iter():
            if element.attrib.get('contextRef') != context_id or len(element):
                continue
            name = local(element.tag)
            if name not in profit_names+income_names:
                continue
            try:
                number = float((element.text or '').replace(',',''))
                if np.isfinite(number):
                    values[name] = (number, element.attrib.get('unitRef'))
            except ValueError:
                continue
        income = next(((name, values[name]) for name in income_names if name in values and values[name][0]>0), None)
        profit = next(((name, values[name]) for name in profit_names if name in values), None)
        if income and profit and income[1][1] == profit[1][1] and 'INR' in (income[1][1] or '').upper():
            publication = []
            for field in ['broadCastDate','exchdisstime','filingDate']:
                if metadata.get(field):
                    try:
                        publication.append(pd.to_datetime(metadata[field], dayfirst=True))
                    except ValueError:
                        pass
            if not publication:
                raise ValueError('No publication time')
            available = max(publication).tz_localize('Asia/Kolkata')
            if available.tz_localize(None) < end:
                raise ValueError('Publication precedes period end')
            return dict(period_end=str(end.date()), available_at=available.isoformat(),
                        income=income[1][0], profit=profit[1][0], net_margin=profit[1][0]/income[1][0],
                        income_tag=income[0], profit_tag=profit[0], context=context_id,
                        context_inferred_from_annual_template=not bool(contexts), source=metadata['xbrl'],
                        currency='INR', consolidation='Consolidated')
    raise ValueError('Compatible current-period income/profit facts not found')


class ExchangeClient:
    def __init__(self, directory):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({'User-Agent':'Mozilla/5.0', 'Referer':'https://www.niftyindices.com/reports/historical-data'})
        self.requests = []

    def get(self, name, url, payload=None):
        destination=self.directory/name
        if destination.exists():
            data=destination.read_bytes()
            self.requests.append(dict(file=name,url=url,cached=True,sha256=hashlib.sha256(data).hexdigest()))
            return data
        response = self.session.post(url,json=payload,timeout=30) if payload else self.session.get(url,timeout=30)
        record=dict(file=name,url=url,status=response.status_code,request=payload)
        self.requests.append(record)
        response.raise_for_status()
        destination.write_bytes(response.content)
        record['sha256']=hashlib.sha256(response.content).hexdigest()
        return response.content


def download_indices(client):
    target = CONTEXT_DIR/'indices'
    target.mkdir(exist_ok=True)
    audit=[]
    for key, name in INDEX_NAMES.items():
        for kind in (['prices','valuation'] if key=='market' else ['prices']):
            pieces=[]
            for year in range(2016,2027):
                end=f'31-Dec-{year}' if year<2026 else '23-Oct-2026'
                data = "{'name':'%s','startDate':'01-Jan-%s','endDate':'%s','indexName':'%s'}" % (name,year,end,name)
                endpoint='getHistoricaldatatabletoString' if kind=='prices' else 'getpepbHistoricaldataDBtoString'
                try:
                    content=client.get(f'{key}_{kind}_{year}.json','https://www.niftyindices.com/BackPage/'+endpoint,{'cinfo':data})
                    payload=json.loads(content)
                    if isinstance(payload,dict) and 'd' in payload:
                        payload=json.loads(payload['d']) if isinstance(payload['d'],str) else payload['d']
                    if not isinstance(payload,list) or not payload:
                        raise ValueError('No historical rows')
                    pieces.append(pd.DataFrame(payload))
                except Exception as exc:
                    audit.append(dict(index=key,kind=kind,year=year,error=str(exc)))
            if not pieces:
                continue
            frame=pd.concat(pieces,ignore_index=True)
            if kind=='prices':
                frame['Date']=pd.to_datetime(frame.HistoricalDate,format='%d %b %Y')
                frame['close']=pd.to_numeric(frame.CLOSE,errors='coerce')
                frame=frame[['Date','close']]
            else:
                frame['Date']=pd.to_datetime(frame.DATE,format='%d %b %Y')
                for col in ['pe','pb','divYield']:
                    frame[col]=pd.to_numeric(frame[col],errors='coerce')
                frame=frame[['Date','pe','pb','divYield']]
            frame=frame.sort_values('Date').drop_duplicates('Date').set_index('Date')
            if kind=='prices': frame=frame.loc[frame.close>0]
            frame.to_csv(target/f'{key}_{kind}.csv')
            record=dict(index=key,name=name,kind=kind,rows=len(frame),start=str(frame.index.min().date()),end=str(frame.index.max().date()))
            audit.append(record)
            print(record,flush=True)
    return audit


def download_fundamentals(client):
    target=CONTEXT_DIR/'fundamentals'
    target.mkdir(exist_ok=True)
    audit=[]
    for path in sorted((ROOT/'data'/'research_v2').glob('*.csv')):
        ticker=path.stem.split('_')[0]
        symbol=ticker.removesuffix('.NS')
        url=('https://www.nseindia.com/api/corporates-financial-results?index=equities&symbol='+symbol+
             '&period=Annual&from_date=01-01-2016&to_date=27-10-2026')
        good, errors=[],[]
        try:
            records=json.loads(client.get(f'{symbol}_annual_metadata.json',url))
            if not isinstance(records,list): raise ValueError('Expected a financial-results list')
            integrated_url=('https://www.nseindia.com/api/integrated-filing-results?index=equities&symbol='+symbol+
                            '&type=Integrated%20Filing-%20Financials&from_date=01-01-2025&to_date=27-10-2026&page=1&size=100')
            try:
                integrated=json.loads(client.get(f'{symbol}_integrated_metadata.json',integrated_url))
                if integrated.get('totalCount',0)>100:
                    raise ValueError('Integrated filing response exceeds one page; explicit pagination required')
                for item in integrated.get('data',[]):
                    if '-MAR-' not in str(item.get('qe_Date','')).upper() or item.get('audited')!='Audited':
                        continue
                    records.append(dict(toDate=item['qe_Date'],period='Annual',consolidated=item.get('consolidated'),
                                        broadCastDate=item.get('broadcast_Date'),exchdisstime=item.get('creation_Date'),
                                        filingDate=item.get('revised_Date'),xbrl=item.get('xbrl'),seqNumber='integrated_'+item['seq_Id']))
            except Exception as exc:
                errors.append(dict(source=integrated_url,error=str(exc)))
            for record in records:
                link=record.get('xbrl') or ''
                if record.get('consolidated')!='Consolidated' or not link.lower().endswith('.xml'):
                    continue
                try:
                    content=client.get(f'{symbol}_{record["seqNumber"]}.xml',link)
                    good.append(parse_annual_filing(content,record))
                except Exception as exc:
                    errors.append(dict(source=link,error=str(exc)))
            frame=pd.DataFrame(good)
            if not frame.empty:
                frame=frame.sort_values('available_at').drop_duplicates('available_at',keep='last')
                frame.to_csv(target/f'{ticker}.csv',index=False)
            item=dict(ticker=ticker,metadata_records=len(records),usable_filings=len(frame),errors=errors,
                      first_release=str(frame.available_at.min()) if len(frame) else None,
                      last_release=str(frame.available_at.max()) if len(frame) else None)
        except Exception as exc:
            item=dict(ticker=ticker,usable_filings=0,error=str(exc))
        audit.append(item)
        print({k:v for k,v in item.items() if k!='errors'},flush=True)
    return audit


def main():
    client=ExchangeClient(CONTEXT_DIR/'raw')
    try:
        indices=download_indices(client)
        facts=download_fundamentals(client)
        manifest=dict(retrieved_at=datetime.now(timezone.utc).isoformat(),indices=indices,fundamentals=facts,
                      sector_proxy_map=SECTOR_FOR,index_names=INDEX_NAMES,
                      valuation_scope='NIFTY 50 index P/E, P/B and dividend yield; not company P/E',
                      caveats=['Static economic sector proxies, not historical index membership',
                               'Historical snapshots may be revised; not a vendor point-in-time archive',
                               'Only successfully parsed audited consolidated annual filings are used; missing records remain missing',
                               'No per-share valuation from corporate EPS: split/share basis is not verified'])
        (CONTEXT_DIR/'manifest.json').write_text(json.dumps(manifest,indent=2))
    finally:
        (CONTEXT_DIR/'request_audit.json').write_text(json.dumps(client.requests,indent=2))

if __name__=='__main__': main()
