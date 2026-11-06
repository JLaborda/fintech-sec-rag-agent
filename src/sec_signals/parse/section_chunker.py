"""Section-aware 10-K chunking."""

from __future__ import annotations

import re
from datetime import date

from sec_signals.models.enums import DemoTicker, FormType
from sec_signals.models.filing import Chunk

_ITEM_RE = re.compile(
    r"(?im)^\s*item\s+(\d+[a-z]?)\.?\s*(.*)$"
)


def chunk_filing_text(
    text: str,
    *,
    ticker: str,
    cik: str,
    accession_number: str,
    form: str,
    filing_date: str,
    max_chars: int = 3500,
) -> list[Chunk]:
    lines = text.splitlines()
    sections: list[tuple[str, str, list[str]]] = []
    current_item = "Unknown"
    current_section = "Unknown"
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if buf:
            sections.append((current_item, current_section, buf))
            buf = []

    for line in lines:
        match = _ITEM_RE.match(line.strip())
        if match:
            flush()
            current_item = f"Item {match.group(1).upper()}"
            current_section = match.group(2).strip() or current_item
            continue
        buf.append(line)
    flush()

    chunks: list[Chunk] = []
    filing_dt = date.fromisoformat(filing_date)
    ticker_enum = DemoTicker(ticker)
    form_enum = FormType(form)
    idx = 0
    for item, section, body_lines in sections:
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        start = 0
        while start < len(body):
            piece = body[start : start + max_chars]
            chunk_id = f"{accession_number}:{idx}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    ticker=ticker_enum,
                    cik=cik,
                    accession_number=accession_number,
                    form=form_enum,
                    filing_date=filing_dt,
                    section=section,
                    item=item,
                    text=piece,
                    char_start=start,
                    char_end=start + len(piece),
                )
            )
            idx += 1
            if start + max_chars >= len(body):
                break
            start += max_chars - 200  # overlap
    if not chunks and text.strip():
        chunks.append(
            Chunk(
                chunk_id=f"{accession_number}:0",
                ticker=ticker_enum,
                cik=cik,
                accession_number=accession_number,
                form=form_enum,
                filing_date=filing_dt,
                section="Full document",
                item="Unknown",
                text=text[:max_chars],
                char_start=0,
                char_end=min(len(text), max_chars),
            )
        )
    return chunks
