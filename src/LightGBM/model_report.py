"""Rebuild consolidated regression, direction, ranking and paired comparison reports."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.LightGBM import MODEL_VERSION
from src.LightGBM.config import HORIZON_NAMES
from src.LightGBM.metrics import summary_metrics, directional_metrics, ranking_metrics, paired_uncertainty


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def improvement(candidate, reference):
    return 100*(1-candidate/reference) if reference else None


def generate_report(directory):
    directory=Path(directory)
    protocol=json.loads((directory/"protocol.json").read_text())
    if protocol.get("algorithm")!="lightgbm" or protocol.get("model_version")!=MODEL_VERSION:
        raise ValueError("Expected a LightGBM experiment; refusing to write reports into another algorithm's directory")
    out=directory/"comparisons"
    out.mkdir(exist_ok=True)
    summary, comparisons, validation, stock_rows, yearly_rows, intervals, rank_rows=[],[],[],[],[],[],[]
    selections={}
    lines=["# LightGBM versus XGBoost", "",
           "Frozen XGBoost-selected features and exact matched observations. LightGBM baseline and tuned "
           "models are separate; tuning/early stopping uses validation only. Historical test data have "
           "already been inspected in earlier research, so these are exploratory results, not a new prospective test.", "",
           "| Sessions | Model | Validation RMSE | Unseen MAE | Unseen RMSE | RMSE improvement vs XGBoost | Direction | Always up |",
           "|---|---|---:|---:|---:|---:|---:|---:|"]
    interpretations=[]
    for horizon in protocol["horizons"]:
        label=HORIZON_NAMES[horizon]
        frame=pd.read_csv(directory/"reports"/(label+"_predictions.csv"),parse_dates=["Date","target_date"]).set_index("Date")
        metadata=json.loads((directory/"reports"/(label+"_metadata.json")).read_text())
        candidates=[name for name in frame if name.startswith("lightgbm_")]
        reference_dir=Path(protocol["reference_directory"])
        family=protocol["reference_selections"][str(horizon)]["family"]
        price_reference=json.loads((reference_dir/"price_only"/f"h{horizon}"/"report.json").read_text())
        cv_scores={"lightgbm_"+stage:r["selected"]["cv_rmse"] for stage,r in metadata["reports"].items()}
        cv_scores["xgboost"]=metadata["reports"]["baseline"]["xgboost_reference_cv"]["cv_rmse"]
        cv_scores["price_only"]=price_reference["best_trial"]["cv_rmse"]
        stage=min(metadata["reports"],key=lambda s:metadata["reports"][s]["selected"]["cv_rmse"])
        selected_name="lightgbm_"+stage
        selections[str(horizon)]=dict(lightgbm_stage=stage,
            lightgbm_model_path=metadata["reports"][stage]["model_path"],
            lightgbm_cv_rmse=cv_scores[selected_name],xgboost_cv_rmse=cv_scores["xgboost"],
            preferred_algorithm_by_validation="lightgbm" if cv_scores[selected_name]<cv_scores["xgboost"] else "xgboost",
            caveat="Selection uses validation only; small differences are not proof of future superiority")
        names=candidates+["xgboost","price_only","zero_return","historical_mean","stock_mean"]
        groups={"seen":frame.loc[frame.group=="seen"],"unseen":frame.loc[frame.group=="unseen"],"all":frame}
        horizon_results={}
        for group_name, group in groups.items():
            metrics={name:summary_metrics(group,name) for name in names}
            direction_baselines={
                "always_up":directional_metrics(group.target,np.ones(len(group))),
                "always_down":directional_metrics(group.target,-np.ones(len(group))),
                "training_majority":directional_metrics(group.target,np.full(len(group),metadata["training_majority_direction"])),
            }
            rankings={name:ranking_metrics(group,name,horizon) for name in names}
            horizon_results[group_name]=dict(rows=len(group),stocks=group.ticker.nunique(),metrics=metrics,
                                            direction_baselines=direction_baselines,cross_sectional_ranking=rankings)
            for name, values in metrics.items():
                direction=values["direction"]
                summary.append(dict(horizon=horizon,group=group_name,model=name,validation_rmse=cv_scores.get(name),mae=values["mae"],rmse=values["rmse"],
                    r2=values["r2"],pearson=values["pearson"],spearman=values["spearman"],price_mape=values["price_mape"],
                    direction_accuracy=direction["accuracy"],balanced_accuracy=direction["balanced_accuracy_nonflat"],
                    up_precision=direction["classes"]["UP"]["precision"],up_recall=direction["classes"]["UP"]["recall"],
                    down_precision=direction["classes"]["DOWN"]["precision"],down_recall=direction["classes"]["DOWN"]["recall"],
                    always_up=direction_baselines["always_up"]["accuracy"],always_down=direction_baselines["always_down"]["accuracy"],
                    collapse=direction["collapse"],rank_ic=rankings[name]["mean_rank_ic"],rows=len(group)))
                rank_rows.append(dict(horizon=horizon,group=group_name,model=name,**rankings[name]))
            for candidate in candidates:
                for reference in ["xgboost","price_only","historical_mean"]:
                    uncertainty=paired_uncertainty(group,candidate,reference,horizon)
                    intervals.append(dict(horizon=horizon,group=group_name,**uncertainty))
                    a,b=metrics[candidate],metrics[reference]
                    comparisons.append(dict(horizon=horizon,group=group_name,candidate=candidate,reference=reference,
                                            mae_difference=a["mae"]-b["mae"],rmse_difference=a["rmse"]-b["rmse"],
                                            mae_improvement_pct=improvement(a["mae"],b["mae"]),
                                            rmse_improvement_pct=improvement(a["rmse"],b["rmse"]),
                                            direction_difference_pp=100*(a["direction"]["accuracy"]-b["direction"]["accuracy"]),
                                            mae_difference_ci95=uncertainty["mae_difference_ci95"],
                                            rmse_difference_ci95=uncertainty["rmse_difference_ci95"]))
            if group_name=="unseen":
                for name in candidates+["xgboost","price_only"]:
                    m=metrics[name]
                    lines.append(f'| {horizon} | {name} | {cv_scores[name]:.6f} | {m["mae"]:.6f} | {m["rmse"]:.6f} | '
                                 f'{improvement(m["rmse"],metrics["xgboost"]["rmse"]):+.2f}% | '
                                 f'{m["direction"]["accuracy"]:.2%} | {direction_baselines["always_up"]["accuracy"]:.2%} |')
                selected=selected_name
                m=metrics[selected]
                interval=next(v for v in intervals if v["horizon"]==horizon and v["group"]=="unseen" and v["candidate"]==selected and v["reference"]=="xgboost")
                ci=interval["rmse_difference_ci95"]
                uncertainty_text=("insufficient time coverage for an uncertainty interval" if ci is None else
                                  "the approximate date-block interval includes no improvement" if ci[0]<=0<=ci[1] else
                                  "the approximate date-block interval favors LightGBM in this reused period" if ci[1]<0 else
                                  "the approximate date-block interval favors XGBoost in this reused period")
                interpretations.append(f'- {horizon} sessions: {selected} RMSE improvement versus XGBoost '
                    f'{improvement(m["rmse"],metrics["xgboost"]["rmse"]):+.2f}%; {uncertainty_text}. '
                    f'Direction {m["direction"]["accuracy"]:.2%} versus always-up {direction_baselines["always_up"]["accuracy"]:.2%}; '
                    f'prediction pattern: {m["direction"]["collapse"]}.')
                interpretations.append(f'  Algorithm preference by validation: {selections[str(horizon)]["preferred_algorithm_by_validation"]}; '
                    f'LightGBM CV {cv_scores[selected]:.9f}, XGBoost CV {cv_scores["xgboost"]:.9f}.')
        for ticker, group in frame.groupby("ticker"):
            for name in names:
                m=summary_metrics(group,name)
                stock_rows.append(dict(horizon=horizon,ticker=ticker,group=group.group.iloc[0],model=name,
                                       mae=m["mae"],rmse=m["rmse"],direction=m["direction"]["accuracy"],pearson=m["pearson"],spearman=m["spearman"]))
        for (group_name,year), group in frame.groupby(["group",frame.index.year]):
            for name in names:
                m=summary_metrics(group,name)
                yearly_rows.append(dict(horizon=horizon,group=group_name,year=int(year),model=name,rows=len(group),
                                        mae=m["mae"],rmse=m["rmse"],direction=m["direction"]["accuracy"]))
        for stage, report in metadata["reports"].items():
            for fold in report["selected"]["folds"]:
                validation.append(dict(horizon=horizon,model="lightgbm_"+stage,**fold))
        for name,path in [("xgboost",reference_dir/family/f"h{horizon}"/"report.json"),
                          ("price_only",reference_dir/"price_only"/f"h{horizon}"/"report.json")]:
            ref=json.loads(path.read_text())
            for fold in ref["best_trial"]["folds"]:
                validation.append(dict(horizon=horizon,model=name,**fold))
        dump(directory/"reports"/(label+"_metrics.json"),horizon_results)
    pd.DataFrame(summary).to_csv(out/"horizon_summary.csv",index=False)
    pd.DataFrame(comparisons).to_csv(out/"xgboost_vs_lightgbm.csv",index=False)
    pd.DataFrame(validation).to_csv(out/"validation_stability.csv",index=False)
    pd.DataFrame(stock_rows).to_csv(out/"per_stock.csv",index=False)
    pd.DataFrame(yearly_rows).to_csv(out/"yearly.csv",index=False)
    dump(out/"uncertainty.json",intervals)
    dump(out/"ranking.json",rank_rows)
    dump(directory/"selected.json",selections)
    lines += ["", "Positive error-improvement percentages mean lower LightGBM error; negative means deterioration. "
              "Direction is not price accuracy. price_only is the existing price-feature-only XGBoost model; "
              "zero-return/unchanged-price and training-mean baselines are also in the metrics and CSVs.", "",
              "## Interpretation", ""]+interpretations+[
              "", "## Protocol and limitations", "",
              "- Independent models for 1, 21, 252 sessions, predicting cumulative adjusted-close log return.",
              "- Features are fixed to XGBoost's validation-selected family for each horizon. No new features or feature selection in this benchmark.",
              "- Same frozen 40-stock sources, 2017 start, 2021–2022 and 2023–2024 validation windows, 2025 test boundary and five excluded companies.",
              "- Training and validation labels are strictly purged before the next boundary. The past-only reference protocol has zero additional embargo sessions; no right-side future training is used. No random splitting.",
              "- Input NaNs are native LightGBM missing values; infinities, missing named columns and nonnumeric features are rejected. No feature scaling or fitted imputation. Label mean/std scaling is fitted on training only, matching XGBoost.",
              "- Baseline uses the requested conservative configuration, 500 maximum trees and validation early stopping. Row subsampling is explicitly enabled with subsample_freq=1; it would otherwise be inactive in LightGBM.",
              "- Baseline and optional tuned parameters/tree counts are selected on validation only. Their artifacts and results remain separate. Seed, versions, source hashes and every trial are saved.",
              "- Pearson and pooled Spearman describe regression association; cross-sectional daily Spearman IC evaluates ranking among stocks. Undefined constant-prediction correlations remain null, not invented zeros.",
              "- Direction confusion matrix is DOWN/FLAT/UP, rows actual and columns predicted. UP/DOWN balanced accuracy averages their recalls when both actual classes occur; flat predictions count as errors. No probability is inferred from regression output.",
              "- Circular date-block intervals retain cross-stock dependence, with block length max(21,H). Less than two blocks yields no interval. Annual test coverage is especially inadequate. Intervals do not fully correct for repeated research or changing market regimes.",
              "- Fundamental data retain the source study's publication lag, missingness and archive/taxonomy limitations. Historical snapshots are not guaranteed immutable point-in-time archives.",
              "- All test years and companies have been inspected previously; these results cannot be presented as an untouched future holdout or a maximum achievable accuracy.",
              "- No live trading, Monte Carlo or directional probability model is implemented. A prospective paper test and execution-cost study are still required for deployment.", "",
              "Official implementation references: [LGBMRegressor](https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.LGBMRegressor.html), "
              "[early stopping](https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.early_stopping.html)."]
    (out/"comparison.md").write_text("\n".join(lines)+"\n",encoding="utf-8")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory",type=Path,required=True)
    generate_report(parser.parse_args().directory)
