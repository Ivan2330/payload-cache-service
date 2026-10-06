"""Database tables.

Two tables, one per thing worth caching:

* ``transformed_strings`` - the expensive part: one row per distinct source
  string, so the transformer is never asked about the same string twice.
* ``payloads`` - the assembled answer, keyed by a hash of the request, so a
  repeated POST costs one primary-key lookup and no work at all.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TransformedString(Base):
    __tablename__ = "transformed_strings"

    # The source string is the natural key: it is what we look up by and it is
    # unique by definition. A surrogate id would add a column and a second
    # index without buying anything.
    source: Mapped[str] = mapped_column(String(1024), primary_key=True)
    transformed: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Payload(Base):
    __tablename__ = "payloads"

    # SHA-256 of the canonical request. Deterministic, so two identical
    # requests produce the same identifier without a lookup table and without
    # a race between concurrent writers.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    output: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
