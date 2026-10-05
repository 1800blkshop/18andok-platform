
import json
import os
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from git import Repo
except ImportError:
    Repo = None

BUSINESS_NAME = "18&ok"
PROFIT_TARGET = 100000.00
MARKET_LOCATION = "East Baton Rouge, LA"

def fetch_macro_indicators():
    print("[1/4] Scanning global economic telemetry...")
    metrics = {"sp500": None, "btc": None}

    if yf is None:
        print("Warning: yfinance is not installed. Skipping live market data fetch.")
        return metrics

    try:
        sp = yf.Ticker("^GSPC").history(period="1d")
        btc = yf.Ticker("BTC-USD").history(period="1d")

        if not sp.empty:
            metrics["sp500"] = float(sp["Close"].iloc[-1])
        if not btc.empty:
            metrics["btc"] = float(btc["Close"].iloc[-1])
    except Exception as exc:
        print(f"Warning: Market data fetch interrupted: {exc}")

    return metrics

def execute_strategic_rebalance(metrics):
    print("[2/4] Recalculating margins for maximum conversion...")

    operational_matrix = {
        "business": BUSINESS_NAME,
        "target_profit": PROFIT_TARGET,
        "location_node": MARKET_LOCATION,
        "status": "AGGRESSIVE_RUNNING",
        "parameters": {
            "wholesale_markup_percentage": 0.35,
            "jewelry_premium_multiplier": 1.50,
            "lead_generation_velocity": "MAX",
            "ad_spend_distribution": "NATIONAL_INTERNATIONAL",
        },
    }

    if metrics.get("sp500") and metrics["sp500"] > 5500:
        operational_matrix["parameters"]["wholesale_markup_percentage"] = 0.45
        operational_matrix["parameters"]["jewelry_premium_multiplier"] = 1.75
        operational_matrix["strategy_mode"] = "MAX_VELOCITY_EXPANSION"
    else:
        operational_matrix["strategy_mode"] = "HIGH_CONVERSION_EFFICIENCY"

    return operational_matrix

def write_market_matrix(matrix_data):
    base_dir = Path(__file__).resolve().parent
    matrix_file = base_dir / "active_market_matrix.json"
    matrix_file.write_text(json.dumps(matrix_data, indent=4) + "\n", encoding="utf-8")
    return matrix_file

def sync_to_github(matrix_file):
    if Repo is None:
        print("[3/4] GitPython is not installed. Skipping git sync.")
        return

    try:
        repo = Repo(str(matrix_file.parent))
    except Exception as exc:
        print(f"[3/4] Unable to open repository: {exc}")
        return

    if "origin" not in repo.remotes:
        print("[3/4] No origin remote configured. Skipping git sync.")
        return

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("[3/4] No GitHub token configured. Skipping git sync.")
        return

    print("[3/4] Packaging system modifications...")
    with repo.config_writer() as writer:
        writer.set_value("user", "name", "18andok Autonomous Agent")
        writer.set_value("user", "email", "1800blkshop@gmail.com")

    repo.git.add(str(matrix_file.name))
    if not repo.is_dirty(untracked_files=True):
        print("[4/4] System optimal: No structural variation detected.")
        return

    print("[4/4] Activating autonomous git synchronization loop...")
    repo.index.commit("AI Optimization Engine: Re-balanced parameters for $100k target.")
    origin = repo.remote(name="origin")
    origin.push()
    print(">> Success: System parameters synchronized. Render deployment triggered automatically.")

if __name__ == "__main__":
    market_signals = fetch_macro_indicators()
    current_strategy = execute_strategic_rebalance(market_signals)
    matrix_file = write_market_matrix(current_strategy)
    sync_to_github(matrix_file)
