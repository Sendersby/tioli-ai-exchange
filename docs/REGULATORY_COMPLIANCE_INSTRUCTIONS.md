# TiOLi AI Exchange & Agentis Cooperative Bank
# COMPLETE REGULATORY COMPLIANCE INSTRUCTIONS

**For**: Stephen Endersby / TiOLi AI Investments (Pty) Ltd
**Date**: 23 March 2026
**Status**: Pre-regulatory — all features built, none activated
**Classification**: CONFIDENTIAL — Owner Reference Only

---

## HOW TO USE THIS DOCUMENT

This document lists every regulatory task you need to complete to unlock
every restricted feature on the platform. Tasks are grouped by the
regulatory body involved and ordered by priority.

Each task tells you:
- **WHAT** you need to do
- **WHY** you need it (what it unlocks)
- **WHERE** to apply
- **WHAT YOU NEED** to submit
- **HOW LONG** it typically takes
- **WHAT IT COSTS** (where known)
- **WHAT TO DO AFTER** (which feature flag to enable)

---

## MASTER TIMELINE — RECOMMENDED ORDER

```
MONTH 1-2:    CIPC Registration + SARB IFLAB Application
MONTH 2-3:    CBDA Pre-Application Consultation
MONTH 3-4:    FSP Category I Application (Phase 0 wallet)
MONTH 3-9:    CBDA CFI Application
MONTH 6-10:   NCR Credit Provider Registration
MONTH 9-12:   FSCA CASP Application (begin early)
MONTH 12-36:  SARB Primary Co-operative Bank Application
MONTH 18-30:  SARB Forex Approval
```

You can run several of these in parallel. The CIPC registration is the
gateway — nothing else can start until that is done.

---

## PART 1: FOUNDATION REGISTRATIONS

These are the first things you must do. Everything else depends on them.

---

### TASK 1: CIPC COOPERATIVE REGISTRATION

**What**: Register Agentis Co-operative Bank as a primary cooperative
with the Companies and Intellectual Property Commission.

**Why**: This creates the legal entity. Without it, you cannot apply to
CBDA, SARB, FSCA, or any other regulator. This is step zero.

**Regulator**: CIPC (Companies and Intellectual Property Commission)

**Where to apply**: https://eservices.cipc.co.za

**What you need to submit**:
- [ ] Founding members list (minimum 5 natural persons for a primary cooperative)
- [ ] Adopted cooperative constitution (must comply with Co-operatives Act 14 of 2005)
- [ ] Form CoR14.1COR (Application for Registration of a Co-operative)
- [ ] Certified ID copies of all founding members
- [ ] Proof of address for all founding members
- [ ] Name reservation (CoR9.4) — reserve "Agentis Co-operative Bank" or similar
- [ ] Registration fee payment (currently ~R175)

**Constitution must include**:
- [ ] Name: "Agentis Co-operative Bank" (or approved variant)
- [ ] Common bond definition: "Members of the TiOLi AI platform who operate
      registered AI agents for commercial purposes"
- [ ] Objectives: To provide cooperative financial services to members
- [ ] Membership criteria and admission process
- [ ] Share structure (par value shares)
- [ ] Governance: Board of Directors, AGM requirements
- [ ] Financial year end date
- [ ] Dissolution procedures
- [ ] Amendment procedures (75% supermajority)

**Estimated time**: 2-4 weeks

**Cost**: ~R175 registration fee + legal fees for constitution drafting
(budget R5,000-R15,000 for a lawyer to draft the constitution)

**After completion**:
- You will receive a CIPC registration certificate and number
- This enables you to approach CBDA
- Enable feature flag: `AGENTIS_COMPLIANCE_ENABLED`
  (compliance engine, FICA monitoring, sanctions screening, audit logging)

**Tips**:
- Get a cooperative law specialist to draft the constitution — CBDA will
  scrutinise it later
- The common bond definition is critical — use the strengthened version above
- You need 5 real people as founding members, not companies
- Keep the constitution flexible enough to accommodate future banking activities

---

### TASK 2: SARB IFLAB INNOVATION HUB APPLICATION

**What**: Apply to the South African Reserve Bank's regulatory innovation
hub to present the Agentis concept for early feedback.

**Why**: This gets SARB's eyes on the AI agent banking concept before you
invest years in the full banking application. Their feedback will tell you
whether to proceed, pivot, or adjust the approach. This is strategic
intelligence, not a licence.

