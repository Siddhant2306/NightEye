from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
import numpy as np
import pandas as pd
import pathlib as pl

PROJECT_ROOT = pl.Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_FILE = MODEL_DIR / "reliance_xgb.joblib"
PREDICTIONS_FILE = PROJECT_ROOT / "reports" / "reliance_test_predictions.csv"

def evaluate_model(model, X_test, y_test, test):
    predictions = model.predict(X_test)

    # Simple baseline: predict zero return every day.
    baseline = np.zeros(len(y_test))

    model_mae = mean_absolute_error(y_test, predictions)
    model_rmse = np.sqrt(mean_squared_error(y_test, predictions))

    baseline_mae = mean_absolute_error(y_test, baseline)
    baseline_rmse = np.sqrt(mean_squared_error(y_test, baseline))

    # Directional accuracy is descriptive, not a profitability measure.
    direction_accuracy = np.mean(
        np.sign(predictions) == np.sign(y_test.to_numpy())
    )

    print("\n========== TEST RESULTS ==========")
    print(f"XGBoost MAE:              {model_mae:.6f}")
    print(f"XGBoost RMSE:             {model_rmse:.6f}")
    print(f"Zero-return baseline MAE: {baseline_mae:.6f}")
    print(f"Zero-return baseline RMSE:{baseline_rmse:.6f}")
    print(f"Directional accuracy:     {direction_accuracy:.2%}")

    results = pd.DataFrame(
        {
            "actual_next_day_log_return": y_test,
            "predicted_log_return": predictions,
            "zero_return_baseline": baseline,
        },
        index=test.index,
    )
    results.index.name = "Date"

    PREDICTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(PREDICTIONS_FILE)

    print(f"\nTest predictions saved to: {PREDICTIONS_FILE}")

    return {
        "mae": float(model_mae),
        "rmse": float(model_rmse),
        "baseline_mae": float(baseline_mae),
        "baseline_rmse": float(baseline_rmse),
        "directional_accuracy": float(direction_accuracy),
    }


# --------------------------------------------------
# 7. Save the model artifact
# --------------------------------------------------

def save_model(model, feature_cols, metrics):
    artifact = {
        "model": model,
        "feature_cols": feature_cols,
        "ticker": "RELIANCE.NS",
        "target": "next_trading_day_log_return",
        "metrics": metrics,
    }

    joblib.dump(artifact, MODEL_FILE)
    print(f"Saved trained model to: {MODEL_FILE}")


