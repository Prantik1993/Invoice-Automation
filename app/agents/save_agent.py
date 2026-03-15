"""
Save Agent — always saves invoice to DB first (as pending or approved).
For auto-approved: saves as approved + moves file immediately.
For needs_review: saves as pending — Streamlit shows it, HITL resumes graph.
File move for HITL invoices happens in final_approve_node after human approves.
"""
from datetime import datetime, date, timedelta
from sqlalchemy.exc import IntegrityError

from app.agents.tools.invoice_tools import move_to_processed, move_to_duplicates
from app.database import AsyncSessionLocal
from app.models.invoice import Invoice
from app.core.logging import get_logger

logger = get_logger("save_agent")


def _parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except Exception:
        return None


async def save_agent_node(state: dict) -> dict:
    log = list(state.get("agent_log", []))
    log.append("save_agent: started")

    fields = dict(state.get("extracted_fields", {}))
    needs_review = state.get("needs_review", True)
    pdf_path = state["pdf_path"]
    pdf_filename = state["pdf_filename"]

    invoice_number = state.get("resolved_invoice_number") or fields.get("invoice_number")
    bill_date = _parse_date(state.get("resolved_bill_date") or fields.get("bill_date"))
    due_date = _parse_date(state.get("resolved_due_date") or fields.get("due_date"))

    if not due_date and bill_date:
        due_date = bill_date + timedelta(days=14)

    async with AsyncSessionLocal() as db:
        invoice = Invoice(
            pdf_filename=pdf_filename,
            pdf_path=pdf_path,
            account_number=fields.get("account_number"),
            invoice_number=invoice_number,
            bill_date=bill_date,
            due_date=due_date,
            total_due=fields.get("total_due"),
            bill_to_address=fields.get("bill_to_address"),
            bill_from_address=fields.get("bill_from_address"),
            remittance_address=fields.get("remittance_address"),
            vendor_name=state.get("vendor_name"),
            thread_id=state.get("thread_id"),
            confidence=state.get("confidence", 0.0),
            extraction_method=state.get("extraction_method", "direct"),
            needs_review=needs_review,
            # Auto-approved: mark approved now. Needs review: pending until human approves.
            status="approved" if not needs_review else "pending",
            approved_at=datetime.utcnow() if not needs_review else None,
        )
        db.add(invoice)

        try:
            await db.commit()
            await db.refresh(invoice)
            invoice_id = invoice.id
            log.append(f"save_agent: saved to DB id={invoice_id} status={'pending' if needs_review else 'approved'}")
        except IntegrityError:
            await db.rollback()
            log.append("save_agent: duplicate invoice_number — IntegrityError")
            logger.warning("db_duplicate", invoice_number=invoice_number, filename=pdf_filename)
            move_to_duplicates.invoke({"pdf_path": pdf_path, "filename": pdf_filename})
            return {"status": "duplicate", "is_duplicate": True, "agent_log": log}

    # Auto-approved: move file immediately
    if not needs_review:
        result = move_to_processed.invoke({"pdf_path": pdf_path, "filename": pdf_filename})
        log.append(f"save_agent: auto-approved, file moved → {result}")
    else:
        log.append("save_agent: saved as pending — invoice will appear in Streamlit review queue")

    logger.info("invoice_saved", invoice_id=invoice_id, filename=pdf_filename,
                needs_review=needs_review, status=invoice.status)

    return {
        "invoice_id": invoice_id,
        "status": "pending" if needs_review else "approved",
        "agent_log": log,
    }