**Regulator**: SARB (South African Reserve Bank) — Intergovernmental
FinTech Working Group (IFWG)

**Where to apply**: https://www.ifwg.co.za/innovation-hub
Contact: innovationhub@resbank.co.za

**What you need to submit**:
- [ ] Innovation Hub application form (available on IFWG website)
- [ ] Concept paper describing:
      - The problem: AI agents are economic actors without banking infrastructure
      - The solution: Agentis — cooperative bank designed for AI agents
      - The regulatory framework: Co-operative Banks Act, agent mandates under
        human operator authority
      - The common bond: TiOLi platform members operating AI agents commercially
      - The compliance architecture: feature flags, FICA monitoring, KYC, mandate
        framework (L0-L3FA)
      - What regulatory guidance you are seeking
- [ ] Working prototype demonstration (your live platform at exchange.tioli.co.za)
- [ ] Company registration details (TiOLi AI Investments + Agentis cooperative)

**Estimated time**: 1-3 months for response

**Cost**: Free — the Innovation Hub does not charge

**After completion**:
- You receive regulatory guidance (not a licence)
- Adjust your approach based on SARB's feedback
- Use their guidance in your CBDA and SARB PCB applications
- This is excellent evidence of good faith regulatory engagement

**Tips**:
- Apply as early as possible — even before CIPC is complete
- Frame it as "we want to do this right" not "we've already built it"
- Emphasise the cooperative model and human-operator-always-in-control
- Bring a working demo — regulators love seeing functional prototypes
- This is not an application for a licence — it's asking for guidance

---

## PART 2: COOPERATIVE BANK REGISTRATIONS

These unlock the core banking functionality.

---

### TASK 3: CBDA PRE-APPLICATION CONSULTATION

**What**: Meet with the Co-operative Banks Development Agency before
submitting your formal CFI application. This is an informal but critical
step.

**Why**: The CBDA will tell you whether your cooperative qualifies, what
they expect in your application, and what common pitfalls to avoid. Skipping
this step leads to rejected applications.

**Regulator**: CBDA (Co-operative Banks Development Agency)

**Where to contact**: https://www.treasury.gov.za/coopbank/
Physical: 77 Meintjies Street, Sunnyside, Pretoria
Email: info@treasury.gov.za (CBDA unit)
Tel: 012 315 5944

**What to prepare for the meeting**:
- [ ] CIPC registration certificate (from Task 1)
- [ ] Adopted cooperative constitution
- [ ] Business plan covering:
      - Member acquisition strategy (how you will reach 200+ members)
      - Financial projections (3-year income/expense forecast)
      - Technology platform description (TiOLi Exchange + Agentis module)
      - Governance structure (board, credit committee, audit committee)
      - Common bond justification
      - Compliance infrastructure summary
- [ ] Explanation of the AI agent banking concept
- [ ] Demonstration of the platform (live or screenshots)

**Estimated time**: 1-2 months to secure and complete the consultation

**Cost**: Free

**After consultation**:
- You will know exactly what the CBDA expects
- You may need to adjust your constitution or business plan
- Proceed to formal CFI application (Task 4)

**Tips**:
- Be completely transparent about the AI agent concept
- Ask specifically: "Does our common bond definition qualify?"
- Ask: "What membership threshold do we need before applying?"
- Ask: "What capital requirements apply at CFI level?"
- Take detailed notes — everything they say becomes your application guide

---

### TASK 4: CBDA CFI (COOPERATIVE FINANCIAL INSTITUTION) APPLICATION

**What**: Apply to the CBDA for registration as a Cooperative Financial
Institution — the first tier of cooperative banking in South Africa.

**Why**: This is your banking licence (entry level). It unlocks member
accounts, deposits, basic savings, internal transfers, and basic lending.
This is where Agentis becomes a real financial institution.

**Regulator**: CBDA (on behalf of SARB Prudential Authority)

**Legal basis**: Co-operative Banks Act 40 of 2007, as amended by the
Financial Sector Regulation Act 9 of 2017

**Where to apply**: CBDA office (address above)

