"""Bedrock Converse client wrapper for Haiku 4.5."""

from __future__ import annotations

from typing import Any

import boto3

from sec_signals.config import DEFAULT_LLM_MODEL_ID, DEFAULT_REGION


class BedrockConverseClient:
    def __init__(
        self,
        *,
        region: str = DEFAULT_REGION,
        model_id: str = DEFAULT_LLM_MODEL_ID,
        client: Any | None = None,
    ) -> None:
        if model_id != DEFAULT_LLM_MODEL_ID and "claude-haiku-4-5" not in model_id:
            raise ValueError("Phase-1 generation model must be Claude Haiku 4.5 EU geo profile")
        self.region = region
        self.model_id = model_id
        self._client = client or boto3.client("bedrock-runtime", region_name=region)

    def converse_text(self, system: str, user: str, *, max_tokens: int = 4096) -> str:
        response = self._client.converse(
            modelId=self.model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
        )
        parts = response["output"]["message"]["content"]
        texts = [part.get("text", "") for part in parts if "text" in part]
        return "".join(texts).strip()
