"""Quick end-to-end smoke test for dataset_cache pregeneration."""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from app.training.runtime.dataset_cache import DATASET_CACHE_VERSION, pregenerate_dataset_caches


def main() -> None:
    base = Path(__file__).resolve().parents[2] / ".test_tmp_cache"
    base.mkdir(exist_ok=True)
    root = base / "dataset"
    for split in ("train", "val"):
        (root / "images" / split).mkdir(parents=True, exist_ok=True)
        (root / "labels" / split).mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (64, 48), "#336699")
        img.save(root / "images" / split / "img.png")
        (root / "labels" / split / "img.txt").write_text("0 0.5 0.5 0.5 0.5\n", encoding="utf-8")

    data_yaml = root / "data.yaml"
    data_yaml.write_text(
        f"path: {root}\ntrain: images/train\nval: images/val\nnames: [object]\n",
        encoding="utf-8",
    )

    produced = pregenerate_dataset_caches(data_yaml)
    print("Produced:", produced)
    assert produced["train"] == 1 and produced["val"] == 1, f"Expected 1 label each, got {produced}"

    cache = np.load(str(root / "labels" / "train.cache"), allow_pickle=True).item()
    assert cache["version"] == DATASET_CACHE_VERSION, f"Version mismatch: {cache['version']}"
    assert len(cache["labels"]) == 1
    assert cache["results"][0] == 1  # nf
    print("Cache version:", cache["version"])
    print("Labels count:", len(cache["labels"]))
    print("Results (nf,nm,ne,nc,total):", cache["results"])

    import ultralytics.data.utils as u

    im_files = sorted(str(p) for p in (root / "images" / "train").iterdir() if p.suffix == ".png")
    lb_files = u.img2label_paths(im_files)
    expected_hash = u.get_hash(lb_files + im_files)
    assert cache["hash"] == expected_hash, "Hash mismatch — YOLO would rescan!"
    print("Hash match: True")

    import shutil
    shutil.rmtree(base, ignore_errors=True)
    print("ALL OK")


if __name__ == "__main__":
    main()