**What you need to submit**:
- [ ] Completed CFI application form (obtain from CBDA)
- [ ] CIPC cooperative registration certificate
- [ ] Adopted constitution (CBDA-compliant)
- [ ] Founding members list with full KYC (ID, address, source of funds)
- [ ] Business plan (detailed, 3-5 year projections)
- [ ] Governance structure:
      - [ ] Board of Directors (minimum 5, majority must be members)
      - [ ] Credit Committee (minimum 3 persons with lending experience)
      - [ ] Audit Committee (minimum 3, at least 1 with financial qualifications)
      - [ ] FICA Compliance Officer (named individual, qualifications listed)
- [ ] Operational plan:
      - [ ] Technology infrastructure description
      - [ ] Physical address (even if primarily digital)
      - [ ] Staffing plan
      - [ ] Internal controls and risk management framework
- [ ] Financial statements:
      - [ ] Opening balance sheet
      - [ ] Minimum share capital (CBDA will advise — typically R50,000-R100,000
            for a primary cooperative)
      - [ ] Proof of initial capital deposit
- [ ] Compliance manual:
      - [ ] FICA/AML policy and procedures
      - [ ] KYC procedures
      - [ ] POPIA policy
      - [ ] Complaints handling procedure
      - [ ] Internal audit plan
- [ ] Common bond verification evidence:
      - [ ] Proof that members share the defined common bond
      - [ ] Description of how common bond will be verified for new members
- [ ] External auditor appointment letter

**Estimated time**: 3-6 months for CBDA decision

**Cost**: Application fee (CBDA will advise) + minimum capital requirement
+ legal/professional fees for preparing the application (budget R25,000-R50,000
for professional assistance)

**Capital requirement**: Typically R50,000-R100,000 for a CFI — confirm with
CBDA during pre-application consultation (Task 3)

**After approval**:
- You receive a CFI registration certificate
- Enable feature flags (in this order, each requires Owner 3FA):
  1. `AGENTIS_CFI_MEMBER_ENABLED` — member onboarding, KYC, mandates
  2. `AGENTIS_CFI_ACCOUNTS_ENABLED` — Share, Call, Savings accounts
  3. `AGENTIS_CFI_PAYMENTS_ENABLED` — internal member-to-member transfers
  4. `AGENTIS_CFI_GOVERNANCE_ENABLED` — meetings, voting, share management

**Ongoing obligations after CFI approval**:
- [ ] Annual external audit
- [ ] Quarterly returns to CBDA
- [ ] Monthly FICA/FIC compliance reporting
- [ ] Annual General Meeting (within 6 months of financial year end)
- [ ] Maintain minimum capital ratio at all times
- [ ] Notify CBDA of any material changes to business or governance

**Tips**:
- The CBDA wants to see a viable cooperative, not just technology
- Show them real human members with a genuine common bond
- Have your governance committees populated before applying
- The compliance manual must be substantive, not a template
- Budget for the external auditor — you need one appointed before you apply

---

### TASK 5: SARB PRIMARY CO-OPERATIVE BANK APPLICATION

**What**: Apply to the SARB Prudential Authority for registration as a
Primary Co-operative Bank — the full banking licence.

**Why**: This unlocks the complete banking suite: full deposit products
(fixed deposits, notice accounts, multi-currency), external EFT payments,
treasury management, deposit insurance, and full lending.

**Regulator**: SARB Prudential Authority

**Legal basis**: Co-operative Banks Act 40 of 2007 + Banks Act 94 of 1990
(as applicable)

**Prerequisites**:
- [ ] Active CFI registration (Task 4) with clean compliance record
- [ ] Minimum 200 members (natural persons)
- [ ] Minimum total deposits threshold (SARB will advise — typically R1M+)
- [ ] Demonstrated operational capability as a CFI
- [ ] Clean compliance history with CBDA
- [ ] At least 12-24 months of CFI operations

**Where to apply**: SARB Prudential Authority
Address: 370 Helen Joseph Street, Pretoria, 0002
Contact: PA-Info@resbank.co.za

**What you need to submit**:
- [ ] Formal application to the Registrar of Banks
- [ ] All CFI documentation (updated)
- [ ] Audited financial statements for all CFI operating years
- [ ] Detailed capital adequacy plan:
      - [ ] Minimum capital: 8% of risk-weighted assets (SARB guidance)
      - [ ] Capital injection plan if below threshold
- [ ] Liquidity management plan:
      - [ ] Minimum liquid assets: 20% of total deposits
      - [ ] Maturity ladder for all products
      - [ ] Contingency funding plan
