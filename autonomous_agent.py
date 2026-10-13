#!/usr/bin/env python3
"""
Safe Autonomous Agent for 18&ok LLC (non-custodial / sandbox-first).

- Uses Decimal for money calculations.
- Records immutable ledger entries under corporate_ledger/.
- Requires approval for large transactions.
- Does NOT perform live payouts or settlements; LIVE_RUN must be explicitly enabled and accompanied
  by provider integration and legal/compliance sign-offs.
"""
from __future__ import annotations

import os
import sys
import logging
import tempfile
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

# Config (via env)
LOG_DIR = Path(os.getenv("CORP_LEDGER_DIR", "./corporate_ledger"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
COMPLIANCE_LOG = LOG_DIR / "compliance_audit.log"

MIN_REQUIRED_MARGIN = Decimal(os.getenv("MIN_REQUIRED_MARGIN", "0.25"))
MAX_AUTONOMOUS_TRANSACTION = Decimal(os.getenv("MAX_TRANSACTION_LIMIT", "5000.00"))

LIVE_RUN = os.getenv("LIVE_RUN", "false").lower() in ("1", "true", "yes")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("1", "true", "yes")
AUTO_APPROVE = os.getenv("AUTO_APPROVE", "false").lower() in ("1", "true", "yes")
APPROVAL_DIR = Path(os.getenv("APPROVAL_DIR", "./approvals"))
APPROVAL_DIR.mkdir(parents=True, exist_ok=True)

# Logging: console + append-only compliance file
logger = logging.getLogger("autonomous_agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] 18&ok LLC Agent: %(message)s"))
    logger.addHandler(ch)
    fh = logging.FileHandler(str(COMPLIANCE_LOG), mode="a", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] 18&ok LLC Agent: %(message)s"))
    logger.addHandler(fh)


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tf:
        json.dump(data, tf, indent=2, default=str)
        tf.flush()
    Path(tf.name).replace(path)


def ledger_entry(entry: Dict[str, Any]) -> Path:
    """Write an immutable ledger record for auditing."""
    trade_id = entry.get("trade_id") or f"trade_{int(datetime.utcnow().timestamp())}_{os.urandom(4).hex()}"
    entry["recorded_at"] = datetime.utcnow().isoformat() + "Z"
    path = LOG_DIR / f"{trade_id}.json"
    atomic_write_json(path, entry)
    logger.info("Ledger entry written: %s", path)
    return path


def is_approved(intent_id: str) -> bool:
    if AUTO_APPROVE:
        return True
    return (APPROVAL_DIR / f"{intent_id}.approved").exists()


class AutonomousLLCAgent:
    def __init__(self):
        self.legal_name = "18&ok LLC"
        self.trade_name = "OK"
        self.location = "East Baton Rouge, LA"

        try:
            self.min_profit_margin = Decimal(os.getenv("MIN_REQUIRED_MARGIN", str(MIN_REQUIRED_MARGIN)))
            self.max_transaction_limit = Decimal(os.getenv("MAX_TRANSACTION_LIMIT", str(MAX_AUTONOMOUS_TRANSACTION)))
        except InvalidOperation:
            self.min_profit_margin = MIN_REQUIRED_MARGIN
            self.max_transaction_limit = MAX_AUTONOMOUS_TRANSACTION

        # keys optional for sandbox; do NOT enable live transfers without explicit provider integration
        self.stripe_key = os.getenv("STRIPE_SECRET_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")

        if not self.openai_key:
            logger.warning("OPENAI_API_KEY not set — AI outreach disabled for sandbox runs.")
        if not self.stripe_key:
            logger.info("STRIPE_SECRET_KEY not set — live payment captures disabled by default.")

        self.system_active = True
        logger.info("Autonomous agent initialized (LIVE_RUN=%s, DRY_RUN=%s).", LIVE_RUN, DRY_RUN)

    def audit_and_execute_deal(self, trade_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate deal and (only in sandbox) record & simulate execution. Returns structured result."""
        if not self.system_active:
            logger.warning("System inactive. Execution blocked.")
            return {"accepted": False, "reason": "system_inactive"}

        asset = trade_payload.get("asset_name")
        intent_id = trade_payload.get("intent_id") or f"intent-{os.urandom(6).hex()}"
        try:
            cost = Decimal(str(trade_payload.get("wholesale_cost")))
            value = Decimal(str(trade_payload.get("international_market_value")))
        except (InvalidOperation, TypeError):
            logger.error("Invalid numeric values in payload")
            return {"accepted": False, "reason": "invalid_numbers"}

        if value == 0:
            logger.error("Sell value cannot be zero")
            return {"accepted": False, "reason": "zero_value"}

        gross_profit = (value - cost).quantize(Decimal("0.01"))
        margin = (gross_profit / value).quantize(Decimal("0.0001"))

        # Record an intent ledger before any action
        intent_record = {
            "trade_id": intent_id,
            "asset_name": asset,
            "supplier_cost": str(cost),
            "buyer_price": str(value),
            "gross_profit": str(gross_profit),
            "margin": str(margin),
            "buyer_id": trade_payload.get("buyer_id"),
            "status": "INTENT_EVALUATED",
        }
        ledger_entry(intent_record)

        # Margin check
        if margin < self.min_profit_margin:
            logger.info("Deal rejected: margin %s below required %s", margin, self.min_profit_margin)
            ledger_entry({**intent_record, "status": "REJECTED_MARGIN"})
            return {"accepted": False, "reason": "margin_too_low", "margin": str(margin)}

        # Transaction limit check — require approval if exceeds autonomous cap
        if cost > self.max_transaction_limit:
            logger.warning("Cost %s exceeds autonomous limit %s; requires human approval", cost, self.max_transaction_limit)
            ledger_entry({**intent_record, "status": "REQUIRES_APPROVAL"})
            return {"accepted": False, "reason": "requires_approval", "cost": str(cost)}

        # Approval gate for live-run
        if LIVE_RUN and not is_approved(intent_id):
            logger.warning("LIVE_RUN enabled but intent %s is not approved. Blocking live execution.", intent_id)
            ledger_entry({**intent_record, "status": "BLOCKED_NO_APPROVAL"})
            return {"accepted": False, "reason": "awaiting_approval", "intent_id": intent_id}

        # At this point, in sandbox we simulate execution and record settlement
        execution_id = f"exec-{os.urandom(6).hex()}"
        execution_record = {
            "trade_id": execution_id,
            "intent_id": intent_id,
            "asset_name": asset,
            "supplier_cost": str(cost),
            "buyer_price": str(value),
            "gross_profit": str(gross_profit),
            "margin": str(margin),
            "status": "EXECUTED_SANDBOX" if not LIVE_RUN else "EXECUTED_LIVE_PENDING_SETTLEMENT",
        }
        ledger_entry(execution_record)

        logger.info("[AUTONOMOUS] Intent %s executed with exec id %s (sandbox=%s)", intent_id, execution_id, not LIVE_RUN)

        return {
            "accepted": True,
            "intent_id": intent_id,
            "execution_id": execution_id,
            "gross_profit": str(gross_profit),
            "margin": str(margin),
            "sandbox": not LIVE_RUN,
        }

    def trigger_monitoring_alert(self, asset: str, cost: Decimal) -> None:
        payload = {
            "event": "monitor_alert",
            "asset": asset,
            "cost": str(cost),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        logger.info("Monitor alert: %s", payload)
        # Append a dedicated monitoring file
        monitor_file = LOG_DIR / "monitor_events.jsonl"
        with open(monitor_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
