#!/usr/bin/env python
"""Download the four SAM2.1 weights used by YoloWebAgentStarter.

Uses Python ``requests`` (streamed) to bypass the broken curl/Schannel path that
failed with "Curl return value 35" when ultralytics tried to auto-download from
GitHub. Saves each file beside this script (the ``models/`` dir).

Downloads from ultralytics/ultralytics assets release v8.4.0:
    https://github.com/ultralytics/assets/releases/download/v8.4.0/<name>

After download each file is sanity-checked:
  1. size > minimum expected bytes,
  2. torch.load able to open it (structure check only).
Optionally the model is actually loaded with ultralytics when --load-test.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys

import requests

BASE_URL = "https://github.com/ultralytics/assets/releases/download/v8.4.0"
# name -> (approx bytes, human label)
FILES = {
    "sam2.1_t.pt": (365_000_000, "tiny (~350 MB)"),
    "sam2.1_s.pt": (440_000_000, "small (~420 MB)"),
    "sam2.1_b.pt": (470_000_000, "base (~450 MB)"),
    "sam2.1_l.pt": (890_000_000, "large (~850 MB)"),
}


def sha256(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def download(url: str, dest: str) -> None:
    """Stream download with progress to stdout, resumable via existing file skip."""
    if os.path.exists(dest):
        print(f"[skip] already present: {dest}")
        return
    tmp = dest + ".part"
    r = requests.get(url, stream=True, timeout=60, allow_redirects=True)
    r.raise_for_status()
    total = int(r.headers.get("Content-Length", 0))
    done = 0
    with open(tmp, "wb") as fh:
        for chunk in r.iter_content(chunk_size=1 << 20):
            if chunk:
                fh.write(chunk)
                done += len(chunk)
                mb = done / 1e6
                pct = (100.0 * done / total) if total else 0.0
                print(f"\r  {mb:7.1f}/{total/1e6:7.1f} MB  {pct:5.1f}%", end="", flush=True)
    print()
    os.replace(tmp, dest)
    print(f"[ok] {os.path.basename(dest)} ({(os.path.getsize(dest))/1e6:.1f} MB)")


def torch_load_check(path: str) -> bool:
    """Try to open with torch.load and report the top-level structure type."""
    try:
        import torch
    except Exception as exc:  # pragma: no cover
        print(f"  [warn] torch unavailable: {exc}")
        return True  # cannot verify in this env
    try:
        ckpt = torch.load(path, map_location="cpu", weights_only=True)
        if isinstance(ckpt, dict):
            keys = list(ckpt.keys())[:8]
            print(f"  [torch.load] ok, dict keys sample: {keys}")
            return True
        print(f"  [torch.load] ok, top-level type: {type(ckpt).__name__}")
        return True
    except Exception as exc:
        print(f"  [torch.load] FAILED: {exc}")
        return False


def ultralytics_load(path: str) -> bool:
    """Actually construct the SAM model to prove runtime loadability."""
    try:
        from ultralytics import SAM
    except Exception as exc:
        print(f"  [skip ultralytics load] {exc}")
        return True
    try:
        m = SAM(path)
        print(f"  [ultralytics] SAM loaded, is_sam2.1={m.is_sam2}")
        return True
    except Exception as exc:
        print(f"  [ultralytics] FAILED: {exc}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(FILES), action="append",
                    help="restrict to specific file(s); repeatable")
    ap.add_argument("--load-test", action="store_true",
                    help="additionally load each file with ultralytics SAM()")
    ap.add_argument("--target", default=None, help="target dir (default: this script's dir)")
    args = ap.parse_args()

    target = os.path.abspath(args.target or os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(target, exist_ok=True)
    names = args.only or list(FILES)
    rc = 0
    for name in names:
        print(f"\n=== {name} ({FILES[name][1]}) ===")
        dest = os.path.join(target, name)
        if not os.path.exists(dest):
            url = f"{BASE_URL}/{name}"
            print(f"  downloading {url}")
            download(url, dest)
        else:
            print(f"  present: {(os.path.getsize(dest))/1e6:.1f} MB")
        size = os.path.getsize(dest)
        if size < FILES[name][0]:
            print(f"  [!!] size {size/1e6:.1f} MB below expected {FILES[name][0]/1e6:.1f} MB")
            rc = 1
        else:
            print(f"  size ok: {size/1e6:.1f} MB")
        if not torch_load_check(dest):
            rc = 1
        if args.load_test and not ultralytics_load(dest):
            rc = 1
    print(f"\nDone. target={target}")
    return rc


if __name__ == "__main__":
    sys.exit(main())