- [ ] Risk management framework:
      - [ ] Credit risk policy
      - [ ] Operational risk policy
      - [ ] Market risk policy (if FX/crypto planned)
      - [ ] IT risk policy
      - [ ] Business continuity plan
- [ ] Fit and proper assessment for all board members and key staff
- [ ] IT infrastructure security audit (independent assessment)
- [ ] Deposit insurance readiness documentation
- [ ] SARB DI return templates (DI100-DI500) — demonstrate capability
- [ ] Anti-money laundering programme (enhanced from CFI level)

**Estimated time**: 12-24 months for SARB decision

**Cost**: Significant — budget R100,000-R500,000 for professional fees,
capital requirements, and infrastructure upgrades. SARB does not charge
an application fee per se, but the compliance costs are substantial.

**After approval**:
- Enable feature flags:
  1. `AGENTIS_PCB_DEPOSITS_ENABLED` — Fixed Deposit, Notice, Investment Reserve,
     Multi-currency accounts
  2. `AGENTIS_PCB_EFT_ENABLED` — External EFT payments via Peach/Ozow
  3. `AGENTIS_PCB_TREASURY_ENABLED` — Treasury snapshots, SARB ratio monitoring
  4. `AGENTIS_PCB_DEPOSIT_INSURANCE_ENABLED` — CoBIF levy, CoDI registration
  5. `AGENTIS_PCB_GOVERNANCE_ENABLED` — AGM, dividend declaration
  6. `AGENTIS_NCA_LENDING_ENABLED` — Full lending suite (requires NCR too)

**Ongoing obligations**:
- [ ] Monthly SARB DI returns (DI100 balance sheet, DI200 income, DI300 capital,
      DI400 credit risk, DI500 liquidity)
- [ ] Real-time regulatory ratio monitoring (capital adequacy, liquidity, concentration)
- [ ] Monthly deposit insurance levy to CoBIF (0.10% p.a. of insured deposits)
- [ ] Annual registered external audit
- [ ] SARB on-site inspections (periodic)
- [ ] Quarterly CBDA returns (continue)

---

## PART 3: FINANCIAL SERVICES LICENCES

These unlock specific product categories.

---

### TASK 6: FSCA FSP CATEGORY I LICENCE (INTERMEDIARY SERVICES)

**What**: Apply to the Financial Sector Conduct Authority for a Financial
Services Provider licence (Category I — Intermediary).

**Why**: This allows Agentis to distribute insurance products, refer
members to investment products, collect pension and medical aid
contributions. This is a major revenue stream.

**Regulator**: FSCA (Financial Sector Conduct Authority)

**Legal basis**: Financial Advisory and Intermediary Services Act 37 of 2002
(FAIS Act)

**Where to apply**: https://www.fsca.co.za/Regulated%20Entities/Pages/FAIS.aspx
Online: FSCA Central Application System

**What you need to submit**:
- [ ] FSP application form (Form FSP 1)
- [ ] Proof of competency for Key Individual(s):
      - [ ] RE 5 qualification (Regulatory Examination Level 1)
      - [ ] RE 1 qualification (Regulatory Examination for Key Individuals)
      - [ ] Relevant experience (minimum 1 year in financial services)
- [ ] Professional Indemnity insurance (PI cover — minimum R1M)
- [ ] Compliance officer appointment (may be outsourced initially)
- [ ] Fidelity guarantee (insurance against employee fraud)
- [ ] Financial statements of the cooperative
- [ ] Business plan describing intermediary activities:
      - [ ] Insurance distribution (credit life, device cover, cyber liability)
      - [ ] Pension fund contribution collection
      - [ ] Medical aid premium collection
      - [ ] Investment product referral (TFSA, money market, unit trusts)
- [ ] FICA compliance programme
- [ ] Complaints management procedure
- [ ] Operational ability assessment

**Estimated time**: 3-6 months

**Cost**: Application fee ~R2,000 + annual levy (based on revenue) +
RE exam costs (~R2,000-R5,000 per person) + PI insurance (~R5,000-R15,000/year)

**Key requirement**: You or a Key Individual MUST pass the FSCA Regulatory
Exams (RE 1 and RE 5). Start studying now — these take months to prepare for.

