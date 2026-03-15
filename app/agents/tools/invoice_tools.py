import shutil
from datetime import datetime, date, timedelta
from pathlib import Path
from langchain_core.tools import tool

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@tool
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from a PDF using PyMuPDF. Returns empty string if no text layer found."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        logger.info("tool_pdf_extracted", path=pdf_path, chars=len(text))
        return text.strip()
    except Exception as e:
        logger.error("tool_pdf_failed", path=pdf_path, error=str(e))
        return ""


@tool
def extract_text_via_ocr(pdf_path: str) -> str:
    """Extract text from a scanned PDF using Tesseract OCR. Fallback when direct extraction returns too little text."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
        images = convert_from_path(pdf_path, dpi=300)
        text = "".join(pytesseract.image_to_string(img) for img in images)
        logger.info("tool_ocr_extracted", path=pdf_path, chars=len(text))
        return text.strip()
    except Exception as e:
        logger.error("tool_ocr_failed", path=pdf_path, error=str(e))
        return ""


@tool
def move_to_duplicates(pdf_path: str, filename: str) -> str:
    """Move a PDF to the duplicates folder."""
    dest = Path(settings.duplicates_folder) / filename
    try:
        Path(settings.duplicates_folder).mkdir(parents=True, exist_ok=True)
        shutil.move(pdf_path, dest)
        logger.info("tool_moved_duplicate", filename=filename)
        return f"Moved to {dest}"
    except Exception as e:
        logger.error("tool_move_duplicate_failed", error=str(e))
        return f"Move failed: {e}"


@tool
def move_to_processed(pdf_path: str, filename: str) -> str:
    """Move a PDF to the processed folder after approval."""
    dest = Path(settings.processed_folder) / filename
    try:
        Path(settings.processed_folder).mkdir(parents=True, exist_ok=True)
        shutil.move(pdf_path, dest)
        logger.info("tool_moved_processed", filename=filename)
        return f"Moved to {dest}"
    except Exception as e:
        logger.error("tool_move_processed_failed", error=str(e))
        return f"Move failed: {e}"


@tool
def move_to_failed(pdf_path: str, filename: str) -> str:
    """Move a PDF to the failed folder when all extraction methods are exhausted."""
    dest = Path(settings.failed_folder) / filename
    try:
        Path(settings.failed_folder).mkdir(parents=True, exist_ok=True)
        shutil.move(pdf_path, dest)
        logger.info("tool_moved_failed", filename=filename)
        return f"Moved to {dest}"
    except Exception as e:
        return f"Move failed: {e}"


@tool
def check_filename_duplicate(filename: str) -> bool:
    """Check if a PDF with this filename has already been processed, failed, or flagged as duplicate.

    Checks all three terminal folders so previously-failed invoices are not
    reprocessed on watcher restart.
    """
    terminal_folders = [
        settings.processed_folder,
        settings.duplicates_folder,
        settings.failed_folder,
    ]
    return any((Path(folder) / filename).exists() for folder in terminal_folders)


@tool
def resolve_due_date(bill_date_str: str | None) -> str | None:
    """Calculate due date as bill_date + configured payment days. Returns ISO date string or None."""
    if not bill_date_str:
        return None
    try:
        bill_date = datetime.strptime(bill_date_str, "%Y-%m-%d").date()
        return (bill_date + timedelta(days=settings.default_payment_days)).isoformat()
    except Exception:
        return None


@tool
def generate_invoice_number(account_number: str | None, bill_date_str: str | None) -> str:
    """Generate a fallback invoice number as AccountNumber_BillDate when none is found in the PDF."""
    acc = account_number or "UNKNOWN"
    if bill_date_str:
        try:
            d = datetime.strptime(bill_date_str, "%Y-%m-%d")
            return f"{acc}_{d.strftime('%Y%m%d')}"
        except Exception:
            pass
    return f"{acc}_NODATE"


PDF_TOOLS = [extract_text_from_pdf, extract_text_via_ocr]
FILE_TOOLS = [move_to_duplicates, move_to_processed, move_to_failed, check_filename_duplicate]
FIELD_TOOLS = [resolve_due_date, generate_invoice_number]
ALL_TOOLS = PDF_TOOLS + FILE_TOOLS + FIELD_TOOLS