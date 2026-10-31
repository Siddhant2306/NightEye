"""Train-only preprocessing; causal per-company windows; explicit saved weights."""
import copy
import warnings
import numpy as np
import pandas as pd
import torch
from torch import nn
from src.pipeline import weights


class Network(nn.Module):
    def __init__(self, features, hidden=16, dropout=.1):
        super().__init__()
        self.lstm = nn.LSTM(features*2, hidden, batch_first=True)
        self.dropout = nn.Dropout(dropout)
        self.return_head = nn.Linear(hidden, 1)
        self.direction_head = nn.Linear(hidden, 1)

    def forward(self, x):
        sequence, _ = self.lstm(x)
        last = self.dropout(sequence[:, -1])
        return self.return_head(last).squeeze(-1), self.direction_head(last).squeeze(-1)


def sequences(panel, columns, lookback=20):
    if lookback < 2 or len(set(columns)) != len(columns):
        raise ValueError("Use unique columns and a lookback of at least two sessions")
    panel=panel.copy()
    panel["_sequence_order"]=np.arange(len(panel))
    parts = []
    for ticker, stock in panel.groupby("ticker", sort=False):
        stock = stock.sort_index().copy()
        if stock.index.has_duplicates:
            raise ValueError("Duplicate date within a stock sequence")
        if len(stock) < lookback:
            continue
        values = stock[columns].to_numpy(dtype=np.float32)
        windows = np.lib.stride_tricks.sliding_window_view(values, lookback, axis=0).transpose(0, 2, 1)
        stock = stock.iloc[lookback-1:].copy()
        # Views share a compact base matrix; batches materialize only their own windows.
        stock["_sequence"] = pd.Series(list(windows), index=stock.index, dtype=object)
        stock["_sequence_start"] = panel.loc[panel.ticker == ticker].sort_index().index[:len(stock)].to_numpy()
        parts.append(stock)
    if not parts:
        raise ValueError("Not enough historical rows for sequence construction")
    return pd.concat(parts).sort_values("_sequence_order").drop(columns="_sequence_order")


def preprocessing(training, columns):
    values = training[columns].to_numpy(dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        center = np.nanmedian(values, axis=0)
        spread = np.nanstd(values, axis=0)
    return np.nan_to_num(center, nan=0.).astype(np.float32), np.where(np.isfinite(spread) & (spread > 1e-8), spread, 1.).astype(np.float32)


def tensor_batch(frame, indices, center, spread):
    raw = np.stack(frame["_sequence"].iloc[indices].to_numpy())
    missing = ~np.isfinite(raw)
    values = np.where(missing, center[None, None, :], raw)
    scaled = np.clip((values-center)/spread, -10, 10)
    return torch.from_numpy(np.concatenate([scaled, missing.astype(np.float32)], axis=2).astype(np.float32))


def fit(training, valid, columns, config, epochs=8, patience=3):
    torch.set_num_threads(2)
    torch.manual_seed(42)
    torch.use_deterministic_algorithms(True)
    rng = np.random.default_rng(42)
    center, spread = preprocessing(training, columns)
    target_center = float(training.target.mean())
    target_scale = max(float(training.target.std()), 1e-8)
    model = Network(len(columns), config["hidden"], config["dropout"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    batch_size = config.get("batch_size", 512)
    y = torch.tensor((training.target.to_numpy()-target_center)/target_scale, dtype=torch.float32)
    direction = torch.tensor((training.target.to_numpy() > 0).astype(np.float32))
    sample_weights = torch.tensor(weights(training), dtype=torch.float32)
    best_loss, best_state, best_epoch, stale = float("inf"), None, 0, 0
    curves = []
    for epoch in range(1, epochs+1):
        model.train()
        order = rng.permutation(len(training))
        total = 0.
        for start in range(0, len(order), batch_size):
            indices = order[start:start+batch_size]
            optimizer.zero_grad()
            pred, logits = model(tensor_batch(training, indices, center, spread))
            loss_each = (pred-y[indices])**2+.25*nn.functional.binary_cross_entropy_with_logits(logits, direction[indices], reduction="none")
            loss = (loss_each*sample_weights[indices]).mean()
            if not torch.isfinite(loss):
                raise ValueError("Nonfinite LSTM training loss")
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
            total += float(loss.detach())*len(indices)
        record = dict(epoch=epoch, training_loss=total/len(training))
        if valid is not None:
            estimate, probability = infer(model, valid, center, spread)
            actual = (valid.target.to_numpy()-target_center)/target_scale
            labels = (valid.target.to_numpy() > 0).astype(float)
            probability = np.clip(probability, 1e-7, 1-1e-7)
            loss_each = (estimate-actual)**2+.25*(-labels*np.log(probability)-(1-labels)*np.log(1-probability))
            val_loss = float(np.mean(loss_each*weights(valid)))
            record["validation_loss"] = val_loss
            if val_loss < best_loss-1e-5:
                best_loss, best_epoch, stale = val_loss, epoch, 0
                best_state = copy.deepcopy(model.state_dict())
            else:
                stale += 1
        else:
            best_epoch = epoch
        curves.append(record)
        print(f"    epoch {epoch}/{epochs}: {record}", flush=True)
        if valid is not None and stale >= patience:
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    shared = dict(algorithm="lstm", columns=columns, config=config, lookback=int(training._sequence.iloc[0].shape[0]),
        feature_center=center, feature_spread=spread,
        state={k:v.detach().cpu().numpy().copy() for k,v in model.state_dict().items()},
        rounds=best_epoch, learning_curve=curves)
    regression = dict(shared, task="return", center=target_center, scale=target_scale)
    classifier = dict(shared, task="direction", center=0., scale=1.)
    return regression, classifier


def infer(model, frame, center, spread, batch_size=1024):
    model.eval()
    returns, probabilities = [], []
    with torch.inference_mode():
        for start in range(0, len(frame), batch_size):
            indices = np.arange(start, min(start+batch_size, len(frame)))
            pred, logits = model(tensor_batch(frame, indices, center, spread))
            returns.append(pred.numpy())
            probabilities.append(torch.sigmoid(logits).numpy())
    return np.concatenate(returns), np.concatenate(probabilities)


def predict(bundle, frame):
    torch.set_num_threads(2)
    if "_sequence" not in frame:
        raise ValueError("LSTM requires complete per-stock sequences; pass full feature history through sequences()")
    model = Network(len(bundle["columns"]), bundle["config"]["hidden"], bundle["config"]["dropout"])
    model.load_state_dict({k:torch.from_numpy(v.copy()) for k,v in bundle["state"].items()})
    returns, probability = infer(model, frame, bundle["feature_center"], bundle["feature_spread"])
    prediction = returns.astype(float)*bundle["scale"]+bundle["center"] if bundle["task"] == "return" else probability.astype(float)
    if not np.isfinite(prediction).all():
        raise ValueError("Nonfinite LSTM predictions")
    return prediction
