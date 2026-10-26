"""
Inventory Aging & Price Advisor (novelty feature).

Every car that sits on the lot costs the dealership money (floor-plan interest,
insurance, depreciation). The advisor looks at how long a car has been in stock
and suggests a markdown so aging stock gets sold before it loses more value.

Rules are cumulative from the car's *current* price and never go below a
minimum-margin floor over cost.
"""
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

# (minimum days on lot, markdown %, stage key, label, bootstrap colour)
AGING_RULES = [
    (120, Decimal("8"), "critical", "Critical - consider wholesale/auction", "danger"),
    (90, Decimal("5"), "stale", "Stale", "danger"),
    (45, Decimal("2"), "aging", "Aging", "warning"),
    (0, Decimal("0"), "fresh", "Fresh", "success"),
]

# Never suggest a price that leaves less than this margin over cost.
MIN_MARGIN_PERCENT = Decimal("2")

# Estimated daily holding cost as a % of cost price (interest + insurance + lot).
DAILY_HOLDING_COST_PERCENT = Decimal("0.05")


@dataclass
class PriceAdvice:
    stage: str
    stage_label: str
    color: str
    markdown_percent: Decimal
    current_price: Decimal
    suggested_price: Decimal
    floor_price: Decimal
    holding_cost: Decimal
    hit_floor: bool

    @property
    def needs_action(self):
        return self.suggested_price < self.current_price

    @property
    def saving(self):
        return self.current_price - self.suggested_price


def _round_price(value):
    """Round down to the nearest 500 - dealers like clean sticker prices."""
    return (value / 500).quantize(Decimal("1"), rounding=ROUND_DOWN) * 500


def advise(days_on_lot, list_price, cost_price, original_price=None):
    """
    Markdown % is measured against the car's *original* listing price, so a
    stage's markdown is applied once - pressing "apply" twice does nothing more.
    """
    list_price = Decimal(list_price)
    cost_price = Decimal(cost_price)
    original_price = Decimal(original_price) if original_price else list_price

    for min_days, percent, stage, label, color in AGING_RULES:
        if days_on_lot >= min_days:
            break

    floor_price = (cost_price * (1 + MIN_MARGIN_PERCENT / 100)).quantize(Decimal("1"))
    target = _round_price(original_price * (1 - percent / 100)) if percent else original_price
    hit_floor = target < floor_price
    # Never go below the floor, and never suggest *raising* the price.
    suggested = min(list_price, max(target, floor_price))

    holding_cost = (cost_price * DAILY_HOLDING_COST_PERCENT / 100 * days_on_lot).quantize(Decimal("1"))

    return PriceAdvice(
        stage=stage,
        stage_label=label,
        color=color,
        markdown_percent=percent,
        current_price=list_price,
        suggested_price=suggested,
        floor_price=floor_price,
        holding_cost=holding_cost,
        hit_floor=hit_floor,
    )
