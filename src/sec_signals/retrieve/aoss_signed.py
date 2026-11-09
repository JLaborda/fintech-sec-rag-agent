"""OpenSearch Serverless SigV4 HTTP client (VECTORSEARCH-compatible)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

DEFAULT_TIMEOUT: tuple[float, float] = (3.05, 60.0)
DEFAULT_INDEX_NAME = "sec-10k-chunks"
DEFAULT_EMBED_DIM = 1024


class CredentialsLike(Protocol):
    access_key: str
    secret_key: str
    token: str | None


class HttpLike(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        data: bytes | None = None,
        timeout: float | tuple[float, float] | None = None,
    ) -> Any: ...


def _freeze_credentials(credentials: Any) -> CredentialsLike:
    getter = getattr(credentials, "get_frozen_credentials", None)
    if callable(getter):
        return getter()
    return credentials


class AossSignedClient:
    """Minimal AOSS REST client compatible with ChunkIndexer / OpenSearchClient.

    VECTORSEARCH collections reject custom document IDs and `_delete_by_query`.
    Indexing uses POST `/_doc`; deletes search then DELETE `/_doc/{id}`.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        region: str,
        credentials: CredentialsLike,
        http: HttpLike | None = None,
        index_name: str = DEFAULT_INDEX_NAME,
        service: str = "aoss",
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
        credential_provider: Callable[[], Any] | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.region = region
        self._credentials = credentials
        self._credential_provider = credential_provider
        self._http = http or requests.Session()
        self.index_name = index_name
        self.service = service
        self.timeout = timeout
        host = urlparse(self.endpoint).netloc
        if not host:
            raise ValueError(f"invalid AOSS endpoint: {endpoint}")
        self._host = host

    def _resolve_credentials(self) -> CredentialsLike:
        if self._credential_provider is not None:
            return _freeze_credentials(self._credential_provider())
        return _freeze_credentials(self._credentials)

    def _signed_request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> dict[str, Any]:
        url = f"{self.endpoint}{path}"
        raw = json.dumps(body).encode("utf-8") if body is not None else None
        payload_hash = hashlib.sha256(raw if raw is not None else b"").hexdigest()
        headers = {
            "Host": self._host,
            "Content-Type": "application/json",
            "X-Amz-Content-SHA256": payload_hash,
        }
        aws_request = AWSRequest(method=method, url=url, data=raw, headers=headers)
        SigV4Auth(self._resolve_credentials(), self.service, self.region).add_auth(aws_request)
        signed_headers = dict(aws_request.headers.items())
        response = self._http.request(
            method,
            url,
            headers=signed_headers,
            data=raw,
            timeout=self.timeout,
        )
        status = getattr(response, "status_code", 200)
        if allow_404 and status == 404:
            return {"status_code": 404}
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        if status == 404 and method == "HEAD":
            return {"status_code": 404}
        if hasattr(response, "json") and method != "HEAD":
            try:
                return response.json()
            except Exception:  # noqa: BLE001 — empty body on some AOSS ops
                return {"status_code": status}
        if method == "HEAD":
            return {"status_code": status}
        text = getattr(response, "text", "") or ""
        if not text:
            return {"status_code": status}
        return json.loads(text)

    def ensure_index(self, *, dimension: int = DEFAULT_EMBED_DIM) -> None:
        """Create sec-10k-chunks with knn_vector mapping when missing."""
        head = self._signed_request("HEAD", f"/{self.index_name}", allow_404=True)
        if head.get("status_code") != 404:
            return
        body = {
            "settings": {"index.knn": True},
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "ticker": {"type": "keyword"},
                    "cik": {"type": "keyword"},
                    "accession_number": {"type": "keyword"},
                    "form": {"type": "keyword"},
                    "filing_date": {"type": "keyword"},
                    "section": {"type": "keyword"},
                    "item": {"type": "keyword"},
                    "text": {"type": "text"},
                    "char_start": {"type": "integer"},
                    "char_end": {"type": "integer"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": dimension,
                        "method": {
                            "name": "hnsw",
                            "engine": "nmslib",
                            "space_type": "cosinesimil",
                        },
                    },
                }
            },
        }
        self._signed_request("PUT", f"/{self.index_name}", body=body)

    def index(self, *, index: str, id: str, body: dict[str, Any]) -> Any:
        """Index a document. ``id`` is ignored: VECTORSEARCH forbids custom IDs."""
        _ = id
        return self._signed_request("POST", f"/{index}/_doc", body=body)

    def search(self, *, index: str, body: dict[str, Any]) -> Any:
        return self._signed_request("POST", f"/{index}/_search", body=body)

    def delete(self, *, index: str, id: str) -> Any:
        return self._signed_request("DELETE", f"/{index}/_doc/{id}")

    def delete_by_query(self, *, index: str, body: dict[str, Any]) -> Any:
        """AOSS-compatible rebuild helper: search matching docs, then DELETE by ``_id``.

        VECTORSEARCH does not support ``_delete_by_query``.
        """
        query = body.get("query") if isinstance(body, dict) else None
        search_body: dict[str, Any] = {
            "size": 1000,
            "query": query or {"match_all": {}},
            "_source": False,
        }
        deleted = 0
        while True:
            result = self.search(index=index, body=search_body)
            hits = result.get("hits", {}).get("hits", [])
            if not hits:
                break
            for hit in hits:
                doc_id = hit.get("_id")
                if not doc_id:
                    continue
                self.delete(index=index, id=doc_id)
                deleted += 1
            if len(hits) < search_body["size"]:
                break
        return {"deleted": deleted}


def build_aoss_client(
    *,
    endpoint: str,
    region: str,
    index_name: str = DEFAULT_INDEX_NAME,
    credentials: CredentialsLike | None = None,
    http: HttpLike | None = None,
    timeout: tuple[float, float] = DEFAULT_TIMEOUT,
    ensure_knn_index: bool = False,
    embed_dimensions: int = DEFAULT_EMBED_DIM,
) -> AossSignedClient:
    credential_provider: Callable[[], Any] | None = None
    if credentials is None:
        session = boto3.Session(region_name=region)
        creds = session.get_credentials()
        if creds is None:
            raise RuntimeError("AWS credentials required for AOSS client")
        credentials = creds
        credential_provider = session.get_credentials
    client = AossSignedClient(
        endpoint=endpoint,
        region=region,
        credentials=credentials,
        http=http,
        index_name=index_name,
        timeout=timeout,
        credential_provider=credential_provider,
    )
    if ensure_knn_index:
        client.ensure_index(dimension=embed_dimensions)
    return client
