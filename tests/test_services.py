import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.duplicate_checker import check_duplicate
from app.core.exceptions import DuplicateInvoiceError


# ── Duplicate Checker Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_raises_when_found():
    """Existing invoice in DB → DuplicateInvoiceError raised."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()  # record found
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(DuplicateInvoiceError):
        await check_duplicate(mock_db, "ACC-001", "INV-001", 100.0)


@pytest.mark.asyncio
async def test_duplicate_passes_when_not_found():
    """No existing invoice in DB → no exception raised."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # no record
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Should not raise
    await check_duplicate(mock_db, "ACC-001", "INV-001", 100.0)


@pytest.mark.asyncio
async def test_duplicate_error_message_contains_invoice_number():
    """Error message should include invoice number for debuggability."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(DuplicateInvoiceError) as exc_info:
        await check_duplicate(mock_db, "ACC-001", "INV-XYZ", 100.0)

    assert "INV-XYZ" in str(exc_info.value)


# ── PDF Extractor Tests ───────────────────────────────────────────────────────

def test_pdf_extractor_raises_on_nonexistent_path():
    """Non-existent file → PDFExtractionError raised."""
    from app.services.pdf_extractor import extract_text_from_pdf
    from app.core.exceptions import PDFExtractionError

    with pytest.raises(PDFExtractionError):
        extract_text_from_pdf("/nonexistent/path/file.pdf")


def test_pdf_extractor_raises_on_non_pdf(tmp_path):
    """Text file passed as PDF → PDFExtractionError raised."""
    from app.services.pdf_extractor import extract_text_from_pdf
    from app.core.exceptions import PDFExtractionError

    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_text("this is not a pdf")

    with pytest.raises(PDFExtractionError):
        extract_text_from_pdf(str(fake_pdf))


# ── Template Learning Tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_approval_activates_template_on_first_approval():
    """First approval → template is_active becomes True."""
    from app.services.template_learning import record_approval, get_or_create_template

    mock_db = AsyncMock()
    mock_template = MagicMock()
    mock_template.is_active = False
    mock_template.approval_count = 0
    mock_template.recent_confidences = []

    with patch("app.services.template_learning.get_or_create_template",
               AsyncMock(return_value=mock_template)):
        await record_approval(mock_db, "ATT", 0.92)

    assert mock_template.is_active is True
    assert mock_template.approval_count == 1


@pytest.mark.asyncio
async def test_check_layout_change_returns_false_for_new_vendor():
    """Vendor with no template → layout change returns False."""
    from app.services.template_learning import check_layout_change

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # no template
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await check_layout_change(mock_db, "NEW_VENDOR", 0.90)
    assert result is False


@pytest.mark.asyncio
async def test_check_layout_change_detects_low_confidence():
    """Active vendor with avg confidence < 0.70 → layout change detected."""
    from app.services.template_learning import check_layout_change

    mock_db = AsyncMock()
    mock_template = MagicMock()
    mock_template.is_active = True
    # 10 invoices all with low confidence
    mock_template.recent_confidences = [0.55, 0.60, 0.58, 0.62, 0.55,
                                         0.60, 0.58, 0.62, 0.55, 0.60]
    mock_template.avg_confidence = 0.0

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_template
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await check_layout_change(mock_db, "ATT", 0.58)
    assert result is True
    assert mock_template.is_active is False