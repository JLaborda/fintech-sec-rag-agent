"""Titan Text Embeddings V2 client."""

from __future__ import annotations

import json
from typing import Any

import boto3

from sec_signals.config import DEFAULT_EMBED_DIM, DEFAULT_EMBED_MODEL_ID, DEFAULT_REGION


class TitanEmbedClient:
    def __init__(
        self,
        *,
        region: str = DEFAULT_REGION,
        model_id: str = DEFAULT_EMBED_MODEL_ID,
        dimensions: int = DEFAULT_EMBED_DIM,
        client: Any | None = None,
    ) -> None:
        if model_id != DEFAULT_EMBED_MODEL_ID:
            raise ValueError("Phase-1 embeddings must use amazon.titan-embed-text-v2:0")
        if dimensions != DEFAULT_EMBED_DIM:
            raise ValueError("Phase-1 embeddings must be 1024-d")
        self.region = region
        self.model_id = model_id
        self.dimensions = dimensions
        self._client = client or boto3.client("bedrock-runtime", region_name=region)

    def embed(self, text: str) -> list[float]:
        body = {
            "inputText": text,
            "dimensions": self.dimensions,
            "normalize": True,
        }
        response = self._client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body).encode("utf-8"),
        )
        payload = json.loads(response["body"].read())
        embedding = payload["embedding"]
        if len(embedding) != self.dimensions:
            raise ValueError(f"expected {self.dimensions}-d embedding")
        return list(embedding)
