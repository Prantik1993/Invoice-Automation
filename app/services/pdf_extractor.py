import fitz  # PyMuPDF
from app.core.exceptions import PDFExtractionError
from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from PDF using PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()

        logger.info("pdf_extracted", path=pdf_path, char_count=len(text))
        return text.strip()

    except Exception as e:
        logger.error("pdf_extraction_failed", path=pdf_path, error=str(e))
        raise PDFExtractionError(f"Failed to extract text from {pdf_path}: {e}")
