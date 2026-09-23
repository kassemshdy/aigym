"""A minimal S3 client that signs its own requests, instead of boto3.

Railway Buckets are S3-compatible, and this project performs exactly three
operations on one — put an object, list objects, delete an object — for the
nightly database dump and its retention window. boto3 is tens of megabytes
of wheel and a heavy import, in an image the API itself also ships; SigV4 is
a published algorithm and ``httpx`` is already a dependency.

Virtual-hosted-style addressing (the bucket as a subdomain of the endpoint),
which is what Railway Buckets use.

Everything here holds the object in memory. That is fine for a database dump
of a few gyms and wrong for anything approaching a gigabyte — at that point
this needs multipart upload, which is the moment to reach for boto3 after
all rather than grow this file.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
from dataclasses import dataclass
from urllib.parse import quote, urlparse
from xml.etree import ElementTree

import httpx

ALGORITHM = "AWS4-HMAC-SHA256"
_S3_XMLNS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    last_modified: str


@dataclass(frozen=True)
class Bucket:
    """One bucket's S3 credentials. Every field comes from Railway's own
    bucket variables (BUCKET / ENDPOINT / REGION / ACCESS_KEY_ID /
    SECRET_ACCESS_KEY), mapped onto AIGYM_-prefixed settings."""

    name: str
    endpoint: str
    region: str
    access_key_id: str
    secret_access_key: str

    @property
    def host(self) -> str:
        return f"{self.name}.{urlparse(self.endpoint).netloc}"

    def canonical_request(
        self,
        method: str,
        key: str,
        *,
        headers: dict[str, str],
        query: str,
        payload_hash: str,
    ) -> str:
        """Split out from :meth:`_send` so a test can assert the exact string
        that gets hashed. A signer that is wrong is wrong in this string, and
        the server's only feedback is a 403 with no detail."""
        signed_headers = ";".join(sorted(headers))
        canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))
        return "\n".join(
            [
                method,
                # Path segments are escaped, the separators are not: keys here
                # are date-stamped paths like db/2026-09-23T02:00:00Z.sql.gz.
                "/" + quote(key, safe="/"),
                query,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )

    def _send(
        self,
        method: str,
        key: str = "",
        *,
        body: bytes = b"",
        query: dict[str, str] | None = None,
        content_type: str | None = None,
        now: dt.datetime | None = None,
    ) -> httpx.Response:
        now = now or dt.datetime.now(dt.UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        datestamp = now.strftime("%Y%m%d")
        payload_hash = _sha256(body)

        canonical_query = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted((query or {}).items())
        )
        headers = {
            "host": self.host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if content_type:
            headers["content-type"] = content_type

        request = self.canonical_request(
            method, key, headers=headers, query=canonical_query, payload_hash=payload_hash
        )
        scope = f"{datestamp}/{self.region}/s3/aws4_request"
        to_sign = "\n".join([ALGORITHM, amz_date, scope, _sha256(request.encode())])

        signing_key = _sign(f"AWS4{self.secret_access_key}".encode(), datestamp)
        for part in (self.region, "s3", "aws4_request"):
            signing_key = _sign(signing_key, part)
        signature = hmac.new(signing_key, to_sign.encode(), hashlib.sha256).hexdigest()

        signed_headers = ";".join(sorted(headers))
        headers["authorization"] = (
            f"{ALGORITHM} Credential={self.access_key_id}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        url = f"https://{self.host}/{quote(key, safe='/')}"
        if canonical_query:
            url = f"{url}?{canonical_query}"

        # Generous: a dump upload is one large body over a single request,
        # and the default 5s would fail on anything but a tiny database.
        response = httpx.request(method, url, content=body, headers=headers, timeout=600.0)
        if response.status_code >= 400:
            raise RuntimeError(f"{method} {key or '/'} → {response.status_code}: {response.text}")
        return response

    def put(self, key: str, body: bytes, *, content_type: str = "application/octet-stream") -> None:
        self._send("PUT", key, body=body, content_type=content_type)

    def delete(self, key: str) -> None:
        self._send("DELETE", key)

    def list(self, prefix: str = "") -> list[StoredObject]:
        """Follows continuation tokens, so a caller pruning old dumps sees
        every one of them rather than the first page."""
        found: list[StoredObject] = []
        token: str | None = None
        while True:
            query = {"list-type": "2", "prefix": prefix}
            if token:
                query["continuation-token"] = token
            root = ElementTree.fromstring(self._send("GET", query=query).text)
            for node in root.findall(f"{_S3_XMLNS}Contents"):
                found.append(
                    StoredObject(
                        key=node.findtext(f"{_S3_XMLNS}Key", ""),
                        size=int(node.findtext(f"{_S3_XMLNS}Size", "0")),
                        last_modified=node.findtext(f"{_S3_XMLNS}LastModified", ""),
                    )
                )
            if root.findtext(f"{_S3_XMLNS}IsTruncated", "false") != "true":
                return found
            token = root.findtext(f"{_S3_XMLNS}NextContinuationToken")
            if not token:
                return found
