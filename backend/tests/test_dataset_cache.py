from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image

from app.training.runtime.dataset_cache import DATASET_CACHE_VERSION, pregenerate_dataset_caches
from app.training.runtime.runner import _diagnose_failure, _RESTRICTED_TOKEN_HINT


def _make_image_bytes() -> bytes:
    image = Image.new("RGB", (64, 48), "#336699")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _build_dataset(root: Path) -> Path:
    """Write a minimal YOLO-compatible dataset (detect) with one train + one val image."""
    (root / "images" / "train").mkdir(parents=True)
    (root / "images" / "val").mkdir(parents=True)
    (root / "labels" / "train").mkdir(parents=True)
    (root / "labels" / "val").mkdir(parents=True)

    (root / "images" / "train" / "img.png").write_bytes(_make_image_bytes())
    (root / "images" / "val" / "img.png").write_bytes(_make_image_bytes())
    # one normalized bbox: class 0, x_center y_center w h
    (root / "labels" / "train" / "img.txt").write_text("0 0.5 0.5 0.5 0.5\n", encoding="utf-8")
    (root / "labels" / "val" / "img.txt").write_text("0 0.4 0.6 0.2 0.3\n", encoding="utf-8")

    data_yaml = root / "data.yaml"
    data_yaml.write_text(
        "path: REPLACED\ntrain: images/train\nval: images/val\nnames: [object]\n",
        encoding="utf-8",
    )
    # substitute the absolute root
    content = data_yaml.read_text(encoding="utf-8").replace("REPLACED", str(root))
    data_yaml.write_text(content, encoding="utf-8")
    return data_yaml


def test_pregenerate_dataset_caches_writes_compatible_cache(tmp_path: Path) -> None:
    root = _build_dataset(tmp_path)
    data_yaml = root / "data.yaml"

    produced = pregenerate_dataset_caches(data_yaml)

    assert set(produced) == {"train", "val", "test"}
    assert produced["train"] == 1
    assert produced["val"] == 1

    cache_path = root / "labels" / "train.cache"
    assert cache_path.is_file()
    loaded = np.load(str(cache_path), allow_pickle=True).item()
    assert loaded["version"] == DATASET_CACHE_VERSION
    assert len(loaded["labels"]) == 1
    assert loaded["results"][0] == 1  # nf
    # Labels carry the fields YOLO reads on load
    label = loaded["labels"][0]
    assert label["im_file"].endswith("img.png")
    assert label["bbox_format"] == "xywh"
    assert np.asarray(label["cls"]).reshape(-1).tolist() == [0.0]
    assert np.asarray(label["bboxes"]).reshape(-1).tolist() == [0.5, 0.5, 0.5, 0.5]


def test_pregenerate_cache_hash_stays_valid_when_images_unchanged(tmp_path: Path) -> None:
    """A pre-generated cache must satisfy the hash check when YOLO later scans it."""
    root = _build_dataset(tmp_path)
    data_yaml = root / "data.yaml"
    pregenerate_dataset_caches(data_yaml)

    import ultralytics.data.utils as u

    cache = np.load(str(root / "labels" / "val.cache"), allow_pickle=True).item()
    im_files = [str(p) for p in (root / "images" / "val").iterdir()]
    label_files = u.img2label_paths(im_files)
    assert cache["hash"] == u.get_hash(label_files + im_files)


def test_diagnose_failure_detects_winerror5() -> None:
    assert _diagnose_failure(None, "Traceback ... [WinError 5] 拒绝访问。") == _RESTRICTED_TOKEN_HINT
    assert _diagnose_failure("[WinError 5] access denied", "") == _RESTRICTED_TOKEN_HINT
    assert _diagnose_failure(None, "Epoch 1/50 ... loss 0.5") is None