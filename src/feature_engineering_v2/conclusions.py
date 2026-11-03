"""Answer the specification's sixteen research questions using completed tables."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from src.feature_engineering_v2.prepare import DEFAULT


def table(frame,columns):
    frame=frame.reindex(columns=columns)
    lines=["| "+" | ".join(columns)+" |","|"+"---|"*len(columns)]
    for _,row in frame[columns].iterrows():
        values=[]
        for value in row:
            if pd.isna(value): values.append("—")
            elif isinstance(value,(float,np.floating)): values.append(f"{value:.6f}")
            else: values.append(str(value))
        lines.append("| "+" | ".join(values)+" |")
    return "\n".join(lines)


def generate(root):
    validation=pd.read_csv(root/"validation_error_comparison.csv")
    ablation=pd.read_csv(root/"feature_ablation_results.csv")
    hyper=pd.read_csv(root/"hyperparameter_results.csv")
    comparison=pd.read_csv(root/"model_comparison.csv")
    direction=pd.read_csv(root/"direction_metrics.csv")
    intervals=pd.read_csv(root/"interval_metrics.csv")
    regimes=pd.read_csv(root/"regime_metrics.csv")
    selected=validation.loc[validation.task=="return"]
    tree_gain=selected.loc[selected.algorithm.isin(["xgboost","lightgbm"])].copy()
    tree_gain["relative_validation_gain_vs_F0"]=(tree_gain.F0_error-tree_gain.validation_error)/tree_gain.F0_error
    sequence=hyper.loc[(hyper.algorithm=="lstm")&(hyper.task=="return")&hyper.configuration.isin(["A_sequence_60","A_sequence_120"])].copy()
    references=[]
    for _,row in sequence.iterrows():
        matching=hyper.loc[(hyper.algorithm=="lstm")&(hyper.horizon==row.horizon)&(hyper.task=="return")&(hyper.lookback==20)&
            (hyper.method=="fresh")&(hyper.parameters==row.parameters)&(hyper.groups.fillna("")==str(row.groups if pd.notna(row.groups) else ""))&(hyper.alias_of.isna())]
        references.append(float(matching.mean_validation_error.min()) if len(matching) else np.nan)
    sequence["matched_20_session_error"]=references
    sequence["relative_gain_vs_20"]=(sequence.matched_20_session_error-sequence.mean_validation_error)/sequence.matched_20_session_error
    probability=[];baseline_tests=[];overfit=[]
    for _,row in selected.iterrows():
        m=json.loads((root/f"h{int(row.horizon)}"/row.algorithm/"metrics.json").read_text())["all"]
        probability.append(dict(algorithm=row.algorithm,horizon=row.horizon,raw_brier=m["classifier_raw"]["brier"],
            calibrated_brier=m["classifier"]["brier"],prior_brier=m["prior_classifier"]["brier"],
            calibration_helped=m["classifier"]["brier"]<m["classifier_raw"]["brier"]))
        baseline_tests.append(dict(algorithm=row.algorithm,horizon=row.horizon,beats_zero_validation=row.validation_error<row.zero_return_error,
            beats_control_validation=row.validation_error<row.matched_control_error,
            test_rmse=m["regression"]["rmse"],zero_test_rmse=m["zero_return"]["rmse"],control_test_rmse=m["control"]["rmse"],
            beats_zero_test=m["regression"]["rmse"]<m["zero_return"]["rmse"],beats_control_test=m["regression"]["rmse"]<m["control"]["rmse"]))
        if row.algorithm=="lstm":
            for fold in [1,2]:
                model=joblib.load(root/"development/lstm"/f"h{int(row.horizon)}"/row.selected/f"fold{fold}.joblib")["return"]
                curve=model["learning_curve"]
                if curve and "training_return_rmse" in curve[0]:
                    overfit.append(dict(horizon=row.horizon,fold=fold,selected_epoch=model["rounds"],
                        last_epoch=curve[-1]["epoch"],training_improved=curve[-1]["training_return_rmse"]<curve[0]["training_return_rmse"],
                        last_validation_above_min=curve[-1]["validation_return_rmse"]>min(r["validation_return_rmse"] for r in curve)+1e-6))
    pd.DataFrame(probability).to_csv(root/"probability_calibration_comparison.csv",index=False)
    regime_pairs=regimes.pivot_table(index=["algorithm","horizon","regime_type","regime"],columns="version",values="rmse").reset_index()
    improved_regimes=int((regime_pairs.v2<regime_pairs.previous).sum())
    lines=["# NightEye feature-engineering v2 — final research report","",
        "This is a bounded development-only search on the original frozen 40-stock study. All eighteen algorithm/task/horizon choices were frozen together before this run opened final-test labels. The historical test has already been inspected in earlier research, so it is not a new prospective holdout.","",
        "## 1. Lowest validation RMSE by horizon","",
        "Primary selection uses mean macro-stock RMSE over both purged folds. Stability selection may retain a configuration within 0.1% of the mean minimum with a better worst baseline-relative fold and fewer features; >0.5% fold deterioration versus F0 is excluded. The absolute unconstrained minimum is also recorded.","",
        table(selected,["algorithm","horizon","selected","validation_error","absolute_minimum","absolute_minimum_error","F0_error","old_selected_error","zero_return_error","matched_control_error"]),"",
        "## 2. Feature families that reduced validation error","",
        "The table below shows positive mean improvements over each algorithm/task's own F0. A family already present in F0 is deduplicated. F0 schemas can differ between algorithms/tasks; this is not a single common feature-count contest.",""]
    improved=ablation.loc[(ablation.task=="return")&(ablation.relative_improvement_vs_F0>0)&(ablation.alias_of.isna())&(ablation.configuration!="W0")]
    lines += [table(improved,["algorithm","horizon","configuration","groups","relative_improvement_vs_F0","improved_folds","features"]),"",
        "## 3. Were improvements consistent across both folds?","",
        table(selected,["algorithm","horizon","selected","fold1_error","fold2_error","std","consistent_improvement_vs_F0"]),"",
        "One-fold wins and tiny changes relative to fold variability are not evidence of reliable generalization. Inspect both fold values, not only the mean.","",
        "## 4. Training–validation gap","",
        table(selected,["algorithm","horizon","selected","gap_change"]),"",
        "Negative gap change means the measured macro validation-minus-training error gap narrowed. It does not by itself prove improvement: a deliberately underfit model can also have a small gap.","",
        "## 5. Which tree algorithm benefited more?","",
        table(tree_gain,["algorithm","horizon","selected","relative_validation_gain_vs_F0"]),"",
        "XGBoost retained its existing F0 whenever no stable gain qualified; LightGBM's selected changes are quantified above. The same search rule and final-test keys were used, but initial selected schemas and native regularization units differ. No broad superiority claim follows from a tiny isolated gain.","",
        "## 6. Longer LSTM sequences","",
        table(sequence,["horizon","configuration","family","lookback","mean_validation_error","matched_20_session_error","relative_gain_vs_20"]),"",
        "These are one-factor changes on the validation-selected return family's fresh 20-session architecture. Compare with that matching fresh family, not an unrelated baseline. All test keys remain identical; longer sequence warmup slightly changes early training counts.","",
        "## 7. More epochs","",
        table(hyper.loc[(hyper.algorithm=="lstm")&(hyper.task=="return")&hyper.configuration.isin(["E_40","E_60"])],
              ["horizon","configuration","epoch_ceiling","mean_validation_error","alias_of"]),"",
        "An alias means the matching run stopped naturally before 20 epochs; 40/60 ceilings produce the same seeded stopped trajectory and were not wastefully retrained. Non-alias entries are actual extended runs. A higher ceiling is not accumulated knowledge.","",
        "## 8. Did LSTM still overfit?","",
        table(pd.DataFrame(overfit),["horizon","fold","selected_epoch","last_epoch","training_improved","last_validation_above_min"]),"",
        "The learning charts expose training RMSE/joint loss and separate validation return RMSE/direction log loss, with independently chosen checkpoints. True in the last two columns indicates that continued fitting reduced training error while the last validation error exceeded its best checkpoint. The last epoch is never automatically the chosen model.","",
        "## 9. Did models beat unchanged price?","",
        "Validation zero-return error appears in question 1. Final-test comparisons below are on exactly matched observations. A small positive price-level correlation is not sufficient; compare log-return error and the unchanged-price control.","",
        table(comparison.loc[comparison.group=="all"],["algorithm","horizon","version","rmse","mae","r2","pearson","spearman","bias"]),"",
        table(pd.DataFrame(baseline_tests),["algorithm","horizon","beats_zero_validation","test_rmse","zero_test_rmse","beats_zero_test"]),"",
        "The full unchanged-price and matched-control scores are also saved in each h*/algorithm/metrics.json. A new model is not called improved merely because it beats the older LSTM.","",
        "## 10. Matched-control comparison","",
        table(pd.DataFrame(baseline_tests),["algorithm","horizon","beats_control_validation","test_rmse","control_test_rmse","beats_control_test"]),"",
        "Each metrics.json includes approximate paired date-block intervals against the same control. Annual intervals are withheld when there are fewer than two horizon-sized origin-date blocks.","",
        "## 11. Balanced directional accuracy","",
        table(direction.loc[direction.group=="all"],["algorithm","horizon","version","accuracy","balanced_accuracy","up_precision","up_recall","not_up_recall","f1","up_predictions","not_up_predictions"]),"",
        "UP means positive return; NOT_UP includes flat outcomes. Always-UP accuracy can be high in a bullish subset while balanced accuracy remains 50%. Counts and confusion matrices are included; precision without signal support is not convincing.","",
        "## 12. Did probability calibration improve?","",
        table(pd.DataFrame(probability),["algorithm","horizon","raw_brier","calibrated_brier","prior_brier","calibration_helped"]),"",
        "Lower Brier is better. Raw-versus-calibrated reliability diagrams are in charts/calibration_*.png. The calibrator used only the separate calibration block; the final test did not fit or select it. Calibration can worsen later-regime performance, and the dashboard retains those failures.","",
        "## 13. Interval coverage","",
        table(intervals.loc[(intervals.scope=="group")&(intervals.name=="all")&(intervals.nominal==.8)],
              ["algorithm","horizon","version","nominal","observed","mean_log_width","mean_width_pct_of_origin"]),"",
        "Coverage must be considered alongside width: widening an interval can improve coverage without improving the return forecast. Company coverage and all three nominal levels are in interval_metrics.csv. No distribution-free or live coverage guarantee is claimed.","",
        "## 14. Market regimes","",
        f"New RMSE is lower in {improved_regimes} of {len(regime_pairs)} observed algorithm/horizon/regime buckets. This count is descriptive, not a significance test. regime_metrics.csv compares old and new forecasts under the same causal states, including interval coverage. Fixed thresholds were declared before optimization. A favorable regime cannot establish robustness in the others.","",
        "## 15. Strategy after costs",""]
    if (root/"backtest_comparison.csv").exists():
        backtest=pd.read_csv(root/"backtest_comparison.csv")
        lines += [table(backtest,["algorithm","horizon","version","total_return","buy_hold_return","sharpe","max_drawdown","trades","truncated_trades","exposure","cash_costs","gross_traded_notional_over_initial_cash"]),""]
    lines += ["The execution methodology and 10 bp cost + 5 bp slippage per side are unchanged. Signals include unlabeled late origins; positions enter next open and are explicitly liquidated at the final open when truncated. No parameters were selected from test strategy returns. Fractional adjusted units are a proxy, not an executable brokerage ledger.","",
        "## 16. Is the improvement meaningful?","",
        "The tables distinguish an unconstrained validation minimum, a stability-selected model, final-test performance, historical strategy outcomes and prospective journal outcomes. A reliable improvement needs consistent fold gains, superiority to simple baselines, sensible uncertainty coverage/width, and prospective evidence. This finite search cannot establish maximum attainable accuracy, a universal stock model or a market edge.","",
        "Original datasets, model artifacts, calibration banks, verification reports and the nine original journal records are protected by hashes. New configurations and model inputs live in this separate experiment. Compatible weights were reused/continued; feature-schema changes were fitted fresh. LSTM weight fine-tuning resets AdamW because the old optimizer state was not saved.","",
        "## Output and commands","",
        "Open index.html for the study dashboard, forecasts/index.html for Monte Carlo price paths, and backtest/report.html for strategy results. A separate paper_journal_v2 contains any new prospective records; their outcomes remain pending until enough real sessions occur. See FEATURE_ENGINEERING_V2.md in the repository for runnable commands and scope."]
    (root/"FINAL_REPORT.md").write_text("\n".join(lines),encoding="utf-8")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,default=DEFAULT)
    generate(p.parse_args().output.resolve())
