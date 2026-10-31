"""Matched recent-period ablations for new market, sector and published financial information."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pandas as pd
from src.pipeline import ROOT
from src.fetch_research_data import NEW_HOLDOUTS
from src.helper.load_data import load_data
from src.research_v2 import evaluate_family, candidates
from src.XGBoost.context_features import make_context_features, FAMILIES, COMPANY, VALUATION
from src.context_sources import SECTOR_FOR


def prepare(args,horizon):
    frames,sources=[],[]
    for path in sorted(args.data_dir.glob('*.csv')):
        ticker=path.stem.split('_')[0]
        history=load_data(path)
        frame,columns=make_context_features(history,horizon,ticker,args.context_dir,'market_sector_fundamentals')
        frame['ticker']=ticker
        frames.append(frame)
        sources.append(dict(ticker=ticker,price_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            usable_rows=len(frame),financial_coverage={c:float(frame[c].notna().mean()) for c in COMPANY},
                            valuation_coverage={c:float(frame[c].notna().mean()) for c in VALUATION}))
    return pd.concat(frames).sort_index(),columns,sources


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data'/'research_v2')
    parser.add_argument('--context-dir',type=Path,default=ROOT/'data'/'context_v3')
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts'/'context_v3')
    parser.add_argument('--trials',type=int,default=12)
    parser.add_argument('--horizons',type=int,nargs='+',default=[1,21,252])
    args=parser.parse_args()
    if args.trials<1 or any(h<1 for h in args.horizons): parser.error('Trials and horizons must be positive')
    tickers={p.stem.split('_')[0] for p in args.data_dir.glob('*.csv')}
    if tickers-set(SECTOR_FOR):
        raise ValueError(f'Missing sector proxies: {sorted(tickers-set(SECTOR_FOR))}')
    args.output.mkdir(parents=True,exist_ok=True)
    protocol_path=args.output/'protocol.json'
    if protocol_path.exists(): raise ValueError('Select a new experiment output directory')
    context_hashes={str(p.relative_to(args.context_dir)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for sub in ['indices','fundamentals'] for p in sorted((args.context_dir/sub).glob('*.csv'))}
    protocol=dict(training_start='2017-01-01',test_start='2025-01-01',
                  validation_edges=['2021-01-01','2023-01-01','2025-01-01'],families=FAMILIES,
                  horizons=args.horizons,trials=args.trials,candidates=candidates(args.trials),
                  held_out_tickers=NEW_HOLDOUTS,context_hashes=context_hashes,
                  selection='Lowest mean macro-stock validation RMSE over two purged chronological folds',
                  caveats=['Reused test years and companies, not fresh prospective evidence',
                           'Annual test origins cover less than one independent annual period',
                           'Use matched price-only control; not directly comparable to v2 period metrics',
                           'Static sector proxies; index historical figures and financial archives may be revised',
                           'Individual company P/E not tested: EPS/share basis remains unverified'])
    protocol_path.write_text(json.dumps(protocol,indent=2))
    reports=[]
    for h in args.horizons:
        data,all_columns,sources=prepare(args,h)
        for family in FAMILIES:
            # Recreate only the column selection, using the common complete panel and source snapshot.
            probe_path=next(args.data_dir.glob('RELIANCE.NS_*.csv'))
            _,columns=make_context_features(load_data(probe_path),h,'RELIANCE.NS',args.context_dir,family)
            config=SimpleNamespace(data_dir=args.data_dir,context_dir=args.context_dir,output=args.output,
                trials=args.trials,test_start='2025-01-01',holdout_tickers=NEW_HOLDOUTS,
                feature_builder='context_v3',fundamentals_dir=None)
            reports.append(evaluate_family(config,h,family,prepared=(data,columns,sources),fold_edges=protocol['validation_edges']))
    selected={}
    for h in args.horizons:
        options=[r for r in reports if r['horizon']==h]
        if len({r['test_keys_sha256'] for r in options})!=1: raise ValueError('Unmatched samples')
        winner=min(options,key=lambda r:r['best_trial']['cv_rmse'])
        selected[str(h)]=dict(family=winner['family'],cv_rmse=winner['best_trial']['cv_rmse'],
                             model_path=str(args.output/winner['family']/f'h{h}'/'model.joblib'))
    (args.output/'selected.json').write_text(json.dumps(selected,indent=2))
    print(json.dumps(selected,indent=2),flush=True)

if __name__=='__main__': main()
