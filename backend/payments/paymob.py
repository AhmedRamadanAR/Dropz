# payments/paymob.py
import requests
from django.conf import settings

BASE = settings.PAYMOB["PAYMOB_BASE"]

import logging

logger = logging.getLogger("payments")


class PaymobService:
    @staticmethod
    def authenticate():
        url = f"{BASE}/auth/tokens"
        resp = requests.post(url, json={"api_key": settings.PAYMOB["API_KEY"]}, timeout=15)
        logger.debug(f"Authenticate response: {resp.text}")
        resp.raise_for_status()
        return resp.json().get("token")

    @staticmethod
    def create_order(auth_token: str, payment):
        url = f"{BASE}/ecommerce/orders"
        payload = {
            "auth_token": auth_token,
            "amount_cents": payment.amount_cents,
            "currency": "EGP",
            "delivery_needed": False,
            "items": [],
        }
        resp = requests.post(url, json=payload, timeout=15)
        logger.debug(f"Create order payload: {payload}")
        logger.debug(f"Create order response: {resp.text}")
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def generate_payment_key(auth_token: str, payment, billing_data: dict):
        url = f"{BASE}/acceptance/payment_keys"
        payload = {
            "expiration": 3600,
            "auth_token": auth_token,
            "order_id": payment.paymob_order_id,
            "integration_id": settings.PAYMOB["INTEGRATION_ID"],
            "amount_cents": payment.amount_cents,
            "currency": "EGP",
            "billing_data": billing_data,
        }
        resp = requests.post(url, json=payload, timeout=15)
        logger.debug(f"Generate payment key payload: {payload}")
        logger.debug(f"Generate payment key response: {resp.text}")
        resp.raise_for_status()
        return resp.json()