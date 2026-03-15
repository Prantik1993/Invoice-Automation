"""
Review API — human approval endpoints.
Human edits fields in Streamlit → clicks Approve → this endpoint:
  1. Resumes the LangGraph graph with corrections via thread_id (HITL)
  2. Directly updates DB with corrected values (handles date parsing)
  3. Triggers vendor template learning
"""
from datetime import datetime, date
import shutil
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.types import Command

from app.database import get_db, AsyncSessionLocal
from app.models.invoice import Invoice
from app.agents.graph import get_graph
from app.services.template_learning import record_approval
from app.config import settings
from app.core.logging import get_logger

router = APIRouter(prefix="/review", tags=["review"])
logger = get_logger("review_api")


def _parse_date(value) -> date | None:
    """Parse date string in any common format to Python date object."""
    if not value:
        return None
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


class ApprovePayload(BaseModel):
    account_number: str | None = None
    invoice_number: str | None = None
    bill_date: str | None = None
    due_date: str | None = None
    total_due: float | None = None
    bill_to_address: str | None = None
    bill_from_address: str | None = None
    remittance_address: str | None = None
    thread_id: str | None = None  # LangGraph thread_id for HITL resume


@router.put("/{invoice_id}/approve")
async def approve_invoice(
    invoice_id: int,
    payload: ApprovePayload,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    corrections = payload.model_dump(exclude_none=True, exclude={"thread_id"})

    # ── Resume LangGraph graph via HITL if thread_id present ────────────────
    if payload.thread_id:
        try:
            graph = await get_graph()
            config = {"configurable": {"thread_id": payload.thread_id}}
            await graph.ainvoke(Command(resume=corrections), config=config)
            logger.info("graph_resumed", thread_id=payload.thread_id, invoice_id=invoice_id)
        except Exception as e:
            logger.warning("graph_resume_failed", error=str(e), invoice_id=invoice_id)

    # ── Always update DB directly with human corrections ─────────────────────
    # This guarantees DB is correct even if graph resume fails
    date_fields = {"bill_date", "due_date"}
    string_fields = {"account_number", "invoice_number", "bill_to_address",
                     "bill_from_address", "remittance_address"}

    for field, value in corrections.items():
        if field in date_fields:
            setattr(invoice, field, _parse_date(value))
        elif field in string_fields:
            setattr(invoice, field, str(value) if value else None)
        elif field == "total_due":
            setattr(invoice, field, float(value) if value else None)

    invoice.needs_review = False
    invoice.status = "approved"
    invoice.approved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(invoice)

    # ── Move PDF to processed ────────────────────────────────────────────────
    if invoice.pdf_path:
        try:
            shutil.move(
                invoice.pdf_path,
                f"{settings.processed_folder}/{invoice.pdf_filename}"
            )
        except Exception as e:
            logger.warning("file_move_failed", invoice_id=invoice_id, error=str(e))

    # ── Vendor template learning ─────────────────────────────────────────────
    if invoice.vendor_name:
        try:
            async with AsyncSessionLocal() as tdb:
                await record_approval(tdb, invoice.vendor_name, invoice.confidence or 0.0)
                await tdb.commit()
                logger.info("template_updated", vendor=invoice.vendor_name)
        except Exception as e:
            logger.error("template_learning_failed", vendor=invoice.vendor_name, error=str(e))

    logger.info("invoice_approved", invoice_id=invoice_id, vendor=invoice.vendor_name)
    return {"status": "approved", "invoice_id": invoice_id}


@router.put("/{invoice_id}/reject")
async def reject_invoice(invoice_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice.status = "rejected"
    invoice.needs_review = False
    await db.commit()

    logger.info("invoice_rejected", invoice_id=invoice_id)
    return {"status": "rejected", "invoice_id": invoice_id}