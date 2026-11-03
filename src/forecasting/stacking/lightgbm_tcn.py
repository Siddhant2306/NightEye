"""Monthly LightGBM–TCN blend experiment."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.feature_engineering_v2.metrics import score
from src.feature_engineering_v2.models import predict, tree_fit
from src.forecasting.diagnostics import plotting, save_figure
from src.forecasting.ensemble import loss
from src.forecasting.protocol import window
from src.forecasting.stacking.oof import inner_split
from src.forecasting.stacking.study import COMPACT, PARAMS, REPAIR, ROOT, SOURCE, hash_file, slice_keys
from src.forecasting.train import save_json


OUTPUT = ROOT.with_name('lightgbm_tcn_monthly_v1')
RECIPES = [
    PARAMS,
    dict(PARAMS, learning_rate=.015, l2=25.),
    dict(PARAMS, learning_rate=.025, depth=3, leaf_min=100, l2=40.),
]
WEIGHTS = (1., .9, .75, .5)


def choose_weight(rows, task):
    first = [r for r in rows if r['fold'] == 1 and r['task'] == task]
    selected = min(first, key=lambda r: (r['loss'], -r['lightgbm_weight']))['lightgbm_weight']
    second = {r['lightgbm_weight']: r['loss'] for r in rows if r['fold'] == 2 and r['task'] == task}
    return selected if second[selected] < second[1.] else 1.


def run():
    OUTPUT.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((SOURCE/'protocol.json').read_text())
    edges = {k: pd.Timestamp(v) for k, v in protocol['boundaries'].items()}
    source_oof = ROOT/'h21/oof.csv'
    source_test = ROOT/'test_predictions.csv'
    inputs = [SOURCE/'protocol.json', SOURCE/'data/development_h21.joblib', source_oof,
              source_test, REPAIR/'h21/lightgbm/test_predictions.csv']
    hashes = {str(p): hash_file(p) for p in inputs}
    save_json(OUTPUT/'design.json', dict(horizon=21, boundaries=protocol['boundaries'],
        columns=COMPACT, recipes=RECIPES, ceiling=1000, patience=60, weights=WEIGHTS, inputs=hashes,
        rule='Select recipe on inner chronological validation. Propose blend on outer fold 1 and retain it only if it beats LightGBM on outer fold 2.'))
    dev = joblib.load(inputs[1]).dropna(subset=['target','target_date','risk_scale'])
    assert not dev.ticker.isin(protocol['held_out_companies']).any()
    oof = pd.read_csv(source_oof, parse_dates=['origin','target_date'])
    trials, checkpoints, validation, oof_parts = [], [], [], []
    for fold, start, end in [(1,'fold1','fold2'), (2,'fold2','calibration'), (3,'calibration',None)]:
        train, valid = inner_split(dev, edges[start], 21)
        heads = {}
        for task in ('return','direction'):
            candidates = []
            for number, params in enumerate(RECIPES):
                model = tree_fit('lightgbm',task,train,COMPACT,params,1000,valid,60)
                value = loss(valid.target.to_numpy(), predict(model,valid),task)
                candidates.append((value,number,model))
                checkpoints.append(dict(fold=fold,task=task,recipe=number,rounds=model['rounds'],inner_loss=value))
            _, number, heads[task] = min(candidates,key=lambda item:item[:2])
            print(f'Fold {fold} {task}: recipe {number}, {heads[task]["rounds"]} rounds',flush=True)
        joblib.dump(heads, OUTPUT/f'fold{fold}.joblib',compress=3)
        if end is None:
            continue
        expected = window(dev,edges[start],edges[end])
        aligned = {}
        for name in ('lightgbm','tcn'):
            rows = oof.loc[(oof.fold==fold)&(oof.model==name)].set_index('origin')
            aligned[name] = slice_keys(rows,expected)
            np.testing.assert_array_equal(aligned[name].target_date,expected.target_date)
            np.testing.assert_allclose(aligned[name].target,expected.target,atol=1e-14)
        part = expected[['ticker','target','target_date']].copy()
        part['fold'] = fold
        part['latest_selection_label'] = valid.target_date.max()
        assert part.latest_selection_label.max() < part.index.min()
        for task,column in [('return','regression'),('direction','probability_up')]:
            actual = expected.target.to_numpy()
            light = predict(heads[task],expected)
            tcn = aligned['tcn'][column].to_numpy()
            prior = aligned['lightgbm'][column].to_numpy()
            part[f'lightgbm_{task}'],part[f'tcn_{task}'] = light,tcn
            validation.append(dict(fold=fold,task=task,prior_loss=loss(actual,prior,task),
                                   strengthened_loss=loss(actual,light,task)))
            for weight in WEIGHTS:
                trials.append(dict(fold=fold,task=task,lightgbm_weight=weight,
                                   loss=loss(actual,weight*light+(1-weight)*tcn,task)))
        oof_parts.append(part)
    chosen = {task: choose_weight(trials,task) for task in ('return','direction')}
    pd.DataFrame(trials).to_csv(OUTPUT/'validation_blends.csv',index=False)
    pd.DataFrame(validation).to_csv(OUTPUT/'validation_lightgbm.csv',index=False)
    pd.DataFrame(checkpoints).to_csv(OUTPUT/'checkpoints.csv',index=False)
    pd.concat(oof_parts).to_csv(OUTPUT/'oof_predictions.csv')
    save_json(OUTPUT/'selection_frozen.json',dict(weights=chosen,at=pd.Timestamp.now(tz='UTC').isoformat(),
        checkpoint=hash_file(OUTPUT/'fold3.joblib')))
    actual = joblib.load(SOURCE/'data/evaluation_h21.joblib').dropna(subset=['target','target_date','risk_scale'])
    panel = joblib.load(SOURCE/'data/unlabeled_h21.joblib')
    features = slice_keys(panel,actual)
    previous = pd.read_csv(source_test,parse_dates=['Date','target_date']).set_index('Date')
    base = {}
    for name in ('lightgbm','tcn','repair_lightgbm'):
        rows = previous.loc[(previous.horizon==21)&(previous.model==name)]
        base[name] = slice_keys(rows,actual)
        np.testing.assert_array_equal(base[name].target_date,actual.target_date)
        np.testing.assert_allclose(base[name].target,actual.target,atol=1e-14)
    light = {task:predict(heads[task],features) for task in chosen}
    # Compare raw probabilities throughout, before any calibration.
    combinations = {name:(p.regression.to_numpy(),p.raw_probability.to_numpy()) for name,p in base.items()}
    combinations['unchanged'] = (np.zeros(len(actual)),np.full(len(actual),.5))
    combinations['strengthened_lightgbm'] = (light['return'],light['direction'])
    for weight in WEIGHTS[1:]:
        combinations[f'fixed_{int(weight*100)}'] = tuple(
            weight*light[task]+(1-weight)*combinations['tcn'][i] for i,task in enumerate(chosen))
    combinations['selected'] = tuple(
        chosen[task]*light[task]+(1-chosen[task])*combinations['tcn'][i] for i,task in enumerate(chosen))
    unseen = actual.ticker.isin(protocol['held_out_companies']).to_numpy()
    metrics, predictions = [], []
    for name,(returns,probs) in combinations.items():
        predictions.append(actual[['ticker','target','target_date']].assign(model=name,prediction=returns,probability_up=probs))
        for group,mask in [('all',np.ones(len(actual),dtype=bool)),('unseen',unseen)]:
            frame = actual.iloc[mask]
            direction = score(frame,probs[mask],'direction')
            metrics.append(dict(model=name,group=group,rmse=score(frame,returns[mask],'return')['rmse'],
                balanced_accuracy=direction['balanced_accuracy'],brier=direction['brier'],log_loss=direction['log_loss']))
    result = pd.DataFrame(metrics)
    result.to_csv(OUTPUT/'metrics.csv',index=False)
    pd.concat(predictions).to_csv(OUTPUT/'test_predictions.csv')
    plt,_ = plotting()
    fig,axes = plt.subplots(1,2,figsize=(13,5))
    for axis,group in zip(axes,['all','unseen']):
        rows = result.loc[result.group==group].sort_values('rmse',ascending=False)
        axis.barh(rows.model,rows.rmse)
        axis.axvline(rows.loc[rows.model=='unchanged','rmse'].iloc[0],color='black',linestyle='--')
        axis.set(title=group,xlabel='21-session log-return RMSE')
    fig.tight_layout()
    save_figure(fig,OUTPUT/'comparison')
    if any(hash_file(Path(path))!=digest for path,digest in hashes.items()):
        raise ValueError('Source experiment changed')
    print(result.to_string(index=False),flush=True)


if __name__ == '__main__':
    run()