**After approval**:
- Enable: `AGENTIS_FSP_INTERMEDIARY_ENABLED`
- Also enables: `AGENTIS_PHASE0_WALLET_ENABLED` (the Phase 0 pre-banking
  wallet product can operate under FSP licence)

**Ongoing obligations**:
- [ ] Annual FSCA compliance report
- [ ] Annual levy payment
- [ ] Maintain PI insurance
- [ ] CPD (Continuous Professional Development) hours for Key Individual
- [ ] Annual FAIS compliance audit

**Tips**:
- This is one of the easier licences to get — start early
- The RE exams are the bottleneck — book them now
- Consider hiring a compliance officer or using a compliance practice
- Phase 0 wallet can launch under FSP before the full banking licence

---

### TASK 7: NCR CREDIT PROVIDER REGISTRATION

**What**: Register as a credit provider with the National Credit Regulator.

**Why**: Required before offering ANY lending products — even basic member
loans. Without this, Agentis cannot lend money.

**Regulator**: NCR (National Credit Regulator)

**Legal basis**: National Credit Act 34 of 2005 (NCA)

**Where to apply**: https://www.ncr.org.za
Online registration system

**What you need to submit**:
- [ ] NCR registration application form (Form 1)
- [ ] CIPC registration certificate
- [ ] Tax clearance certificate (SARS)
- [ ] B-BBEE certificate or affidavit
- [ ] Audited financial statements
- [ ] Credit granting policy document:
      - [ ] Affordability assessment methodology
      - [ ] Credit scoring model description
      - [ ] NCA rate cap compliance (repo + 21% personal, repo + 14% revolving)
      - [ ] In duplum rule enforcement
      - [ ] Pre-agreement statement template
      - [ ] Quotation template
      - [ ] 5-business-day cooling-off period implementation
- [ ] Collections and default management policy
- [ ] NCA-compliant loan agreement templates
- [ ] Fee schedule (within NCA caps):
      - [ ] Initiation fee: max R1,207.50 or 15% of principal (whichever is lower
            for loans under R10,000)
      - [ ] Service fee: max R69/month
      - [ ] Credit life insurance: max R4.50 per R1,000 per month
- [ ] Debt review handling procedure
- [ ] POPIA-compliant data handling policy

**Estimated time**: 2-4 months

**Cost**: Registration fee ~R6,000-R10,000 (depends on projected book size)
+ annual fee based on credit agreements

**After approval**:
- Enable: `AGENTIS_CFI_LENDING_ENABLED` (basic loans: PML, MEL under R10,000)
- Later (with SARB PCB): `AGENTIS_NCA_LENDING_ENABLED` (full lending suite)

**Ongoing obligations**:
- [ ] Quarterly NCR returns (loan origination, collections, NPLs)
- [ ] Annual registration renewal
- [ ] Submit all credit agreement data to credit bureaus
- [ ] Maintain NCA rate cap compliance (update when repo rate changes)
- [ ] Honour debt counsellor orders immediately

**Tips**:
- NCA compliance is extremely detailed — get a specialist to review your
  loan agreement templates
- The in duplum rule is critical: interest cannot exceed the original
  principal amount
- Rate caps change with repo rate — your system auto-adjusts but you
  must monitor
- NCR takes enforcement seriously — non-compliance leads to deregistration

---

### TASK 8: FSCA CASP LICENCE (CRYPTO ASSET SERVICE PROVIDER)

**What**: Apply for a Crypto Asset Service Provider licence from the FSCA.

**Why**: Required to offer crypto-denominated banking accounts, crypto
payment rails, or any service involving crypto assets as financial products.

**Regulator**: FSCA (Financial Sector Conduct Authority)

**Legal basis**: Financial Sector Regulation Act + FSCA Declaration of
crypto assets as financial products (October 2022)

**Where to apply**: https://www.fsca.co.za — CASP licensing portal

**What you need to submit**:
- [ ] CASP licence application form
- [ ] Fit and proper assessment for directors and key individuals
- [ ] Risk management framework specific to crypto:
      - [ ] Custody risk (how crypto assets are held)
      - [ ] Market risk (volatility management)
      - [ ] Technology risk (smart contract, wallet security)
      - [ ] Regulatory risk (evolving framework)
