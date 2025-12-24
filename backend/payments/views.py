import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import Payment
from .serializers import PaymentSerializer
from .paymob import PaymobService, validate_paymob_hmac

from carts.models import Cart, CartItem


logger = logging.getLogger("payments")


class PaymobPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response({"detail": "This endpoint expects POST requests."}, status=200)

    def post(self, request, order_id):
        from orders.models import Order

        order = get_object_or_404(Order, id=order_id)

        with transaction.atomic():
            payment = Payment.objects.create(
                order=order,
                amount_cents=int(order.total_cents),
                method="paymob",
            )

            try:
                token = PaymobService.authenticate()
                order_response = PaymobService.create_order(token, payment)
                payment.paymob_order_id = order_response.get("id")

                billing_data = {
                    "apartment": "NA",
                    "email": request.user.email or "customer@example.com",
                    "floor": "NA",
                    "first_name": request.user.first_name or "NA",
                    "last_name": request.user.last_name or "NA",
                    "street": "NA",
                    "building": "NA",
                    "phone_number": getattr(request.user, "phone_number", None) or "01000000000",
                    "city": "NA",
                    "country": "NA",
                    "state": "NA",
                }

                key_response = PaymobService.generate_payment_key(token, payment, billing_data)
                payment.paymob_payment_key = key_response.get("token")
                payment.response_payload = {"order": order_response, "payment_key": key_response}
                payment.save()

            except Exception as e:
                payment.status = "failed"
                payment.response_payload = {"error": str(e)}
                payment.save()
                logger.exception(f"Paymob order creation failed for order {order_id}")

                return Response({"error": f"Paymob order creation failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        iframe_url = f"https://accept.paymob.com/api/acceptance/iframes/{settings.PAYMOB['IFRAME_ID']}?payment_token={payment.paymob_payment_key}"

        response = JsonResponse({"iframe_url": iframe_url, "payment": PaymentSerializer(payment).data}, status=201)
        response["ngrok-skip-browser-warning"] = "true"
        return response


@method_decorator(csrf_exempt, name="dispatch")
class PaymobWebhookView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data
        obj = data.get("obj", {})
        received_hmac = request.GET.get("hmac")

        if not received_hmac or not validate_paymob_hmac(obj, received_hmac):
            return Response(
                {"detail": "Invalid HMAC"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        transaction_id = obj.get("id")
        success = obj.get("success")
        merchant_order_id = obj.get("order", {}).get("merchant_order_id")

        try:
            if merchant_order_id:
                payment = Payment.objects.get(id=int(merchant_order_id))
            else:
                payment = Payment.objects.get(
                    paymob_transaction_id=transaction_id
                )
            
            if success:
                payment.status = "success"
                
                if payment.order:
                    payment.order.status = "paid"
                    payment.order.save()
                    
                    for order_item in payment.order.items.all():
                        product = order_item.product
                        product.stock_quantity -= order_item.quantity
                        product.save()
                    
                    try:
                        cart = Cart.objects.get(user=payment.order.user)
                        CartItem.objects.filter(cart=cart).delete()
                    except Cart.DoesNotExist:
                        pass  
                    
            else:
                payment.status = "failed"

            
            # Update payment with transaction details
            payment.paymob_transaction_id = transaction_id
            payment.paymob_order_id = obj.get("order", {}).get("id")
            payment.response_payload = data
            payment.save()
            
        except Payment.DoesNotExist:
            # Create new payment record if payment was created outside our flow
            payment = Payment.objects.create(
                paymob_transaction_id=transaction_id,
                paymob_order_id=obj.get("order", {}).get("id"),
                amount_cents=int(obj.get("amount_cents", 0)),
                status="success" if success else "failed",
                response_payload=data,
            )
            
            # If payment is successful but we don't have order linked,
            # try to decrease stock if order exists
            if success and hasattr(payment, 'order') and payment.order:
                for order_item in payment.order.items.all():
                    product = order_item.product
                    product.stock_quantity -= order_item.quantity
                    product.save()

        return Response(
            {"status": payment.status}, 
            status=status.HTTP_200_OK
        )
class PaymentStatusView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        return Response({"is_paid": payment.status == "success", "status": payment.status})