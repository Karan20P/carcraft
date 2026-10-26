from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Order


class CheckoutForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Order
        fields = ("shipping_address", "phone")
        widgets = {"shipping_address": forms.Textarea(attrs={"rows": 3})}
