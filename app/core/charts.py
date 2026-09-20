"""Chart generation using matplotlib."""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from app.core.models import AnalysisResult
from app.core.utils import ensure_dir, format_currency

# Professional color palette
COLORS = ["#2E86AB", "#A23B72", "#F18F01", "#2D8659", "#C73E1D", "#5C8001", "#8338EC", "#3A86FF"]
BG_COLOR = "#FAFAFA"
GRID_COLOR = "#E0E0E0"


def _setup_axes(ax, title: str, ylabel: str = "", xlabel: str = ""):
    ax.set_title(title, fontsize=13, fontweight="bold", pad=15, color="#333333")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10, color="#555555")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10, color="#555555")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.grid(True, axis="y", color=GRID_COLOR, linewidth=0.7, alpha=0.7)
    ax.set_facecolor(BG_COLOR)


def generate_revenue_trend_chart(time_analysis: dict, output_path: str, title: str = "Revenue Trend") -> str | None:
    """Generate a revenue trend chart from monthly totals."""
    monthly = time_analysis.get("monthly_totals", {})
    if len(monthly) < 2:
        return None

    labels = list(monthly.keys())
    values = list(monthly.values())

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(labels, values, marker="o", color=COLORS[0], linewidth=2, markersize=6)
    ax.fill_between(range(len(labels)), values, alpha=0.15, color=COLORS[0])
    _setup_axes(ax, title, ylabel="Revenue")

    # Format y-axis
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    plt.xticks(rotation=45, ha="right", fontsize=9)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def generate_top_items_chart(category_analysis: dict, output_path: str, title: str = "Top Items by Revenue") -> str | None:
    """Generate a horizontal bar chart of top items."""
    top = category_analysis.get("top", [])
    if not top:
        return None

    names = [item["name"][:25] for item in top[:8]]
    values = [item["value"] for item in top[:8]]

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(names[::-1], values[::-1], color=COLORS[1])
    _setup_axes(ax, title, xlabel="Revenue")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def generate_concentration_chart(category_analysis: dict, output_path: str, title: str = "Revenue Distribution") -> str | None:
    """Generate a pie/donut chart showing revenue distribution."""
    top = category_analysis.get("top", [])
    total = category_analysis.get("total_value", 0)
    if not top or total == 0:
        return None

    top_sum = sum(item["value"] for item in top[:5])
    other = total - top_sum
    labels = [item["name"][:20] for item in top[:5]]
    values = [item["value"] for item in top[:5]]
    if other > 0:
        labels.append("Others")
        values.append(other)

    # Filter out negative or zero values (pie charts can't handle negatives)
    filtered = [(l, v) for l, v in zip(labels, values) if v > 0]
    if not filtered:
        return None
    labels, values = zip(*filtered)
    labels, values = list(labels), list(values)

    fig, ax = plt.subplots(figsize=(7, 5))
    colors = COLORS[:len(labels)]
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct="%1.1f%%", startangle=90,
        colors=colors, pctdistance=0.85,
    )
    for text in autotexts:
        text.set_fontsize(8)
    centre_circle = plt.Circle((0, 0), 0.70, fc="white")
    ax.add_artist(centre_circle)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=15, color="#333333")
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def generate_margin_chart(profitability: dict, output_path: str, title: str = "Profitability Overview") -> str | None:
    """Generate a simple profitability bar chart."""
    if not profitability or "gross_margin_pct" not in profitability:
        return None

    revenue = profitability.get("total_revenue", 0)
    cost = profitability.get("total_cost", 0)
    profit = profitability.get("gross_profit", 0)
    margin = profitability.get("gross_margin_pct", 0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 3.5))

    # Revenue vs Cost vs Profit
    labels = ["Revenue", "Cost", "Profit"]
    values = [revenue, cost, profit]
    colors = [COLORS[0], COLORS[4], COLORS[3]]
    ax1.bar(labels, values, color=colors)
    _setup_axes(ax1, "Revenue vs Cost vs Profit", ylabel="Amount")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    # Margin gauge
    ax2.barh(["Margin"], [margin], color=COLORS[3])
    ax2.set_xlim(0, 100)
    _setup_axes(ax2, "Gross Margin %", xlabel="%")

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def generate_daily_trend_chart(time_analysis: dict, output_path: str, title: str = "Daily Revenue") -> str | None:
    """Generate a daily revenue bar chart."""
    daily = time_analysis.get("daily_totals", {})
    if len(daily) < 2:
        return None

    # Limit to last 30 days for readability
    items = list(daily.items())[-30:]
    labels = [k for k, _ in items]
    values = [v for _, v in items]

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.bar(labels, values, color=COLORS[0], alpha=0.8)
    _setup_axes(ax, title, ylabel="Revenue")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    # Show only every Nth label to avoid overlap
    n = len(labels)
    step = max(1, n // 10)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([labels[i] for i in range(0, n, step)], rotation=45, ha="right", fontsize=7)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def generate_charts_for_result(result: AnalysisResult, output_dir: str) -> dict[str, str]:
    """Generate all relevant charts for an analysis result."""
    charts = {}
    ensure_dir(output_dir)

    prefix = result.entity_type

    # Revenue trend
    if result.time_analysis and result.time_analysis.get("monthly_totals"):
        path = os.path.join(output_dir, f"{prefix}_revenue_trend.png")
        chart = generate_revenue_trend_chart(result.time_analysis, path, f"{prefix.title()} Revenue Trend")
        if chart:
            charts[f"{prefix}_revenue_trend"] = chart

    # Daily trend
    if result.time_analysis and result.time_analysis.get("daily_totals"):
        path = os.path.join(output_dir, f"{prefix}_daily_trend.png")
        chart = generate_daily_trend_chart(result.time_analysis, path, f"{prefix.title()} Daily Revenue")
        if chart:
            charts[f"{prefix}_daily_trend"] = chart

    # Top items (from product_analysis if available, otherwise category_analysis)
    cat_data = result.product_analysis or result.category_analysis
    if cat_data and cat_data.get("top"):
        dim_label = cat_data.get("dimension", result.entity_type)
        path = os.path.join(output_dir, f"{prefix}_top_items.png")
        chart = generate_top_items_chart(cat_data, path, f"Top {dim_label.title()} by Revenue")
        if chart:
            charts[f"{prefix}_top_items"] = chart

    # Concentration
    if cat_data and cat_data.get("top"):
        path = os.path.join(output_dir, f"{prefix}_concentration.png")
        chart = generate_concentration_chart(cat_data, path, f"{dim_label.title()} Revenue Distribution")
        if chart:
            charts[f"{prefix}_concentration"] = chart

    # Profitability
    if result.profitability:
        path = os.path.join(output_dir, f"{prefix}_profitability.png")
        chart = generate_margin_chart(result.profitability, path, f"{prefix.title()} Profitability")
        if chart:
            charts[f"{prefix}_profitability"] = chart

    return charts
