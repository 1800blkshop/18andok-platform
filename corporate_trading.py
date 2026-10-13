#!/usr/bin/env python3
"""
Safe corporate trading module for 18&ok LLC.

Sandbox-first logic:
- DOES NOT perform live transfers unless LIVE_RUN=true and a real provider is configured.
- Logs legal/compliance records to corporate_ledger/.
- Uses Decimal for money math to avoid float rounding errors.
- Implements approval gating and KYC stub checks.
- Records realized profits in accounting.json after a simulated settlement.

Operational notes:
- Keep LIVE_RUN=false until provider contracts, legal review, KYC/AML, and approval controls are in place.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

# Decimal config
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

# Configuration
LOG_DIR = Path(os.getenv("CORP_LEDGER_DIR", "./corporate_ledger"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

MIN_REQUIRED_MARGIN = Decimal(os.getenv("MIN_REQUIRED_MARGIN", "0.25"))
LIVE_RUN = os.getenv("LIVE_RUN", "false").lower() in ("1", "true", "yes")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("1", "true", "yes")
APPROVAL_DIR = Path(os.getenv("APPROVAL_DIR", "./approvals"))
APPROVAL_DIR.mkdir(exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("corp_trading")


def decimal_of(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tf:
        json.dump(data, tf, indent=2)
        tf.flush()
    Path(tf.name).replace(path)


def ledger_entry(trade_id: str, action: str, product: str, amount: Decimal, counterparty: str, status: str) -> Path:
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entity_name": "18&ok LLC",
        "trade_name": "OK",
        "trade_id": trade_id,
        "action": action,
        "product_description": product,
        "amount_usd": str(amount),
        "counterparty_id": counterparty,
        "status": status,
    }
    file_path = LOG_DIR / f"trade_{trade_id}.json"
    atomic_write_json(file_path, record)
    logger.info("Ledger record saved: %s", file_path)
    return file_path


def kyc_clear(entity_id: Any) -> bool:
    # Minimal stub; in production, this should call your KYC provider or database
    if entity_id is None:
        return False
    return True


def require_approval(trade_id: str) -> bool:
    if os.getenv("AUTO_APPROVE", "false").lower() in ("1", "true", "yes"):
        return True
    return (APPROVAL_DIR / f"{trade_id}.approved").exists()


def _simulate_provider_purchase(supplier_id: str, amount: Decimal, idempotency_key: str) -> Dict[str, Any]:
    provider_tx = f"sandbox_buy_{uuid4().hex}"
    logger.info("Simulated sandbox purchase: provider_tx=%s supplier=%s amount=%s key=%s", provider_tx, supplier_id, amount, idempotency_key)
    return {"success": True, "provider_tx_id": provider_tx}


def _simulate_provider_capture(buyer_id: str, amount: Decimal, idempotency_key: str) -> Dict[str, Any]:
    provider_tx = f"sandbox_sell_{uuid4().hex}"
    logger.info("Simulated sandbox capture: provider_tx=%s buyer=%s amount=%s key=%s", provider_tx, buyer_id, amount, idempotency_key)
    return {"success": True, "provider_tx_id": provider_tx}


def execute_autonomous_corporate_buy(supplier_id: str, product_name: str, cost: Decimal, idempotency_key: Optional[str] = None) -> str:
    trade_id = f"TXN_BUY_{int(datetime.utcnow().timestamp())}_{uuid4().hex[:8]}"
    if LIVE_RUN:
        raise RuntimeError("LIVE_RUN is enabled, but no real provider integration is configured. Aborting safe execution.")
    result = _simulate_provider_purchase(supplier_id, cost, idempotency_key or trade_id)
    status = "EXECUTED_SANDBOX" if result.get("success") else "FAILED"
    ledger_entry(trade_id, "BUY", product_name, cost, supplier_id, status)
    return trade_id


def execute_autonomous_corporate_sell(buyer_id: str, product_name: str, sale_price: Decimal, idempotency_key: Optional[str] = None) -> str:
    trade_id = f"TXN_SELL_{int(datetime.utcnow().timestamp())}_{uuid4().hex[:8]}"
    if LIVE_RUN:
        raise RuntimeError("LIVE_RUN is enabled, but no real provider integration is configured. Aborting safe execution.")
    result = _simulate_provider_capture(buyer_id, sale_price, idempotency_key or trade_id)
    status = "EXECUTED_SANDBOX" if result.get("success") else "FAILED"
    ledger_entry(trade_id, "SELL", product_name, sale_price, buyer_id, status)
    return trade_id


def write_accounting_entry(product: str, buy_tx: str, sell_tx: str, gross_profit: Decimal, margin: Decimal) -> None:
    accounting_file = LOG_DIR / "accounting.json"
    entries = []
    if accounting_file.exists():
        try:
            entries = json.loads(accounting_file.read_text(encoding="utf-8"))
        except Exception:
            entries = []
    entries.append({
        "id": f"profit-{uuid4().hex}",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "product": product,
        "buy_tx": buy_tx,
        "sell_tx": sell_tx,
        "gross_profit": str(gross_profit),
        "margin": str(margin),
        "status": "REALIZED_SANDBOX"
    })
    atomic_write_json(accounting_file, entries)
    logger.info("Recorded profit entry in %s", accounting_file)


def evaluate_and_trade(opportunity: Dict[str, Any]) -> Dict[str, Any]:
    product = opportunity.get("product_name")
    buy_cost = decimal_of(opportunity.get("supplier_cost"))
    sell_price = decimal_of(opportunity.get("buyer_price"))
    supplier_id = opportunity.get("supplier_id")
    buyer_id = opportunity.get("buyer_id")

    if buy_cost is None or sell_price is None:
        raise ValueError("Invalid numeric values for buy_cost or sell_price")

    gross_profit = sell_price - buy_cost
    if sell_price == 0:
        raise ValueError("sell_price cannot be zero")
    actual_margin = gross_profit / sell_price

    if actual_margin < MIN_REQUIRED_MARGIN:
        logger.warning("Trade rejected: actual margin %s below required %s", actual_margin, MIN_REQUIRED_MARGIN)
        return {"accepted": False, "reason": "margin_too_low", "margin": str(actual_margin)}

    # KYC gate stub
    if not (kyc_clear(supplier_id) and kyc_clear(buyer_id)):
        logger.warning("KYC not cleared for supplier/buyer. Trade remains on hold.")
        return {"accepted": False, "reason": "kyc_not_clear"}

    # Manual approval gate / sandbox only
    intent_id = f"intent-{uuid4().hex}"
    if not require_approval(intent_id):
        logger.info("Trade %s requires manual approval before any live action; keeping sandbox-only.", intent_id)
    # In a sandbox environment, we can still run the simulated trade.
    buy_tx = execute_autonomous_corporate_buy(supplier_id, product, buy_cost, idempotency_key=intent_id)
    sell_tx = execute_autonomous_corporate_sell(buyer_id, product, sell_price, idempotency_key=intent_id)

    write_accounting_entry(product, buy_tx, sell_tx, gross_profit, actual_margin)

    return {
        "accepted": True,
        "buy_tx": buy_tx,
        "sell_tx": sell_tx,
        "gross_profit": str(gross_profit),
        "margin": str(actual_margin),
    }


if __name__ == "__main__":
    sample_deal = {
        "product_name": "Wholesale Industrial Tool Set Batch #44",
        "supplier_cost": "750.00",
        "buyer_price": "1100.00",
        "supplier_id": "SUP_CJ_9921",
        "buyer_id": "BUY_EBAY_4002",
    }
    print(evaluate_and_trade(sample_deal))
