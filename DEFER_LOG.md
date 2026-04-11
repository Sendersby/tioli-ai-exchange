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
