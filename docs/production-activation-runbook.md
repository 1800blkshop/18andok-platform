# Production Activation Runbook — Non-Custodial Mode (18&ok LLC)

This runbook details go/no-go criteria and checks when operating in non-custodial mode (Company collects service fees only; settlements occur via escrow or connected accounts).

Sign-off fields:
- Legal (name / date):
- Finance (name / date):
- Compliance (name / date):
- Operations (name / date):
- Technical (name / date):

Go/No-Go criteria (all must be met):
- Counsel confirms non-custodial model reduces licensing risk for planned activities: YES / NO
- KYC/AML screening provider integrated and tested: YES / NO
- Payment provider configured to capture service fees and to instruct or coordinate escrow/Connect payouts: YES / NO
- Webhook signature verification and replay protection implemented: YES / NO
- Idempotency keys and retries tested in sandbox: YES / NO
- Approval gating for fee capture configured and tested: YES / NO
- Reconciliation automation in place for settlements and fee captures: YES / NO

Operational steps to enable service-fee capture (sandbox first)
1) Set LIVE_RUN=false and use test provider keys.
2) Ensure .env and secrets store only test keys.
3) Run full sandbox flows: fee capture, webhook handling, idempotency replay, and ledger reconciliation.
4) After counsel sign-off, test a staged pilot with a small set of vetted buyers/sellers.

Emergency rollback
- Disable fee-capture by setting LIVE_RUN=false or flipping feature flag.
- Put all new intents on hold and notify legal & finance.

(Keep this file updated after counsel review.)