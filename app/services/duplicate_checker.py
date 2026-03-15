from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.invoice import Invoice
from app.core.exceptions import DuplicateInvoiceError
from app.core.logging import get_logger

logger = get_logger(__name__)


async def check_duplicate(
    db: AsyncSession,
    account_number: str,
    invoice_number: str,
    total_due: float,
) -> None:
    """Raise DuplicateInvoiceError if invoice already exists."""
    result = await db.execute(
        select(Invoice).where(
            Invoice.account_number == account_number,
            Invoice.invoice_number == invoice_number,
            Invoice.total_due == total_due,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        logger.warning("duplicate_detected", invoice_number=invoice_number, account_number=account_number)
        raise DuplicateInvoiceError(f"Invoice {invoice_number} already exists.")
