#!/usr/bin/env python
"""Multithreaded segmented (resumable) downloader for one large file.

Why: a single long HTTP connection from this network keeps getting cut (the
proxy/CDN drops it after ~1-1.6 MB). Splitting the remaining byte range into
segments, each fetched by its own worker thread over its own connection, works
around that: a dropped connection only costs one small segment, which the worker
retries in place, and many connections run in parallel.

A partial contiguous prefix (e.g. sam2.1_l.pt.part = bytes [0, P)) is preserved
and used as the base; only bytes [P, size) are segmented.

Downloaded via proxies if HTTP(S)_PROXY env present.

Usage:
    python download_seg.py <name> [--size <bytes>] [--segments N] [--prefix <file>]
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time

import requests

BASE = "https://github.com/ultralytics/assets/releases/download/v8.4.0/{name}"
TRUSTED_SIZES = {
    "sam2.1_t.pt": 78_105_722,
    "sam2.1_s.pt": 92_319_866,
    "sam2.1_b.pt": 161_935_802,
    "sam2.1_l.pt": 449_239_354,
}
CHUNK = 1 << 20


def proxies():
    hp = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if hp:
        return {"http": hp, "https": hp}
    return None


def get_size(name: str) -> int:
    if name in TRUSTED_SIZES:
        return TRUSTED_SIZES[name]
    r = requests.head(BASE.format(name=name), allow_redirects=True, timeout=30,
                      proxies=proxies())
    r.raise_for_status()
    return int(r.headers["Content-Length"])


def download_range(name, a, b, part_path, stall, max_retry):
    """Download bytes [a,b) into part_path (absolute). Worker-loop with resume."""
    url = BASE.format(name=name)
    px = proxies()
    for attempt in range(max_retry):
        cur = os.path.getsize(part_path) if os.path.exists(part_path) else 0
        lo = a + cur
        if lo >= b:
            return True
        try:
            with requests.get(url, headers={"Range": f"bytes={lo}-{b-1}"},
                              stream=True, timeout=(15, 90), allow_redirects=True,
                              proxies=px) as r:
                if r.status_code not in (200, 206):
                    time.sleep(2)
                    continue
                with open(part_path, "ab" if cur else "wb") as fh:
                    for chunk in r.iter_content(chunk_size=CHUNK):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        got = os.path.getsize(part_path)
                        seg = part_path.split(".pt")[0].split(".")[-1]
                        sys.stdout.write(f"\r  [{seg}] {got/1e6:7.2f}MB")
                        sys.stdout.flush()
                if os.path.getsize(part_path) >= (b - a):
                    return True
        except Exception as exc:  # noqa: BLE001
            # connection dropped mid-segment; retry resumes this segment in place
            sys.stdout.write(f"\n  seg(offset {a}) resume after {type(exc).__name__}\n")
            sys.stdout.flush()
            time.sleep(1.5)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--segments", type=int, default=16)
    ap.add_argument("--prefix", default=None)
    ap.add_argument("--base", default=None)
    ap.add_argument("--max-retry", type=int, default=200)
    args = ap.parse_args()

    name = args.name
    total = args.size or get_size(name)
    base = os.path.abspath(args.base or os.path.dirname(os.path.abspath(__file__)))
    dest = os.path.join(base, name)

    if os.path.exists(dest) and os.path.getsize(dest) >= total:
        print(f"[done] {name} already complete", flush=True)
        return 0

    # contig prefix already downloaded (.part), reused as segment 0 base
    prefix = args.prefix or (dest + ".part")
    p_size = os.path.getsize(prefix) if os.path.exists(prefix) else 0
    if p_size > total:
        p_size = 0
    print(f"[info] total={total} ({total/1e6:.1f}MB) prefix={p_size} ({p_size/1e6:.1f}MB)", flush=True)

    segments = args.segments
    span = total - p_size
    step = max(1, (span + segments - 1) // segments)
    seg_paths = []
    ranges = []
    for i in range(segments):
        a = p_size + i * step
        b = min(a + step, total)
        if a >= total:
            break
        sp = os.path.join(base, f".{name}.{i:02d}.part")
        seg_paths.append(sp)
        ranges.append((a, b))

    finished = [False] * len(ranges)

    def runner(i):
        a, b = ranges[i]
        finished[i] = download_range(name, a, b, seg_paths[i], 0, args.max_retry)

    from collections import deque
    active = deque()
    idx = 0
    n = len(ranges)
    while idx < n or active:
        while len(active) < 12 and idx < n:
            t = threading.Thread(target=runner, args=(idx,), daemon=True)
            t.start()
            active.append(t)
            idx += 1
        # reap finished threads (FIFO check)
        if active:
            t = active[0]
            t.join(timeout=0.5)
            if not t.is_alive():
                active.popleft()
        time.sleep(0.05)

    if not all(finished):
        print(f"[!!] not all segments finished ({sum(finished)}/{len(finished)})",
              flush=True)
        return 1

    # assemble: prefix + seg0..segN
    print(f"[assemble] writing {dest}", flush=True)
    tmp = dest + ".asm"
    with open(tmp, "wb") as out:
        if p_size:
            with open(prefix, "rb") as pf:
                chunk = pf.read(1 << 20)
                while chunk:
                    out.write(chunk)
                    chunk = pf.read(1 << 20)
        for sp in seg_paths:
            with open(sp, "rb") as sf:
                chunk = sf.read(1 << 20)
                while chunk:
                    out.write(chunk)
                    chunk = sf.read(1 << 20)
    got = os.path.getsize(tmp)
    print(f"[assemble] {got} bytes (expect {total})", flush=True)
    if got >= total:
        os.replace(tmp, dest)
        print(f"[done] {name} complete", flush=True)
        # clean seg files
        for sp in seg_paths:
            try:
                os.remove(sp)
            except OSError:
                pass
        return 0
    print(f"[!!] size mismatch, kept {tmp}", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())