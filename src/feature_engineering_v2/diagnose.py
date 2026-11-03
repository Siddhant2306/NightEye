"""Read-only failure diagnosis; no model/feature search or benchmark rewriting."""
import argparse
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.feature_engineering_v2.prepare import DEFAULT,check_protected
from src.feature_engineering_v2.inference import task_frame
from src.feature_engineering_v2.models import predict
from src.feature_engineering_v2.calibration import guarded_calibrate,losses
from src.forecasting.protocol import window
from src.forecasting.models import logit
from src.forecasting.train import save_json
from src.feature_engineering_v2.conclusions import table


def finish_review(root,output):
    scores=pd.read_csv(output/'error_decomposition.csv');all_scores=scores.loc[scores.group=='all']
    gates=json.loads((output/'pretest_calibration_gate.json').read_text());comparison=[]
    for _,row in all_scores.iterrows():
        h=int(row.horizon);a=row.algorithm
        frame=pd.read_csv(root/f'h{h}'/a/'test_predictions.csv')
        accepted=gates[f'{a}_h{h}']['accepted']
        # Accepted guard refits the same logistic calibration on the same full
        # calibration block, so existing adjusted predictions reproduce it.
        p=frame.probability_up if accepted else frame.raw_probability
        comparison.append(dict(algorithm=a,horizon=h,guard_accepted=accepted,
            raw_brier=row.raw_brier,old_calibrated_brier=row.calibrated_brier,
            guarded_brier=losses(frame.target,p)['brier']))
    result=pd.DataFrame(comparison);result.to_csv(output/'fixed_policy_diagnostic.csv',index=False)
    from src.forecasting.diagnostics import plotting,save_figure
    plt,_=plotting();fig,axes=plt.subplots(1,3,figsize=(16,5))
    names=[f'{r.algorithm}\n{int(r.horizon)} sessions' for _,r in all_scores.iterrows()];x=np.arange(len(names))
    axes[0].bar(x,100*all_scores.rmse_gain_vs_zero,color='#d55e00');axes[0].axhline(0,color='#555')
    axes[0].set_ylabel('RMSE reduction versus unchanged price (%)');axes[0].set_title('Point forecasts: all nine are below zero')
    axes[1].bar(x-.18,all_scores.raw_brier,width=.36,label='Raw');axes[1].bar(x+.18,all_scores.calibrated_brier,width=.36,label='Previous calibration')
    axes[1].set_ylabel('Brier loss (lower is better)');axes[1].set_title('Calibration worsened later-test loss');axes[1].legend(fontsize=8)
    for ax in axes[:2]: ax.set_xticks(x,names,rotation=75,fontsize=7)
    annual=all_scores.loc[all_scores.horizon==252];z=np.arange(len(annual))
    axes[2].bar(z,100*annual.below80,label='Below interval',color='#d55e00')
    axes[2].bar(z,100*annual.coverage80,bottom=100*annual.below80,label='Inside interval',color='#0072b2')
    axes[2].bar(z,100*annual.above80,bottom=100*(annual.below80+annual.coverage80),label='Above interval',color='#999')
    axes[2].set_xticks(z,annual.algorithm,rotation=25);axes[2].set_ylabel('Annual test outcomes (%)');axes[2].set_title('Annual misses are mostly below the range');axes[2].legend(fontsize=8)
    fig.suptitle('Existing-model diagnosis · full 40-stock historical test · descriptive, not new validation')
    fig.tight_layout(rect=(0,0,1,.94));save_figure(fig,output/'failure_overview')
    summary=['# What needs fixing first','',
        'The full 40-stock test exposes weaker results than the five held-out-company subset. Every current model/horizon has higher RMSE than unchanged price. The annual classifier calibration period was 95.36% UP; the full annual test was 59.28% UP. More indicators or epochs do not resolve that mismatch.','',
        '## Implemented fix: validate optional probability calibration before fitting it automatically','',
        'Future v2 fits now use a fixed purged forward gate inside the pre-test calibration block. Eight combinations reject calibration; daily LSTM passes that earlier check. Passing does not guarantee later performance: daily LSTM calibration still worsened this historical test. The gate is a safeguard, not a new source of forecasting skill. Rejected calibration retains the raw probability, which remains unvalidated. Existing models, forecasts, paper records and benchmark metrics are unchanged.','',
        table(result,['algorithm','horizon','guard_accepted','raw_brier','old_calibrated_brier','guarded_brier']),
        '', 'This fixed-policy comparison is retrospective diagnosis after inspecting the test, not an independent performance claim. The test did not choose which calibrations pass. No new weights were trained and no claim of improved point predictions is made.','',
        '## Remaining failures and repair criteria','',
        '| Failure | Evidence | Next repair criterion |','|---|---|---|',
        '| Weak point signal | All nine full-test RMSE scores lose to unchanged price; daily prediction variation is only about 1–3% of outcome variation | Require consistent past-fold gains over unchanged price and the existing mean control before accepting a change. Do not force more variable predictions merely to make charts look responsive. |',
        '| Annual calibration support | 4,760 rows but only 136 overlapping origin dates, shorter than one 252-session horizon | Collect older rolling out-of-fit calibration windows; enforce label maturity and report date-block support. Leave annual probability/coverage unvalidated in the meantime. |',
        '| Annual interval location shift | 48–62% of test outcomes fall below the nominal 80% range; fewer than 0.2% fall above | Test residual-location and risk-scaling repairs on older rolling windows. Evaluate both lower/upper miss rates and widths. Do not shift or widen bands using test residuals. |',
        '| Direction collapse | Raw forecasts are already heavily tilted UP; calibration pushes them further toward prior prevalence | Inspect raw/calibrated confusion counts and conditional skill against the prevalence baseline. Do not force a 50/50 output mix or claim signal from accuracy alone. |',
        '| Company/regime dependence | Held-out-company gains do not transfer to the whole universe; slices differ | Require per-company and per-regime validation stability, with support counts. Do not pick favorable companies from this test. |',
        '| LSTM overfitting | Existing curves show training loss falling after validation worsens; longer search did not establish general gains | Retain independent best checkpoints and early stopping; further epochs are not the first repair. |',
        '', '## Files','',
        '[Detailed evidence](REPORT.md) · [Overview chart](failure_overview.png) · [Integrity audit](verification.json)','',
        'The existing benchmark stays frozen. Subsequent forecasting repairs need older rolling validation plus genuinely later/prospective outcomes, because this test has already informed the diagnosis.']
    (output/'VERDICT_AND_FIXES.md').write_text('\n'.join(summary),encoding='utf-8')


