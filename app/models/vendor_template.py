from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class VendorTemplate(Base):
    __tablename__ = "vendor_templates"

    id = Column(Integer, primary_key=True, index=True)
    vendor_name = Column(String, unique=True, index=True)  # e.g. "ATT", "Verizon"

    # Learning state
    approval_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=False)  # active after 1st approval

    # Confidence tracking (last 10 invoices)
    recent_confidences = Column(JSON, default=list)  # [0.92, 0.88, ...]
    avg_confidence = Column(Float, default=0.0)

    # Known address patterns for matching
    known_bill_from = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
