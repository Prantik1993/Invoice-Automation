class InvoiceAutomationError(Exception):
    """Base exception for all invoice automation errors."""
    pass


class DuplicateInvoiceError(InvoiceAutomationError):
    """Raised when invoice already exists in the database."""
    pass


class PDFExtractionError(InvoiceAutomationError):
    """Raised when PyMuPDF cannot extract text from PDF."""
    pass


class OCRFailedError(InvoiceAutomationError):
    """Raised when Tesseract OCR fails or returns empty text."""
    pass


class LLMExtractionError(InvoiceAutomationError):
    """Raised when OpenAI fails to extract fields from text."""
    pass


class LowConfidenceError(InvoiceAutomationError):
    """Raised when extraction confidence is below threshold."""
    def __init__(self, confidence: float, threshold: float):
        self.confidence = confidence
        self.threshold = threshold
        super().__init__(f"Confidence {confidence:.2f} below threshold {threshold:.2f}")


class VendorTemplateError(InvoiceAutomationError):
    """Raised when vendor template operations fail."""
    pass


class FileOperationError(InvoiceAutomationError):
    """Raised when file move/copy operations fail."""
    pass
