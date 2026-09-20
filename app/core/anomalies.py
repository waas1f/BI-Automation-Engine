"""Anomaly detection: identify unusual values using statistical methods."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.utils import logger


def detect_numeric_anomalies(series: pd.Series, col_name: str, method: str = "iqr") -> list[dict]:
    """Detect anomalies in a numeric series using IQR or z-score."""
    clean = series.dropna()
    if len(clean) < 4:
        return []

    anomalies = []
    q1 = float(clean.quantile(0.25))
    q3 = float(clean.quantile(0.75))
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    outliers = clean[(clean < lower_bound) | (clean > upper_bound)]
    if len(outliers) == 0:
        return []

    # Only report if outliers are a small fraction (< 20% of data)
    outlier_pct = len(outliers) / len(clean) * 100
    if outlier_pct > 20:
        return []

    for idx, val in outliers.items():
        direction = "high" if val > upper_bound else "low"
        anomalies.append({
            "column": col_name,
            "index": str(idx),
            "value": round(float(val), 2),
            "direction": direction,
            "lower_bound": round(lower_bound, 2),
            "upper_bound": round(upper_bound, 2),
            "method": method,
        })

    return anomalies


def detect_trend_anomalies(time_series: dict) -> list[dict]:
    """Detect sudden changes in time series data."""
    anomalies = []
    monthly = time_series.get("monthly_totals", {})
    if len(monthly) < 3:
        return anomalies

    values = list(monthly.values())
    keys = list(monthly.keys())

    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        if prev > 0:
            change_pct = ((curr - prev) / abs(prev)) * 100
            if abs(change_pct) > 30:
                anomalies.append({
                    "period": keys[i],
                    "previous_period": keys[i - 1],
                    "change_pct": round(change_pct, 1),
                    "direction": "surge" if change_pct > 0 else "drop",
                    "value": curr,
                    "previous_value": prev,
                })

    return anomalies


def detect_concentration_risk(category_data: dict, threshold: float = 25.0) -> list[dict]:
    """Detect customer/supplier concentration risks."""
    anomalies = []
    top = category_data.get("top", [])
    if not top:
        return anomalies

    for item in top:
        if item["pct"] >= threshold:
            anomalies.append({
                "entity": item["name"],
                "share_pct": item["pct"],
                "risk_level": "high" if item["pct"] >= 35 else "moderate",
                "description": f"{item['name']} accounts for {item['pct']}% of total.",
            })

    return anomalies


def detect_all_anomalies(df: pd.DataFrame, analytics_result) -> list[dict]:
    """Run all anomaly detection checks on a dataframe and analytics result."""
    all_anomalies = []

    # Numeric anomalies
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        anomalies = detect_numeric_anomalies(df[col], col)
        all_anomalies.extend(anomalies)

    # Trend anomalies
    if analytics_result.time_analysis:
        trend_anomalies = detect_trend_anomalies(analytics_result.time_analysis)
        all_anomalies.extend(trend_anomalies)

    # Concentration risks (from product_analysis if available, otherwise category_analysis)
    cat_data = analytics_result.product_analysis or analytics_result.category_analysis
    if cat_data:
        conc_anomalies = detect_concentration_risk(cat_data)
        all_anomalies.extend(conc_anomalies)

    return all_anomalies
