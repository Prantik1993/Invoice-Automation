from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.vendor_template import VendorTemplate
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


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
    """Return True if vendor has an active template and is eligible for auto-approval."""
    result = await db.execute(
        select(VendorTemplate).where(
            VendorTemplate.vendor_name == vendor_name,
            VendorTemplate.is_active == True,
        )
    )
    return result.scalar_one_or_none() is not None


async def record_approval(
    db: AsyncSession,
    vendor_name: str,
    confidence: float,
    bill_from_address: str | None = None,
) -> None:
    """Record a human approval. Activates the vendor template on first approval.

    bill_from_address is stored so future extractions from the same vendor
    can be validated against a known-good address.
    """
    template = await get_or_create_template(db, vendor_name)
    template.approval_count += 1

    if not template.is_active:
        template.is_active = True
        logger.info("vendor_template_activated", vendor=vendor_name)

    # Store the bill_from address from the first approved invoice.
    # This gives us a reference point for future layout-change detection.
    if bill_from_address and not template.known_bill_from:
        template.known_bill_from = bill_from_address
        logger.info("vendor_bill_from_stored", vendor=vendor_name)

    _update_confidence_window(template, confidence)
    await db.flush()


async def check_layout_change(db: AsyncSession, vendor_name: str, confidence: float) -> bool:
    """Return True if the vendor's rolling confidence average has dropped below threshold.

    When a layout change is detected the template is disabled and the vendor
    returns to the human review queue until the next manual approval.
    """
    result = await db.execute(
        select(VendorTemplate).where(VendorTemplate.vendor_name == vendor_name)
    )
    template = result.scalar_one_or_none()
    if not template or not template.is_active:
        return False

    _update_confidence_window(template, confidence)

    window = settings.template_monitor_window
    confidences = template.recent_confidences or []

    if len(confidences) >= window:
        avg = sum(confidences[-window:]) / window
        template.avg_confidence = avg

        if avg < settings.layout_change_threshold:
            template.is_active = False
            template.approval_count = 0
            template.recent_confidences = []
            logger.warning(
                "layout_change_detected",
                vendor=vendor_name,
                avg_confidence=avg,
                threshold=settings.layout_change_threshold,
                window=window,
            )
            await db.flush()
            return True

    return False


def _update_confidence_window(template: VendorTemplate, confidence: float) -> None:
    window = settings.template_monitor_window
    confidences = list(template.recent_confidences or [])
    confidences.append(confidence)
    template.recent_confidences = confidences[-window:]