def summarize(frame):
    y=frame.target.to_numpy();p=frame.regression.to_numpy();error=p-y
    mse=float(np.mean(error**2));zero=float(np.mean(y**2));bias=float(error.mean())
    lo=frame['lower_0.8'].to_numpy();hi=frame['upper_0.8'].to_numpy()
    return dict(rows=len(frame),dates=int(frame.index.nunique()),actual_mean=float(y.mean()),predicted_mean=float(p.mean()),
        actual_std=float(y.std()),prediction_std=float(p.std()),prediction_to_actual_std=float(p.std()/y.std()) if y.std()>0 else None,
        rmse=float(np.sqrt(mse)),zero_rmse=float(np.sqrt(zero)),rmse_gain_vs_zero=float(1-np.sqrt(mse/zero)) if zero else None,
        bias=bias,bias_fraction_of_mse=bias*bias/mse if mse else 0.,
        error_std=float(error.std()),observed_up=float((y>0).mean()),raw_up_predictions=float((frame.raw_probability>=.5).mean()),
        calibrated_up_predictions=float((frame.probability_up>=.5).mean()),
        raw_brier=losses(y,frame.raw_probability)['brier'],calibrated_brier=losses(y,frame.probability_up)['brier'],
        coverage80=float(((y>=lo)&(y<=hi)).mean()),below80=float((y<lo).mean()),above80=float((y>hi).mean()),
        mean_width80=float((hi-lo).mean()),risk_scale_mean=float(frame.risk_scale.mean()),
        normalized_error_median=float(np.median((y-p)/frame.risk_scale.to_numpy())))