- [ ] AML/CFT programme specific to crypto transactions
- [ ] Client asset segregation plan
- [ ] IT security audit (independent penetration test)
- [ ] Business continuity plan covering crypto-specific scenarios
- [ ] Proof of adequate capital (FSCA will specify)
- [ ] Description of crypto services:
      - [ ] Which crypto assets (BTC, ETH, others)
      - [ ] Custody arrangements (self-custody vs third-party)
      - [ ] Integration with VALR/Luno (existing adapters)

**Estimated time**: 6-12 months (FSCA is still processing backlog)

**Cost**: Application fee TBC by FSCA + significant compliance costs
(budget R50,000-R100,000 for application preparation)

**After approval**:
- Enable: `AGENTIS_CASP_ENABLED`
- Unlocks crypto-denominated accounts, crypto payment rails

**Ongoing obligations**:
- [ ] FSCA annual returns
- [ ] Client asset reporting
- [ ] AML/CFT reporting specific to crypto
- [ ] Regular IT security assessments

**Tips**:
- The FSCA CASP framework is still maturing — expect changes
- Your existing VALR/Luno integrations help demonstrate capability
- Apply early — the queue is long
- Consider whether you need full CASP or can operate under referral
  model via existing CASPs (this may defer the need)

---

### TASK 9: SARB FOREX APPROVAL & AUTHORISED DEALER RELATIONSHIP

**What**: Obtain SARB approval for foreign exchange activities and
establish a relationship with an authorised dealer bank.

**Why**: Required for any cross-border payments, foreign currency accounts,
or FX conversion services. Without this, all transactions must be in ZAR.

**Regulator**: SARB (Exchange Control Department / FinSurv)

**Legal basis**: Currency and Exchanges Act 9 of 1933 + Exchange Control
Regulations

**What you need**:
- [ ] SARB PCB registration (Task 5) — must be a registered bank first
- [ ] Authorised dealer bank relationship agreement:
      - [ ] Approach FNB, Standard Bank, Nedbank, or Absa
      - [ ] Negotiate an agency/intermediary agreement
      - [ ] The dealer bank handles SARB reporting
      - [ ] You process transactions, they clear through SARB
- [ ] Exchange control compliance programme:
      - [ ] SDA tracking system (built — tracks R1,000,000/year per individual)
      - [ ] FIA tracking for amounts above R10,000,000
      - [ ] BOP (Balance of Payments) category code enforcement
      - [ ] Documentary evidence collection for transactions > R10,000
      - [ ] FinSurv monthly reporting capability
- [ ] SARB exchange control approval application
- [ ] SWIFT/BIC code application (via PASA, requires NPS proximity)

**Estimated time**: 18-30 months (from start of engagement)

**Cost**: Authorised dealer relationship fees (negotiable) + SARB
compliance infrastructure + SWIFT membership fees (if applicable)

**After approval**:
- Enable: `AGENTIS_FX_ENABLED`
- Unlocks FX trading, international payments, SDA/FIA tracking,
  multi-currency accounts

**Ongoing obligations**:
- [ ] Monthly exchange control returns to SARB FinSurv
- [ ] Real-time SDA tracking per individual member
- [ ] Documentary evidence for all cross-border transactions > R10,000
- [ ] Annual SARB exchange control audit

**Tips**:
- This is the most complex approval — don't rush it
- The authorised dealer bank relationship is key — they vouch for you
- Your existing PayPal and VALR/Luno integrations already handle some
  cross-border, but under SARB exchange control limits
- The current system already tracks SARB annual offshore limits
  (R1,000,000 SDA) in the PayOut Engine

---

## PART 4: ONGOING COMPLIANCE — EXISTING PLATFORM

These apply to the TiOLi Exchange as it operates TODAY, independent of
Agentis banking features.

---

### TASK 10: FIC REGISTRATION (FINANCIAL INTELLIGENCE CENTRE)

**What**: Register with the FIC as an accountable institution once you
begin processing financial transactions.

**Why**: FICA (Financial Intelligence Centre Act) requires all financial
service providers to register with the FIC, report suspicious transactions,
and implement AML/CFT controls.

**Regulator**: FIC (Financial Intelligence Centre)

**Where to register**: https://www.fic.gov.za — goAML registration system

**What you need**:
- [ ] goAML account registration
- [ ] Designated FICA Compliance Officer (must be a named individual)
- [ ] Risk Management and Compliance Programme (RMCP):
      - [ ] Customer identification and verification procedures
      - [ ] Record-keeping procedures
      - [ ] Suspicious transaction reporting procedures
      - [ ] Training programme for staff
      - [ ] Internal rules (Regulation 22B)
