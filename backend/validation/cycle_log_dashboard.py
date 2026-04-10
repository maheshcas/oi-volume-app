from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


DEFAULT_LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "optionlens_cycle_log.jsonl"


def _safe_get(obj: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = obj
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def load_jsonl(path: Path) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    rows: list[dict[str, Any]] = []
    for rec in records:
        rows.append(
            {
                "timestamp": rec.get("timestamp"),
                "spot": rec.get("spot", rec.get("spot_price")),
                "primary_bias": rec.get("primary_bias"),
                "bull_force": _safe_get(rec, "directional_force", "bull", default=None),
                "bear_force": _safe_get(rec, "directional_force", "bear", default=None),
                "clarity": rec.get("clarity"),
                "execution_risk": rec.get("execution_risk", rec.get("risk")),
                "trap_probability": rec.get("trap_probability"),
                "trap_type": rec.get("trap_type"),
                "trade_action": rec.get("trade_action"),
                "breakout_strength": rec.get("breakout_strength"),
                "rejection_wick_score": rec.get("rejection_wick_score"),
                "time_above_level_ratio": rec.get("time_above_level_ratio"),
                "oi_shift_score": rec.get("oi_shift_score"),
                "oi_velocity_score": rec.get("oi_velocity_score"),
                "volume_expansion_score": rec.get("volume_expansion_score"),
                "directional_pressure_score": rec.get("directional_pressure_score"),
                "dps_adjusted": rec.get("dps_adjusted"),
                "oi_scenario": rec.get("oi_scenario"),
                "dps_scenario_multiplier": rec.get("dps_scenario_multiplier"),
                "reversal_decay_cycles": rec.get("reversal_decay_cycles"),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    numeric_cols = [
        "spot",
        "bull_force",
        "bear_force",
        "clarity",
        "execution_risk",
        "trap_probability",
        "breakout_strength",
        "rejection_wick_score",
        "time_above_level_ratio",
        "oi_shift_score",
        "oi_velocity_score",
        "volume_expansion_score",
        "directional_pressure_score",
        "dps_adjusted",
        "dps_scenario_multiplier",
        "reversal_decay_cycles",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def _bias_flip_count(series: pd.Series) -> int:
    cleaned = series.fillna(method="ffill").fillna("Unknown")
    if cleaned.empty:
        return 0
    flips = (cleaned != cleaned.shift(1)).sum() - 1
    return int(max(0, flips))


def _plot_bias_segments(df: pd.DataFrame) -> go.Figure:
    color_map = {"Bullish": "#22c55e", "Bearish": "#ef4444", "Neutral": "#9ca3af"}
    fig = go.Figure()
    if df.empty:
        return fig

    run_start = 0
    values = df["primary_bias"].fillna("Neutral").tolist()
    for i in range(1, len(values) + 1):
        if i == len(values) or values[i] != values[run_start]:
            chunk = df.iloc[run_start:i]
            bias = values[run_start]
            fig.add_trace(
                go.Scatter(
                    x=chunk["timestamp"],
                    y=chunk["spot"],
                    mode="lines",
                    name=bias,
                    line={"color": color_map.get(bias, "#9ca3af"), "width": 3},
                    showlegend=False,
                )
            )
            run_start = i

    fig.update_layout(
        title="Primary Bias Timeline (spot colored by bias)",
        xaxis_title="Time",
        yaxis_title="Spot",
        template="plotly_dark",
        height=350,
    )
    return fig


def main() -> None:
    st.set_page_config(page_title="OptionLens Log Validation", layout="wide")
    st.title("OptionLens Cycle Log Validation Dashboard")

    st.sidebar.header("Input")
    path_text = st.sidebar.text_input("JSONL path", str(DEFAULT_LOG_PATH))
    uploaded = st.sidebar.file_uploader("Or upload JSONL", type=["jsonl", "log", "txt"])

    if uploaded is not None:
        temp_path = Path(".streamlit_uploaded_cycle_log.jsonl")
        temp_path.write_bytes(uploaded.getvalue())
        log_path = temp_path
    else:
        log_path = Path(path_text)

    if not log_path.exists():
        st.error(f"File not found: {log_path}")
        return

    df = load_jsonl(log_path)
    if df.empty:
        st.warning("No valid records found in log file.")
        return

    trap_mean = float(df["trap_probability"].mean(skipna=True))
    trap_max = float(df["trap_probability"].max(skipna=True))
    clarity_mean = float(df["clarity"].mean(skipna=True))
    bias_flip_count = _bias_flip_count(df["primary_bias"])
    dps_mean = float(df["dps_adjusted"].mean(skipna=True))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Trap Mean", f"{trap_mean:.2f}")
    c2.metric("Trap Max", f"{trap_max:.2f}")
    c3.metric("Clarity Mean", f"{clarity_mean:.2f}")
    c4.metric("Bias Flip Count", f"{bias_flip_count}")
    c5.metric("DPS Adj Mean", f"{dps_mean:.3f}")

    trap_fig = go.Figure()
    trap_fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["trap_probability"], mode="lines", name="Trap Probability", line={"color": "#f59e0b"})
    )
    spikes = df[df["trap_probability"] > 60]
    trap_fig.add_trace(
        go.Scatter(
            x=spikes["timestamp"],
            y=spikes["trap_probability"],
            mode="markers",
            name="Trap Spike > 60",
            marker={"color": "red", "size": 8},
        )
    )
    trap_fig.update_layout(title="Trap Probability Over Time", template="plotly_dark", height=320)

    force_fig = go.Figure()
    force_fig.add_trace(go.Scatter(x=df["timestamp"], y=df["bull_force"], mode="lines", name="Bull Force", line={"color": "#22c55e"}))
    force_fig.add_trace(go.Scatter(x=df["timestamp"], y=df["bear_force"], mode="lines", name="Bear Force", line={"color": "#ef4444"}))
    force_fig.update_layout(title="Bull vs Bear Force", template="plotly_dark", height=320)

    dps_fig = go.Figure()
    dps_fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["directional_pressure_score"],
            mode="lines",
            name="DPS Raw",
            line={"color": "#38bdf8"},
        )
    )
    dps_fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["dps_adjusted"],
            mode="lines",
            name="DPS Adjusted",
            line={"color": "#f59e0b"},
        )
    )
    dps_fig.update_layout(title="Directional Pressure Score (Raw vs Adjusted)", template="plotly_dark", height=320)

    clarity_fig = go.Figure()
    clarity_fig.add_trace(go.Scatter(x=df["timestamp"], y=df["clarity"], mode="lines", name="Clarity", line={"color": "#38bdf8"}))
    clarity_fig.update_layout(title="Structural Clarity Over Time", template="plotly_dark", height=320)

    risk_fig = go.Figure()
    risk_fig.add_trace(
        go.Scatter(x=df["timestamp"], y=df["execution_risk"], mode="lines", name="Execution Risk", line={"color": "#f87171"})
    )
    risk_fig.update_layout(title="Execution Risk Over Time", template="plotly_dark", height=320)

    row1_col1, row1_col2 = st.columns(2)
    row1_col1.plotly_chart(trap_fig, use_container_width=True)
    row1_col2.plotly_chart(force_fig, use_container_width=True)

    row2_col1, row2_col2 = st.columns(2)
    row2_col1.plotly_chart(dps_fig, use_container_width=True)
    row2_col2.plotly_chart(risk_fig, use_container_width=True)

    st.plotly_chart(clarity_fig, use_container_width=True)

    bias_fig = _plot_bias_segments(df)
    st.plotly_chart(bias_fig, use_container_width=True)

    h1, h2, h3 = st.columns(3)
    h1.plotly_chart(
        go.Figure(data=[go.Histogram(x=df["oi_shift_score"], marker={"color": "#38bdf8"})]).update_layout(
            title="Histogram: OI Shift Score", template="plotly_dark", height=300
        ),
        use_container_width=True,
    )
    h2.plotly_chart(
        go.Figure(data=[go.Histogram(x=df["volume_expansion_score"], marker={"color": "#34d399"})]).update_layout(
            title="Histogram: Volume Expansion Score", template="plotly_dark", height=300
        ),
        use_container_width=True,
    )
    h3.plotly_chart(
        go.Figure(data=[go.Histogram(x=df["breakout_strength"], marker={"color": "#f97316"})]).update_layout(
            title="Histogram: Breakout Strength", template="plotly_dark", height=300
        ),
        use_container_width=True,
    )

    st.subheader("OI Scenario Distribution")
    scenario_counts = (
        df["oi_scenario"].fillna("UNKNOWN").value_counts(dropna=False).rename_axis("oi_scenario").reset_index(name="count")
    )
    st.dataframe(scenario_counts, use_container_width=True, height=220)

    st.subheader("Raw Cycle Records")
    st.dataframe(df, use_container_width=True, height=320)


if __name__ == "__main__":
    main()
