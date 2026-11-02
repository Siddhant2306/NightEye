"""Small validation-only permutation audit for selected LSTM input features."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from src.feature_engineering_v2.prepare import DEFAULT
from src.feature_engineering_v2.develop import development_folds
from src.feature_engineering_v2.inference import task_frame
from src.feature_engineering_v2.models import predict
from src.feature_engineering_v2.metrics import score
from src.feature_engineering_v2.report import feature_weights,plot_importance


def generate(root):
    protocol=json.loads((root/"protocol.json").read_text());rows=[]
    for h in protocol["horizons"]:
        selected=json.loads((root/"development/lstm"/f"h{h}"/"selection.json").read_text())["return"]["selected"]
        raw=joblib.load(root/"data"/f"development_h{h}.joblib")
        edges={k:pd.Timestamp(v) for k,v in protocol["boundaries"].items()}
        for fold in [1,2]:
            model=joblib.load(root/"development/lstm"/f"h{h}"/selected/f"fold{fold}.joblib")["return"]
            frame=task_frame(raw,model)
            _,valid=development_folds(frame,edges)[fold-1]
            positions=[]
            for indices in valid.groupby("ticker",sort=False).indices.values():
                positions.extend(np.asarray(indices)[np.linspace(0,len(indices)-1,min(32,len(indices)),dtype=int)])
            sample=valid.iloc[sorted(positions)].copy()
            original=np.stack(sample._sequence.to_numpy())
            baseline=score(sample,predict(model,sample),"return")["macro_rmse"]
            features=feature_weights(model).sort_values("importance",ascending=False).head(12).feature
            for column in features:
                j=model["columns"].index(column);mutated=original.copy();rng=np.random.default_rng(42)
                for indices in sample.groupby("ticker",sort=False).indices.values():
                    indices=np.asarray(indices);mutated[indices,:,j]=original[rng.permutation(indices),:,j]
                corrupted=sample.copy();corrupted["_sequence"]=pd.Series(list(mutated),index=sample.index,dtype=object)
                error=score(corrupted,predict(model,corrupted),"return")["macro_rmse"]
                rows.append(dict(horizon=h,fold=fold,feature=column,importance=error-baseline,baseline_rmse=baseline,permuted_rmse=error,rows=len(sample),
                    kind="Validation-window permutation delta macro RMSE; top 12 input-weight screened; <=32 origins per stock; not used for selection"))
            print(f"Permutation importance LSTM h{h} fold {fold}",flush=True)
    result=pd.DataFrame(rows);result.to_csv(root/"lstm_validation_permutation_importance.csv",index=False)
    for h,part in result.groupby("horizon"):
        table=part.groupby("feature",as_index=False).importance.mean();table["kind"]="Validation permutation delta RMSE (small fixed subset)"
        plot_importance(table,f"LSTM {h}: validation permutation audit",root/"charts"/f"permutation_lstm_h{h}")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,default=DEFAULT)
    generate(p.parse_args().output.resolve())
