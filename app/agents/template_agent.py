from app.database import AsyncSessionLocal
from app.services.template_learning import is_vendor_active, check_layout_change
from app.core.logging import get_logger

logger = get_logger("template_agent")


async def template_agent_node(state: dict) -> dict:
    log = list(state.get("agent_log", []))
    log.append("template_agent: started")

    vendor_name = state.get("vendor_name")
    confidence = state.get("confidence", 0.0)
    needs_review = state.get("needs_review", True)

    if not vendor_name:
        log.append("template_agent: no vendor name — skipping template check")
        return {"needs_review": True, "agent_log": log}

    async with AsyncSessionLocal() as db:
        layout_changed = await check_layout_change(db, vendor_name, confidence)
        if layout_changed:
            log.append(f"template_agent: layout change detected for {vendor_name} → review")
            logger.warning("layout_change", vendor=vendor_name, confidence=confidence)
            return {"needs_review": True, "layout_change_detected": True, "agent_log": log}

        if needs_review:
            log.append("template_agent: validation flagged review — respecting it")
            return {"needs_review": True, "agent_log": log}

        active = await is_vendor_active(db, vendor_name)
        if active:
            log.append(f"template_agent: {vendor_name} active template → auto-approve")
            logger.info("auto_approve", vendor=vendor_name, confidence=confidence)
            return {"needs_review": False, "agent_log": log}

    log.append(f"template_agent: {vendor_name} no active template → review")
    return {"needs_review": True, "agent_log": log}