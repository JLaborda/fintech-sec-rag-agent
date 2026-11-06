"""Hermetic signal emission Pydantic models (schema 0.1.0)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sec_signals.models.enums import DemoTicker, FactorId, FactorStatus, FormType

FACTOR_SCHEMA_VERSION = "0.1.0"


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str = Field(min_length=1)
    item: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    chunk_id: str | None = None


class FactorSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor_id: FactorId
    status: FactorStatus
    polarity: float | None = None
    conviction: float | None = None
    citation: Citation | None = None
    reasoning: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_status_shape(self) -> FactorSignal:
        if self.status is FactorStatus.OK:
            if self.polarity is None or self.conviction is None or self.citation is None:
                raise ValueError("ok factors require polarity, conviction, and citation")
            if not (-1.0 <= self.polarity <= 1.0):
                raise ValueError("polarity must be in [-1.0, 1.0]")
            if not (0.0 <= self.conviction <= 1.0):
                raise ValueError("conviction must be in [0.0, 1.0]")
            return self
        if self.status is FactorStatus.INSUFFICIENT_EVIDENCE:
            if self.polarity is not None:
                raise ValueError("insufficient_evidence forbids polarity")
            if self.conviction is not None:
                raise ValueError("insufficient_evidence forbids conviction")
            if self.citation is not None:
                raise ValueError("insufficient_evidence forbids citation")
            return self
        raise ValueError(f"unsupported status: {self.status}")


class KeyEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    citation: Citation


class SignalEmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor_schema_version: Literal["0.1.0"] = FACTOR_SCHEMA_VERSION
    model_or_pipeline_version: str = Field(min_length=1)
    ticker: DemoTicker
    cik: Annotated[str, Field(pattern=r"^[0-9]+$")]
    accession_number: str = Field(min_length=1)
    form: FormType
    filing_date: date
    factors: list[FactorSignal]
    key_events: list[KeyEvent] | None = None
    disclaimer: str = Field(min_length=1)
    emitted_at: datetime

    @field_validator("factors")
    @classmethod
    def _exactly_five_unique_catalog(cls, factors: list[FactorSignal]) -> list[FactorSignal]:
        if len(factors) != 5:
            raise ValueError("exactly five factors required")
        ids = [f.factor_id for f in factors]
        if set(ids) != set(FactorId):
            raise ValueError("factors must cover the closed catalog exactly once each")
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate factor_id")
        return factors
