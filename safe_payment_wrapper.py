#!/usr/bin/env python3
import os
import logging
from decimal import Decimal, InvalidOperation, getcontext, ROUND_HALF_UP
from pathlib import Path
from typing import Optional, Dict, Any
from uuid import uuid4

import stripe

getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

logger = logging.getLogger("safe_payment_wrapper")

LIVE_RUN = os.getenv("LIVE_RUN", "false").lower() in ("1", "true", "yes")
AUTO_APPROVE = os.getenv("AUTO_APPROVE", "false").lower() in ("1", "true", "yes")
APPROVAL_DIR = Path(os.getenv("APPROVAL_DIR", "./approvals"))
APPROVAL_DIR.mkdir(parents=True, exist_ok=True)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

def _to_cents(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1")))

def _is_approved(intent_id: str) -> bool:
    if AUTO_APPROVE:
        return True
    return (APPROVAL_DIR / f"{intent_id}.approved").exists()

def capture_pre_approved_customer_payment_safe(
    customer_id: str,
    payment_method_id: str,
    amount_usd: Any,
    description: str,
    intent_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Safe sandbox-first payment wrapper.
    - LIVE_RUN=false -> simulate success, no real charge
    - LIVE_RUN=true -> require approval file or AUTO_APPROVE
    """
    try:
        amount = Decimal(str(amount_usd))
    except (InvalidOperation, ValueError):
        return {"success": False, "error": "invalid_amount"}

    if amount <= 0:
        return {"success": False, "error": "amount_must_be_positive"}

    intent_id = intent_id or f"intent-{uuid4().hex}"
    idempotency_key = idempotency_key or f"idemp-{uuid4().hex}"

    if not LIVE_RUN:
        fake_provider_id = f"sandbox_charge_{uuid4().hex}"
        logger.info("[SANDBOX] Simulated charge: intent=%s amount=%s provider_id=%s", intent_id, amount, fake_provider_id)
        return {
            "success": True,
            "provider_id": fake_provider_id,
            "status": "succeeded",
            "sandbox": True,
            "intent_id": intent_id,
        }

    if not _is_approved(intent_id):
        logger.warning("Intent %s not approved; live charge blocked", intent_id)
        return {
            "success": False,
            "status": "awaiting_approval",
            "error": "approval_required",
            "intent_id": intent_id,
        }

    if not STRIPE_SECRET_KEY:
        logger.error("STRIPE_SECRET_KEY missing")
        return {"success": False, "status": "missing_credentials", "error": "missing_provider_credentials"}

    amount_cents = _to_cents(amount)

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            customer=customer_id,
            payment_method=payment_method_id,
            off_session=True,
            confirm=True,
            description=description,
            metadata={"intent_id": intent_id},
            idempotency_key=idempotency_key,
        )

        if intent.status == "succeeded":
            logger.info("Live charge succeeded: intent=%s provider_id=%s", intent_id, intent.id)
            return {"success": True, "provider_id": intent.id, "status": "succeeded", "sandbox": False, "intent_id": intent_id}
        elif intent.status in ("requires_action", "requires_source_action"):
            logger.warning("Payment requires customer action: intent=%s status=%s", intent_id, intent.status)
            return {"success": False, "status": intent.status, "error": "requires_customer_action", "intent_id": intent_id}
        else:
            logger.warning("Unhandled PaymentIntent status: intent=%s status=%s", intent_id, intent.status)
            return {"success": False, "status": intent.status, "error": "unknown_status", "intent_id": intent_id}

    except stripe.error.CardError as e:
        logger.error("Card declined: %s", e.user_message)
        return {"success": False, "status": "card_error", "error": e.user_message, "intent_id": intent_id}
    except stripe.error.StripeError as e:
        logger.error("StripeError: %s", e)
        return {"success": False, "status": "stripe_error", "error": str(e), "intent_id": intent_id}
    except Exception as e:
        logger.exception("Unexpected error")
        return {"success": False, "status": "internal_error", "error": str(e), "intent_id": intent_id}
