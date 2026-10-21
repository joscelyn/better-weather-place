#!/usr/bin/env python3
"""Verify byte-range delivery for one PMTiles archive and one COG."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "outputs/rapport-http-range.md"
JSON_PATH = ROOT / "outputs/test-http-range.json"
CASES = (
    ("PMTiles", "data/1991-2020/tavg/01.pmtiles", ROOT / "work/tiles/1991-2020/tavg/01.pmtiles"),
    ("COG", "data/1991-2020/raw/tavg/01.tif", ROOT / "work/derived/1991-2020-masked/tavg/01.tif"),
)


def request_range(url: str, start: int, end: int) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, {key.lower(): value for key, value in response.headers.items()}, response.read()
    except urllib.error.HTTPError as error:
        return error.code, {key.lower(): value for key, value in error.headers.items()}, error.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5173/")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/") + "/"
    results = []
    for kind, relative, local_path in CASES:
        file_size = local_path.stat().st_size
        for label, start, end in (("début", 0, 63), ("milieu", file_size // 2, file_size // 2 + 63)):
            status, headers, body = request_range(base_url + relative, start, end)
            with local_path.open("rb") as stream:
                stream.seek(start)
                expected = stream.read(end - start + 1)
            content_range = headers.get("content-range", "")
            valid = status == 206 and body == expected and content_range.startswith(f"bytes {start}-{end}/")
            results.append({
                "format": kind,
                "portion": label,
                "url": base_url + relative,
                "requested_range": f"bytes={start}-{end}",
                "status": status,
                "content_range": content_range,
                "accept_ranges": headers.get("accept-ranges", ""),
                "bytes_received": len(body),
                "matches_local_file": body == expected,
                "valid": valid,
            })
    JSON_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    rows = [
        f"| {row['format']} | {row['portion']} | {row['status']} | `{row['content_range']}` | "
        f"{row['bytes_received']} | {'OK' if row['valid'] else 'ÉCHEC'} |"
        for row in results
    ]
    REPORT_PATH.write_text(
        "# Test des requêtes HTTP Range\n\n"
        f"Serveur testé : `{base_url}`\n\n"
        "Chaque réponse est comparée octet par octet au fichier local correspondant.\n\n"
        "| Format | Portion | HTTP | Content-Range | Octets | Résultat |\n"
        "|---|---|---:|---|---:|---|\n"
        + "\n".join(rows)
        + "\n"
    )
    passed = sum(result["valid"] for result in results)
    print(f"{passed}/{len(results)} requêtes Range conformes; rapport: {REPORT_PATH}")
    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
