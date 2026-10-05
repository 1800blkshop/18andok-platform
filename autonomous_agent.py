import os
import sys
import json
import yfinance as yf
from git import Repo

# 1. FIXED BUSINESS PARAMS FOR 18&OK LLC
BUSINESS_NAME = "18&ok"
PROFIT_TARGET = 100000.00
MARKET_LOCATION = "East Baton Rouge, LA"

def fetch_macro_indicators():
    """Gathers real-time economic indicators to tune the business aggressive scale."""
    print("[1/4] Scanning global economic telemetry...")
    metrics = {"sp500": None, "btc": None}
    try:
        # Check standard equity markets and core digital assets
        sp = yf.Ticker("^GSPC").history(period="1d")
        btc = yf.Ticker("BTC-USD").history(period="1d")
        
        if not sp.empty:
            metrics["sp500"] = float(sp['Close'].iloc[-1])
        if not btc.empty:
            metrics["btc"] = float(btc['Close'].iloc[-1])
    except Exception as e:
        print(f"Warning: Market data fetch interrupted: {e}")
    return metrics

def execute_strategic_rebalance(metrics):
    """Dynamically alters operations to maximize sales velocities based on economic metrics."""
    print("[2/4] Recalculating margins for maximum conversion...")
    
    # Baseline defaults for high-margin wholesale, gear, and jewelry lines
    operational_matrix = {
        "business": BUSINESS_NAME,
        "target_profit": PROFIT_TARGET,
        "location_node": MARKET_LOCATION,
        "status": "AGGRESSIVE_RUNNING",
        "parameters": {
            "wholesale_markup_percentage": 0.35,
            "jewelry_premium_multiplier": 1.50,
            "lead_generation_velocity": "MAX",
            "ad_spend_distribution": "NATIONAL_INTERNATIONAL"
        }
    }
    
    # If macro indicators suggest high liquidity, automatically crank up high-ticket margins
    if metrics["sp500"] and metrics["sp500"] > 5500:
        operational_matrix["parameters"]["wholesale_markup_percentage"] = 0.45
        operational_matrix["parameters"]["jewelry_premium_multiplier"] = 1.75
        operational_matrix["strategy_mode"] = "MAX_VELOCITY_EXPANSION"
    else:
        operational_matrix["strategy_mode"] = "HIGH_CONVERSION_EFFICIENCY"
        
    return operational_matrix

def commit_and_sync_infrastructure(matrix_data):
    """Autonomously overrides repository config files and force pushes updates to GitHub."""
    print("[3/4] Packaging system modifications...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Write live structural definitions directly to disk
    matrix_file_path = os.path.join(base_dir, "active_market_matrix.json")
    with open(matrix_file_path, "w") as f:
        json.dump(matrix_data, f, indent=4)
        
    try:
        print("[4/4] Activating autonomous git synchronization loop...")
        repo = Repo(base_dir)
        
        # Configure Git identifiers safely for the system worker
        repo.config_writer().set_value("user", "name", "18andok Autonomous Agent").release()
        repo.config_writer().set_value("user", "email", "1800blkshop@gmail.com").release()
        
        # Stages, commits, and routes updates directly back to GitHub
        repo.git.add(matrix_file_path)
        if repo.is_dirty():
            repo.index.commit("AI Optimization Engine: Re-balanced parameters for $100k target.")
            origin = repo.remote(name='origin')
            origin.push()
            print(">> Success: System parameters synchronized. Render deployment triggered automatically.")
        else:
            print(">> System Optimal: No structural variation detected. Running at peak velocity.")
    except Exception as e:
        print(f"Execution Error: Git automation loop requires active environment tokens. Details: {e}")

if __name__ == "__main__":
    market_signals = fetch_macro_indicators()
    current_strategy = execute_strategic_rebalance(market_signals)
    commit_and_sync_infrastructure(current_strategy)
