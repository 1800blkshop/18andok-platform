#!/usr/bin/env python3
"""
18&ok LLC — platform worker entry point.

This is the long-running process the Render background workers start
(`python main.py`). It runs the arbitrage/deal scan on a fixed interval
and stays alive between sweeps, logging a heartbeat so the service is
visibly healthy in the Render console.

Safety defaults (sandbox-first, per README-runbook.md):
- LIVE_RUN=false, DRY_RUN=true, AUTO_APPROVE=false unless the environment
  explicitly overrides them. No real money moves from this process.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone

# Render env vars were originally created with mixed/lowercase names
# (e.g. "Stripe_secret_key"). The code base reads UPPERCASE names, so
# normalize any lowercase variant into its uppercase form at startup.
_KNOWN_KEYS = [
    "STRIPE_SECRET_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "OWNER_CELL_PHONE",
    "LIVE_RUN",
    "DRY_RUN",
    "AUTO_APPROVE",
    "TRADE_HUB_API_KEY",
    "WHOLESALE_API_KEY",
]
_lower_map = {k.lower(): k for k in os.environ}
for _key in _KNOWN_KEYS:
    if _key not in os.environ and _key.lower() in _lower_map:
        os.environ[_key] = os.environ[_lower_map[_key.lower()]]

# Sandbox-first safety defaults.
os.environ.setdefault("LIVE_RUN", "false")
os.environ.setdefault("DRY_RUN", "true")
os.environ.setdefault("AUTO_APPROVE", "false")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("18andok-main")

SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "3600"))


def run_one_sweep() -> None:
    """Run a single deal/arbitrage scan. Never raises."""
    try:
        from arbitrage_scanner import ensure_transactions_file, execute_arbitrage_scan

        ensure_transactions_file()
        execute_arbitrage_scan()
        logger.info("Sweep complete.")
    except Exception as exc:  # keep the worker alive on any scan failure
        logger.error("Sweep failed (worker staying alive): %s", exc)


def main() -> None:
    logger.info("=== 18&ok LLC platform worker starting ===")
    logger.info(
        "Safety flags: LIVE_RUN=%s DRY_RUN=%s AUTO_APPROVE=%s | scan interval=%ss",
        os.environ["LIVE_RUN"],
        os.environ["DRY_RUN"],
        os.environ["AUTO_APPROVE"],
        SCAN_INTERVAL_SECONDS,
    )
    while True:
        logger.info(
            "Heartbeat %s — running sweep",
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        )
        run_one_sweep()
        logger.info("Sleeping %ss until next sweep.", SCAN_INTERVAL_SECONDS)
        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
