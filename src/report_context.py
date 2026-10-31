"""Matched-baseline reporting for market, sector, index valuation and company filings."""
import argparse
import json
from pathlib import Path
import pandas as pd
from src.pipeline import ROOT
from src.report_reduced import paired_intervals


def summarize(directory):
    protocol=json.loads((directory/'protocol.json').read_text())
    manifest=json.loads((ROOT/'data'/'context_v3'/'manifest.json').read_text())
    selected=json.loads((directory/'selected.json').read_text())
    reports={}
    for path in directory.glob('*/h*/report.json'):
        report=json.loads(path.read_text())
        reports[(report['horizon'],report['family'])]=(report,path)
    rows, uncertainty=[],[]
    lines=['# Market, sector and fundamental context experiment','',
           'This is a matched recent-period study on the same 40-stock frozen price snapshot through '
           'October 23, 2026. Training origins start in 2017; the test begins January 2025. '
           'Two purged validation windows are 2021–2022 and 2023–2024. Five companies remain excluded '
           'from all fitting and tuning. These test years and companies were inspected before; this is '
           'exploratory research, not new prospective evidence.','',
           f'Official exchange downloads contain {len(manifest["index_names"])} index-price series, Nifty 50 '
           f'valuation history, and {sum(r["usable_filings"] for r in manifest["fundamentals"])} usable original '
           'audited consolidated annual filings across all 40 companies.','',
           '## Validation-selected models','',
           '| Sessions | Selected family | Unseen direction | Always up | Selected RMSE | Matched price-only RMSE | RMSE reduction vs price-only | Price MAPE |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for h in protocol['horizons']:
        control,control_path=reports[(h,'price_only')]
        control_predictions=pd.read_csv(control_path.parent/'test_predictions.csv',parse_dates=['Date'])
        control_predictions=control_predictions.set_index(['Date','ticker'])
        for family in protocol['families']:
            report,path=reports[(h,family)]
            if report['test_keys_sha256'] != control['test_keys_sha256']:
                raise ValueError('Different test observations')
            predictions=pd.read_csv(path.parent/'test_predictions.csv',parse_dates=['Date'])
            keys=pd.MultiIndex.from_frame(predictions[['Date','ticker']])
            predictions['price_only']=control_predictions.reindex(keys).xgboost.to_numpy()
            if predictions.price_only.isna().any(): raise ValueError('Unmatched baseline predictions')
            for group in ['seen','unseen']:
                metrics=report['metrics'][group]
                baseline=control['metrics'][group]['xgboost']['rmse']
                row=dict(horizon=h,family=family,group=group,features=report['feature_count'],
                         cv_rmse=report['best_trial']['cv_rmse'],direction=metrics['xgboost']['directional_accuracy'],
                         always_up=metrics['always_up_direction'],rmse=metrics['xgboost']['rmse'],
                         matched_price_only_rmse=baseline,rmse_reduction=1-metrics['xgboost']['rmse']/baseline,
                         historical_mean_rmse=metrics['historical_mean']['rmse'],
                         zero_rmse=metrics['zero_return']['rmse'],price_mape=metrics['xgboost']['price_mape'],
                         positive_fraction=metrics['positive_prediction_fraction'],rows=metrics['rows'])
                rows.append(row)
                if family!='price_only':
                    intervals=paired_intervals(predictions.loc[predictions.group==group],h,'price_only')
                    uncertainty.append(dict(horizon=h,family=family,group=group,**intervals))
            if family==selected[str(h)]['family']:
                m=report['metrics']['unseen']; b=control['metrics']['unseen']['xgboost']['rmse']
                lines.append(f'| {h} | {family} | {m["xgboost"]["directional_accuracy"]:.2%} | {m["always_up_direction"]:.2%} | '
                             f'{m["xgboost"]["rmse"]:.6f} | {b:.6f} | {1-m["xgboost"]["rmse"]/b:+.2%} | {m["xgboost"]["price_mape"]:.2%} |')
    lines += ['', '## Interpretation of this run','',
              'Daily validation preferred the price-only control. The validation-selected monthly '
              'fundamental/context bundle reduced unseen-stock RMSE by about 0.25% versus the matched '
              'control, but its paired uncertainty interval includes no improvement. The selected annual '
              'bundle increased unseen-stock RMSE by about 17.38%. All of its annual predictions were '
              'positive, and its 89.39% direction score equals the always-up baseline. These inputs did '
              'not establish a dependable incremental forecasting edge in this experiment.','',
              'The market-only monthly model happened to have a larger test RMSE reduction (about '
              '0.77%), but did not win validation. Selecting it after inspecting that test result would '
              'be hindsight selection. No annual confidence interval is reported because the test '
              'contains only 196 unique annual-origin dates, fewer than the 252-session horizon.','',
              'Fifteen automated tests passed. All fifteen saved models reproduced every recorded '
              'test prediction and passed native reload, inverse scaling, held-out company exclusion, '
              'common-sample, purged-label-boundary and latest-row inference checks. Input hashes '
              'remained unchanged during the run. See verification.json.','',
              'Positive RMSE reduction means improvement. Selection is based on validation macro-stock '
              'RMSE, never the highest test direction percentage. Price MAPE is percentage error, not accuracy. '
              'The baseline is retrained on the same recent-period data and search budget; do not compare '
              'these percentages directly with the earlier 2021-start experiment.','',
              '## All predefined ablations on unseen companies','',
              '| Sessions | Family | Features | Validation RMSE | Unseen direction | Unseen RMSE | Reduction vs matched control |',
              '|---|---|---:|---:|---:|---:|---:|']
    for row in sorted([r for r in rows if r['group']=='unseen'],key=lambda r:(r['horizon'],r['cv_rmse'])):
        lines.append(f'| {row["horizon"]} | {row["family"]} | {row["features"]} | {row["cv_rmse"]:.6f} | '
                     f'{row["direction"]:.2%} | {row["rmse"]:.6f} | {row["rmse_reduction"]:+.2%} |')
    lines += ['', '## Inputs tested','',
              '- Price-only control: the previously selected 5-feature core for daily forecasts, original 18 features for monthly/annual forecasts.',
              '- Market: lagged Nifty returns and volatility, plus stock momentum relative to the market (7 additional features).',
              '- Market and sector: a declared economic sector-proxy index and relative momentum (5 additional features). These are broad static proxies, not claims of historical constituent membership.',
              '- Index valuation: dated Nifty 50 earnings yield (1/P/E), book yield (1/P/B), and dividend yield (3 additional features). These describe the index, not individual company P/E.',
              '- Company fundamentals: reported annual consolidated net profit/income, symmetric year-over-year income and profit growth from previously published annual filings, and publication age (4 additional features).','',
              'Market/sector observations and dated valuation figures are made usable on the next calendar '
              'day and joined backward to stock sessions. Corporate facts are joined only after their actual '
              'publication day; later revisions are not backfilled. Missing inputs remain missing and '
              'financial observations expire after 550 days. Growth is computed only when a prior annual '
              'period was already published; missing years are not treated as zero growth.','',
              '## Data and interpretation limits','',
              'Individual stock P/E and EPS yield were deliberately not constructed: the historical EPS '
              'and vendor-adjusted share bases have not been verified. The company fundamental test uses '
              'scale-independent income/profit ratios instead. It does not establish whether correctly '
              'constructed company P/E helps.','',
              'Older exchange XBRL files sometimes omit base context definitions. The parser accepts '
              'the recognized FourD annual/YTD template only for annual metadata, records that inference, '
              'and otherwise requires explicit annual dates. Financial tag names and bank formats differ; '
              'the exact accepted tags and source URLs are saved. This is a research extraction, not a '
              'fully reconciled financial database. Source revisions, taxonomy changes, and index valuation '
              'methodology changes remain risks. No current EPS or current P/E was copied into old dates.','',
              'The post-2025 integrated-filing feed was included. Four companies still lack successfully '
              'parsed post-2024 annual filings: BAJAJFINSV, HEROMOTOCO, POWERGRID, TATASTEEL. Their stale '
              'inputs become missing; coverage.json quantifies the actual model input coverage.','',
              'Paired moving date-block intervals in uncertainty.json compare every added-information '
              'family with the matched price-only model, preserving cross-stock dependence. They are '
              'approximate, do not account fully for repeated experimentation, and are particularly weak '
              'for annual forecasts: the available 2025 annual origins cover less than one independent '
              'annual market period, so no annual uncertainty interval is reported. Neither a high annual direction percentage nor a favorable point '
              'estimate demonstrates a real-market trading edge.','',
              'This study fits 360 validation models and 15 final evaluation models. It does not place '
              'trades, refit for live deployment, or implement Monte Carlo. A future prospective evaluation '
              'and an execution-cost study remain necessary before real-money use.','',
              'Sources: [Nifty historical prices and valuations](https://www.niftyindices.com/reports/historical-data), '
              '[NSE financial results](https://www.nseindia.com/companies-listing/corporate-filings-financial-results), '
              '[NSE integrated financial filings](https://www.nseindia.com/companies-listing/corporate-integrated-filing), '
              '[NSE index P/E methodology](https://www.nseindia.com/static/products-services/indices-price-earnings-ratio).']
    pd.DataFrame(rows).to_csv(directory/'comparison.csv',index=False)
    (directory/'uncertainty.json').write_text(json.dumps(uncertainty,indent=2))
    (ROOT/'RESULTS_CONTEXT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'artifacts'/'context_v3')
    summarize(parser.parse_args().directory)
