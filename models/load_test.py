#!/usr/bin/env python
"""Quick load-verification for the four SAM2.1 weights using ultralytics SAM()."""
import glob
import os
import sys
import time

from ultralytics import SAM, YOLO

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    files = sorted(glob.glob(os.path.join(base, "*.pt")))
    ok = True
    for p in files:
        t = time.time()
        try:
            m = SAM(p)
            is_sam2 = getattr(m, "is_sam2", None)
            print(f"{os.path.basename(p):14} LOAD_OK  sam2={is_sam2}  load={time.time()-t:.1f}s")
            del m
        except Exception as e:
            print(f"{os.path.basename(p):14} LOAD_FAIL {type(e).__name__}: {str(e)[:140]}")
            ok = False
    sys.exit(0 if ok else 1)