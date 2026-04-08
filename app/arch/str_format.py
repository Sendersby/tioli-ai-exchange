"""STR (Suspicious Transaction Report) filing format — FIC-compatible."""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.str_format")


def generate_str_xml(transaction_id, agent_id, amount, currency, risk_score, flags):
    """Generate a FIC-compatible STR XML document."""
    now = datetime.now(timezone.utc)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<SuspiciousTransactionReport xmlns="urn:fic:str:v1">
  <ReportHeader>
    <ReportingEntity>TiOLi Group Holdings (Pty) Ltd</ReportingEntity>
    <RegistrationNumber>2011/001439/07</RegistrationNumber>
    <ReportDate>{now.strftime('%Y-%m-%d')}</ReportDate>
    <ReportTime>{now.strftime('%H:%M:%S')}</ReportTime>
    <ReportType>STR</ReportType>
  </ReportHeader>
  <TransactionDetails>
    <TransactionID>{transaction_id}</TransactionID>
    <TransactionDate>{now.strftime('%Y-%m-%d')}</TransactionDate>
    <Amount>{amount}</Amount>
    <Currency>{currency}</Currency>
    <AgentID>{agent_id}</AgentID>
  </TransactionDetails>
  <RiskAssessment>
    <RiskScore>{risk_score}</RiskScore>
    <Flags>{'|'.join(flags)}</Flags>
  </RiskAssessment>
  <ComplianceOfficer>
    <Name>Stephen Alan Endersby</Name>
    <Designation>Information Officer</Designation>
  </ComplianceOfficer>
</SuspiciousTransactionReport>"""

    return {
        "xml": xml,
        "report_date": now.isoformat(),
        "transaction_id": transaction_id,
        "status": "GENERATED",
        "note": "Submit to FIC via goAML portal. Manual submission required until API access approved.",
    }
