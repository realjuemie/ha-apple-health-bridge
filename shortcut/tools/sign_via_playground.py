#!/usr/bin/env python3
"""Sign an unsigned Shortcut through the anonymous Cherri Playground session."""

from __future__ import annotations

import argparse
from http.cookiejar import CookieJar
import json
from pathlib import Path
from urllib.parse import quote, unquote, urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener


PLAYGROUND = "https://playground.cherrilang.org/"
USER_AGENT = "AppleHealthBridge-Builder/1.0"


def sign(source: Path, destination: Path) -> int:
    shortcut_xml = source.read_text(encoding="utf-8")
    cookies = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookies))
    common_headers = {
        "Accept": "application/json",
        "Referer": PLAYGROUND,
        "User-Agent": USER_AGENT,
    }

    opener.open(Request(PLAYGROUND, headers=common_headers), timeout=30).read()
    try:
        xsrf_token = next(
            unquote(cookie.value) for cookie in cookies if cookie.name == "XSRF-TOKEN"
        )
    except StopIteration as error:
        raise RuntimeError("Playground did not issue an XSRF token") from error

    payload = json.dumps(
        {"name": destination.stem, "data": shortcut_xml}, ensure_ascii=False
    ).encode("utf-8")
    request = Request(
        urljoin(PLAYGROUND, "sign"),
        data=payload,
        headers={
            **common_headers,
            "Content-Type": "application/json",
            "X-XSRF-TOKEN": xsrf_token,
        },
        method="POST",
    )
    response_path = opener.open(request, timeout=120).read().decode("utf-8").strip()
    if response_path.startswith('"'):
        response_path = json.loads(response_path)

    signed_data = opener.open(
        Request(
            urljoin(PLAYGROUND, quote(response_path, safe="/")),
            headers={"User-Agent": USER_AGENT},
        ),
        timeout=120,
    ).read()
    if not signed_data.startswith(b"AEA1"):
        raise RuntimeError("Signing service returned an invalid Shortcut package")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(signed_data)
    return len(signed_data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    size = sign(args.source, args.destination)
    print(f"Wrote signed Shortcut ({size} bytes) to {args.destination}")


if __name__ == "__main__":
    main()
