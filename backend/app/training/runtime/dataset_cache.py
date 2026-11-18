from __future__ import annotations

"""Serial (pipe-free) Ultralytics ``*.cache`` pre-generation for local training.

On restricted Windows tokens (antivirus EDR / non-elevated scheduler) the ``yolo.exe``
subprocess cannot create the anonymous pipe that Python 3.11's
``multiprocessing.pool.ThreadPool`` builds unconditionally, so Ultralytics' first-time
label scan (``data/dataset.py::cache_labels``) dies with
``PermissionError: [WinError 5]`` before any training epoch starts.  The subprocess only
skips that scan when a valid ``*.cache`` file already exists.

This module pre-generates the train/val ``*.cache`` files in the *backend* process
(usually outside the restricted token) using a plain serial loop that never touches
``multiprocessing`` or pipes.  It reuses Ultralytics' own ``verify_image_label`` and
``save_dataset_cache_file`` so the file is byte-identical to what Ultralytics would have
written — the YOLO subprocess loads it and the crashed path is never entered.

Default training (``cache=False``) hits ``ThreadPool`` only in the label scan, so a
pre-generated cache fully avoids it.  I/O during actual dataloading is inside the Torch
workers and is unaffected.
"""

import logging
from pathlib import Path
from typing import Any

from app.core.errors import ValidationError

logger = logging.getLogger("ywa.training.cache")

# Keep in sync with Ultralytics' DATASET_CACHE_VERSION when upgrading the dependency.
DATASET_CACHE_VERSION = "1.0.4"


def _image_files(image_dir: Path) -> list[str]:
    """Return image paths in an ``images/<split>`` dir, sorted like Ultralytics glob."""
    from ultralytics.data.utils import IMG_FORMATS

    formats = {".jpeg", ".jpg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".dng", ".mpo"}
    formats |= {("." + s).lower() for s in IMG_FORMATS}
    return sorted(
        str(p) for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in formats
    )


def _load_data_yaml(data_yaml: Path) -> tuple[Path, dict[str, Any]]:
    """Load a YOLO data.yaml and return (resolved root, raw config)."""
    import yaml

    with open(data_yaml, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle) or {}
    root = Path(cfg.get("path") or data_yaml.parent.resolve()).resolve()
    return root, cfg


def _scan_split(
    root: Path, split: str, num_cls: int, single_cls: bool, keypoint: bool, prefix: str
) -> int:
    """Serially scan one images/<split> dir and write its labels/<split>.cache file.

    Faithful serial equivalent of ``YOLODataset.cache_labels`` for the default hooks:
    ``verify_image_label`` + ``result_to_label``.  Returns the number of found labels.
    """
    from itertools import repeat

    import ultralytics.data.utils as u
    from ultralytics.data.utils import verify_image_label

    image_dir = root / "images" / split
    if not image_dir.is_dir():
        return 0
    im_files = _image_files(image_dir)
    label_files = u.img2label_paths(im_files)

    nkpt, ndim = 0, 0
    nm = nf = ne = nc = 0
    labels: list[dict[str, Any]] = []
    msgs: list[str] = []
    for args in zip(
        im_files,
        label_files,
        repeat(prefix),
        repeat(keypoint),
        repeat(num_cls),
        repeat(nkpt),
        repeat(ndim),
        repeat(single_cls),
    ):
        result = verify_image_label(args)
        im_file_ct, lb, shape, segments, result_keypoint, nm_f, nf_f, ne_f, nc_f, msg = result
        label = (
            {
                "im_file": im_file_ct,
                "shape": shape,
                "cls": lb[:, 0:1],
                "bboxes": lb[:, 1:],
                "segments": segments,
                "keypoints": result_keypoint,
                "normalized": True,
                "bbox_format": "xywh",
            }
            if im_file_ct
            else None
        )
        nm += nm_f
        nf += nf_f
        ne += ne_f
        nc += nc_f
        if label is not None:
            labels.append(label)
        if msg:
            msgs.append(msg)

    cache = {
        "labels": labels,
        "hash": u.get_hash(label_files + im_files),
        "results": (nf, nm, ne, nc, len(im_files)),
        "msgs": msgs,
        "version": DATASET_CACHE_VERSION,
    }
    cache_dir = root / "labels"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / (split + ".cache")
    u.save_dataset_cache_file(f"{prefix}", cache_path, dict(cache), DATASET_CACHE_VERSION)
    logger.debug("Pregenerated cache for %s split: %s labels", split, nf)
    return nf


def pregenerate_dataset_caches(data_yaml: Path, *, prefix: str = "") -> dict[str, int]:
    """Pre-generate train/val/test ``*.cache`` files for an exported YOLO dataset.

    Runs serially in-process (no ``multiprocessing`` / pipes), writing the same cache
    format Ultralytics reads, so the ``yolo.exe`` subprocess loads labels without the
    ``ThreadPool`` path that fails under a restricted Windows token.

    Args:
        data_yaml: Path to the exported ``data.yaml``.
        prefix: Optional log prefix (e.g. dataset label).

    Returns:
        Mapping of split -> number of cached labels for splits that exist.

    Raises:
        ValidationError: if the train split has no valid annotated images.
    """
    root, cfg = _load_data_yaml(data_yaml)
    names = cfg.get("names", [])
    num_cls = (
        len(names)
        if isinstance(names, (list, dict)) and names
        else max(int(cfg.get("nc", 1)), 1)
    )
    single_cls = str(cfg.get("single_cls", False)).lower() == "true"
    keypoint = bool(cfg.get("kpt_shape"))

    produced: dict[str, int] = {}
    for split in ("train", "val", "test"):
        count = _scan_split(root, split, num_cls, single_cls, keypoint, prefix)
        produced[split] = count

    if not produced.get("train") and not produced.get("val"):
        raise ValidationError(
            "training_dataset_empty",
            "Training dataset has no annotated images in the train or val split.",
            details={"split_counts": produced},
        )
    return produced