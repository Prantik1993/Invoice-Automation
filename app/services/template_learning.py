from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.vendor_template import VendorTemplate
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

LAYOUT_CHANGE_THRESHOLD = 0.70
MONITOR_WINDOW = 10


async def get_or_create_template(db: AsyncSession, vendor_name: str) -> VendorTemplate:
    result = await db.execute(
        select(VendorTemplate).where(VendorTemplate.vendor_name == vendor_name)
    )
    template = result.scalar_one_or_none()

    if not template:
        template = VendorTemplate(vendor_name=vendor_name)
        db.add(template)
        await db.flush()
        logger.info("vendor_template_created", vendor=vendor_name)

    return template


async def is_vendor_active(db: AsyncSession, vendor_name: str) -> bool:
    """Returns True if vendor has an active template (auto-approve eligible)."""
    result = await db.execute(
        select(VendorTemplate).where(
            VendorTemplate.vendor_name == vendor_name,
            VendorTemplate.is_active == True,
        )
    )
    return result.scalar_one_or_none() is not None


async def record_approval(db: AsyncSession, vendor_name: str, confidence: float) -> None:
    """Called after human approves. Activates template on first approval."""
    template = await get_or_create_template(db, vendor_name)

    template.approval_count += 1

    # Activate immediately after first human approval
    if not template.is_active:
        template.is_active = True
        logger.info("vendor_template_activated", vendor=vendor_name)

    await _update_confidence_window(template, confidence)
    await db.flush()


async def check_layout_change(db: AsyncSession, vendor_name: str, confidence: float) -> bool:
    """Returns True if layout change detected and template was disabled."""
    result = await db.execute(
        select(VendorTemplate).where(VendorTemplate.vendor_name == vendor_name)
    )
    template = result.scalar_one_or_none()
    if not template or not template.is_active:
        return False

    await _update_confidence_window(template, confidence)

    confidences = template.recent_confidences or []
    if len(confidences) >= MONITOR_WINDOW:
        avg = sum(confidences[-MONITOR_WINDOW:]) / MONITOR_WINDOW
        template.avg_confidence = avg

        if avg < LAYOUT_CHANGE_THRESHOLD:
            template.is_active = False
            template.approval_count = 0
            template.recent_confidences = []
            logger.warning("layout_change_detected", vendor=vendor_name, avg_confidence=avg)
            await db.flush()
            return True

    return False


async def _update_confidence_window(template: VendorTemplate, confidence: float) -> None:
    confidences = list(template.recent_confidences or [])
    confidences.append(confidence)
    template.recent_confidences = confidences[-MONITOR_WINDOW:]