def run(root,output):
    if output.exists(): raise FileExistsError("Choose a new diagnosis directory")
    output.mkdir(parents=True)
    protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    protocol=json.loads((root/'protocol.json').read_text());rows=[];regimes=[];companies=[];calrows=[];gates={}
    for h in protocol['horizons']:
        dev=joblib.load(root/'data'/f'development_h{h}.joblib')
        for a in protocol['algorithms']:
            folder=root/f'h{h}'/a;bundle=joblib.load(folder/'model.joblib')
            frame=pd.read_csv(folder/'test_predictions.csv',parse_dates=['Date','target_date']).set_index('Date')
            for group,part in [('all',frame),('seen',frame.loc[frame.group=='seen']),('unseen',frame.loc[frame.group=='unseen'])]:
                rows.append(dict(algorithm=a,horizon=h,group=group,**summarize(part)))
            for kind in ['vol_regime','trend_regime']:
                for state,part in frame.groupby(kind): regimes.append(dict(algorithm=a,horizon=h,kind=kind,state=state,**summarize(part)))
            for ticker,part in frame.groupby('ticker'): companies.append(dict(algorithm=a,horizon=h,ticker=ticker,**summarize(part)))
            # Targets in this frame were available strictly before the original test.
            panel=task_frame(dev,bundle['direction']).dropna(subset=['target','target_date','risk_scale'])
            cal=window(panel,pd.Timestamp(protocol['boundaries']['calibration']),pd.Timestamp(protocol['boundaries']['test']))
            assert cal.target_date.max()<pd.Timestamp(protocol['boundaries']['test'])
            raw=predict(bundle['direction'],cal)
            _,gate=guarded_calibrate(raw,cal,h)
            gates[f'{a}_h{h}']=gate
            actual=cal.target.to_numpy();bank=np.asarray(bundle['residual_bank'])
            # Residual bank order is the saved return-head calibration order, audited by verify.py.
            regpanel=task_frame(dev,bundle['regression']).dropna(subset=['target','target_date','risk_scale'])
            regcal=window(regpanel,pd.Timestamp(protocol['boundaries']['calibration']),pd.Timestamp(protocol['boundaries']['test']))
            assert len(regcal)==len(bank)
            calrows.append(dict(algorithm=a,horizon=h,rows=len(cal),origin_dates=int(cal.index.nunique()),
                horizon_sized_origin_blocks=int(cal.index.nunique()//h),up_frequency=float((actual>0).mean()),
                residual_mean=float(bank.mean()),residual_p10=float(np.quantile(bank,.1)),residual_p50=float(np.median(bank)),residual_p90=float(np.quantile(bank,.9)),
                risk_scale_mean=float(regcal.risk_scale.mean()),gate_accepted=gate['accepted'],gate_reason=gate['reason']))
            print(f'Diagnosed {a} h{h}: {gate["reason"]}',flush=True)
    scores=pd.DataFrame(rows);states=pd.DataFrame(regimes);stocks=pd.DataFrame(companies);calibration=pd.DataFrame(calrows)
    for name,data in [('error_decomposition',scores),('regime_failures',states),('company_failures',stocks),('calibration_shift',calibration)]:data.to_csv(output/f'{name}.csv',index=False)
    save_json(output/'pretest_calibration_gate.json',gates)
    lines=['# Existing-model failure review','',
        'No features, algorithms, weights, saved probabilities, intervals or benchmark results were changed. Final-test diagnostics below explain failures; they do not select a new model. Calibration safeguard decisions use only a fixed, purged split inside the pre-test calibration block.','',
        '## 1. Does the point forecast beat unchanged price?','',
        table(scores.loc[scores.group=='all'],['algorithm','horizon','rmse','zero_rmse','rmse_gain_vs_zero','bias','prediction_to_actual_std']),
        '', 'Positive RMSE gain favors the model. A small prediction/actual standard-deviation ratio indicates weak differentiation, but alone does not prove a bug: noisy outcomes can justify conservative conditional means. Bias fraction below is descriptive; subtracting the measured test bias would leak test outcomes.','',
        table(scores.loc[scores.group=='all'],['algorithm','horizon','bias_fraction_of_mse','error_std','actual_mean','predicted_mean']),
        '', '## 2. Calibration shifts probabilities without establishing a directional signal','',
        table(scores.loc[scores.group=='all'],['algorithm','horizon','observed_up','raw_up_predictions','calibrated_up_predictions','raw_brier','calibrated_brier']),
        '', 'Brier is lower-is-better. Compare raw and adjusted outputs to distinguish model collapse from a calibrator-induced base-rate shift. A high raw accuracy or all-UP output is not evidence of identifying down moves.','',
        '## 3. Why uncertainty ranges fail','',
        table(calibration,['algorithm','horizon','origin_dates','horizon_sized_origin_blocks','up_frequency','residual_p10','residual_p50','residual_p90','risk_scale_mean']),
        '',table(scores.loc[scores.group=='all'],['algorithm','horizon','coverage80','below80','above80','risk_scale_mean','normalized_error_median']),
        '', 'Large lower-tail miss rates show whether the calibration distribution sits above later outcomes. Volatility scaling cannot remove a shift in residual location or repair unseen tails. Horizon-sized block counts are rough support diagnostics, not independent-sample counts or coverage guarantees.','',
        '## 4. Pre-test-only calibration safeguard','',
        table(calibration,['algorithm','horizon','gate_accepted','gate_reason']),
        '', 'The proposed fix requires a fixed 70/30 chronological calibration split, label-maturity purging, at least two horizon-sized date blocks in both parts, and improvement over raw probability and the earlier prevalence prior on BOTH Brier and log loss. Rejection keeps raw probabilities; it does not certify them. Annual data may be insufficient to validate any recalibration in this block. Full decision evidence is in pretest_calibration_gate.json. No test-based raw/calibrated switching is performed.','',
        '## 5. Company and regime dependence','',
        'company_failures.csv contains every company, including the five held-out names. regime_failures.csv retains every observed market state. These are descriptive slices; thin annual samples and overlap prevent strong ranking claims.','',
        table(stocks.sort_values('rmse_gain_vs_zero').head(15),['algorithm','horizon','ticker','rmse','zero_rmse','rmse_gain_vs_zero','bias','coverage80']),
        '', '## Prioritized fixes','',
        '1. Stop applying unvalidated probability calibration automatically. Gate it on mature, chronological pre-test outcomes; report raw probability as unvalidated whenever the gate rejects.',
        '2. Keep annual uncertainty explicitly unvalidated. Before changing its residual centering, width or volatility mapping, compare those repairs on older rolling out-of-fit windows with all target dates matured before each forecast origin. Do not widen/shift ranges until they fit this inspected test.',
        '3. Address model weakness only where validation shows persistent gains over unchanged price and historical-mean controls. Retain simple tree benchmarks; longer LSTM training already showed overfitting. Check down-market errors and cross-company stability rather than overall accuracy alone.',
        '4. Preserve this benchmark. A repair now informed by these test results needs a later untouched period or prospective outcomes to establish improvement. Existing paper records remain unchanged.','']
    (output/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    finish_review(root,output)
    changed=[p for p,d in protected.items() if not Path(p).exists() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=d]
    if changed: raise AssertionError(f'Benchmark mutated: {changed[:3]}')
    save_json(output/'verification.json',dict(benchmark_files_unchanged=len(protected),original_files_unchanged=check_protected(root),test_used_for_diagnosis_only=True,calibration_gate_uses_pretest_only=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--experiment',type=Path,default=DEFAULT)
    p.add_argument('--output',type=Path,default=Path('artifacts/analysis/feature_v2_failure_review'))
    args=p.parse_args();run(args.experiment.resolve(),args.output.resolve())
