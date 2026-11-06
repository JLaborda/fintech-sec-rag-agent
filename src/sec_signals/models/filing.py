"""Filing and chunk models."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sec_signals.models.enums import DemoTicker, FormType


class Filing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: DemoTicker
    cik: str = Field(pattern=r"^[0-9]+$")
    accession_number: str = Field(min_length=1)
    form: FormType
    filing_date: date
    source_urls: list[str] = Field(min_length=1)
    raw_s3_uri: str = Field(min_length=1)
    primary_document: str = Field(min_length=1)
    ingested_at: datetime


class Chunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    ticker: DemoTicker
    cik: str = Field(pattern=r"^[0-9]+$")
    accession_number: str = Field(min_length=1)
    form: FormType
    filing_date: date
    section: str = Field(min_length=1)
    item: str = Field(min_length=1)
    text: str = Field(min_length=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    embedding: list[float] | None = None

    @field_validator("embedding")
    @classmethod
    def _embedding_dim(cls, value: list[float] | None) -> list[float] | None:
        if value is not None and len(value) != 1024:
            raise ValueError("embedding must be 1024-d Titan V2 vector when present")
        return value
