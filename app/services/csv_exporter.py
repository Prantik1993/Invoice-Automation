import csv
from datetime import datetime
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.invoice import Invoice
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

FIELDS = [
    "pdf_filename", "account_number", "invoice_number",
    "bill_date", "due_date", "total_due",
    "bill_to_address", "bill_from_address", "remittance_address",
    "confidence", "approved_at",
]


async def generate_csv(db: AsyncSession, limit: int = settings.export_limit) -> str:
    """Export approved invoices to a timestamped CSV. Returns the file path."""
    result = await db.execute(
        select(Invoice)
        .where(Invoice.status == "approved")
        .order_by(Invoice.approved_at.desc())
        .limit(limit)
    )
    invoices = result.scalars().all()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(settings.exports_folder) / f"invoices_{timestamp}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for inv in invoices:
            writer.writerow({field: getattr(inv, field, None) for field in FIELDS})

    logger.info("csv_generated", path=str(output_path), count=len(invoices))
    return str(output_path)