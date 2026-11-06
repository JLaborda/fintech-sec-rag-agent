"""Environment configuration for Phase-1 demo."""

from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_REGION = "eu-west-1"
DEFAULT_LLM_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
DEFAULT_EMBED_DIM = 1024


@dataclass(frozen=True)
class Settings:
    aws_region: str = DEFAULT_REGION
    raw_bucket: str = ""
    curated_prefix: str = "curated/signals"
    signals_debug_prefix: str = "signals"
    glue_database: str = "sec_signals"
    glue_table: str = "curated_signals"
    athena_workgroup: str = "primary"
    aoss_endpoint: str = ""
    aoss_collection: str = ""
    llm_model_id: str = DEFAULT_LLM_MODEL_ID
    embed_model_id: str = DEFAULT_EMBED_MODEL_ID
    embed_dimensions: int = DEFAULT_EMBED_DIM
    edgar_user_agent: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            aws_region=os.getenv("AWS_REGION", DEFAULT_REGION),
            raw_bucket=os.getenv("SEC_SIGNALS_RAW_BUCKET", ""),
            curated_prefix=os.getenv("SEC_SIGNALS_CURATED_PREFIX", "curated/signals"),
            signals_debug_prefix=os.getenv("SEC_SIGNALS_DEBUG_PREFIX", "signals"),
            glue_database=os.getenv("SEC_SIGNALS_GLUE_DATABASE", "sec_signals"),
            glue_table=os.getenv("SEC_SIGNALS_GLUE_TABLE", "curated_signals"),
            athena_workgroup=os.getenv("SEC_SIGNALS_ATHENA_WORKGROUP", "primary"),
            aoss_endpoint=os.getenv("SEC_SIGNALS_AOSS_ENDPOINT", ""),
            aoss_collection=os.getenv("SEC_SIGNALS_AOSS_COLLECTION", ""),
            llm_model_id=os.getenv("SEC_SIGNALS_LLM_MODEL_ID", DEFAULT_LLM_MODEL_ID),
            embed_model_id=os.getenv("SEC_SIGNALS_EMBED_MODEL_ID", DEFAULT_EMBED_MODEL_ID),
            embed_dimensions=int(os.getenv("SEC_SIGNALS_EMBED_DIM", str(DEFAULT_EMBED_DIM))),
            edgar_user_agent=os.getenv("SEC_EDGAR_USER_AGENT", ""),
        )


def get_settings() -> Settings:
    return Settings.from_env()