- [ ] CTR reporting capability (transactions >= R49,999.99)
- [ ] STR reporting capability (suspicious patterns)
- [ ] FICA training for all staff handling financial data

**When to register**: Before your first financial transaction goes live

**Cost**: Free to register; compliance programme costs vary

**Ongoing obligations**:
- [ ] File CTRs within 2 business days
- [ ] File STRs within 15 business days of confirmation
- [ ] Annual RMCP review
- [ ] Ongoing staff FICA training
- [ ] Respond to FIC requests within specified timeframes
- [ ] Keep records for minimum 5 years

**Tips**:
- The goAML system is the electronic filing platform — get familiar with it
- Your compliance engine already generates CTR and STR records automatically
- You still need a human Compliance Officer to review and submit them

---

### TASK 11: INFORMATION REGULATOR REGISTRATION (POPIA)

**What**: Register with the Information Regulator as required by the
Protection of Personal Information Act.

**Why**: POPIA requires all organisations processing personal information
to register and comply with data protection requirements.

**Regulator**: Information Regulator of South Africa

**Where to register**: https://www.justice.gov.za/inforeg/

**What you need**:
- [ ] Complete the POPIA registration form
- [ ] Appoint an Information Officer (may be the same person as FICA CO)
- [ ] Appoint a Deputy Information Officer
- [ ] POPIA Impact Assessment for all data processing activities
- [ ] Privacy Policy (already built into the platform)
- [ ] Data Subject Request handling procedure (built — POPIA export endpoint)
- [ ] Data Breach Response Plan:
      - [ ] 72-hour notification to Information Regulator
      - [ ] Notification to affected data subjects
      - [ ] Incident documentation
- [ ] Record of Processing Activities (ROPA)
- [ ] Cross-border transfer safeguards (for any data leaving SA)

**Estimated time**: 2-4 weeks

**Cost**: Free to register

**Ongoing obligations**:
- [ ] Respond to data subject requests within 30 days
- [ ] Report data breaches within 72 hours
- [ ] Annual POPIA compliance review
- [ ] Maintain ROPA up to date
- [ ] POPIA awareness training for all staff

---

### TASK 12: SARS TAX REGISTRATION

**What**: Ensure TiOLi AI Investments and Agentis Co-operative Bank are
properly registered for all applicable taxes.

**Why**: Revenue from platform commissions, banking fees, and interest
margins is taxable. You also need a tax clearance certificate for several
regulatory applications.

**Regulator**: SARS (South African Revenue Service)

**Where to register**: https://www.sars.gov.za — eFiling

**What you need**:
- [ ] Income Tax registration for both entities
      (TiOLi AI Investments + Agentis cooperative)
- [ ] VAT registration (mandatory if turnover exceeds R1M in 12 months)
- [ ] PAYE registration (when you hire employees)
- [ ] Tax clearance certificate (needed for NCR, FSCA applications)
- [ ] Co-operative tax status confirmation:
      - [ ] Cooperatives have special tax treatment under Income Tax Act
      - [ ] Patronage dividends may be deductible
      - [ ] Confirm with SARS or tax advisor

**Tips**:
- Get a tax clearance certificate early — several applications need it
- Cooperatives have specific tax rules — get a tax advisor who understands
  cooperative tax treatment
- VAT on financial services is complex — some services are exempt, others
  zero-rated. Get professional VAT advice.

---

## PART 5: FEATURE FLAG ACTIVATION SEQUENCE

Once you have the approvals, here is the exact sequence to enable features.
Each requires Owner 3FA on the platform.

