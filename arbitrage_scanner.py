#!/usr/bin/env python3
"""Refactored arbitrage scanner with approval-gated transfer flow for 18&ok LLC.

Flow:
- Scanner finds profitable deals and creates a PENDING transaction record in transactions.json
- KYC/AML checks are performed using kyc_status.json (editable by operators) or external provider hooks
- Manual approval is required unless AUTO_APPROVE is enabled for testing
- Once approved and KYC-clear, the system will attempt a transfer using the configured provider in SANDBOX mode

Safety defaults:
- LIVE_RUN defaults to false; money will never flow without setting LIVE_RUN=true and configuring a real provider
- AUTO_APPROVE defaults to false; approvals must be granted by creating an approval file or setting AUTO_APPROVE
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Decimal precision for money-safe calculations
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

# Operational constraints for 18&ok LLC
MIN_PROFIT_MARGIN = Decimal(os.getenv("MIN_PROFIT_MARGIN", "0.25"))
TARGET_SECTORS = [sector.lower() for sector in os.getenv("TARGET_SECTORS", "tools,retail_lots,industrial").split(",")]
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in {"1", "true", "yes", "y"}
AUTO_APPROVE = os.getenv("AUTO_APPROVE", "false").lower() in {"1", "true", "yes", "y"}
LIVE_RUN = os.getenv("LIVE_RUN", "false").lower() in {"1", "true", "yes", "y"}
APPROVAL_TIMEOUT = int(os.getenv("APPROVAL_TIMEOUT_SECONDS", "3600"))

TRADE_HUB_API_KEY = os.getenv("TRADE_HUB_API_KEY")
WHOLESALE_API_KEY = os.getenv("WHOLESALE_API_KEY")
TRADE_HUB_BASE = os.getenv("TRADE_HUB_BASE_URL", "https://b2b-trade-hub.example")
WHOLESALE_BASE = os.getenv("WHOLESALE_BASE_URL", "https://wholesale-supply.example")

# Files
BASE_DIR = Path(__file__).resolve().parent
TRANSACTIONS_FILE = BASE_DIR / "transactions.json"
KYC_STATUS_FILE = BASE_DIR / "kyc_status.json"
APPROVALS_DIR = BASE_DIR / "approvals"
APPROVALS_DIR.mkdir(exist_ok=True)

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("arbitrage_scanner")


def init_session(timeout: float = 10.0, max_retries: int = 3) -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=max_retries,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods={"GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"},
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"Accept": "application/json"})
    session.timeout = timeout
    return session


SESSION = init_session()


def safe_decimal(value: Any) -> Optional[Decimal]:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    try:
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").strip()
            return Decimal(cleaned)
        return Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return None


def mask_payload(payload: Dict[str, Any], keys_to_mask: tuple[str, ...] = ("buyer_id", "supplier_id")) -> Dict[str, Any]:
    masked = dict(payload)
    for key in keys_to_mask:
        if key in masked:
            masked[key] = "[REDACTED]"
    return masked


def read_json_file(path: Path, default: Any):
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        logger.exception("Failed to read JSON from %s", path)
        return default


def write_json_file(path: Path, data: Any) -> None:
    try:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        logger.exception("Failed to write JSON to %s", path)


# Transaction ledger helpers
def ensure_transactions_file():
    if not TRANSACTIONS_FILE.exists():
        write_json_file(TRANSACTIONS_FILE, [])


def append_transaction(tx: Dict[str, Any]) -> None:
    ensure_transactions_file()
    transactions = read_json_file(TRANSACTIONS_FILE, [])
    transactions.append(tx)
    write_json_file(TRANSACTIONS_FILE, transactions)


def update_transaction_status(tx_id: str, status: str, extras: Optional[Dict[str, Any]] = None) -> None:
    transactions = read_json_file(TRANSACTIONS_FILE, [])
    changed = False
    for tx in transactions:
        if tx.get("id") == tx_id:
            tx["status"] = status
            tx["updated_at"] = datetime.utcnow().isoformat() + "Z"
            if extras:
                tx.update(extras)
            changed = True
            break
    if changed:
        write_json_file(TRANSACTIONS_FILE, transactions)


# KYC/AML stub — uses kyc_status.json for operators to mark IDs as clear
def is_kyc_clear(entity_id: str) -> bool:
    status_map = read_json_file(KYC_STATUS_FILE, {})
    val = status_map.get(entity_id)
    if isinstance(val, str):
        return val.lower() in {"clear", "true", "approved"}
    return bool(val)


# Approval helpers — approval can be given by creating a file approvals/{tx_id}.approved
# or by enabling AUTO_APPROVE (for testing only)
def approval_file_path(tx_id: str) -> Path:
    return APPROVALS_DIR / f"{tx_id}.approved"


def is_approved(tx_id: str) -> bool:
    if AUTO_APPROVE:
        logger.info("AUTO_APPROVE is enabled — treating transaction %s as approved", tx_id)
        return True
    if approval_file_path(tx_id).exists():
        return True
    return False


def wait_for_approval(tx_id: str, timeout_seconds: int = APPROVAL_TIMEOUT) -> bool:
    """Polls for an approval file for up to timeout_seconds. Returns True if approved."""
    start = time.time()
    logger.info("Waiting up to %s seconds for approval of transaction %s", timeout_seconds, tx_id)
    while time.time() - start < timeout_seconds:
        if is_approved(tx_id):
            logger.info("Transaction %s approved", tx_id)
            return True
        time.sleep(5)
    logger.warning("Approval timeout for transaction %s", tx_id)
    return False


# Provider integration stub — SANDBOX by default. Do not use in production without proper credentials
def provider_transfer(tx: Dict[str, Any]) -> Dict[str, Any]:
    # If LIVE_RUN is false, simulate a sandbox transfer and return a fake transaction id
    logger.info("Provider transfer called for tx %s (LIVE_RUN=%s)", tx.get("id"), LIVE_RUN)
    if not LIVE_RUN:
        fake_id = f"sandbox_{uuid4().hex}"
        logger.info("Simulating sandbox transfer, fake provider id=%s", fake_id)
        return {"success": True, "provider_id": fake_id, "mode": "SANDBOX"}

    # Placeholder: insert real provider call here (OAuth/mTLS, idempotency, retries, error handling)
    # Raise if not configured to prevent accidental money movement
    logger.error("LIVE_RUN requested but no provider implementation is configured. Aborting transfer.")
    return {"success": False, "error": "No provider configured"}


# API interactions (schema-validated minimal)
def fetch_live_buyer_demands() -> List[Dict[str, Any]]:
    if not TRADE_HUB_API_KEY:
        logger.error("TRADE_HUB_API_KEY not set; skipping buyer-demand fetch.")
        return []

    url = f"{TRADE_HUB_BASE}/api/requests"
    headers = {"Authorization": f"Bearer {TRADE_HUB_API_KEY}", "Accept": "application/json"}
    try:
        response = SESSION.get(url, headers=headers, params={"status": "active"}, timeout=SESSION.timeout)
        response.raise_for_status()
        data = response.json()
        requests_data = data.get("requests") or []
        if not isinstance(requests_data, list):
            logger.warning("Unexpected buyer-demand payload format: %r", data)
            return []
        return requests_data
    except Exception as exc:
        logger.exception("Error fetching buyer demands: %s", exc)
        return []


def find_supplier_match(item_keywords: str) -> Optional[Dict[str, Any]]:
    if not WHOLESALE_API_KEY:
        logger.error("WHOLESALE_API_KEY not set; skipping supplier match lookup.")
        return None

    url = f"{WHOLESALE_BASE}/api/search"
    params = {"q": item_keywords, "condition": "new", "bulk": "true", "limit": 10}
    headers = {"Authorization": f"Bearer {WHOLESALE_API_KEY}", "Accept": "application/json"}
    try:
        response = SESSION.get(url, headers=headers, params=params, timeout=SESSION.timeout)
        response.raise_for_status()
        data = response.json()
        products = data.get("products") or []
        if not isinstance(products, list):
            logger.warning("Unexpected supplier payload format: %r", data)
            return None

        valid_products: List[Dict[str, Any]] = []
        for product in products:
            price_decimal = safe_decimal(product.get("price"))
            supplier_id = product.get("supplier_id")
            if price_decimal is None or not supplier_id:
                continue
            valid_products.append({**product, "price_decimal": price_decimal})

        if not valid_products:
            return None

        return min(valid_products, key=lambda product: product["price_decimal"])
    except Exception as exc:
        logger.exception("Error finding supplier match for %s: %s", item_keywords, exc)
        return None


# Transaction creation and routing
def create_pending_transaction(buyer_data: Dict[str, Any], supplier_data: Dict[str, Any], supplier_cost: Decimal, buyer_target_price: Decimal) -> Dict[str, Any]:
    tx_id = uuid4().hex
    tx = {
        "id": tx_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "status": "PENDING_APPROVAL",
        "buyer_id": buyer_data.get("buyer_id"),
        "supplier_id": supplier_data.get("supplier_id"),
        "product_name": buyer_data.get("product_name"),
        "buyer_target_price": str(buyer_target_price),
        "supplier_cost": str(supplier_cost),
        "gross_profit": str(buyer_target_price - supplier_cost),
    }
    append_transaction(tx)
    logger.info("Created pending transaction %s: %s", tx_id, mask_payload(tx))
    return tx


def handle_approval_and_transfer(tx: Dict[str, Any]) -> None:
    tx_id = tx["id"]

    # Verify KYC for both parties
    buyer_ok = is_kyc_clear(str(tx.get("buyer_id")))
    supplier_ok = is_kyc_clear(str(tx.get("supplier_id")))
    if not (buyer_ok and supplier_ok):
        logger.warning("KYC/AML not cleared for transaction %s (buyer_ok=%s supplier_ok=%s). Marking as ON_HOLD.", tx_id, buyer_ok, supplier_ok)
        update_transaction_status(tx_id, "ON_HOLD", extras={"kyc": {"buyer_ok": buyer_ok, "supplier_ok": supplier_ok}})
        return

    # Wait for approval (non-blocking in sense of long polling; controlled by timeout)
    if not is_approved(tx_id):
        approved = wait_for_approval(tx_id)
        if not approved:
            update_transaction_status(tx_id, "AWAITING_APPROVAL")
            logger.info("Transaction %s awaiting manual approval", tx_id)
            return

    # Execute provider transfer (sandbox or live depending on LIVE_RUN)
    update_transaction_status(tx_id, "APPROVED")
    result = provider_transfer(tx)
    if result.get("success"):
        update_transaction_status(tx_id, "COMPLETED", extras={"provider_id": result.get("provider_id")})
        logger.info("Transaction %s completed via provider id=%s", tx_id, result.get("provider_id"))
    else:
        update_transaction_status(tx_id, "FAILED", extras={"provider_error": result.get("error")})
        logger.error("Transaction %s failed: %s", tx_id, result.get("error"))


def prepare_deal_routing(buyer_data: Dict[str, Any], supplier_data: Dict[str, Any], supplier_cost: Decimal, buyer_target_price: Decimal) -> None:
    """Create a pending transaction and attempt approval-gated routing."""
    tx = create_pending_transaction(buyer_data, supplier_data, supplier_cost, buyer_target_price)

    # If DRY_RUN is set, do not proceed with approval/transfer step
    if DRY_RUN:
        logger.info("DRY_RUN enabled; transaction %s will remain pending for manual inspection.", tx["id"])
        return

    # For convenience, attempt to handle approval and transfer immediately (will respect approval gating)
    handle_approval_and_transfer(tx)


def execute_arbitrage_scan() -> None:
    logger.info("Initiating 18&ok LLC profit scanning loop...")
    active_demands = fetch_live_buyer_demands()

    for demand in active_demands:
        category = (demand.get("category") or "").lower()
        product_name = demand.get("product_name")
        buyer_target_price = safe_decimal(demand.get("target_price"))
        buyer_id = demand.get("buyer_id")

        if not product_name or buyer_id is None or buyer_target_price is None or buyer_target_price <= 0:
            logger.debug("Skipping incomplete demand: %s", demand)
            continue

        if not any(sector in category for sector in TARGET_SECTORS):
            logger.debug("Skipping demand outside target sectors: %s", category)
            continue

        supplier_match = find_supplier_match(product_name)
        if not supplier_match:
            logger.debug("No supplier match found for %s", product_name)
            continue

        supplier_cost = supplier_match.get("price_decimal")
        if supplier_cost is None:
            logger.debug("Supplier match missing price for %s", product_name)
            continue

        gross_profit = buyer_target_price - supplier_cost
        margin = gross_profit / buyer_target_price if buyer_target_price != 0 else Decimal("0")

        if margin >= MIN_PROFIT_MARGIN:
            logger.info(
                "[PROFIT OPPORTUNITY FOUND] Product=%s BuyerTarget=%s SupplierCost=%s ProjectedMargin=%.2f%% NetProfit=%s",
                product_name,
                buyer_target_price,
                supplier_cost,
                float(margin * Decimal("100")),
                gross_profit,
            )
            # enrich buyer_data for transaction record
            buyer_data = {**demand, "product_name": product_name}
            prepare_deal_routing(buyer_data, supplier_match, supplier_cost, buyer_target_price)
        else:
            logger.debug("Demand %s did not meet minimum margin requirement: %.2f%%", product_name, float(margin * Decimal("100")))


if __name__ == "__main__":
    # Ensure supporting files exist
    ensure_transactions_file()
    if not KYC_STATUS_FILE.exists():
        write_json_file(KYC_STATUS_FILE, {})

    execute_arbitrage_scan()

