"""LangGraph multi-agent graph for invoice processing.

Flow:
    supervisor → duplicate_agent → extraction_agent → validation_agent
              → template_agent → save_agent
              → human_review_node (interrupt, if needs_review)
              → supervisor → final_approve_node
"""
from typing import Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

import aiosqlite


class InvoiceState(TypedDict, total=False):
    pdf_path: str
    pdf_filename: str
    thread_id: Optional[str]
    raw_text: str
    extraction_method: str
    extracted_fields: dict
    confidence: float
    vendor_name: Optional[str]
    resolved_invoice_number: Optional[str]
    resolved_bill_date: Optional[str]
    resolved_due_date: Optional[str]
    is_duplicate: bool
    needs_review: bool
    layout_change_detected: bool
    supervisor_decision: Optional[str]
    human_corrections: Optional[dict]
    invoice_id: Optional[int]
    status: str
    error: Optional[str]
    agent_log: list


def make_initial_state(pdf_path: str, pdf_filename: str, thread_id: str = None) -> InvoiceState:
    return InvoiceState(
        pdf_path=pdf_path,
        pdf_filename=pdf_filename,
        thread_id=thread_id,
        raw_text="",
        extraction_method="direct",
        extracted_fields={},
        confidence=0.0,
        vendor_name=None,
        resolved_invoice_number=None,
        resolved_bill_date=None,
        resolved_due_date=None,
        is_duplicate=False,
        needs_review=True,
        layout_change_detected=False,
        supervisor_decision=None,
        human_corrections=None,
        invoice_id=None,
        status="processing",
        error=None,
        agent_log=[],
    )


async def supervisor_node(state: InvoiceState) -> dict:
    from app.core.logging import get_logger
    logger = get_logger("supervisor")

    decision = state.get("supervisor_decision")
    log = list(state.get("agent_log", []))

    if not decision:
        log.append("supervisor: start → duplicate_agent")
        return {"supervisor_decision": "duplicate_agent", "agent_log": log}

    if state.get("is_duplicate"):
        log.append("supervisor: duplicate → END")
        return {"status": "duplicate", "supervisor_decision": "end", "agent_log": log}

    if state.get("error"):
        log.append(f"supervisor: error → END [{state['error']}]")
        return {"status": "failed", "supervisor_decision": "end", "agent_log": log}

    if decision == "duplicate_agent":
        log.append("supervisor: duplicate clear → extraction_agent")
        return {"supervisor_decision": "extraction_agent", "agent_log": log}

    if decision == "extraction_agent":
        if not state.get("raw_text"):
            log.append("supervisor: empty text → OCR retry")
            return {"supervisor_decision": "extraction_retry", "agent_log": log}
        log.append("supervisor: extraction done → validation_agent")
        return {"supervisor_decision": "validation_agent", "agent_log": log}

    if decision == "extraction_retry":
        if not state.get("raw_text"):
            log.append("supervisor: all extraction failed → END")
            return {"status": "failed", "error": "All extraction methods exhausted",
                    "supervisor_decision": "end", "agent_log": log}
        log.append("supervisor: OCR retry succeeded → validation_agent")
        return {"supervisor_decision": "validation_agent", "agent_log": log}

    if decision == "validation_agent":
        log.append("supervisor: validation done → template_agent")
        return {"supervisor_decision": "template_agent", "agent_log": log}

    if decision == "template_agent":
        log.append("supervisor: template done → save_agent")
        return {"supervisor_decision": "save_agent", "agent_log": log}

    if decision == "save_agent":
        if state.get("needs_review"):
            log.append("supervisor: saved as pending → human_review_node")
            return {"supervisor_decision": "human_review", "agent_log": log}
        log.append("supervisor: auto-approved → END")
        return {"supervisor_decision": "end", "agent_log": log}

    if decision == "human_review":
        log.append("supervisor: human approved → final_approve")
        return {"supervisor_decision": "final_approve", "agent_log": log}

    log.append(f"supervisor: unknown decision '{decision}' → END")
    logger.error("supervisor_unknown_decision", decision=decision)
    return {"status": "failed", "supervisor_decision": "end", "agent_log": log}


