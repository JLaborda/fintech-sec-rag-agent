"""OpenSearch Serverless SigV4 HTTP client (index / search / delete_by_query)."""

from __future__ import annotations

import json
from typing import Any, Protocol
from urllib.parse import urlparse

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


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
    ) -> Any: ...


class AossSignedClient:
    """Minimal AOSS REST client compatible with ChunkIndexer / OpenSearchClient."""

    def __init__(
        self,
        *,
        endpoint: str,
        region: str,
        credentials: CredentialsLike,
        http: HttpLike | None = None,
        index_name: str = "sec-10k-chunks",
        service: str = "aoss",
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.region = region
        self._credentials = credentials
        self._http = http or requests.Session()
        self.index_name = index_name
        self.service = service
        host = urlparse(self.endpoint).netloc
        if not host:
            raise ValueError(f"invalid AOSS endpoint: {endpoint}")
        self._host = host

    def _signed_request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.endpoint}{path}"
        raw = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {
            "Host": self._host,
            "Content-Type": "application/json",
        }
        aws_request = AWSRequest(method=method, url=url, data=raw, headers=headers)
        SigV4Auth(self._credentials, self.service, self.region).add_auth(aws_request)
        signed_headers = dict(aws_request.headers.items())
        response = self._http.request(method, url, headers=signed_headers, data=raw)
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        if hasattr(response, "json"):
            return response.json()
        return json.loads(response.text)

    def index(self, *, index: str, id: str, body: dict[str, Any]) -> Any:
        return self._signed_request("PUT", f"/{index}/_doc/{id}", body=body)

    def search(self, *, index: str, body: dict[str, Any]) -> Any:
        return self._signed_request("POST", f"/{index}/_search", body=body)

    def delete_by_query(self, *, index: str, body: dict[str, Any]) -> Any:
        return self._signed_request("POST", f"/{index}/_delete_by_query", body=body)


def build_aoss_client(
    *,
    endpoint: str,
    region: str,
    index_name: str = "sec-10k-chunks",
    credentials: CredentialsLike | None = None,
    http: HttpLike | None = None,
) -> AossSignedClient:
    if credentials is None:
        session = boto3.Session(region_name=region)
        creds = session.get_credentials()
        if creds is None:
            raise RuntimeError("AWS credentials required for AOSS client")
        credentials = creds.get_frozen_credentials()
    return AossSignedClient(
        endpoint=endpoint,
        region=region,
        credentials=credentials,
        http=http,
        index_name=index_name,
    )
