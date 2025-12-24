from django.urls import path
from .views import PaymobPaymentView, PaymobWebhookView, PaymentStatusView

urlpatterns = [
    path("pay/<int:order_id>/", PaymobPaymentView.as_view(), name="paymob-pay"),
    path("webhook/", PaymobWebhookView.as_view(), name="paymob-webhook"),
    path("status/<int:payment_id>/", PaymentStatusView.as_view(), name="payment-status"),
]