def supervisor_router(state: InvoiceState) -> str:
    mapping = {
        "duplicate_agent": "duplicate_agent",
        "extraction_agent": "extraction_agent",
        "extraction_retry": "extraction_agent",
        "validation_agent": "validation_agent",
        "template_agent": "template_agent",
        "save_agent": "save_agent",
        "human_review": "human_review_node",
        "final_approve": "final_approve_node",
        "end": END,
    }
    return mapping.get(state.get("supervisor_decision"), END)


async def human_review_node(state: InvoiceState) -> dict:
    """Pause the graph here. Invoice is already saved as pending in the DB.

    Streamlit shows it in the review queue. On approval the API calls
    Command(resume=corrections) which wakes this node and returns corrections
    to the graph.
    """
    from app.core.logging import get_logger
    logger = get_logger("human_review")

    logger.info(
        "graph_paused_for_hitl",
        filename=state["pdf_filename"],
        invoice_id=state.get("invoice_id"),
        thread_id=state.get("thread_id"),
    )

    corrections = interrupt({
        "message": "Invoice requires human review",
        "pdf_filename": state["pdf_filename"],
        "thread_id": state.get("thread_id"),
        "invoice_id": state.get("invoice_id"),
        "confidence": state.get("confidence"),
        "extracted_fields": state.get("extracted_fields", {}),
    })

    logger.info("graph_resumed", filename=state["pdf_filename"])

    return {
        "human_corrections": corrections if isinstance(corrections, dict) else {},
        "supervisor_decision": "human_review",
        "needs_review": False,
        "agent_log": list(state.get("agent_log", [])) + [
            "human_review_node: corrections received, resuming"
        ],
    }


async def final_approve_node(state: InvoiceState) -> dict:
    """Mark the graph run as complete after HITL approval.

    The actual DB update, file move, and template learning are handled by
    review.py so they run exactly once regardless of whether the graph
    resume succeeds or times out.
    """
    from app.core.logging import get_logger
    logger = get_logger("final_approve")

    log = list(state.get("agent_log", []))
    log.append("final_approve_node: graph run complete")

    logger.info("graph_run_complete", invoice_id=state.get("invoice_id"))
    return {"status": "approved", "agent_log": log}


def build_graph(checkpointer):
    from app.agents.duplicate_agent import duplicate_agent_node
    from app.agents.extraction_agent import extraction_agent_node
    from app.agents.validation_agent import validation_agent_node
    from app.agents.template_agent import template_agent_node
    from app.agents.save_agent import save_agent_node

    builder = StateGraph(InvoiceState)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("duplicate_agent", duplicate_agent_node)
    builder.add_node("extraction_agent", extraction_agent_node)
    builder.add_node("validation_agent", validation_agent_node)
    builder.add_node("template_agent", template_agent_node)
    builder.add_node("save_agent", save_agent_node)
    builder.add_node("human_review_node", human_review_node)
    builder.add_node("final_approve_node", final_approve_node)

    builder.set_entry_point("supervisor")

    builder.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "duplicate_agent": "duplicate_agent",
            "extraction_agent": "extraction_agent",
            "validation_agent": "validation_agent",
            "template_agent": "template_agent",
            "save_agent": "save_agent",
            "human_review_node": "human_review_node",
            "final_approve_node": "final_approve_node",
            END: END,
        },
    )

    builder.add_edge("duplicate_agent", "supervisor")
    builder.add_edge("extraction_agent", "supervisor")
    builder.add_edge("validation_agent", "supervisor")
    builder.add_edge("template_agent", "supervisor")
    builder.add_edge("save_agent", "supervisor")
    builder.add_edge("human_review_node", "supervisor")
    builder.add_edge("final_approve_node", END)

    return builder.compile(checkpointer=checkpointer)


_graph = None
_db_conn = None


async def get_graph():
    global _graph, _db_conn
    if _graph is None:
        from pathlib import Path
        Path("./data").mkdir(parents=True, exist_ok=True)
        _db_conn = await aiosqlite.connect("./data/checkpoints.db")
        checkpointer = AsyncSqliteSaver(_db_conn)
        _graph = build_graph(checkpointer)
    return _graph


async def close_graph():
    global _db_conn
    if _db_conn:
        await _db_conn.close()
        _db_conn = None