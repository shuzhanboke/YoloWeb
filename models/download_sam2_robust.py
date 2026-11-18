#!/usr/bin/env python
"""Download one SAM2.1 weight with Range-resume, driven by an external supervisor.

This script downloads exactly the files given on the command line, resuming any
existing `.part` file via HTTP Range, and exits. It is meant to be re-invoked by
a supervisor (see download_sam2_robust.ps1) that kills and restarts it whenever
the on-disk `.part` size stops growing, so a stalled GitHub CDN connection never
blocks completion.

Multipart functionality lives here; the supervisor handles liveness/timeouts.

Usage:
    python download_sam2_one.py <name> [<name> ...]
"""

from __future__ import annotations

import os
import sys
import time

import requests

CHUNK = 1 << 20


def sizes():
    # name -> expected bytes
    return {
        "sam2.1_t.pt": 78_105_722,
        "sam2.1_s.pt": 92_319_866,
        "sam2.1_b.pt": 161_935_802,
        "sam2.1_l.pt": 449_239_354,
    }


def download_one(name: str, target: str) -> bool:
    expected = sizes()[name]
    dest = os.path.join(target, name)
    part = dest + ".part"
    if os.path.exists(dest) and os.path.getsize(dest) >= expected:
        print(f"[done] {name} already present", flush=True)
        return True
    headers = {}
    resume = os.path.getsize(part) if os.path.exists(part) else 0
    if resume:
        headers["Range"] = f"bytes={resume}-"
    url = f"https://github.com/ultralytics/assets/releases/download/v8.4.0/{name}"
    proxies = None
    hp = os.environ.get("HTTPS_PROXY")
    if hp:
        proxies = {"http": hp, "https": hp}
    r = requests.get(url, headers=headers, stream=True, timeout=60, allow_redirects=True,
                     proxies=proxies)
    r.raise_for_status()
    mode = "ab" if resume and r.status_code == 206 else "wb"
    with open(part, mode) as fh:
        for chunk in r.iter_content(chunk_size=CHUNK):
            if not chunk:
                continue
            fh.write(chunk)
            cur = os.path.getsize(part) / 1e6
            sys.stdout.write(f"\r  {cur:9.2f} MB")
            sys.stdout.flush()
    if os.path.getsize(part) >= expected:
        os.replace(part, dest)
        print(f"\n[done] {name} complete ({os.path.getsize(dest)/1e6:.1f} MB)", flush=True)
        return True
    return False


def main() -> int:
    target = os.path.dirname(os.path.abspath(__file__))
    names = sys.argv[1:] or list(sizes())
    rc = 0
    for n in names:
        if n not in sizes():
            print(f"[skip] unknown {n}", flush=True)
            continue
        print(f"=== {n} ===", flush=True)
        try:
            if not download_one(n, target):
                print(f"[partial] {n} still downloading", flush=True)
                rc = 1
        except Exception as exc:  # noqa: BLE001
            print(f"[error] {n}: {type(exc).__name__}: {exc}", flush=True)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())