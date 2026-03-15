import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.agents.validation_agent import validation_agent_node
from app.agents.duplicate_agent import duplicate_agent_node
from app.agents.template_agent import template_agent_node
from app.agents.save_agent import save_agent_node
from app.config import settings
from datetime import date, timedelta


# ── Validation Agent ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validation_flags_low_confidence():
    state = {
        "pdf_path": "test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {
            "account_number": "ACC-001",
            "invoice_number": "INV-001",
            "total_due": 100.0,
            "bill_date": "2024-01-01",
        },
        "confidence": 0.50,
        "agent_log": [],
    }
    result = await validation_agent_node(state)
    assert result["needs_review"] is True


@pytest.mark.asyncio
async def test_validation_passes_high_confidence():
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
    state = {
        "pdf_path": "test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {"invoice_number": "INV-001"},
        "confidence": 0.95,
        "agent_log": [],
    }
    result = await validation_agent_node(state)
    assert result["needs_review"] is True


@pytest.mark.asyncio
async def test_validation_generates_invoice_number_when_missing():
    state = {
        "pdf_path": "test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {
            "account_number": "ACC-001",
            "total_due": 100.0,
            "bill_date": "2024-01-15",
        },
        "confidence": 0.95,
        "agent_log": [],
    }
    result = await validation_agent_node(state)
    assert result["resolved_invoice_number"] == "ACC-001_20240115"


@pytest.mark.asyncio
async def test_validation_computes_due_date_from_bill_date():
    """due_date is calculated as bill_date + default_payment_days from config."""
    bill_date = date(2024, 1, 1)
    expected = bill_date + timedelta(days=settings.default_payment_days)

    state = {
        "pdf_path": "test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {
            "account_number": "ACC-001",
            "total_due": 100.0,
            "bill_date": "2024-01-01",
        },
        "confidence": 0.95,
        "agent_log": [],
    }
    result = await validation_agent_node(state)
    assert result["resolved_due_date"] == expected.isoformat()


@pytest.mark.asyncio
async def test_validation_preserves_prior_agent_log():
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
    assert "supervisor: start" in result["agent_log"]
    assert "extraction_agent: done" in result["agent_log"]
    assert any("validation_agent" in e for e in result["agent_log"])


# ── Duplicate Agent ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_agent_no_duplicate(tmp_path):
    pdf_file = tmp_path / "invoice.pdf"
    pdf_file.write_bytes(b"fake pdf content")
    state = {"pdf_path": str(pdf_file), "pdf_filename": "invoice.pdf", "agent_log": []}

    with patch("app.agents.duplicate_agent.check_filename_duplicate") as mock_check:
        mock_check.invoke.return_value = False
        result = await duplicate_agent_node(state)

    assert result["is_duplicate"] is False


@pytest.mark.asyncio
async def test_duplicate_agent_detects_duplicate(tmp_path):
    pdf_file = tmp_path / "invoice.pdf"
    pdf_file.write_bytes(b"fake pdf content")
    state = {"pdf_path": str(pdf_file), "pdf_filename": "invoice.pdf", "agent_log": []}

    with patch("app.agents.duplicate_agent.check_filename_duplicate") as mock_check, \
         patch("app.agents.duplicate_agent.move_to_duplicates") as mock_move:
        mock_check.invoke.return_value = True
        mock_move.invoke.return_value = "Moved to duplicates/"
        result = await duplicate_agent_node(state)

    assert result["is_duplicate"] is True
    assert result["status"] == "duplicate"


# ── Template Agent ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_template_agent_no_vendor_skips_check():
    state = {"vendor_name": None, "confidence": 0.90, "needs_review": True, "agent_log": []}
    with patch("app.agents.template_agent.AsyncSessionLocal"):
        result = await template_agent_node(state)
    assert result["needs_review"] is True


@pytest.mark.asyncio
async def test_template_agent_active_vendor_auto_approves():
    state = {"vendor_name": "ATT", "confidence": 0.92, "needs_review": False, "agent_log": []}

    with patch("app.agents.template_agent.AsyncSessionLocal") as mock_cls:
        mock_db = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.agents.template_agent.check_layout_change", AsyncMock(return_value=False)), \
             patch("app.agents.template_agent.is_vendor_active", AsyncMock(return_value=True)):
            result = await template_agent_node(state)

    assert result["needs_review"] is False


@pytest.mark.asyncio
async def test_template_agent_layout_change_forces_review():
    state = {"vendor_name": "ATT", "confidence": 0.55, "needs_review": False, "agent_log": []}

    with patch("app.agents.template_agent.AsyncSessionLocal") as mock_cls:
        mock_db = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.agents.template_agent.check_layout_change", AsyncMock(return_value=True)):
            result = await template_agent_node(state)

    assert result["needs_review"] is True
    assert result.get("layout_change_detected") is True


@pytest.mark.asyncio
async def test_template_agent_validation_flag_respected():
    """Vendor is active but validation already flagged review — must not override."""
    state = {"vendor_name": "ATT", "confidence": 0.92, "needs_review": True, "agent_log": []}

    with patch("app.agents.template_agent.AsyncSessionLocal") as mock_cls:
        mock_db = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.agents.template_agent.check_layout_change", AsyncMock(return_value=False)), \
             patch("app.agents.template_agent.is_vendor_active", AsyncMock(return_value=True)):
            result = await template_agent_node(state)

    assert result["needs_review"] is True


# ── Save Agent ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_agent_pending_does_not_move_file():
    state = {
        "pdf_path": "./data/incoming/test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {
            "account_number": "ACC-001",
            "total_due": 150.0,
            "bill_date": "2024-01-01",
        },
        "resolved_invoice_number": "ACC-001_20240101",
        "resolved_bill_date": "2024-01-01",
        "resolved_due_date": "2024-01-15",
        "vendor_name": "ATT",
        "thread_id": "thread-123",
        "confidence": 0.88,
        "extraction_method": "direct",
        "needs_review": True,
        "agent_log": [],
    }

    with patch("app.agents.save_agent.move_to_processed") as mock_move, \
         patch("app.agents.save_agent.AsyncSessionLocal") as mock_cls:
        mock_db = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_invoice = MagicMock()
        mock_invoice.id = 42
        mock_invoice.status = "pending"

        async def fake_refresh(obj):
            obj.id = 42
            obj.status = "pending"

        mock_db.commit = AsyncMock()
        mock_db.refresh = fake_refresh
        mock_db.add = MagicMock()

        await save_agent_node(state)

    mock_move.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_save_agent_auto_approved_moves_file():
    state = {
        "pdf_path": "./data/incoming/test.pdf",
        "pdf_filename": "test.pdf",
        "extracted_fields": {
            "account_number": "ACC-001",
            "total_due": 150.0,
            "bill_date": "2024-01-01",
        },
        "resolved_invoice_number": "ACC-001_20240101",
        "resolved_bill_date": "2024-01-01",
        "resolved_due_date": "2024-01-15",
        "vendor_name": "ATT",
        "thread_id": "thread-456",
        "confidence": 0.92,
        "extraction_method": "direct",
        "needs_review": False,
        "agent_log": [],
    }

    with patch("app.agents.save_agent.move_to_processed") as mock_move, \
         patch("app.agents.save_agent.AsyncSessionLocal") as mock_cls:
        mock_db = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_move.invoke.return_value = "Moved to processed/"

        async def fake_refresh(obj):
            obj.id = 7
            obj.status = "approved"

        mock_db.commit = AsyncMock()
        mock_db.refresh = fake_refresh
        mock_db.add = MagicMock()

        await save_agent_node(state)

    mock_move.invoke.assert_called_once()