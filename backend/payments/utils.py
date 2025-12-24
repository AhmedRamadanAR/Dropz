import hashlib
import hmac
from django.conf import settings

HMAC_KEYS = [
    "amount_cents",
    "created_at",
    "currency",
    "error_occured",
    "has_parent_transaction",
    "id",
    "integration_id",
    "is_3d_secure",
    "is_auth",
    "is_capture",
    "is_refunded",
    "is_standalone_payment",
    "is_voided",
    "order.id",
    "owner",
    "pending",
    "source_data.pan",
    "source_data.sub_type",
    "source_data.type",
    "success",
]

def value_to_str(value):
    """Convert value to string in the format Paymob expects for HMAC"""
    if isinstance(value, bool):
        return str(value).lower()  # True/False -> "true"/"false"
    elif value is None:
        return ""
    return str(value)

def validate_paymob_hmac(obj_data: dict, received_hmac: str) -> bool:
    """
    Validate HMAC signature from Paymob webhook.
    Docs: https://docs.paymob.com/docs/hmac-calculation
    """
    hmac_secret = settings.PAYMOB["HMAC_SECRET"]

    # Concatenate fields in required order
    concatenated = ""
    for key in HMAC_KEYS:
        parts = key.split(".")
        value = obj_data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part, "")
            else:
                value = ""
        concatenated += value_to_str(value)

    print("Concatenated String for HMAC:", concatenated)

    computed_hmac = hmac.new(
        hmac_secret.encode(),
        concatenated.encode(),
        hashlib.sha512,
    ).hexdigest()

    print("Computed HMAC:", computed_hmac)
    return hmac.compare_digest(computed_hmac, received_hmac)