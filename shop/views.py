from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cart import Cart
from .forms import CheckoutForm
from .models import Category, Order, OrderItem, Part


def part_list(request):
    parts = Part.objects.select_related("category")
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    if q:
        parts = parts.filter(Q(name__icontains=q) | Q(brand__icontains=q) | Q(sku__icontains=q))
    if category:
        parts = parts.filter(category_id=category)
    return render(
        request,
        "shop/part_list.html",
        {"parts": parts, "categories": Category.objects.all(), "filters": request.GET},
    )


@require_POST
def cart_add(request, pk):
    part = get_object_or_404(Part, pk=pk)
    if part.stock == 0:
        messages.error(request, f"{part.name} is out of stock.")
    else:
        Cart(request).add(part, int(request.POST.get("quantity", 1)))
        messages.success(request, f"Added {part.name} to cart.")
    return redirect(request.POST.get("next") or "shop:cart")


@require_POST
def cart_update(request, pk):
    part = get_object_or_404(Part, pk=pk)
    Cart(request).set(part, int(request.POST.get("quantity", 0)))
    return redirect("shop:cart")


def cart_view(request):
    cart = Cart(request)
    return render(request, "shop/cart.html", {"items": list(cart), "total": cart.total})


@login_required
def checkout(request):
    cart = Cart(request)
    items = list(cart)
    if not items:
        messages.info(request, "Your cart is empty.")
        return redirect("shop:list")

    form = CheckoutForm(request.POST or None, initial={"phone": request.user.phone})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Lock stock rows so two customers can't buy the last unit at once.
            locked = {p.pk: p for p in Part.objects.select_for_update().filter(pk__in=[i["part"].pk for i in items])}
            short = [i["part"].name for i in items if locked[i["part"].pk].stock < i["quantity"]]
            if short:
                messages.error(request, "Not enough stock for: " + ", ".join(short))
                return redirect("shop:cart")

            order = form.save(commit=False)
            order.customer = request.user
            order.total = cart.total
            order.save()
            for item in items:
                OrderItem.objects.create(
                    order=order, part=item["part"], quantity=item["quantity"], unit_price=item["part"].price
                )
                Part.objects.filter(pk=item["part"].pk).update(stock=F("stock") - item["quantity"])
        cart.clear()
        messages.success(request, f"Order #{order.pk} placed! (Demo checkout - pay on delivery.)")
        return redirect("shop:orders")

    return render(request, "shop/checkout.html", {"form": form, "items": items, "total": cart.total})


@login_required
def order_list(request):
    orders = request.user.orders.prefetch_related("items__part")
    return render(request, "shop/orders.html", {"orders": orders})
