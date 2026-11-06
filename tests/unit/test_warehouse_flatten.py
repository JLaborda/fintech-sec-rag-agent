"""Warehouse flatten helpers (T053)."""

from datetime import date, datetime, timezone

from sec_signals.models.emission import Citation, FactorSignal, SignalEmission
from sec_signals.models.enums import FactorId, FactorStatus, FormType
from sec_signals.models.warehouse import flatten_emission


def _emission() -> SignalEmission:
    citation = Citation(section="Risk Factors", item="Item 1A", quote="litigation risk")
    factors = []
    for i, fid in enumerate(FactorId):
        if i == 0:
            factors.append(
                FactorSignal(
                    factor_id=fid,
                    status=FactorStatus.OK,
                    polarity=-0.4,
                    conviction=0.8,
                    citation=citation,
                    reasoning="Litigation language implies elevated regulatory risk.",
                )
            )
        else:
            factors.append(
                FactorSignal(
                    factor_id=fid,
                    status=FactorStatus.INSUFFICIENT_EVIDENCE,
                    reasoning=f"No evidence for {fid.value}.",
                )
            )
    return SignalEmission(
        factor_schema_version="0.1.0",
        model_or_pipeline_version="0.1.0",
        ticker="COIN",
        cik="0001679788",
        accession_number="0001679788-25-000010",
        form=FormType.TEN_K,
        filing_date=date(2025, 2, 20),
        factors=factors,
        disclaimer="Research / decision-support only — not investment advice.",
        emitted_at=datetime(2025, 2, 21, tzinfo=timezone.utc),
    )


def test_flatten_yields_five_rows_with_partitions() -> None:
    rows = flatten_emission(_emission())
    assert len(rows) == 5
    assert {r.ticker.value for r in rows} == {"COIN"}
    assert {r.filing_date.isoformat() for r in rows} == {"2025-02-20"}
    ok = next(r for r in rows if r.status is FactorStatus.OK)
    assert ok.polarity == -0.4
    assert ok.citation_quote == "litigation risk"
    insuff = [r for r in rows if r.status is FactorStatus.INSUFFICIENT_EVIDENCE]
    assert all(r.polarity is None for r in insuff)
