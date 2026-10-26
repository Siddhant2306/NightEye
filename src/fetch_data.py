"""Download adjusted daily OHLCV; failures are recorded and never silently ignored."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf

DEFAULT_TICKERS = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'SBIN.NS', 'ITC.NS', 'LT.NS', 'HINDUNILVR.NS', 'MARUTI.NS', 'SUNPHARMA.NS', 'TATASTEEL.NS', 'BHARTIARTL.NS', 'WIPRO.NS', 'AXISBANK.NS']
DATA_DIR = Path(__file__).resolve().parents[1] / 'data'

def fetch_data(ticker, start_date, end_date, output_dir=DATA_DIR):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    data = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True,
                       actions=False, progress=False, threads=False)
    if data.empty:
        raise RuntimeError(f'No data returned for {ticker}')
    if getattr(data.columns, 'nlevels', 1) > 1:
        data.columns = data.columns.get_level_values(0)
    data = data[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    data.index.name = 'Date'
    incomplete_rows = int(data.isna().any(axis=1).sum())
    path = directory / f'{ticker}_{start_date}_to_{end_date}.csv'
    data.to_csv(path)
    return dict(ticker=ticker, rows=len(data), incomplete_rows=incomplete_rows, file=str(path), auto_adjust=True,
                start=str(data.index.min()), end=str(data.index.max()))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tickers', nargs='+', default=DEFAULT_TICKERS)
    parser.add_argument('--start', default='2000-01-01')
    parser.add_argument('--end', default='2026-10-27', help='Exclusive end date')
    parser.add_argument('--output-dir', default=str(DATA_DIR))
    args = parser.parse_args()
    records = []
    for ticker in args.tickers:
        try:
            record = fetch_data(ticker, args.start, args.end, args.output_dir)
        except Exception as exc:
            record = dict(ticker=ticker, error=str(exc))
        records.append(record)
        print(record, flush=True)
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    manifest = dict(provider='Yahoo Finance via yfinance', downloaded_at=datetime.now(timezone.utc).isoformat(), records=records)
    (Path(args.output_dir)/'download_manifest.json').write_text(json.dumps(manifest, indent=2))
    if any('error' in r for r in records):
        raise SystemExit('Some downloads failed; see download_manifest.json')

if __name__ == '__main__':
    main()
