#!/usr/bin/env python3
"""Refactored arbitrage scanner for 18&ok LLC.

This script scans active buyer demands, finds the cheapest supplier match,
computes a gross margin, and stages a deal payload for approval.

Note: The code intentionally does not trigger live funding or escrow movement
unless DRY_RUN is disabled and a proper production integration is configured.
"""

from __future__ import annotations

import logging
import os
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from typing import Any, Dict, List, Optional

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

TRADE_HUB_API_KEY = os.getenv("TRADE_HUB_API_KEY")
WHOLESALE_API_KEY = os.getenv("WHOLESALE_API_KEY")
TRADE_HUB_BASE = os.getenv("TRADE_HUB_BASE_URL", "https://b2b-trade-hub.example")
WHOLESALE_BASE = os.getenv("WHOLESALE_BASE_URL", "https://wholesale-supply.example")

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


def prepare_deal_routing(buyer_data: Dict[str, Any], supplier_data: Dict[str, Any], supplier_cost: Decimal) -> None:
    """Create a deal payload for review. No live transfer occurs in dry-run mode."""
    payload = {
        "business_name": "18&ok LLC",
        "trade_name": "OK",
        "buyer_id": buyer_data.get("buyer_id"),
        "supplier_id": supplier_data.get("supplier_id"),
        "funding_required": str(supplier_cost),
        "payout_destination_bank": "CONNECTED_ACCOUNT",
    }
    logger.info("Deal payload staged (DRY_RUN=%s): %s", DRY_RUN, mask_payload(payload))

    if DRY_RUN:
        logger.info("DRY_RUN enabled; no live funding or escrow transfer will be executed.")
        return

    # Replace this block with your provider-specific integration.
    logger.warning("Live funding sequence requested but not implemented. Ensure KYC, AML, audits, and approval gates are in place before production use.")


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
            prepare_deal_routing(demand, supplier_match, supplier_cost)
        else:
            logger.debug("Demand %s did not meet minimum margin requirement: %.2f%%", product_name, float(margin * Decimal("100")))


if __name__ == "__main__":
    execute_arbitrage_scan()
