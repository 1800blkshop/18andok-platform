# One-page Business Flow — 18&ok LLC (Draft for Counsel & Compliance)

Summary
- Business: 18&ok LLC acts as a matchmaker/agent and the LLC will take title to acquired assets (stocks, land, rare/exotic items) in the LLC's name.
- Role: source, vet, negotiate, acquire and hold assets under the LLC; connect buyers and sellers; provide curated sales and marketing outreach via AI; charge service/commission fees and/or sell assets on behalf of the LLC.

High-level flow
1) Opportunity Identification
   - AI/monitoring identifies candidate asset (stock position, parcel of land, rare item).  
   - Opportunity recorded with unique intent_id and stored in the ledger (corporate_ledger/).

2) Sourcing & Contracting
   - 18&ok negotiates purchase terms with seller.  
   - Seller agreement signed; title/provenance documents collected and stored (encrypted).  
   - LLC signs purchase contract and will take title in the LLC name upon closing.

3) Funding
   - Options:
     A) LLC funds purchase from its capital or investor capital under explicit custody agreement.
     B) Investor provides capital to LLC via escrow or designated account; funds recorded per-investor in ledger.
   - IMPORTANT: If investor capital is accepted, each investor's funds must be tracked and reconciled separately; funds-in-custody triggers money-transmitter and custody considerations.

4) Acquisition & Title
   - Asset transfer completes with title/proof assigned to 18&ok LLC.  
   - All provenance, title and insurance docs archived; accounting entries created with purchase price, fees, and reserves.

5) Holding & Management
   - Asset insured, stored or custodied per asset class (broker/custodian for securities, title company/escrow for real estate, insured storage/shipping for physical goods).  
   - Periodic valuations and ledger updates recorded.

6) Disposition (Sale to Buyer)
   - 18&ok markets and finds buyer using AI outreach; buyer enters purchase agreement with LLC.  
   - Buyer pays LLC (service fee and/or purchase price) via provider.  
   - On receipt and clearance of funds and completion of any milestones, transfer title to buyer and release funds per contract (minus commissions/fees).

7) Reconciliation & Reporting
   - Daily reconciliation of provider settlements to ledger entries; monthly financial reports; tax and audit reporting.

Controls & Approval Points
- Pre-purchase: legal review & signed seller contract required for any acquisition above threshold (configurable).  
- Funding in: any investor capital accepted requires KYC, investor agreement, escrow or custodian arrangement, and explicit finance/compliance sign-off.  
- Transfer of title: require documentation verifying title transfer and insurance confirmation.  
- Disposition: require payment clearance, AML/KYC check on buyer, and release approval.

Audit & Records
- Maintain immutable ledger files per transaction under corporate_ledger/ and accounting.json.  
- Store contracts, title/provenance, insurance, KYC results, and approval artifacts in an encrypted document store and link to the intent id.

Red flags (immediate counsel attention)
- If LLC accepts investor funds pooled/commingled to buy assets, money-transmission and custody laws may apply.  
- If the LLC facilitates securities purchases/sales for others, broker-dealer or investment-adviser licensing questions arise.
- Cross-border sale of restricted goods or cultural property require export permits and compliance.

Note: This document is a draft operational flow intended for counsel and compliance review. It is not legal advice.