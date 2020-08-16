from django.conf import settings
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404, redirect, reverse
from books.models import Book
from .models import Order, OrderItem, Payment
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import stripe
import random
import string
import datetime

stripe.api_key = settings.STRIPE_SECRET_KEY

def profile_view(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True)
    context = {
        'orders': orders,
       
       
    }
    return render(request, "profile.html", context)


def create_ref_code(request):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=15))


@login_required(redirect_field_name='/accounts/login')
def add_to_cart(request, book_slug):
    book = get_object_or_404(Book, slug=book_slug)
    order_item, created = OrderItem.objects.get_or_create(book=book)
    order, created = Order.objects.get_or_create(
        user=request.user, is_ordered=False)
    order.items.add(order_item)
    order.save()
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))




def remove_from_cart(request, book_slug):
    book = get_object_or_404(Book, slug=book_slug)
    order_item = get_object_or_404(OrderItem, book=book)
    order = Order.objects.get(user=request.user, is_ordered=False)
    order.items.remove(order_item)
    order.save()
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))




def order_view(request):
    order_qs = Order.objects.filter(user=request.user, is_ordered=False)
    if order_qs.exists():
        context = {
            'order': order_qs[0]
        }
        return render(request, "order_summary.html", context)
    return Http404






def checkout(request):
    order_qs = Order.objects.filter(user=request.user, is_ordered=False)
    if order_qs.exists():
        order = order_qs[0]
    else:
        return Http404

    if request.method == "POST":

        try:
            # complete the order (ref code and set ordered to true)
            order.ref_code = create_ref_code(request)

            # create a stripe charge
            token = request.POST.get('stripeToken')
            charge = stripe.Charge.create(
                amount=int(order.get_total() * 100),  # cents
                currency="usd",
                source=token,  # obtained with Stripe.js
                description=f"Charge for {request.user.username}"
            )

            # create our payment object and link to the order
            payment = Payment()
            payment.order = order
            payment.stripe_charge_id = charge.id
            payment.total_amount = order.get_total()
            payment.save()

            # add the book to the users book list
            books = [item.book for item in order.items.all()]
            for book in books:
                request.user.userlibrary.books.add(book)

            order.is_ordered = True
            order.save()

            # redirect to the users profile
            messages.success(request, "Your order was successful!")
            return redirect("/cart/profile/")

        # send email to yourself

        except stripe.error.CardError as e:
            messages.error(request, "There was a card error.")
            return redirect(reverse("cart:checkout"))
        except stripe.error.RateLimitError as e:
            messages.error(request, "There was a rate limit error on Stripe.")
            return redirect(reverse("cart:checkout"))
        except stripe.error.InvalidRequestError as e:
            messages.error(request, "Invalid parameters for Stripe request.")
            return redirect(reverse("cart:checkout"))
        except stripe.error.AuthenticationError as e:
            messages.error(request, "Invalid Stripe API keys.")
            return redirect(reverse("cart:checkout"))
        except stripe.error.APIConnectionError as e:
            messages.error(
                request, "There was a network error. Please try again.")
            return redirect(reverse("cart:checkout"))
        except stripe.error.StripeError as e:
            messages.error(request, "There was an error. Please try again.")
            return redirect(reverse("cart:checkout"))
      

    context = {
        'order': order
    }

    return render(request, "checkout.html", context)