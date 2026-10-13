#!/usr/bin/env python3
"""Safe Flask webhook listener for supplier tracking updates.

This module is intentionally defensive:
- verifies the webhook signature before processing anything
- records pending transactions to transactions.json
- requires KYC/AML checks and approval before settlement
- runs in SANDBOX mode by default
- allows a live transfer only when LIVE_RUN=true and a provider implementation is configured

Do not enable LIVE_RUN or AUTO_APPROVE in production without proper legal/compliance review.
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


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def ensure_transactions_file() -> None:
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
        "payload": payload,
    }
    txs.append(tx)
    write_json(TRANSACTIONS_FILE, txs)
    return tx


def update_transaction(order_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    txs = read_json(TRANSACTIONS_FILE, [])
    for tx in txs:
        if tx.get("order_id") == order_id:
            tx.update(fields)
            tx["updated_at"] = datetime.utcnow().isoformat() + "Z"
            write_json(TRANSACTIONS_FILE, txs)
            return tx
    return None


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


def verify_supplier_signature(payload: bytes, signature_header: Optional[str]) -> bool:
    if not WEBHOOK_SECRET:
        print("[SECURITY WARNING] CJ_WEBHOOK_SECRET is not set; signature validation is disabled.")
        return False
    if not signature_header:
        return False

    expected_signature = signature_header.split("=", 1)[1] if "=" in signature_header else signature_header
    computed = hmac.new(WEBHOOK_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, expected_signature)


def provider_transfer_sandbox(tx: Dict[str, Any]) -> Dict[str, Any]:
    provider_id = f"sandbox_{uuid4().hex}"
    print(f"[SANDBOX] Simulated successful transfer for order {tx.get('order_id')}; provider_id={provider_id}")
    return {"success": True, "provider_id": provider_id, "mode": "SANDBOX"}


def provider_transfer_live(tx: Dict[str, Any]) -> Dict[str, Any]:
    # Replace with a real provider integration using OAuth/mTLS or a bank/escrow API.
    # This function intentionally aborts if LIVE_RUN is requested without a real provider implementation.
    print("[LIVE] LIVE_RUN requested, but no provider implementation is configured. Aborting for safety.")
    return {"success": False, "error": "No live provider configured"}


def kyc_clear(entity_id: Any) -> bool:
    if entity_id is None:
        return False
    status_map = read_json(KYC_STATUS_FILE, {})
    value = status_map.get(str(entity_id))
    if isinstance(value, str):
        return value.lower() in {"clear", "approved", "true"}
    return bool(value)


def trigger_profit_settlement_safe(order_id: str, tracking_number: str, payload: Dict[str, Any], raw_payload: bytes, signature_header: Optional[str]):
    # 1) Signature validation must pass before anything is processed
    if not verify_supplier_signature(raw_payload, signature_header):
        print("[UNAUTHORIZED] Invalid supplier webhook signature detected.")
        return {"ok": False, "reason": "invalid_signature"}

    # 2) Idempotent transaction ledger entry
    tx = create_or_get_transaction(order_id, payload)
    if tx.get("status") == "COMPLETED":
        return {"ok": True, "reason": "already_completed", "transaction": tx}

    # 3) KYC/AML stub: operator can set kyc_status.json with buyer/supplier IDs as clear/approved
    buyer_ok = kyc_clear(payload.get("buyer_id"))
    supplier_ok = kyc_clear(payload.get("supplier_id"))
    if not (buyer_ok and supplier_ok):
        update_transaction(order_id, status="ON_HOLD", kyc={"buyer_ok": buyer_ok, "supplier_ok": supplier_ok})
        print(f"[ON_HOLD] KYC not cleared for order {order_id}; buyer_ok={buyer_ok}, supplier_ok={supplier_ok}")
        return {"ok": False, "reason": "kyc_not_clear"}

    # 4) Approval gate: manual approval required unless AUTO_APPROVE is enabled
    update_transaction(order_id, status="AWAITING_APPROVAL")
    if not is_approved(order_id):
        approved = wait_for_approval(order_id)
        if not approved:
            print(f"[AWAITING_APPROVAL] Order {order_id} awaiting admin approval.")
            return {"ok": False, "reason": "awaiting_approval"}

    update_transaction(order_id, status="APPROVED")

    # 5) Provider execution: sandbox by default, live only when explicitly enabled
    result = provider_transfer_live(tx) if LIVE_RUN else provider_transfer_sandbox(tx)
    if result.get("success"):
        update_transaction(order_id, status="COMPLETED", provider_id=result.get("provider_id"), tracking_number=tracking_number)
        print(f"[SETTLEMENT] Order {order_id} completed with provider={result.get('provider_id')}")
        return {"ok": True, "transaction": tx, "provider": result}

    update_transaction(order_id, status="FAILED", provider_error=result.get("error"), tracking_number=tracking_number)
    print(f"[SETTLEMENT FAILED] Order {order_id}: {result.get('error')}")
    return {"ok": False, "reason": "provider_error", "error": result.get("error")}


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
        result = trigger_profit_settlement_safe(
            order_id=order_id,
            tracking_number=tracking_number,
            payload=data,
            raw_payload=raw_payload,
            signature_header=signature_header,
        )
        if result.get("ok"):
            return jsonify({"status": "received", "order_id": order_id, "result": result}), 200
        return jsonify({"status": "received", "order_id": order_id, "result": result}), 202

    return jsonify({"status": "received", "order_id": order_id}), 200


if __name__ == "__main__":
    if not KYC_STATUS_FILE.exists():
        write_json(KYC_STATUS_FILE, {})
    ensure_transactions_file()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

