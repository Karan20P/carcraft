import hashlib

from django import template

register = template.Library()

PAINTS = {
    "pearl white": "#e8e4dc",
    "white": "#e8e4dc",
    "midnight black": "#1b1f25",
    "black": "#1b1f25",
    "fire red": "#c4161c",
    "red": "#c4161c",
    "silky silver": "#aeb4bd",
    "silver": "#aeb4bd",
    "ocean blue": "#1d5bbf",
    "blue": "#1d5bbf",
    "granite grey": "#565d68",
    "grey": "#565d68",
    "gray": "#565d68",
}


@register.filter
def paint(color_name):
    """Map a vehicle colour name to a paint hex for the car silhouette."""
    key = (color_name or "").strip().lower()
    if key in PAINTS:
        return PAINTS[key]
    hue = int(hashlib.md5(key.encode()).hexdigest()[:4], 16) % 360
    return f"hsl({hue} 55% 42%)"


@register.filter
def pct_of(value, maximum):
    """value as a 0-100 percentage of maximum (clamped)."""
    try:
        return max(0, min(100, round(float(value) * 100 / float(maximum))))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0
