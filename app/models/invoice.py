from sqlalchemy import Column, Integer, String, Float, Date, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    pdf_filename = Column(String, nullable=False)
    pdf_path = Column(String, nullable=False)

    # Extracted fields
    account_number = Column(String, index=True)
    invoice_number = Column(String, unique=True, index=True)
    bill_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    total_due = Column(Float, nullable=True)
    bill_to_address = Column(Text, nullable=True)
    bill_from_address = Column(Text, nullable=True)
    remittance_address = Column(Text, nullable=True)

    # Processing metadata
    vendor_name = Column(String, nullable=True, index=True)  # for template learning
    thread_id = Column(String, nullable=True, index=True)   # LangGraph checkpoint thread_id
    confidence = Column(Float, default=0.0)
    extraction_method = Column(String, default="direct")  # direct | ocr
    needs_review = Column(Boolean, default=True)
    status = Column(String, default="pending")  # pending | approved | rejected

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)
