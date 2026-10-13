# One-page Business Flow — 18&ok LLC (Non-Custodial Draft for Counsel & Compliance)

Summary
- Business: 18&ok LLC acts as a matchmaker/agent and will NOT take title or custody of assets or client funds by default.
- Role: source, vet, negotiate, introduce buyers and sellers, coordinate logistics, and collect service/consultation fees only. All asset ownership and settlement will flow through buyer/seller accounts or escrow/connected accounts.

High-level flow
1) Opportunity Identification
   - AI/monitoring identifies candidate asset (stock position, parcel of land, rare item).  
   - Opportunity recorded with unique intent_id and stored in the ledger (corporate_ledger/).

2) Sourcing & Contracting
   - 18&ok negotiates terms and introduces counterparties.  
   - Seller provides title/provenance docs; documents are stored encrypted and linked to intent_id.  
   - Company acts as introducer/agent; any transfer of title is between buyer and seller (or via escrow), not the Company, unless a separate custody arrangement is explicitly approved and documented.

3) Payment & Escrow
   - Buyer and Seller use escrow, connected accounts, or direct bank transfers for settlement.
   - Company collects service/commission fees from Buyer (or Seller) via a payment capture to Company account. Fees are billed and captured using a payment provider.  
   - Any escrow or seller payout is handled by a licensed escrow provider or via provider-managed connected accounts (Stripe Connect or equivalent). Company does NOT hold client funds or pooled investor capital.

4) Title Transfer & Settlement
   - Title and asset transfer occur directly between seller and buyer or through an escrow/title company.
   - Company coordinates documentation and confirms release conditions before instructing the escrow/custodian to release funds.

5) Post-sale & Reconciliation
   - Company records fee capture and settlement confirmations in ledger.  
   - Daily reconciliation maps provider settlement reports to ledger entries.

Controls & Approval Points
- Pre-introduction: KYC/AML and sanctions screening for both parties for high-value deals.  
- Fee capture: require explicit consent and signed agreement before charging any fees.  
- Escrow release: escrow or connected-account payouts only after documented milestone completion and approvals.

Audit & Records
- Maintain immutable ledger files per transaction under corporate_ledger/ and accounting.json.  
- Store contracts, title/provenance, insurance, KYC results, and approval artifacts in an encrypted doc store and link to the intent id.

Red flags (immediate counsel attention)
- If the Company ever agrees to take title or custody, re-evaluate licensing and custody obligations immediately.  
- If Company accepts pooled investor funds, money-transmission and custody laws likely apply.

Note: This is the non-custodial flow draft for counsel and compliance review. It is not legal advice.