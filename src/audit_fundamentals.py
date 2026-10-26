"""Record current Yahoo financial coverage; never convert snapshots into historical features."""
from datetime import datetime, timezone
import json
from pathlib import Path
import yfinance as yf
from src.pipeline import ROOT


def main():
    ticker = yf.Ticker('RELIANCE.NS')
    audit = dict(ticker='RELIANCE.NS', retrieved_at=datetime.now(timezone.utc).isoformat(),
                 purpose='Coverage audit only; no snapshot values enter training')
    for frequency in ['quarterly', 'yearly']:
        try:
            statement = ticker.get_income_stmt(freq=frequency)
            audit[frequency] = dict(periods=[str(c) for c in statement.columns], rows=len(statement),
                                    has_diluted_eps='DilutedEPS' in statement.index,
                                    limitation='Statement period columns are not historical as-published release timestamps')
        except Exception as exc:
            audit[frequency] = dict(error=str(exc))
    audit['decision'] = 'Do not backfill current P/E or current/restated EPS into past training rows. Acquire historical publications first.'
    path = ROOT/'data'/'research_v2'/'fundamental_coverage_audit.json'
    path.write_text(json.dumps(audit, indent=2))
    print(json.dumps(audit, indent=2))

if __name__ == '__main__':
    main()
