# Safe E-commerce / Corporate Trading Runbook

This project is intentionally sandbox-first.

Required defaults:
- LIVE_RUN=false
- DRY_RUN=true
- AUTO_APPROVE=false

Safe flow:
1. Put all provider credentials in a secure secret store or .env file that is not committed.
2. Keep live processing off until there is approval, provider contract, KYC/AML, and reconciliation.
3. Create approval marker files in approvals/:
   - python approval_helper.py intent-001
4. Test all flows in Stripe test mode or sandbox mode.
5. Only when legal/compliance approves, switch LIVE_RUN=true and use production credentials.

Checklist before any live activation:
- Provider contract signed
- KYC/AML check implemented
- Fraud/risk rules configured
- Daily reconciliation enabled
- Audit log retention in place
- Live credentials stored in secrets manager
- Human approval gate configured
- Test mode passed successfully
