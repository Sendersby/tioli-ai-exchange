"""Export service — PDF receipts and CSV tax export.

Generates SARS-compatible CSV exports with ZAR-equivalent values
and PDF transaction receipts for individual transactions.
"""

import csv
import io
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ExportService:
    """Generates PDF receipts and CSV tax exports."""

    def generate_csv_tax_export(
        self, transactions: list[dict], operator_name: str = "",
        tax_year: int | None = None,
    ) -> str:
        """Generate SARS-compatible CSV tax export.

        Columns: Date, Type, From, To, Amount, Currency, ZAR Equivalent,
        Commission, Charity Fee, Net Amount, Transaction ID
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            f"TiOLi AGENTIS — Tax Export",
        ])
        writer.writerow([
            f"Operator: {operator_name}",
            f"Generated: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')}",
            f"Tax Year: {tax_year or 'All'}",
        ])
        writer.writerow([])

        # Column headers
        writer.writerow([
            "Date", "Type", "From", "To", "Amount", "Currency",
            "ZAR Equivalent", "Commission", "Charity Fee",
            "Net Amount", "Transaction ID",
        ])

        # Data rows
        for tx in transactions:
            writer.writerow([
                tx.get("timestamp", "")[:19],
                tx.get("type", ""),
                tx.get("sender_id", "")[:20],
                tx.get("receiver_id", "")[:20],
                f"{tx.get('amount', 0):.4f}",
                tx.get("currency", "TIOLI"),
                f"{tx.get('amount', 0) * 0.055:.2f}",  # ZAR estimate
                f"{tx.get('founder_commission', 0):.4f}",
                f"{tx.get('charity_fee', 0):.4f}",
                f"{tx.get('amount', 0) - tx.get('founder_commission', 0) - tx.get('charity_fee', 0):.4f}",
                tx.get("id", ""),
            ])

        # Summary
        writer.writerow([])
        total_amount = sum(tx.get("amount", 0) for tx in transactions)
        total_commission = sum(tx.get("founder_commission", 0) for tx in transactions)
        total_charity = sum(tx.get("charity_fee", 0) for tx in transactions)
        writer.writerow(["TOTALS", "", "", "", f"{total_amount:.4f}", "",
                         f"{total_amount * 0.055:.2f}",
                         f"{total_commission:.4f}", f"{total_charity:.4f}", "", ""])
        writer.writerow([])
        writer.writerow(["Note: ZAR Equivalent is estimated at R0.055 per TIOLI credit."])
        writer.writerow(["This export is for informational purposes. Consult a tax advisor for SARS filing."])

        return output.getvalue()

    def generate_pdf_receipt(self, transaction: dict) -> str:
        """Generate a text-based receipt (PDF generation requires reportlab).

        Returns formatted receipt text that can be converted to PDF.
        """
        tx = transaction
        amount = tx.get("amount", 0)
        commission = tx.get("founder_commission", 0)
        charity = tx.get("charity_fee", 0)
        net = amount - commission - charity

        receipt = f"""
═══════════════════════════════════════════════════════
           TiOLi AGENTIS
                Transaction Receipt
═══════════════════════════════════════════════════════

Transaction ID:  {tx.get('id', 'N/A')}
Date:            {tx.get('timestamp', 'N/A')[:19]}
Type:            {tx.get('type', 'N/A')}

From:            {tx.get('sender_id', 'N/A')}
To:              {tx.get('receiver_id', 'N/A')}

───────────────────────────────────────────────────────
Amount:          {amount:.4f} {tx.get('currency', 'TIOLI')}
Commission:      {commission:.4f} {tx.get('currency', 'TIOLI')}
Charity Fee:     {charity:.4f} {tx.get('currency', 'TIOLI')}
───────────────────────────────────────────────────────
Net to Receiver: {net:.4f} {tx.get('currency', 'TIOLI')}
ZAR Equivalent:  R{amount * 0.055:.2f}

═══════════════════════════════════════════════════════
TiOLi AI Investments
For the ultimate good of Humanity and Agents
exchange.tioli.co.za
═══════════════════════════════════════════════════════
"""
        return receipt.strip()
