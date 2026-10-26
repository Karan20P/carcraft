"""Session-based shopping cart: {part_id: quantity}."""
from decimal import Decimal

from .models import Part

SESSION_KEY = "cart"


class Cart:
    def __init__(self, request):
        self.session = request.session
        self.data = self.session.setdefault(SESSION_KEY, {})

    def _save(self):
        self.session.modified = True

    def add(self, part, quantity=1):
        key = str(part.pk)
        self.data[key] = min(self.data.get(key, 0) + quantity, part.stock)
        self._save()

    def set(self, part, quantity):
        key = str(part.pk)
        if quantity <= 0:
            self.data.pop(key, None)
        else:
            self.data[key] = min(quantity, part.stock)
        self._save()

    def remove(self, part):
        self.data.pop(str(part.pk), None)
        self._save()

    def clear(self):
        self.session[SESSION_KEY] = {}
        self._save()

    def __iter__(self):
        parts = Part.objects.filter(pk__in=self.data.keys())
        for part in parts:
            qty = self.data[str(part.pk)]
            yield {"part": part, "quantity": qty, "line_total": part.price * qty}

    def __len__(self):
        return sum(self.data.values())

    @property
    def total(self):
        return sum((item["line_total"] for item in self), Decimal("0"))
