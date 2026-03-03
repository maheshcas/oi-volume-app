from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


REQUIRED_COLUMNS = {
    "timestamp",
    "smoothed_score",
    "confidence",
    "alignment_ratio",
    "trap_risk",
    "volume_ratio",
    "regime",
    "projection",
    "actual_5min_move",
    "actual_15min_move",
    "actual_direction",
}

PERCENTILES = [50, 60, 70, 75, 80, 85, 90]


def load_dataset(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found: {p}")

    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Dataset must be a JSON list of snapshot objects.")

    df = pd.DataFrame(raw)
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    for col in ["smoothed_score", "confidence", "alignment_ratio", "trap_risk", "volume_ratio", "actual_5min_move"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["smoothed_score", "confidence", "alignment_ratio", "trap_risk", "volume_ratio", "actual_direction"])
    df["regime"] = df["regime"].astype(str).str.title()
    df["actual_direction"] = df["actual_direction"].astype(str).str.title()
    return df


def compute_percentile_report(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    metrics = {
        "abs_smoothed_score": df["smoothed_score"].abs(),
        "confidence": df["confidence"],
        "alignment_ratio": df["alignment_ratio"],
        "trap_risk": df["trap_risk"],
        "volume_ratio": df["volume_ratio"],
    }
    report: dict[str, dict[str, float]] = {}
    for name, series in metrics.items():
        report[name] = {f"p{p}": round(float(np.percentile(series, p)), 6) for p in PERCENTILES}
    return report


def predict_direction_from_score(score: float, threshold: float) -> str:
    if score > threshold:
        return "Bullish"
    if score < -threshold:
        return "Bearish"
    return "Neutral"


def evaluate_bias_threshold(df: pd.DataFrame, threshold: float) -> dict[str, float]:
    pred = df["smoothed_score"].apply(lambda x: predict_direction_from_score(float(x), threshold))
    actual = df["actual_direction"]

    accuracy = float(accuracy_score(actual, pred))
    precision = float(precision_score(actual, pred, average="macro", zero_division=0))
    recall = float(recall_score(actual, pred, average="macro", zero_division=0))
    f1 = float(f1_score(actual, pred, average="macro", zero_division=0))

    # Directional FP rate: predicted Bullish/Bearish but actual not matching that direction.
    directional_pred = pred.isin(["Bullish", "Bearish"])
    directional_fp = directional_pred & (pred != actual)
    fp_rate = float(directional_fp.sum() / max(1, directional_pred.sum()))

    return {
        "threshold": round(threshold, 4),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp_rate,
    }


def optimize_bias_threshold(df: pd.DataFrame) -> tuple[float, dict[str, float], pd.DataFrame]:
    rows: list[dict[str, float]] = []
    for t in np.arange(0.10, 0.5001, 0.02):
        rows.append(evaluate_bias_threshold(df, float(round(t, 4))))
    perf = pd.DataFrame(rows)
    best = perf.sort_values(["f1", "accuracy"], ascending=[False, False]).iloc[0].to_dict()
    return float(best["threshold"]), best, perf


def _is_reversal(row: pd.Series) -> bool:
    score = float(row["smoothed_score"])
    move_5m = float(row["actual_5min_move"])
    if score > 0:
        return move_5m < 0
    if score < 0:
        return move_5m > 0
    return abs(move_5m) < 1e-9


def evaluate_trap_threshold(df: pd.DataFrame, threshold: float) -> dict[str, float]:
    pred_reversal = df["trap_risk"] > threshold
    actual_reversal = df.apply(_is_reversal, axis=1)

    reversal_accuracy = float(accuracy_score(actual_reversal, pred_reversal))
    false_trap = pred_reversal & (~actual_reversal)
    false_trap_rate = float(false_trap.sum() / max(1, pred_reversal.sum()))
    f1 = float(f1_score(actual_reversal, pred_reversal, zero_division=0))

    return {
        "threshold": round(threshold, 4),
        "reversal_accuracy": reversal_accuracy,
        "false_trap_rate": false_trap_rate,
        "f1": f1,
    }


def optimize_trap_threshold(df: pd.DataFrame) -> tuple[float, dict[str, float]]:
    rows = [evaluate_trap_threshold(df, float(round(t, 4))) for t in np.arange(0.40, 0.9001, 0.05)]
    perf = pd.DataFrame(rows)
    best = perf.sort_values(["f1", "reversal_accuracy"], ascending=[False, False]).iloc[0].to_dict()
    return float(best["threshold"]), best


def evaluate_confidence_gate(df: pd.DataFrame, bias_threshold: float, conf_threshold: float) -> dict[str, float]:
    raw_pred = df["smoothed_score"].apply(lambda x: predict_direction_from_score(float(x), bias_threshold))
    gated_pred = np.where(df["confidence"] < conf_threshold, "Neutral", raw_pred)
    actual = df["actual_direction"]

    accuracy = float(accuracy_score(actual, gated_pred))
    f1 = float(f1_score(actual, gated_pred, average="macro", zero_division=0))

    directional_pred = pd.Series(gated_pred).isin(["Bullish", "Bearish"])
    directional_fp = directional_pred & (pd.Series(gated_pred) != actual.reset_index(drop=True))
    false_signal_rate = float(directional_fp.sum() / max(1, directional_pred.sum()))

    return {
        "threshold": round(conf_threshold, 4),
        "accuracy": accuracy,
        "f1": f1,
        "false_signal_rate": false_signal_rate,
    }


def optimize_confidence_threshold(df: pd.DataFrame, bias_threshold: float) -> tuple[float, dict[str, float]]:
    rows = [evaluate_confidence_gate(df, bias_threshold, float(round(t, 4))) for t in np.arange(0.10, 0.6001, 0.05)]
    perf = pd.DataFrame(rows)
    best = perf.sort_values(["false_signal_rate", "f1", "accuracy"], ascending=[True, False, False]).iloc[0].to_dict()
    return float(best["threshold"]), best


def regime_specific_analysis(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for regime in ["Trend", "Range", "Transition"]:
        subset = df[df["regime"] == regime]
        if subset.empty:
            output[regime] = {
                "optimal_bias_threshold": 0.2,
                "optimal_trap_threshold": 0.6,
                "optimal_confidence_threshold": 0.3,
            }
            continue

        bias_t, _, _ = optimize_bias_threshold(subset)
        trap_t, _ = optimize_trap_threshold(subset)
        conf_t, _ = optimize_confidence_threshold(subset, bias_t)
        output[regime] = {
            "optimal_bias_threshold": round(bias_t, 4),
            "optimal_trap_threshold": round(trap_t, 4),
            "optimal_confidence_threshold": round(conf_t, 4),
        }
    return output


def build_calibration_report(df: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    percentiles = compute_percentile_report(df)

    bias_threshold, bias_best, bias_perf_df = optimize_bias_threshold(df)
    trap_threshold, trap_best = optimize_trap_threshold(df)
    conf_threshold, _ = optimize_confidence_threshold(df, bias_threshold)

    report = {
        "percentiles": percentiles,
        "optimal_bias_threshold": round(bias_threshold, 4),
        "optimal_trap_threshold": round(trap_threshold, 4),
        "optimal_confidence_threshold": round(conf_threshold, 4),
        "regime_specific_thresholds": regime_specific_analysis(df),
        "evaluation_summary": {
            "best_accuracy": round(float(bias_best["accuracy"]), 6),
            "best_f1_score": round(float(bias_best["f1"]), 6),
            "false_positive_rate": round(float(bias_best["false_positive_rate"]), 6),
            "trap_reversal_accuracy": round(float(trap_best["reversal_accuracy"]), 6),
            "trap_false_rate": round(float(trap_best["false_trap_rate"]), 6),
        },
    }
    return report, bias_perf_df


def plot_threshold_performance(perf_df: pd.DataFrame) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("matplotlib is required for plotting. Install it to use --plot.") from exc

    plt.figure(figsize=(8, 4))
    plt.plot(perf_df["threshold"], perf_df["accuracy"], label="Accuracy")
    plt.plot(perf_df["threshold"], perf_df["f1"], label="F1")
    plt.xlabel("Bias Threshold")
    plt.ylabel("Score")
    plt.title("Threshold vs Performance")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate OptionLens thresholds from historical snapshots.")
    parser.add_argument("dataset_path", type=str, help="Path to JSON file containing historical snapshots list.")
    parser.add_argument("--plot", action="store_true", help="Plot threshold vs accuracy/F1 curve.")
    args = parser.parse_args()

    df = load_dataset(args.dataset_path)
    report, bias_perf_df = build_calibration_report(df)
    print(json.dumps(report, indent=2))

    if args.plot:
        plot_threshold_performance(bias_perf_df)


if __name__ == "__main__":
    main()
