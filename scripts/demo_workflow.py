"""Run the stage 20 API demonstration from upload through duplicate detection."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4


def multipart_body(file_path: Path) -> tuple[bytes, str]:
    """Build a small multipart body using only the Python standard library."""

    boundary = f"----document-ai-demo-{uuid4().hex}"
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{file_path.name}"\r\n'
            ).encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            file_path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def request_json(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    content_type: str | None = None,
) -> dict | list:
    headers = {"Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Cannot reach API at {url}: {error.reason}") from error


def upload(api_url: str, file_path: Path) -> dict:
    body, content_type = multipart_body(file_path)
    result = request_json(
        f"{api_url.rstrip('/')}/documents",
        method="POST",
        data=body,
        content_type=content_type,
    )
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected API response")
    return result


def print_result(title: str, result: dict) -> None:
    print(f"\n{title}")
    print(f"  id: {result.get('id')}")
    print(f"  type: {result.get('document_type')}")
    print(f"  status: {result.get('status')}")
    print(f"  duplicate: {result.get('duplicate', False)}")
    for reason in result.get("reasons") or []:
        print(f"  reason: {reason}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the final document workflow demo")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8016",
        help="FastAPI base URL (default: http://localhost:8016)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("demo/invoice_processed.txt"),
        help="Document to upload",
    )
    parser.add_argument(
        "--skip-duplicate-check",
        action="store_true",
        help="Upload only once",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    file_path = args.file.expanduser()
    if not file_path.is_file():
        print(f"Demo file not found: {file_path}", file=sys.stderr)
        return 1

    try:
        health = request_json(f"{args.api_url.rstrip('/')}/health")
        if health != {"status": "ok"}:
            raise RuntimeError(f"API is not healthy: {health}")
        print("✓ FastAPI is healthy")

        first = upload(args.api_url, file_path)
        print_result("First upload", first)

        if not args.skip_duplicate_check:
            duplicate = upload(args.api_url, file_path)
            print_result("Second upload (duplicate check)", duplicate)
            if not duplicate.get("duplicate"):
                raise RuntimeError("Duplicate protection did not activate")
            print("\n✓ Duplicate protection works")

        print(f"\n✓ Open dashboard: http://localhost:8501")
        return 0
    except RuntimeError as error:
        print(f"Demo failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

