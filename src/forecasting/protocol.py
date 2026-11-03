"""Common date boundaries, never shuffled; purge labels crossing every boundary."""
import numpy as np
import pandas as pd


def boundaries(dates):
    dates = pd.DatetimeIndex(dates).unique().sort_values()
    if len(dates) < 1500:
        raise ValueError("Need at least 1500 origin dates for this three-horizon protocol")
    return {name: dates[int(len(dates)*fraction)] for name, fraction in
            [("fold1", .40), ("fold2", .52), ("calibration", .64), ("test", .80)]}


def before(frame, boundary):
    return frame.loc[(frame.index < boundary) & (frame.target_date < boundary)]


def window(frame, start, end):
    return frame.loc[(frame.index >= start) & (frame.index < end) & (frame.target_date < end)]


def partitions(frame, edges, holdouts):
    development = frame.loc[~frame.ticker.isin(holdouts)]
    folds = []
    for start, end in [(edges["fold1"], edges["fold2"]), (edges["fold2"], edges["calibration"])]:
        folds.append((before(development, start), window(development, start, end)))
    fit = before(development, edges["calibration"])
    cal = window(development, edges["calibration"], edges["test"])
    test = frame.loc[frame.index >= edges["test"]]
    if any(len(x) < 100 for pair in folds for x in pair) or min(len(fit), len(cal), len(test)) < 100:
        raise ValueError("Insufficient mature labels after purging; add history rather than removing the purge")
    return folds, fit, cal, test


def span(frame):
    return dict(rows=len(frame), stocks=int(frame.ticker.nunique()), dates=int(frame.index.nunique()),
                first=str(frame.index.min().date()), last=str(frame.index.max().date()),
                latest_label=str(pd.Timestamp(frame.target_date.max()).date()))
