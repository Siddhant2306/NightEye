"""Freeze a larger OHLCV and dividend snapshot for the reduced-feature experiment."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import warnings
import pandas as pd
import yfinance as yf
from src.fetch_data import DEFAULT_TICKERS

UNIVERSE = DEFAULT_TICKERS + [
    'ASIANPAINT.NS', 'BAJFINANCE.NS', 'NTPC.NS', 'TITAN.NS', 'COALINDIA.NS',
    'BAJAJFINSV.NS', 'POWERGRID.NS', 'ONGC.NS', 'JSWSTEEL.NS', 'HCLTECH.NS',
    'TECHM.NS', 'ULTRACEMCO.NS', 'GRASIM.NS', 'CIPLA.NS', 'DRREDDY.NS',
    'EICHERMOT.NS', 'HEROMOTOCO.NS', 'BPCL.NS', 'INDUSINDBK.NS', 'HINDALCO.NS',
    'BRITANNIA.NS', 'DABUR.NS', 'GAIL.NS', 'PIDILITIND.NS', 'SHREECEM.NS']
NEW_HOLDOUTS = ['ASIANPAINT.NS', 'BAJFINANCE.NS', 'NTPC.NS', 'TITAN.NS', 'COALINDIA.NS']
ROOT = Path(__file__).resolve().parents[1]


def fetch(ticker, directory, start, end):
    destination = directory / f'{ticker}_{start}_to_{end}.csv'
    if destination.exists():
        raise FileExistsError(f'Refusing to overwrite frozen snapshot {destination}')
    raw = yf.download(ticker, start=start, end=end, auto_adjust=False,
                      actions=True, progress=False, threads=False)
    if raw.empty:
        raise ValueError(f'No data for {ticker}')
    if raw.columns.nlevels > 1:
        raw.columns = raw.columns.get_level_values(0)
    needed = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume', 'Dividends']
    if not set(needed).issubset(raw.columns):
        raise ValueError(f'Missing price/action columns for {ticker}: {raw.columns.tolist()}')
    raw = raw.sort_index()
    invalid = raw[needed].isna().any(axis=1)
    clean = raw.loc[~invalid].copy()
    if clean.empty:
        raise ValueError(f'No complete rows for {ticker}')
    # Keep adjusted OHLC as the prediction series; calculate yield using raw close and cash dividends.
    factor = clean['Adj Close'] / clean.Close
    prices = clean[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    prices[['Open', 'High', 'Low', 'Close']] = prices[['Open', 'High', 'Low', 'Close']].mul(factor, axis=0)
    prices.index.name = 'Date'
    prices.to_csv(destination)
    actions = pd.DataFrame({'raw_close': clean.Close, 'dividend': clean.Dividends}, index=clean.index)
    actions.index.name = 'Date'
    action_path = directory/'actions'/f'{ticker}.csv'
    actions.to_csv(action_path)
    return dict(ticker=ticker, rows=len(prices), start=str(prices.index.min()), end=str(prices.index.max()),
                incomplete_rows_removed=int(invalid.sum()), dividend_events=int((actions.dividend>0).sum()),
                prices_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                actions_sha256=hashlib.sha256(action_path.read_bytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'data'/'research_v2')
    parser.add_argument('--start', default='2000-01-01')
    parser.add_argument('--end', default='2026-10-27')
    parser.add_argument('--tickers', nargs='+', default=UNIVERSE)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir/'actions').mkdir(exist_ok=True)
    records = []
    for ticker in args.tickers:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                record = fetch(ticker, args.output_dir, args.start, args.end)
        except Exception as exc:
            record = dict(ticker=ticker, error=str(exc))
        records.append(record)
        print(record, flush=True)
    manifest = dict(provider='Yahoo Finance via yfinance', retrieved_at=datetime.now(timezone.utc).isoformat(),
                    raw_prices_split_adjusted_by_provider=True, adjusted_ohlc=True,
                    dividend_event_convention='ex-date, observed cash only; not announcement forecasts',
                    holdout_tickers=NEW_HOLDOUTS, records=records)
    (args.output_dir/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    if any('error' in r for r in records):
        raise SystemExit('Downloads incomplete; see manifest.json')

if __name__ == '__main__':
    main()
