import pandas as pd
import pathlib as pl

DATA_FILE = pl.Path("data/RELIANCE.NS_2000-01-01_to_2025-12-31.csv")

def load_data(path=None):
    path = pl.Path(path) if path else pl.Path(__file__).resolve().parents[2] / DATA_FILE
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    df = pd.read_csv(path)

    # Find the date column, including common CSV index names.
    date_col = next(
        (col for col in df.columns
         if str(col).strip().lower() in ("date", "datetime")),
        None,
    )

    if date_col is None:
        date_col = df.columns[0]

    df[date_col] = pd.to_datetime(df[date_col],format="%Y-%m-%d",errors="coerce",)
    df = df.dropna(subset=[date_col]).set_index(date_col)
    df.index.name = "Date"

    # Normalize column names.
    df.columns = [str(col).strip().lower() for col in df.columns]

    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns: {sorted(missing)}. "
            f"Available columns: {list(df.columns)}"
        )

    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    before_cleaning = len(df)
    df = df.dropna(subset=list(required))
    if len(df) < before_cleaning:
        print(f"Discarded {before_cleaning-len(df)} rows with incomplete OHLCV from {path.name}")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError(f"Nonpositive prices in {path}")
    if (df["volume"] < 0).any():
        raise ValueError(f"Negative volume in {path}")

    if df.empty:
        raise ValueError("No valid historical rows remain after cleaning.")

    print(f"Data range: {df.index.min().date()} to {df.index.max().date()}")
    print(f"Valid rows: {len(df)}")

    return df
