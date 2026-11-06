"""Warehouse tabular rows (SignalFactorRow)."""

from __future__ import annotations

import json
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sec_signals.models.emission import SignalEmission
from sec_signals.models.enums import DemoTicker, FactorId, FactorStatus, FormType


class SignalFactorRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor_schema_version: str = Field(min_length=1)
    ticker: DemoTicker
    filing_date: date
    cik: str
    accession_number: str
    form: FormType
    model_or_pipeline_version: str
    emitted_at: datetime
    factor_id: FactorId
    status: FactorStatus
    polarity: float | None = None
    conviction: float | None = None
    citation_section: str | None = None
    citation_item: str | None = None
    citation_quote: str | None = None
    citation_char_start: int | None = None
    citation_char_end: int | None = None
    citation_chunk_id: str | None = None
    reasoning: str = Field(min_length=1)
    disclaimer: str = Field(min_length=1)
    key_events_json: str | None = None

    @model_validator(mode="after")
    def _ok_requires_citation_and_polarity(self) -> SignalFactorRow:
        if self.status is FactorStatus.OK:
            if self.polarity is None:
                raise ValueError("ok rows require polarity")
            if not self.citation_section or not self.citation_item or not self.citation_quote:
                raise ValueError("ok rows require citation columns")
        if self.status is FactorStatus.INSUFFICIENT_EVIDENCE and self.polarity is not None:
            raise ValueError("insufficient_evidence rows must have null polarity")
        return self


def flatten_emission(emission: SignalEmission) -> list[SignalFactorRow]:
    key_events_json = None
    if emission.key_events:
        key_events_json = json.dumps(
            [e.model_dump(mode="json") for e in emission.key_events],
            separators=(",", ":"),
        )
    rows: list[SignalFactorRow] = []
    for factor in emission.factors:
        citation = factor.citation
        rows.append(
            SignalFactorRow(
                factor_schema_version=emission.factor_schema_version,
                ticker=emission.ticker,
                filing_date=emission.filing_date,
                cik=emission.cik,
                accession_number=emission.accession_number,
                form=emission.form,
                model_or_pipeline_version=emission.model_or_pipeline_version,
                emitted_at=emission.emitted_at,
                factor_id=factor.factor_id,
                status=factor.status,
                polarity=factor.polarity,
                conviction=factor.conviction,
                citation_section=citation.section if citation else None,
                citation_item=citation.item if citation else None,
                citation_quote=citation.quote if citation else None,
                citation_char_start=citation.char_start if citation else None,
                citation_char_end=citation.char_end if citation else None,
                citation_chunk_id=citation.chunk_id if citation else None,
                reasoning=factor.reasoning,
                disclaimer=emission.disclaimer,
                key_events_json=key_events_json,
            )
        )
    if len(rows) != 5:
        raise ValueError("flatten must yield exactly five rows")
    return rows
