"""Tests for the hand-rolled S3 signer.

A signer that is wrong is wrong inside one exact string, and the only
feedback the server gives is `403 SignatureDoesNotMatch` with no detail
about which byte differed. So the canonical request — the part that is
fully specified and easy to get subtly wrong — is asserted character for
character rather than through its signature.

The signature itself is not asserted against a hardcoded hex digest: any
expected value would have to be produced by this same code, which proves
nothing. It is verified for real against the live Railway Bucket the first
time scripts/backup_db.py runs, and the retention prune is what proves
`list` too.
"""

import datetime as dt

from app.integrations.object_storage import ALGORITHM, Bucket

BUCKET = Bucket(
    name="aigym-backups-abc123",
    endpoint="https://t3.storageapi.dev",
    region="auto",
    access_key_id="AKIAEXAMPLE",
    secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
)
WHEN = dt.datetime(2026, 9, 23, 2, 0, 0, tzinfo=dt.UTC)
EMPTY_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_bucket_is_a_subdomain_of_the_endpoint() -> None:
    """Virtual-hosted style, which is what Railway Buckets use. Path style
    would put the bucket in the URI instead, and sign a different string."""
    assert BUCKET.host == "aigym-backups-abc123.t3.storageapi.dev"


def test_canonical_request_for_an_object_put() -> None:
    headers = {
        "host": BUCKET.host,
        "x-amz-content-sha256": EMPTY_SHA,
        "x-amz-date": "20260923T020000Z",
        "content-type": "application/octet-stream",
    }
    request = BUCKET.canonical_request(
        "PUT",
        "db/2026-09-23T02-00-00Z.dump",
        headers=headers,
        query="",
        payload_hash=EMPTY_SHA,
    )
    # Headers sorted by name, each lowercased and newline-terminated, then a
    # blank line, then the signed-header list. The trailing blank line after
    # the headers block is part of the format, not a typo.
    assert request == (
        "PUT\n"
        "/db/2026-09-23T02-00-00Z.dump\n"
        "\n"
        "content-type:application/octet-stream\n"
        f"host:{BUCKET.host}\n"
        f"x-amz-content-sha256:{EMPTY_SHA}\n"
        "x-amz-date:20260923T020000Z\n"
        "\n"
        "content-type;host;x-amz-content-sha256;x-amz-date\n"
        f"{EMPTY_SHA}"
    )


def test_key_separators_survive_escaping() -> None:
    """The slash between prefix and filename must stay a slash: escaping it
    to %2F signs a path the server never sees, and every upload 403s."""
    request = BUCKET.canonical_request(
        "PUT", "db/a b.dump", headers={"host": BUCKET.host}, query="", payload_hash=EMPTY_SHA
    )
    assert request.splitlines()[1] == "/db/a%20b.dump"


def test_authorization_header_carries_the_scope_and_signed_headers(monkeypatch) -> None:
    """The one assertion about a real signed request. httpx is stubbed, so
    this checks what we send, not what a server makes of it."""
    sent: dict[str, object] = {}

    def fake_request(method, url, *, content, headers, timeout):
        sent.update(method=method, url=url, headers=headers)

        class Response:
            status_code = 200
            text = ""

        return Response()

    monkeypatch.setattr("app.integrations.object_storage.httpx.request", fake_request)
    BUCKET._send("PUT", "db/x.dump", body=b"", content_type="application/octet-stream", now=WHEN)

    auth = sent["headers"]["authorization"]  # type: ignore[index]
    assert auth.startswith(f"{ALGORITHM} Credential=AKIAEXAMPLE/20260923/auto/s3/aws4_request, ")
    assert "SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date, " in auth
    assert sent["url"] == f"https://{BUCKET.host}/db/x.dump"


def test_list_query_is_sorted_and_escaped(monkeypatch) -> None:
    """Query parameters must be signed in sorted order, and the URL must
    carry exactly the string that was signed — building the two separately
    is the other classic way to earn a 403."""
    sent: dict[str, object] = {}

    def fake_request(method, url, *, content, headers, timeout):
        sent.update(url=url)

        class Response:
            status_code = 200
            text = '<?xml version="1.0"?><ListBucketResult/>'

        return Response()

    monkeypatch.setattr("app.integrations.object_storage.httpx.request", fake_request)
    assert BUCKET.list("db/") == []
    assert sent["url"] == f"https://{BUCKET.host}/?list-type=2&prefix=db%2F"


def test_list_follows_continuation_tokens(monkeypatch) -> None:
    """Retention deletes everything past the newest N. A `list` that stopped
    at the first page would leave older dumps stored forever while reporting
    that it had pruned."""
    pages = [
        (
            '<?xml version="1.0"?>'
            '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            "<IsTruncated>true</IsTruncated>"
            "<NextContinuationToken>page2</NextContinuationToken>"
            "<Contents><Key>db/one.dump</Key><Size>10</Size>"
            "<LastModified>2026-09-22T02:00:00Z</LastModified></Contents>"
            "</ListBucketResult>"
        ),
        (
            '<?xml version="1.0"?>'
            '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            "<IsTruncated>false</IsTruncated>"
            "<Contents><Key>db/two.dump</Key><Size>20</Size>"
            "<LastModified>2026-09-23T02:00:00Z</LastModified></Contents>"
            "</ListBucketResult>"
        ),
    ]
    seen: list[str] = []

    def fake_request(method, url, *, content, headers, timeout):
        seen.append(url)

        class Response:
            status_code = 200
            text = pages[len(seen) - 1]

        return Response()

    monkeypatch.setattr("app.integrations.object_storage.httpx.request", fake_request)
    found = BUCKET.list("db/")

    assert [o.key for o in found] == ["db/one.dump", "db/two.dump"]
    assert [o.size for o in found] == [10, 20]
    assert "continuation-token=page2" in seen[1]
