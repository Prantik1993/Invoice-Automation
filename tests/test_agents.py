import pytest
from unittest.mock import patch
from app.agents.validation_agent import validation_agent_node
from app.agents.duplicate_agent import duplicate_agent_node


# ── Validation Agent Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validation_flags_low_confidence():
    """Confidence below threshold → needs_review = True."""
    state = {
        "pdf_path": "test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {
            "account_number": "ACC-001",
            "invoice_number": "INV-001",
            "total_due": 100.0,
            "bill_date": "2024-01-01",
        },
        "confidence": 0.50,  # below 0.85 threshold
        "agent_log": [],
    }
    result = await validation_agent_node(state)
    assert result["needs_review"] is True


@pytest.mark.asyncio
async def test_validation_passes_high_confidence():
    """All required fields present + confidence above threshold → needs_review = False."""
    state = {
        "pdf_path": "test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {
            "account_number": "ACC-001",
            "invoice_number": "INV-001",
            "total_due": 100.0,
            "bill_date": "2024-01-01",
        },
        "confidence": 0.95,
        "agent_log": [],
    }
    result = await validation_agent_node(state)
    assert result["needs_review"] is False


@pytest.mark.asyncio
async def test_validation_flags_missing_required_fields():
    """Missing account_number, total_due, bill_date → needs_review = True."""
    state = {
        "pdf_path": "test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {
            # account_number, total_due, bill_date all missing
            "invoice_number": "INV-001",
        },
        "confidence": 0.95,
        "agent_log": [],
    }
    result = await validation_agent_node(state)
    assert result["needs_review"] is True


@pytest.mark.asyncio
async def test_validation_generates_invoice_number_when_missing():
    """invoice_number missing → generated as AccountNumber_BillDate."""
    state = {
        "pdf_path": "test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {
            "account_number": "ACC-001",
            "total_due": 100.0,
            "bill_date": "2024-01-15",
            # invoice_number intentionally missing
        },
        "confidence": 0.95,
        "agent_log": [],
    }
    result = await validation_agent_node(state)
    assert result["resolved_invoice_number"] == "ACC-001_20240115"


@pytest.mark.asyncio
async def test_validation_computes_due_date_from_bill_date():
    """due_date missing → bill_date + 14 days."""
    state = {
        "pdf_path": "test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {
            "account_number": "ACC-001",
            "total_due": 100.0,
            "bill_date": "2024-01-01",
            # due_date intentionally missing
        },
        "confidence": 0.95,
        "agent_log": [],
    }
    result = await validation_agent_node(state)
    assert result["resolved_due_date"] == "2024-01-15"


@pytest.mark.asyncio
async def test_validation_accumulates_agent_log():
    """agent_log entries from previous nodes should be preserved."""
    state = {
        "pdf_path": "test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {
            "account_number": "ACC-001",
            "total_due": 100.0,
            "bill_date": "2024-01-01",
        },
        "confidence": 0.95,
        "agent_log": ["supervisor: start", "extraction_agent: done"],
    }
    result = await validation_agent_node(state)
    # Previous log entries must still be present
    assert "supervisor: start" in result["agent_log"]
    assert "extraction_agent: done" in result["agent_log"]
    # New entries added
    assert any("validation_agent" in entry for entry in result["agent_log"])


# ── Duplicate Agent Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_agent_no_duplicate(tmp_path):
    """File not in processed/ → is_duplicate = False."""
    pdf_file = tmp_path / "invoice.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    state = {
        "pdf_path": str(pdf_file),
        "pdf_filename": "invoice.pdf",
        "agent_log": [],
    }

    # Patch check_filename_duplicate to return False
    with patch("app.agents.duplicate_agent.check_filename_duplicate") as mock_check:
        mock_check.invoke.return_value = False
        result = await duplicate_agent_node(state)

    assert result["is_duplicate"] is False


@pytest.mark.asyncio
async def test_duplicate_agent_detects_duplicate(tmp_path):
    """File already in processed/ → is_duplicate = True."""
    pdf_file = tmp_path / "invoice.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    state = {
        "pdf_path": str(pdf_file),
        "pdf_filename": "invoice.pdf",
        "agent_log": [],
    }

    with patch("app.agents.duplicate_agent.check_filename_duplicate") as mock_check, \
         patch("app.agents.duplicate_agent.move_to_duplicates") as mock_move:
        mock_check.invoke.return_value = True
        mock_move.invoke.return_value = "Moved to duplicates/"
        result = await duplicate_agent_node(state)

    assert result["is_duplicate"] is True
    assert result["status"] == "duplicate"