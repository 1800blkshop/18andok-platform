#!/usr/bin/env python3
"""
Non-custodial trading flow for 18&ok LLC.

This module creates and records trade intents and fee capture intents only.
It does NOT execute buys or take title. Seller/buyer settlement is expected to happen off-platform via escrow or connected accounts.
"""
from __future__ import annotations

import json
import os
import logging
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

# Decimal config
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

LOG_DIR = Path(os.getenv("CORP_LEDGER_DIR", "./corporate_ledger"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

MIN_REQUIRED_MARGIN = Decimal(os.getenv("MIN_REQUIRED_MARGIN", "0.25"))
LIVE_RUN = os.getenv("LIVE_RUN", "false").lower() in ("1", "true", "yes")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("noncustodial_trading")


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tf:
        json.dump(data, tf, indent=2)
        tf.flush()
    Path(tf.name).replace(path)


def create_trade_intent(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    """Record an intent. Does not execute purchase or hold funds."""
    intent_id = f"intent-{uuid4().hex}"
    now = datetime.utcnow().isoformat() + "Z"
    buy_cost = opportunity.get("supplier_cost")
    sell_price = opportunity.get("buyer_price")

    # basic validation
    try:
        buy_cost_dec = Decimal(str(buy_cost))
        sell_price_dec = Decimal(str(sell_price))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid numeric values for supplier_cost or buyer_price")

    gross_profit = sell_price_dec - buy_cost_dec
    margin = (gross_profit / sell_price_dec) if sell_price_dec != 0 else Decimal("0")

    record = {
        "intent_id": intent_id,
        "created_at": now,
        "product_name": opportunity.get("product_name"),
        "supplier_id": opportunity.get("supplier_id"),
        "buyer_id": opportunity.get("buyer_id"),
        "supplier_cost": str(buy_cost_dec),
        "buyer_price": str(sell_price_dec),
        "gross_profit": str(gross_profit),
        "margin": str(margin),
        "status": "INTENT_CREATED",
        "notes": "Non-custodial intent; no purchase executed."
    }

    intents_file = LOG_DIR / "intents.json"
    intents = []
    if intents_file.exists():
        try:
            intents = json.loads(intents_file.read_text(encoding="utf-8"))
        except Exception:
            intents = []
    intents.append(record)
    atomic_write_json(intents_file, intents)
    logger.info("Created trade intent %s", intent_id)
    return record


def create_fee_capture_intent(intent_id: str, amount: Any, payer: str, description: Optional[str] = None) -> Dict[str, Any]:
    """Create an intent to capture a service fee. Actual capture handled by payment provider/escape flow.
    This function only records the fee intent and requires explicit approval to proceed.
    """
    try:
        amt_dec = Decimal(str(amount))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid amount for fee capture")

    fee_id = f"fee-{uuid4().hex}"
    entry = {
        "fee_id": fee_id,
        "intent_id": intent_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "amount": str(amt_dec),
        "payer": payer,
        "description": description or "Service fee",
        "status": "PENDING_APPROVAL"
    }

    fees_file = LOG_DIR / "fees.json"
    fees = []
    if fees_file.exists():
        try:
            fees = json.loads(fees_file.read_text(encoding="utf-8"))
        except Exception:
            fees = []
    fees.append(entry)
    atomic_write_json(fees_file, fees)
    logger.info("Created fee capture intent %s for trade %s", fee_id, intent_id)
    return entry


if __name__ == "__main__":
    sample = {
        "product_name": "Wholesale Industrial Tool Set Batch #44",
        "supplier_cost": "750.00",
        "buyer_price": "1100.00",
        "supplier_id": "SUP_CJ_9921",
        "buyer_id": "BUY_EBAY_4002",
    }
    print(create_trade_intent(sample))
