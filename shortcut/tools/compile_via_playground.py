#!/usr/bin/env python3
"""Compile Cherri source through an anonymous Cherri Playground session."""

from __future__ import annotations

import argparse
from http.cookiejar import CookieJar
import json
from pathlib import Path
import plistlib
from urllib.parse import quote, unquote
from urllib.request import HTTPCookieProcessor, Request, build_opener


PLAYGROUND = "https://playground.cherrilang.org/"
USER_AGENT = "AppleHealthBridge-Builder/1.0"


def compile_shortcut(source: Path, destination: Path) -> int:
    source_text = source.read_text(encoding="utf-8").replace("\r\n", "\n")
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

    active_file = {
        "id": "file-1",
        "name": source.name,
        "content": source_text,
        "compiled": False,
        "error": None,
        "output": None,
        "decompOutput": None,
        "shareLink": None,
    }
    payload = json.dumps(
        {"active_file": active_file, "files": []}, ensure_ascii=False
    ).encode("utf-8")
    request = Request(
        f"{PLAYGROUND}compile",
        data=payload,
        headers={
            **common_headers,
            "Content-Type": "application/json",
            "X-XSRF-TOKEN": xsrf_token,
        },
        method="POST",
    )
    response = json.loads(opener.open(request, timeout=120).read())
    if response.get("error") or not response.get("file"):
        raise RuntimeError(response.get("output") or "Shortcut compilation failed")

    download_url = quote(response["file"], safe=":/")
    shortcut_data = opener.open(
        Request(download_url, headers={"User-Agent": USER_AGENT}), timeout=120
    ).read()
    shortcut = plistlib.loads(shortcut_data)
    if not shortcut.get("WFWorkflowActions"):
        raise RuntimeError("Compiler returned an invalid Shortcut plist")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(shortcut_data)
    return len(shortcut_data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    size = compile_shortcut(args.source, args.destination)
    print(f"Wrote unsigned Shortcut ({size} bytes) to {args.destination}")


if __name__ == "__main__":
    main()
