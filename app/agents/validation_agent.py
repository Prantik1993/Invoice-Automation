"""
Validation Agent — validates fields and applies fallback rules using tools.
"""
from app.agents.tools.invoice_tools import resolve_due_date, generate_invoice_number
from app.config import settings
from app.core.logging import get_logger

logger = get_logger("validation_agent")

REQUIRED_FIELDS = ["account_number", "total_due", "bill_date"]


async def validation_agent_node(state: dict) -> dict:
    log = list(state.get("agent_log", []))
    log.append("validation_agent: started")

    fields = state.get("extracted_fields", {})
    confidence = state.get("confidence", 0.0)

    bill_date = fields.get("bill_date")

    # Tool: resolve due_date if missing
    due_date = fields.get("due_date")
    if not due_date and bill_date:
        due_date = resolve_due_date.invoke({"bill_date_str": bill_date})
        log.append(f"validation_agent: due_date computed → {due_date}")

    # Tool: generate invoice_number if missing
    invoice_number = fields.get("invoice_number")
    if not invoice_number:
        invoice_number = generate_invoice_number.invoke({
            "account_number": fields.get("account_number"),
            "bill_date_str": bill_date,
        })
        log.append(f"validation_agent: invoice_number generated → {invoice_number}")

    # Decide if human review needed
    needs_review = False
    missing = [f for f in REQUIRED_FIELDS if not fields.get(f)]
    if missing:
        log.append(f"validation_agent: missing fields {missing} → needs review")
        needs_review = True

    if confidence < settings.confidence_threshold:
        log.append(f"validation_agent: confidence {confidence:.2f} < {settings.confidence_threshold} → needs review")
        needs_review = True

    if not needs_review:
        log.append(f"validation_agent: all checks passed confidence={confidence:.2f}")

    return {
        "resolved_invoice_number": invoice_number,
        "resolved_bill_date": bill_date,
        "resolved_due_date": due_date,
        "needs_review": needs_review,
        "agent_log": log,
    }
