"""
Unified database schema for Clark County permit system.
Ensures consistency across all databases and provides migration utilities.
"""

import logging
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()
logger = logging.getLogger(__name__)

# --- Begin full unified_schema.py content from old directory ---

class Permit(Base):
    """Unified permit model with all fields from enhanced scraping."""
    __tablename__ = "permits"
    id = Column(Integer, primary_key=True)
    permit_number = Column(String(50), unique=True, nullable=False, index=True)
    record_type = Column(String(100), index=True)
    project_name = Column(String(255))
    description = Column(Text)
    address = Column(String(500))
    status = Column(String(50), index=True)
    date_opened = Column(DateTime, index=True)
    date_closed = Column(DateTime)
    owner_name = Column(String(255))
    owner_address = Column(String(500))
    owner_city = Column(String(100))
    owner_state = Column(String(50))
    owner_zip = Column(String(20))
    job_value = Column(Float)
    funded_amount = Column(String(50), nullable=False, default="")
    total_fees = Column(Float)
    paid_fees = Column(Float)
    balance_due = Column(Float)
    application_date = Column(DateTime)
    issue_date = Column(DateTime)
    finaled_date = Column(DateTime)
    expiration_date = Column(DateTime)
    last_inspection_date = Column(DateTime)
    fees_paid = Column(String(50), nullable=False, default="")
    electronic_plans = Column(Boolean, default=False)
    type_of_work = Column(String(255))
    square_footage = Column(Float)
    zoning = Column(String(50), nullable=False, default="")
    number_of_units = Column(Integer)
    dwelling_units = Column(String(20), nullable=False, default="")
    work_description = Column(Text, nullable=False, default="")
    use_code = Column(String(50), nullable=False, default="")
    occupancy_type = Column(String(100))
    construction_type = Column(String(100))
    parcel_number = Column(String(50), index=True)
    block = Column(String(50))
    lot = Column(String(50))
    subdivision = Column(String(255))
    contractor_name = Column(String(255))
    contractor_phone = Column(String(50), nullable=False, default="")
    contractor_address = Column(Text, nullable=False, default="")
    contractor_license = Column(String(50))
    architect_name = Column(String(255))
    engineer_name = Column(String(255))
    water_provider = Column(String(100))
    sanitation_provider = Column(String(100))
    property_acreage = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_scraped = Column(DateTime)
    scrape_source = Column(String(50))
    completeness_score = Column(Float, default=0.0)
    scraped_date = Column(DateTime, default=datetime.utcnow)
    extraction_notes = Column(Text, default="")
    applied_date = Column(DateTime, index=True)
    issued_date = Column(DateTime, index=True)
    inspections = relationship(
        "Inspection", back_populates="permit", cascade="all, delete-orphan"
    )
    documents = relationship(
        "Document", back_populates="permit", cascade="all, delete-orphan"
    )
    fees = relationship("Fee", back_populates="permit", cascade="all, delete-orphan")
    status_history = relationship(
        "StatusHistory", back_populates="permit", cascade="all, delete-orphan"
    )
    __table_args__ = (
        Index("idx_permit_date_status", "date_opened", "status"),
        Index("idx_permit_owner", "owner_name"),
        Index("idx_permit_address", "address"),
        Index("idx_permit_updated", "updated_at"),
    )
    def to_dict(self):
        import json
        from datetime import date, datetime
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, (datetime, date)):
                result[column.name] = value.isoformat()
            elif column.name in ["job_value", "total_fees", "paid_fees", "balance_due", "square_footage", "property_acreage"]:
                result[column.name] = str(value) if value is not None else ""
            elif column.name == "completeness_score":
                result[column.name] = value if value is not None else 0.0
            elif column.name == "extraction_notes":
                if value:
                    try:
                        result[column.name] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        result[column.name] = []
                else:
                    result[column.name] = []
            else:
                result[column.name] = value if value is not None else ""
        if "record_type" in result:
            result["permit_type"] = result.pop("record_type")
        return result

class Inspection(Base):
    __tablename__ = "inspections"
    id = Column(Integer, primary_key=True)
    permit_id = Column(Integer, ForeignKey("permits.id", ondelete="CASCADE"))
    inspection_type = Column(String(100))
    scheduled_date = Column(DateTime)
    completed_date = Column(DateTime)
    status = Column(String(50))
    inspector_name = Column(String(255))
    comments = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    permit = relationship("Permit", back_populates="inspections")
    __table_args__ = (
        Index("idx_inspection_permit", "permit_id"),
        Index("idx_inspection_date", "scheduled_date"),
    )

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    permit_id = Column(Integer, ForeignKey("permits.id", ondelete="CASCADE"))
    document_type = Column(String(100))
    document_name = Column(String(255))
    file_path = Column(String(500))
    upload_date = Column(DateTime)
    file_size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    permit = relationship("Permit", back_populates="documents")
    __table_args__ = (
        Index("idx_document_permit", "permit_id"),
        Index("idx_document_type", "document_type"),
    )

class Fee(Base):
    __tablename__ = "fees"
    id = Column(Integer, primary_key=True)
    permit_id = Column(Integer, ForeignKey("permits.id", ondelete="CASCADE"))
    fee_type = Column(String(100))
    amount = Column(Float)
    status = Column(String(50))
    paid_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    permit = relationship("Permit", back_populates="fees")
    __table_args__ = (
        Index("idx_fee_permit", "permit_id"),
        Index("idx_fee_status", "status"),
    )

class StatusHistory(Base):
    __tablename__ = "status_history"
    id = Column(Integer, primary_key=True)
    permit_id = Column(Integer, ForeignKey("permits.id", ondelete="CASCADE"))
    old_status = Column(String(50))
    new_status = Column(String(50))
    changed_date = Column(DateTime, default=datetime.utcnow)
    changed_by = Column(String(100))
    notes = Column(Text)
    permit = relationship("Permit", back_populates="status_history")
    __table_args__ = (
        Index("idx_status_history_permit", "permit_id"),
        Index("idx_status_history_date", "changed_date"),
    )

class ScrapeRun(Base):
    __tablename__ = "scrape_runs"
    id = Column(Integer, primary_key=True)
    run_id = Column(String(50), unique=True)
    scraper_type = Column(String(50))
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    status = Column(String(50))
    permits_found = Column(Integer, default=0)
    permits_processed = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    error_details = Column(Text)
    __table_args__ = (
        Index("idx_scrape_run_time", "start_time"),
        Index("idx_scrape_run_status", "status"),
    )

# --- End full unified_schema.py content --- 