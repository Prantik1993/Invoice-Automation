import pytesseract
from pdf2image import convert_from_path
from app.core.exceptions import OCRFailedError
from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_text_via_ocr(pdf_path: str) -> str:
    """Convert PDF pages to images and run Tesseract OCR."""
    try:
        images = convert_from_path(pdf_path, dpi=300)
        text = ""
        for i, image in enumerate(images):
            page_text = pytesseract.image_to_string(image)
            text += page_text

        text = text.strip()
        if not text:
            raise OCRFailedError(f"OCR returned empty text for {pdf_path}")

        logger.info("ocr_extracted", path=pdf_path, char_count=len(text))
        return text

    except OCRFailedError:
        raise
    except Exception as e:
        logger.error("ocr_failed", path=pdf_path, error=str(e))
        raise OCRFailedError(f"OCR failed for {pdf_path}: {e}")
