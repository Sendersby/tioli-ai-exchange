# Payment Workflow Report — TiOLi AGENTIS
## Comprehensive Audit | 2026-04-06

### Payment Paths Tested

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1 | Free signup | PASS | /onboard wizard works, no payment required |
| 2 | $1.99 PayPal | PASS | Live PayPal NCP button present, links to paypal.com/ncp/payment/L2D6BWZGY9KVW |
| 3 | R36 PayFast | CONFIGURED | Button present, ITN callback coded (POST /api/v1/payfast/itn), pending merchant verification |
| 4 | Google Pay | NOT IMPLEMENTED | Not yet built, on roadmap as P1 |
| 5 | Pay before register | GAP | No auth guard on premium-upgrade page. User can pay without account. Post-payment page lacks signup prompt. |
| 6 | Register then pay | PASS | Path: /onboard → dashboard → premium-upgrade → PayPal/PayFast |
| 7 | Cancel subscription | PARTIAL | Cancelled page works (/premium/cancelled). PayFast ITN handles cancellation server-side. No self-service cancel button in dashboard. |

### Payment Infrastructure

| Component | Status |
|-----------|--------|
| PayPal button | Live (no-code link) |
| PayFast integration | Coded, live mode, empty passphrase (verify PayFast dashboard) |
| ITN webhook endpoint | POST /api/v1/payfast/itn — exists and logs to DB |
| Thank-you page | Works — shows "You are Premium" with 7 unlocked features |
| Cancelled page | Works — shows retry link |
| Paywall middleware | Integrated — enforces tier checks on protected endpoints |

### Pricing Consistency

| Tier | Landing Page | Payment Page | Consistent? |
|------|-------------|--------------|-------------|
| Explorer (Free) | R0 / Free | N/A | YES |
| Builder | R299/mo | Not yet payable | N/A |
| AgentHub Pro | $1.99 ~R36 ZAR/mo | $1.99 via PayPal | YES |
| Enterprise | Custom | Enterprise Briefing form | YES |

### Recommendations
1. **P0**: Add auth guard or post-payment signup flow to premium-upgrade page
2. **P1**: Add self-service subscription cancellation in dashboard
3. **P1**: Set PayFast passphrase for signature validation
4. **P2**: Implement Builder tier payment path
