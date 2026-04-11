# AGENTIS Platform Remediation — Deferred Items Log
## Items requiring owner action (cost, credentials, regulatory decisions)

---

| ID | Item | Owner Action Required | Stub Built | Status |
|----|------|----------------------|-----------|--------|
| DEFER-001 | OpenSanctions API | Subscribe to opensanctions.org/api/ | Pending | Awaiting owner |
| DEFER-002 | Sumsub KYC | Sign Sumsub contract | Pending | Awaiting owner |
| DEFER-003 | goAML Credentials | Register with SA FIC | Pending | Awaiting owner |
| DEFER-004 | GitHub Repository | Grant CI access | Pending | Awaiting owner |
| DEFER-005 | PyPI Package | Decide: publish SDK or remove references | Pending | Awaiting owner |
| DEFER-001 | DB Password Rotation | Rotate tioli DB password after remediation complete | .pgpass approach in place, credential no longer inline | Post-remediation |
| DEFER-006 | Offsite Backup | Create DigitalOcean Spaces bucket + configure rclone/boto3 | Backup script ready, boto3 installed, needs bucket credentials | Awaiting owner |

### M-004: PostHog Analytics
- Status: DEFERRED
- Reason: PostHog script scaffold present in index.html but API key (phKey) is empty
- Action required: Owner creates PostHog account at https://app.posthog.com, gets project API key
- Implementation: Set phKey value in static/landing/index.html line ~124
- Impact: No product analytics, funnels, or session replay until configured
| DEFER-007 | Cloudflare WAF/DDoS | Point DNS through Cloudflare proxy (free tier). Requires registrar access for exchange.tioli.co.za and agentisexchange.com. | Nginx configured, just needs DNS change | Awaiting owner |
| DEFER-008 | Offsite Backup | Configure DigitalOcean Spaces bucket, run 'rclone config' to add remote 'do-spaces', uncomment offsite block in /home/tioli/backups/backup.sh | rclone installed, script ready | Awaiting owner |
| DEFER-009 | External Uptime Monitor | Register at uptimerobot.com (free, 5-min checks) or use DO Monitoring alerts | monitor.sh handles basic checks locally | Awaiting owner |
| DEFER-010 | PostHog Analytics | Create account at posthog.com, get API key, set in index.html phKey variable | Script loaded, key empty | Awaiting owner |
