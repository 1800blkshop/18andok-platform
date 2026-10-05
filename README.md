# 18andok-platform
Connecting the plug 🔌 to the socket 
# 18andok-platform
Connecting the plug 🔌 to the socket.

This repository contains a lightweight autonomous market strategy agent that reads live market data,
updates the `active_market_matrix.json` file, and optionally syncs changes back to GitHub when a
valid token is available in the environment.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python autonomous_agent.py
