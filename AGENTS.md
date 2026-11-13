# YoloWebAgentStarter 贡献说明

YoloWebAgentStarter 是 YoloWebAgent 的独立社区版。运行时不得 import、读取或依赖 Enterprise 仓库。

## 产品边界

- Community v2 支持 `detect`、`segment`、`obb` 与 `classify`；其中 polygon 是 segment 的标注表示。
- 核心流程：图片 → 数据集 → bbox/polygon/OBB/分类标注 → 校验 → YOLO 导入/导出 → 本地训练 → 受管 PT/ONNX 产物。SAM 仅用于 segment 的交互式建议，必须由用户确认后走普通标注保存流程。
- 训练在本地以队列方式运行；模型版本只能由受管训练产物创建。本地评估复用已持久化 split，对受管 PT 运行原生 YOLO `val`。
- Agent MVP 在范围内：只读智能助手（数据集/训练/模型问答与报告），以及经人工确认后调用现有领域 Service 提交受管任务（训练、评估、自动标注）。工具调用与运行记录可持久化；LLM 配置可在设置页写入 `{data_dir}/settings.json`（与上游一致），也可由环境变量提供默认值；不得写入 SQLite。
- Auth、RBAC、License、Workflow、Deployment、pose、无人值守 Agent 自动化（定时、触发器、任务自动串联）和文本提示分割均不在范围内；数据集级自动标注仅允许本地受管 PT，且必须人工审核。Agent 不得执行任意路径、外部 PT 或 Shell 命令。
- 服务仅面向本地单用户，默认绑定 `127.0.0.1`。

## 工程规则

- Python 依赖必须安装在仓库的 `.venv` 中；不得安装到系统 Python。
- API 路由只负责适配 HTTP 请求；业务逻辑必须位于领域服务中。
- 文件 IO 必须经由 `backend/app/core/storage.py` 或明确命名的领域边界。
- 标注坐标必须以图片绝对像素持久化；Canvas 状态不是持久化 schema。
- 校验与 YOLO 导出必须复用已持久化的图片 split。
- 新 schema 变更必须提供 Alembic migration；不得添加运行时 SQLite patcher。
- 前端 API 调用必须置于 `frontend/src/api/`；页面组件不得硬编码 API URL。
- 在 `source_snapshot.md` 中保留来源归属；不得复制 Enterprise 的 `.git` 目录或 migration 历史。

## AOCI 认知索引（AI-Oriented Cognition Infrastructure）

仓库已接入 AOCI-CODE（`aoci.exe`），维护可版本化的全局代码/数据库认知索引，供 AI Agent 在改动前快速建立对系统的长期理解。

- **索引产物（随仓库提交、由工具维护，勿手改）**：
  - `aoci.txt` — 根 manifest，声明 meta/code 两个 volume 段
  - `aoci.code.txt` — 代码认知索引（每条为 `filename[Tag]: F:… | R:… | A:… | S:…`）
  - `aoci.meta.txt` — tag 词典（A 分层/B 模块/C 重要性/E 规模）与条目规范
  - `.aoci/` — 治理状态（config、baseline.json、scope、ledger、verify_history）
  - `.gitattributes` — 强制 LF，保证 baseline 字节级一致
- **常用命令**（`aoci --repo <root>`）：
  - `aoci status` — 索引/基线对齐状态
  - `aoci verify` — 结构健全性校验（不改正式索引）
  - `aoci scan` — 重建/刷新基线指纹（已有基线需 `--force`）
  - `aoci update-entry` — 写/改单条索引条目（`--source-sha256` 绑定源码指纹）
  - `aoci mcp` — 作为 MCP stdio 服务（tool: `aoci_get_entries`/`aoci_search`/…）
- **接入方式**：可将 `aoci mcp --repo <root>` 注册为 MCP stdio server，供 Claude Code / Codex / Cursor 等 Agent 读取索引。
- **规则**：对源文件做标注性改动后，用 `python scripts/aoci_build_entries.py` 重生成索引并提交；索引条目反映源码快照，改动源码后 `verify` 会要求同步。

构建/测试脚本见下：

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests
npm --prefix frontend test
npm --prefix frontend run build
```
