# Production Activation Runbook — Tailored for 18&ok LLC

This runbook expands the earlier runbook to reflect that the LLC will take title to assets. It lists required sign-offs, owners, and a go/no-go checklist for production activation.

[Follow the previously supplied comprehensive checklist here.]

Sign-off fields:
- Legal (name / date):
- Finance (name / date):
- Compliance (name / date):
- Operations (name / date):
- Technical (name / date):

Go/No-Go criteria (all must be met):
- Securities counsel check completed (if stocks involved): YES / NO
- Money-transmission risk assessment completed: YES / NO
- Custody arrangement or escrow in place for investor funds: YES / NO
- KYC/AML integration completed and tested: YES / NO
- Insurance and title/provenance verification processes in place: YES / NO
- Reconciliation automation & reports in place: YES / NO
- Manual approval gate configured and tested: YES / NO
- Monitoring/alerts configured and tested: YES / NO

Rollback & emergency procedures
- Disable LIVE_RUN environment variable and trigger incident response
- Pause new acquisition intents and place open intents on hold
- Notify legal & finance and begin containment

(Commit this file with attachments and update after counsel review.)