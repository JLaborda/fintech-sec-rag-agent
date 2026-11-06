"""Pipeline orchestration."""

from sec_signals.pipeline.batch_emit import FilingRef, TickerEmitResult, batch_emit
from sec_signals.pipeline.emit import emit_for_filing

__all__ = [
    "FilingRef",
    "TickerEmitResult",
    "batch_emit",
    "emit_for_filing",
]
