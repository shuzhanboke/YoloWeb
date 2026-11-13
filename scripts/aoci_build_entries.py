#!/usr/bin/env python3
"""Batch-generate AOCI index entries for YoloWebAgentStarter.

Each source file gets one FRAS entry (F/R/A/S + compact A+B+C+[D]+E tag),
written through `aoci update-entry` so governance validates every line.
Deterministic: regenerating produces identical entries.

Usage:
    python scripts/aoci_build_entries.py [--dry-run] [--only backend/app/core/models.py]
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AOCI = r"C:\Users\Lin\AppData\Local\Programs\AOCI-CODE\v0.1.0-rc21\aoci.exe"
APP = "YoloWebAgentStarter"

# AOCI tag dictionaries (from aoci.meta.txt).
# A Layer (code): C-共享基础 E-入口边界 A-应用编排 D-领域逻辑 K-算法 M-中间件 P-持久化 I-集成 R-运行基础 L-库 F-声明配置 O-运维 T-测试 S-文档 X-工具 Z-其他
# B Module (code): G-跨域 U-用户交互 B-核心业务 D-数据状态 I-身份权限 N-网络协议 M-消息事件 S-安全隐私 C-配置策略 O-可观测 R-可靠性 P-性能 W-流程 A-分析 H-硬件 L-本地化 V-构建 Q-质量 E-扩展 Z-其他
# E Scale: L>400 M 200-400 S 100-200 T<100

LAYER_BY_DIR = {
    "core": "C",      # shared foundation
    "api": "E",       # entry boundary
    "dataset": "D",   # domain logic
    "models": "D",
    "training": "D",
    "agent": "D",
    "auto_annotation": "D",
    "video_import": "D",
    "logs": "O",
    "sam": "D",
    "settings": "C",
    "main": "E",
}

MODULE_BY_DIR = {
    "core": "G",      # cross-domain common
    "api": "N",       # network protocol
    "dataset": "B",   # core business
    "models": "B",
    "training": "B",
    "agent": "A",     # analysis intelligence
    "auto_annotation": "A",
    "video_import": "G",
    "logs": "O",      # observability
    "sam": "E",       # extension
    "settings": "C",  # config policy
    "main": "E",
    "tests": "Q",     # quality
}

IMPORTANCE = {
    "core": "9",
    "main": "8",
    "api": "8",
    "models.py": "9",
    "dataset": "7",
    "training": "7",
    "agent": "7",
    "models": "7",
    "alembic": "8",
    "auto_annotation": "6",
    "video_import": "6",
    "sam": "4",
    "logs": "5",
    "settings": "5",
    "tests": "4",
    "scripts": "5",
    "default": "5",
}


def scale(lines: int) -> str:
    if lines > 400:
        return "L"
    if lines >= 200:
        return "M"
    if lines >= 100:
        return "S"
    return "T"


def tag_for(rel: str, lines: int) -> str:
    parts = rel.split("/")
    if parts[0] == "backend" and parts[1] == "app" and len(parts) > 3:
        layer_dir = parts[2]
    elif parts[0] == "backend" and parts[1] == "app":
        layer_dir = "main"
    elif parts[0] == "backend" and parts[1] == "alembic":
        layer_dir = "core"  # migration is foundational persistence
        module = "G"
        imp = "8"
        return f"P{module}{imp}{scale(lines)}"
    elif parts[0] == "backend" and parts[1] == "tests":
        layer_dir = "tests"
    elif parts[0] == "scripts":
        # A Derived: X-开发工具; B Module: G-跨域通用
        return f"XG{IMPORTANCE['scripts']}{scale(lines)}"
    elif parts[0] == "frontend":
        # A Layer(code): C-共享基础 E-入口边界 F-声明配置 L-库; B Module: U-用户交互 N-网络 G-跨域 C-配置策略
        sub = parts[2] if len(parts) > 2 else "src"
        base_name = parts[-1]
        if base_name in ("vite.config.ts", "tsconfig.json", "package.json"):
            layer, module, imp = "F", "C", 6
        elif sub in ("api",):
            layer, module, imp = "E", "N", 8
        elif sub == "pages":
            layer, module, imp = "E", "U", 8
        elif base_name == "main.tsx":
            layer, module, imp = "E", "U", 8
        elif sub in ("utils", "types") or base_name in ("locale.ts", "vite-env.d.ts"):
            layer, module, imp = "L", "G", 6
        else:  # components, training, models, annotation, agent helpers
            layer, module, imp = "C", "U", 7
        return f"{layer}{module}{imp}{scale(lines)}"
    else:
        layer_dir = "default"

    layer = LAYER_BY_DIR.get(layer_dir, "Z")
    module = MODULE_BY_DIR.get(layer_dir, "Z")
    imp = IMPORTANCE.get(layer_dir, IMPORTANCE["default"])
    return f"{layer}{module}{imp}{scale(lines)}"


def describe(rel: str) -> str:
    parts = rel.split("/")
    name = parts[-1]
    if parts[0] == "backend" and parts[1] == "app":
        module = parts[2] if len(parts) > 3 else "core"
        return f"{module}模块 {name}：{module} 领域实现"
    if parts[0] == "backend" and parts[1] == "tests":
        return f"后端测试 {name}"
    if parts[0] == "backend" and parts[1] == "alembic":
        return f"数据库迁移 {name}"
    if parts[0] == "backend" and parts[1] in ("requirements.txt", "pyproject.toml"):
        return f"后端依赖声明 {name}"
    if parts[0] == "frontend":
        return f"前端 {name}"
    if parts[0] == "scripts":
        return f"工具脚本 {name}"
    return f"{name}"


def summarize(rel: str, description: str) -> str:
    return description


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_entry(rel: str, description: str, summary: str, tag: str) -> str:
    bare = Path(rel).name
    return f"{bare}[{tag}]: F:{description} | R:- | A:{APP} | S:{summary}"


def iter_sources():
    """Yield (relative_posix_path, Path) for all indexable source files."""
    exts = {".py", ".ts", ".tsx"}
    names = {
        "requirements.txt", "requirements-dev.txt", "pyproject.toml", "alembic.ini",
        "package.json", "tsconfig.json", "vite.config.ts",
    }
    for p in REPO.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(REPO).as_posix()
        if any(part in {".git", ".venv", "node_modules", "__pycache__", "dist", ".github", "docs/assets"}
               for part in p.parts):
            continue
        if p.suffix in exts or p.name in names:
            yield rel, p


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    only = None
    for arg in sys.argv:
        if arg.startswith("--only="):
            only = arg.split("=", 1)[1]

    sources = sorted(iter_sources(), key=lambda pair: pair[0])
    if only:
        sources = [pair for pair in sources if pair[0] == only]
        if not sources:
            print(f"no source matched --only={only}")
            return 1

    written = 0
    for rel, path in sources:
        try:
            lines = sum(1 for _ in open(path, encoding="utf-8", errors="replace"))
        except OSError:
            lines = 0
        tag = tag_for(rel, lines)
        description = describe(rel)
        summary = summarize(rel, description)
        entry = make_entry(rel, description, summary, tag)
        digest = sha256(path)

        if dry_run:
            print(f"{rel}\t{tag}\t{entry[:120]}")
            written += 1
            continue

        cmd = [
            AOCI, "update-entry", "--repo", str(REPO),
            "--path", rel,
            "--entry", entry,
            "--source-sha256", digest,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip().splitlines()[:3]
            print(f"[SKIP] {rel}: {err}", file=sys.stderr)
        else:
            written += 1

    print(f"processed {written}/{len(sources)} entries (dry_run={dry_run})")
    return 0


if __name__ == "__main__":
    sys.exit(main())