from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.invoice import Invoice
from app.config import settings

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("/pending")
async def get_pending_invoices(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invoice)
        .where(Invoice.needs_review == True)
        .order_by(Invoice.created_at.desc())
    )
    return [_serialize(inv) for inv in result.scalars().all()]


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _serialize(invoice)


@router.get("/")
async def list_invoices(
    limit: int = settings.default_page_limit,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Invoice).order_by(Invoice.created_at.desc()).limit(limit)
    )
    return [_serialize(inv) for inv in result.scalars().all()]


def _serialize(inv: Invoice) -> dict:
    return {
        "id": inv.id,
        "pdf_filename": inv.pdf_filename,
        "account_number": inv.account_number,
        "invoice_number": inv.invoice_number,
        "bill_date": str(inv.bill_date) if inv.bill_date else None,
        "due_date": str(inv.due_date) if inv.due_date else None,
        "total_due": inv.total_due,
        "bill_to_address": inv.bill_to_address,
        "bill_from_address": inv.bill_from_address,
        "remittance_address": inv.remittance_address,
        "vendor_name": inv.vendor_name,
        "thread_id": inv.thread_id,
        "confidence": inv.confidence,
        "extraction_method": inv.extraction_method,
        "needs_review": inv.needs_review,
        "status": inv.status,
        "created_at": str(inv.created_at),
        "approved_at": str(inv.approved_at) if inv.approved_at else None,
    }