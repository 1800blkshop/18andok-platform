# Safe corporate trading and bookkeeping

This repository contains a sandbox-only corporate trading module for 18&ok LLC / "OK".

Important:
- LIVE_RUN is disabled by default.
- DRY_RUN is enabled by default.
- No real payment or settlement call is made unless you explicitly configure a real provider and verify compliance.

What the module does:
- Calculates profit margins using Decimal.
- Validates the required margin threshold.
- Writes immutable ledger records under corporate_ledger/.
- Tracks realized profits in accounting.json.
- Simulates BUY/SELL operations for sandbox testing.
- Requires approval to run a live provider call.

Environment variables:
- LIVE_RUN=false
- DRY_RUN=true
- MIN_REQUIRED_MARGIN=0.25
- CORP_LEDGER_DIR=./corporate_ledger
- APPROVAL_DIR=./approvals

Operational guidance:
- Keep this sandbox-only until KYC/AML is implemented and a provider contract is approved.
- Create approval markers in approvals/<trade_id>.approved if you want to allow a trade to proceed in a test environment.
- Never commit real secret keys or production bank account details.
