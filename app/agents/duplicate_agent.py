from app.agents.tools.invoice_tools import check_filename_duplicate, move_to_duplicates
from app.core.logging import get_logger

logger = get_logger("duplicate_agent")


async def duplicate_agent_node(state: dict) -> dict:
    log = list(state.get("agent_log", []))
    log.append("duplicate_agent: started")

    pdf_path = state["pdf_path"]
    pdf_filename = state["pdf_filename"]

    already_processed = check_filename_duplicate.invoke({"filename": pdf_filename})

    if already_processed:
        result = move_to_duplicates.invoke({"pdf_path": pdf_path, "filename": pdf_filename})
        log.append(f"duplicate_agent: duplicate detected — {result}")
        logger.warning("duplicate_detected", filename=pdf_filename)
        return {"is_duplicate": True, "status": "duplicate", "agent_log": log}

    log.append("duplicate_agent: no duplicate found")
    return {"is_duplicate": False, "agent_log": log}