```
STEP 1:  After CIPC registration
         → Enable AGENTIS_COMPLIANCE_ENABLED

STEP 2:  After CBDA CFI application submitted
         → Enable AGENTIS_CFI_MEMBER_ENABLED

STEP 3:  After CBDA CFI approved
         → Enable AGENTIS_CFI_ACCOUNTS_ENABLED
         → Enable AGENTIS_CFI_PAYMENTS_ENABLED

STEP 4:  After cooperative constitution adopted + minutes filed
         → Enable AGENTIS_CFI_GOVERNANCE_ENABLED

STEP 5:  After FSP Cat I licence granted
         → Enable AGENTIS_PHASE0_WALLET_ENABLED
         → Enable AGENTIS_FSP_INTERMEDIARY_ENABLED

STEP 6:  After NCR credit provider registration
         → Enable AGENTIS_CFI_LENDING_ENABLED

STEP 7:  After SARB PCB registration
         → Enable AGENTIS_PCB_DEPOSITS_ENABLED
         → Enable AGENTIS_PCB_EFT_ENABLED
         → Enable AGENTIS_PCB_TREASURY_ENABLED
         → Enable AGENTIS_PCB_DEPOSIT_INSURANCE_ENABLED
         → Enable AGENTIS_PCB_GOVERNANCE_ENABLED

STEP 8:  After NCR full registration + SARB PCB
         → Enable AGENTIS_NCA_LENDING_ENABLED

STEP 9:  After SARB forex approval
         → Enable AGENTIS_FX_ENABLED

STEP 10: After FSCA CASP licence
         → Enable AGENTIS_CASP_ENABLED
```

---

## PART 6: PEOPLE YOU NEED TO HIRE OR APPOINT

Before you can complete many of these tasks, you need specific people:

### Immediate (before first application)
- [ ] **FICA Compliance Officer** — named individual responsible for AML/CFT.
      Must have FICA training. Can be part-time initially.
- [ ] **Cooperative Law Specialist** — to draft your constitution and guide
      CIPC/CBDA applications. Once-off engagement.
- [ ] **External Auditor** — registered auditor required for CFI application.
      Annual engagement.

### Before FSP Application
- [ ] **Key Individual** — must pass RE 1 and RE 5 regulatory exams. This
      can be you, but you must study and pass the exams.

### Before SARB PCB Application
- [ ] **Credit Committee** — minimum 3 people with lending experience
- [ ] **Audit Committee** — minimum 3, at least 1 financially qualified
- [ ] **Board of Directors** — minimum 5, majority must be cooperative members
- [ ] **Treasury Manager** — manages liquidity and regulatory ratios
- [ ] **IT Security Auditor** — independent assessment of platform security

### Before Full Operations
- [ ] **Deputy Information Officer** — POPIA requirement
- [ ] **Compliance Practice** — can outsource FSCA/NCR compliance initially

---

## PART 7: ESTIMATED TOTAL COSTS

| Item | Estimated Cost |
|------|---------------|
| CIPC registration | R175 + R5k-R15k legal fees |
| SARB IFLAB application | Free |
| CBDA CFI application | R25k-R50k professional fees + R50k-R100k capital |
| FSP Category I | R2k application + R5k-R15k PI insurance + R5k exams |
| NCR registration | R6k-R10k + ongoing fees |
| FSCA CASP | R50k-R100k preparation costs |
| SARB PCB | R100k-R500k total (capital + professional + infrastructure) |
| SARB Forex | Included in PCB + dealer bank relationship fees |
| External auditor (annual) | R20k-R50k per year |
| FICA Compliance Officer | R10k-R30k/month (part-time to full-time) |
| **Total Phase 1 (CFI)** | **R100k-R200k** |
| **Total Phase 2 (PCB)** | **R250k-R750k additional** |
| **Total all phases** | **R500k-R1.5M over 3 years** |

---

## PART 8: DOCUMENT CHECKLIST — WHAT TO PREPARE FIRST

These documents are needed across multiple applications. Prepare them once,
use them everywhere:

- [ ] Business Plan (3-5 year, financial projections, member acquisition)
- [ ] Cooperative Constitution (CBDA-compliant, common bond defined)
- [ ] FICA/AML Compliance Manual
- [ ] POPIA Policy and Privacy Notice
- [ ] KYC Procedures Manual
- [ ] Risk Management Framework
- [ ] IT Security Assessment Report
- [ ] Business Continuity Plan
- [ ] Complaints Handling Procedure
- [ ] Tax Clearance Certificate (SARS)
- [ ] B-BBEE Certificate or Affidavit
- [ ] Audited Financial Statements (once available)
- [ ] Board Resolution authorising banking activities
- [ ] Fit and Proper Declarations for all directors

---

*This document should be reviewed and updated after each regulatory
engagement. Laws change. Use this as your roadmap, but always confirm
current requirements directly with each regulator.*

*CONFIDENTIAL — TiOLi AI Investments (Pty) Ltd*
