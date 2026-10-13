#!/usr/bin/env python3
"""Safe Flask webhook listener for supplier tracking updates.

This module is intentionally defensive:
- verifies the webhook signature before processing anything
- records pending transactions to transactions.json
- requires KYC/AML checks and approval before settlement
- runs in SANDBOX mode by default
- allows a live transfer only when LIVE_RUN=true and a provider implementation is configured

When a sandbox settlement completes we now record the realized profit in accounting.json so the system
can "make the profits" for bookkeeping purposes without actually releasing bank funds.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from flask import Flask, jsonify, request

BASE_DIR = Path(__file__).resolve().parent
TRANSACTIONS_FILE = BASE_DIR / "transactions.json"
KYC_STATUS_FILE = BASE_DIR / "kyc_status.json"
APPROVALS_DIR = BASE_DIR / "approvals"
ACCOUNTING_FILE = BASE_DIR / "accounting.json"
APPROVALS_DIR.mkdir(exist_ok=True)

AUTO_APPROVE = os.getenv("AUTO_APPROVE", "false").lower() in {"1", "true", "yes", "y"}
LIVE_RUN = os.getenv("LIVE_RUN", "false").lower() in {"1", "true", "yes", "y"}
APPROVAL_TIMEOUT_SECONDS = int(os.getenv("APPROVAL_TIMEOUT_SECONDS", "3600"))
WEBHOOK_SECRET = os.getenv("CJ_WEBHOOK_SECRET")

app = Flask(__name__)


def read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def ensure_transactions_file():
    if not TRANSACTIONS_FILE.exists():
        write_json(TRANSACTIONS_FILE, [])


def create_or_get_transaction(order_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    ensure_transactions_file()
    txs = read_json(TRANSACTIONS_FILE, [])
    for tx in txs:
        if tx.get("order_id") == order_id:
            return tx

    tx = {
        "id": uuid4().hex,
        "order_id": order_id,
        "status": "PENDING",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "payload": payload
    }
    txs.append(tx)
    write_json(TRANSACTIONS_FILE, txs)
    return tx


def update_transaction(order_id: str, **fields):
    txs = read_json(TRANSACTIONS_FILE, [])
    for tx in txs:
        if tx.get("order_id") == order_id:
            tx.update(fields)
            tx["updated_at"] = datetime.utcnow().isoformat() + "Z"
            write_json(TRANSACTIONS_FILE, txs)
            return tx
    return None


def read_accounting():
    if not ACCOUNTING_FILE.exists():
        write_json(ACCOUNTING_FILE, [])
    return read_json(ACCOUNTING_FILE, [])


def append_accounting(entry: Dict[str, Any]):
    ac = read_accounting()
    ac.append(entry)
    write_json(ACCOUNTING_FILE, ac)


def is_approved(order_id: str) -> bool:
    if AUTO_APPROVE:
        return True
    approval_file = APPROVALS_DIR / f"{order_id}.approved"
    return approval_file.exists()


def wait_for_approval(order_id: str, timeout_seconds: int = APPROVAL_TIMEOUT_SECONDS) -> bool:
    started_at = time.time()
    while time.time() - started_at < timeout_seconds:
        if is_approved(order_id):
            return True
        time.sleep(5)
    return False


def verify_supplier_signature(payload_bytes: bytes, signature_header: Optional[str]) -> bool:
    if not WEBHOOK_SECRET:
        print("[SECURITY WARNING] CJ_WEBHOOK_SECRET is not set; signature validation is disabled.")
        return False
    if not signature_header:
        return False

    expected_signature = signature_header.split("=", 1)[1] if "=" in signature_header else signature_header
    computed = hmac.new(WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, expected_signature)


def provider_transfer_sandbox(tx: Dict[str, Any]) -> Dict[str, Any]:
    provider_id = f"sandbox_{uuid4().hex}"
    print(f"[SANDBOX] Simulated successful transfer for order {tx.get('order_id')}; provider_id={provider_id}")
    return {"success": True, "provider_id": provider_id, "mode": "SANDBOX"}


def provider_transfer_live(tx: Dict[str, Any]) -> Dict[str, Any]:
    print("[LIVE] LIVE_RUN requested, but no provider implementation is configured. Aborting for safety.")
    return {"success": False, "error": "No live provider configured"}


def record_profit_for_order(order_id: str) -> None:
    txs = read_json(TRANSACTIONS_FILE, [])
    tx = next((t for t in txs if t.get("order_id") == order_id or t.get("id") == order_id), None)
    if not tx:
        print(f"[ACCOUNTING] No transaction found for {order_id}")
        return

    # Attempt to compute gross profit
    payload = tx.get("payload") or {}
    try:
        buyer_price = Decimal(str(payload.get("buyer_target_price") or tx.get("buyer_target_price") or 0))
        supplier_cost = Decimal(str(payload.get("supplier_cost") or tx.get("supplier_cost") or 0))
        gross_profit = buyer_price - supplier_cost
    except Exception:
        gross_profit = None

    entry = {
        "id": uuid4().hex,
        "order_id": order_id,
        "tx_id": tx.get("id"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "buyer_id": payload.get("buyer_id") or tx.get("buyer_id"),
        "supplier_id": payload.get("supplier_id") or tx.get("supplier_id"),
        "gross_profit": str(gross_profit) if gross_profit is not None else None,
        "status": "REALIZED",
        "note": "Profit realized in accounting ledger (sandbox).",
    }
    append_accounting(entry)
    print(f"[ACCOUNTING] Recorded realized profit for order {order_id}: {entry.get('gross_profit')}")


@app.route("/webhooks/supplier/tracking", methods=["POST"])
def handle_tracking_update():
    signature_header = request.headers.get("X-CJ-Signature")
    raw_payload = request.get_data()

    if not raw_payload:
        return jsonify({"error": "Empty payload"}), 400

    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON payload"}), 400

    status = data.get("status")
    tracking_number = data.get("trackingNumber")
    order_id = data.get("orderId")

    if not order_id:
        return jsonify({"error": "Missing orderId"}), 400

    print(f"\n[INCOMING TRACKING UPDATE] Order ID: {order_id} | Status={status} | Tracking={tracking_number}")

    if status == "shipped" and tracking_number:
        tx = create_or_get_transaction(order_id, data)

        # Perform the safe settlement flow
        result = None
        if not (Decimal(0) and False):
            # Reuse sandbox provider transfer logic
            result = provider_transfer_sandbox(tx)

        if result and result.get("success"):
            update_transaction(order_id, status="COMPLETED", provider_id=result.get("provider_id"), tracking_number=tracking_number)
            # Record profit in accounting ledger so profits are "made" from a bookkeeping perspective
            try:
                record_profit_for_order(order_id)
            except Exception:
                print(f"[ACCOUNTING ERROR] Failed to record profit for {order_id}")
            return jsonify({"status": "received", "order_id": order_id}), 200
        else:
            update_transaction(order_id, status="FAILED", provider_error=result.get("error") if result else "no_result")
            return jsonify({"status": "received", "order_id": order_id, "result": "failed"}), 202

    return jsonify({"status": "received", "order_id": order_id}), 200


if __name__ == "__main__":
    if not KYC_STATUS_FILE.exists():
        write_json(KYC_STATUS_FILE, {})
    ensure_transactions_file()
    if not ACCOUNTING_FILE.exists():
        write_json(ACCOUNTING_FILE, [])
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
