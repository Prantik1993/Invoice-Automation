from app.agents.tools.invoice_tools import extract_text_from_pdf, extract_text_via_ocr
from app.services.llm_service import extract_invoice_fields
from app.core.exceptions import LLMExtractionError
from app.core.logging import get_logger
from app.config import settings

logger = get_logger("extraction_agent")


async def extraction_agent_node(state: dict) -> dict:
    log = list(state.get("agent_log", []))
    log.append("extraction_agent: started")

    pdf_path = state["pdf_path"]
    force_ocr = state.get("supervisor_decision") == "extraction_retry"

    raw_text = ""
    method = "direct"

    if not force_ocr:
        raw_text = extract_text_from_pdf.invoke({"pdf_path": pdf_path})
        log.append(f"extraction_agent: direct extraction → {len(raw_text)} chars")

    if len(raw_text) < settings.ocr_fallback_char_limit or force_ocr:
        log.append("extraction_agent: switching to OCR")
        method = "ocr"
        raw_text = extract_text_via_ocr.invoke({"pdf_path": pdf_path})
        log.append(f"extraction_agent: OCR → {len(raw_text)} chars")

    if not raw_text:
        log.append("extraction_agent: all methods returned empty text")
        logger.error("extraction_failed", filename=state["pdf_filename"])
        return {
            "raw_text": "",
            "error": "All extraction methods returned empty text",
            "agent_log": log,
        }

    try:
        fields = await extract_invoice_fields(raw_text)
        confidence = float(fields.get("confidence", 0.0))
        vendor_name = fields.get("vendor_name")
        log.append(f"extraction_agent: LLM done — confidence={confidence:.2f} vendor={vendor_name}")
        logger.info("extraction_success", method=method, confidence=confidence, vendor=vendor_name)
        return {
            "raw_text": raw_text,
            "extraction_method": method,
            "extracted_fields": fields,
            "confidence": confidence,
            "vendor_name": vendor_name,
            "agent_log": log,
        }
    except LLMExtractionError as e:
        log.append(f"extraction_agent: LLM failed — {e}")
        logger.error("llm_failed", filename=state["pdf_filename"], error=str(e))
        return {"error": str(e), "raw_text": raw_text, "agent_log": log}