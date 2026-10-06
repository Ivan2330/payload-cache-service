"""Database tables: one for cached strings, one for assembled payloads."""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TransformedString(Base):
    __tablename__ = "transformed_strings"

    # Natural key: it is what we look up by, and it is unique by definition.
    source: Mapped[str] = mapped_column(String(1024), primary_key=True)
    transformed: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Payload(Base):
    __tablename__ = "payloads"

    # SHA-256 of the canonical request; see service.payload_id.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    output: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
