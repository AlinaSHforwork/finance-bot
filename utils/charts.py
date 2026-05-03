import io
from decimal import Decimal
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


_PALETTE = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
]


def _fig_to_bytes(fig: plt.Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#1a1a2e")
    buf.seek(0)
    data = buf.read()
    plt.close(fig)
    return data


def generate_expense_pie(
    category_totals: list[tuple[str, Decimal]],
    currency: str,
    title: str = "Expenses by Category",
) -> Optional[bytes]:
    if not category_totals:
        return None

    labels = [cat.capitalize() for cat, _ in category_totals]
    values = [float(amt) for _, amt in category_totals]

    fig, ax = plt.subplots(figsize=(7, 5), facecolor="#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,
        autopct="%1.1f%%",
        colors=_PALETTE[: len(values)],
        startangle=140,
        wedgeprops={"linewidth": 1.5, "edgecolor": "#1a1a2e"},
        pctdistance=0.82,
    )

    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(9)

    legend_labels = [
        f"{lbl}  {v:.2f} {currency}"
        for lbl, v in zip(labels, values)
    ]
    patches = [
        mpatches.Patch(color=_PALETTE[i % len(_PALETTE)], label=legend_labels[i])
        for i in range(len(labels))
    ]
    ax.legend(
        handles=patches,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=2,
        fontsize=8,
        framealpha=0.2,
        labelcolor="white",
        facecolor="#1a1a2e",
        edgecolor="#555",
    )

    ax.set_title(title, color="white", fontsize=13, fontweight="bold", pad=14)
    return _fig_to_bytes(fig)


def generate_budget_bar(
    budgets: list[tuple[str, Decimal, Decimal]],
    currency: str,
) -> Optional[bytes]:
    if not budgets:
        return None

    categories = [b[0].capitalize() for b in budgets]
    limits = [float(b[1]) for b in budgets]
    spent = [float(b[2]) for b in budgets]

    x = range(len(categories))
    fig, ax = plt.subplots(figsize=(max(6, len(categories) * 1.2), 5), facecolor="#1a1a2e")
    ax.set_facecolor("#16213e")

    bar_width = 0.35
    bars_limit = ax.bar(
        [i - bar_width / 2 for i in x], limits, bar_width,
        label="Budget", color="#4C72B0", alpha=0.85,
    )
    bars_spent = ax.bar(
        [i + bar_width / 2 for i in x], spent, bar_width,
        label="Spent",
        color=["#C44E52" if s > l else "#55A868" for s, l in zip(spent, limits)],
        alpha=0.9,
    )

    ax.set_xticks(list(x))
    ax.set_xticklabels(categories, color="white", fontsize=9)
    ax.tick_params(colors="white")
    ax.spines["bottom"].set_color("#555")
    ax.spines["left"].set_color("#555")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylabel(currency, color="white", fontsize=10)
    ax.set_title("Budget vs Spending", color="white", fontsize=13, fontweight="bold")
    ax.legend(labelcolor="white", facecolor="#1a1a2e", edgecolor="#555", fontsize=9)
    ax.yaxis.label.set_color("white")

    return _fig_to_bytes(fig)


def generate_monthly_trend(
    daily_totals: list[tuple[str, Decimal]],
    currency: str,
) -> Optional[bytes]:
    if not daily_totals:
        return None

    dates = [d[0] for d in daily_totals]
    amounts = [float(d[1]) for d in daily_totals]

    fig, ax = plt.subplots(figsize=(9, 4), facecolor="#1a1a2e")
    ax.set_facecolor("#16213e")

    ax.fill_between(range(len(dates)), amounts, alpha=0.25, color="#4C72B0")
    ax.plot(range(len(dates)), amounts, color="#4C72B0", linewidth=2, marker="o", markersize=4)

    step = max(1, len(dates) // 7)
    ax.set_xticks(range(0, len(dates), step))
    ax.set_xticklabels([dates[i] for i in range(0, len(dates), step)], color="white", fontsize=8, rotation=30)
    ax.tick_params(colors="white")
    ax.spines["bottom"].set_color("#555")
    ax.spines["left"].set_color("#555")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylabel(currency, color="white")
    ax.set_title("Daily Expenses Trend", color="white", fontsize=13, fontweight="bold")

    return _fig_to_bytes(fig)