"""Build live AWS clients for CLI / Fargate / Lambda (injectable in tests)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import boto3

from sec_signals.config import Settings, get_settings
from sec_signals.extract.bedrock_converse import BedrockConverseClient
from sec_signals.extract.factor_extractor import FactorExtractor
from sec_signals.retrieve.aoss_signed import build_aoss_client
from sec_signals.retrieve.indexer import ChunkIndexer
from sec_signals.retrieve.opensearch_client import OpenSearchClient
from sec_signals.retrieve.retriever import FactorRetriever
from sec_signals.retrieve.titan_embed import TitanEmbedClient


@dataclass(frozen=True)
class RuntimeClients:
    settings: Settings
    bucket: str
    s3_client: Any
    bedrock_client: Any
    aoss_client: Any
    embedder: TitanEmbedClient
    indexer: ChunkIndexer
    search: OpenSearchClient
    retriever: FactorRetriever
    extractor: FactorExtractor


def require_settings_for_live(settings: Settings) -> None:
    """Raise when required live-path settings are missing."""
    if not settings.raw_bucket:
        raise ValueError("SEC_SIGNALS_RAW_BUCKET is required for live AWS paths")
    if not settings.aoss_endpoint:
        raise ValueError("SEC_SIGNALS_AOSS_ENDPOINT is required for live AWS paths")


def build_runtime(
    settings: Settings | None = None,
    *,
    raw_bucket: str | None = None,
) -> RuntimeClients:
    """Wire S3/Bedrock/AOSS clients; ensure knn index exists for VECTORSEARCH."""
    cfg = settings or get_settings()
    if raw_bucket:
        cfg = replace(cfg, raw_bucket=raw_bucket)
    require_settings_for_live(cfg)

    s3_client = boto3.client("s3", region_name=cfg.aws_region)
    bedrock_client = boto3.client("bedrock-runtime", region_name=cfg.aws_region)
    aoss_client = build_aoss_client(
        endpoint=cfg.aoss_endpoint,
        region=cfg.aws_region,
        index_name="sec-10k-chunks",
        ensure_knn_index=True,
        embed_dimensions=cfg.embed_dimensions,
    )
    embedder = TitanEmbedClient(
        region=cfg.aws_region,
        model_id=cfg.embed_model_id,
        dimensions=cfg.embed_dimensions,
        client=bedrock_client,
    )
    converse = BedrockConverseClient(
        region=cfg.aws_region,
        model_id=cfg.llm_model_id,
        client=bedrock_client,
    )
    indexer = ChunkIndexer(embedder=embedder, client=aoss_client)
    search = OpenSearchClient(aoss_client, index_name=aoss_client.index_name)
    retriever = FactorRetriever(embedder=embedder, search=search)
    extractor = FactorExtractor(client=converse)
    return RuntimeClients(
        settings=cfg,
        bucket=cfg.raw_bucket,
        s3_client=s3_client,
        bedrock_client=bedrock_client,
        aoss_client=aoss_client,
        embedder=embedder,
        indexer=indexer,
        search=search,
        retriever=retriever,
        extractor=extractor,
    )
