# CodeTeam Agent 后端

CodeTeam Agent 是一个基于 FastAPI 的 Multi-Agent 软件研发助手后端。系统能够索引代码仓库、检索代码证据，并通过 LangGraph 编排由 Planner、Retriever、Analyst、Developer、Reviewer 和 Reporter 组成的多智能体工作流。

如果你希望从基础概念开始，逐段理解整个项目和关键代码，请阅读[项目完整说明](docs/project-guide.zh-CN.md)。

## 当前功能

- 导入本地代码仓库或克隆远程 Git 仓库。
- 按顶层符号切分 Python 代码，其他支持的文件按限定行数切分。
- 为每个代码块保存文件路径、编程语言、符号名称和起止行号等元数据。
- 在 PostgreSQL 中使用 OpenAI Embedding、pgvector 原生向量字段和 HNSW 索引。
- 在 SQLite 离线开发模式下使用确定性 Hash Embedding 和本地余弦检索。
- 支持向量与关键词混合检索，以及文件路径和符号过滤。
- 执行并持久化 LangGraph 中每个 Agent 的步骤和最终证据报告。
- 支持证据不足时重新检索，以及 Developer 和 Reviewer 之间的有限次数返工循环。
- 部署模式下通过 Celery 和 Redis 执行仓库索引、Agent 分析和 Patch 任务。
- 生成 unified diff 后必须经过人工审批，批准后才会在复制的工作区中应用 Patch。
- 无 API Key 时可使用确定性的 `fake` 模式，也可以接入 OpenAI 结构化输出。

## 本地开发

运行环境要求 Python 3.11 或更高版本，并安装 Git。

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn codeteam.main:app --reload
```

默认数据库为 `sqlite:///./codeteam.db`。服务启动后，可访问
`http://127.0.0.1:8000/docs` 查看并调试交互式 API 文档。

运行以下命令进行代码检查和测试：

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest -q
```

## OpenAI 模式

将 `.env.example` 复制为 `.env`，然后填写以下配置：

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
OPENAI_API_KEY=your-key
```

未配置 API Key 时，系统会在同一套 LangGraph 工作流中使用确定性的备用专家逻辑，因此索引、检索、API 和编排功能仍然可以开发和测试。

## API 使用流程

1. 调用 `POST /api/v1/repositories`，传入 `name`，并提供 `source_url` 或 `local_path`。
2. 调用 `POST /api/v1/repositories/{repository_id}/index` 开始索引仓库。
3. 轮询 `GET /api/v1/repositories/{repository_id}`，直到 `status` 变为 `ready`。
4. 调用 `POST /api/v1/tasks`，传入 `repository_id` 和 `user_request`。
5. 轮询 `GET /api/v1/tasks/{task_id}`，查看 Agent 执行步骤和最终报告。
6. 如果响应中存在 `patch_execution`，先检查生成的 diff，然后调用 `POST /api/v1/tasks/{task_id}/approval`，请求体传入 `{"approved": true}` 或 `{"approved": false}`。
7. 继续轮询任务，直到 Patch 执行状态变为 `succeeded` 或 `failed`，然后检查测试输出和复制工作区路径。系统不会修改源代码仓库。

本地仓库导入请求示例：

```json
{
	"name": "sample-service",
	"local_path": "C:\\projects\\sample-service"
}
```

## Docker 部署

Docker Compose 会运行四个服务：FastAPI、Celery Worker、Redis，以及安装了 pgvector 的 PostgreSQL。PostgreSQL 使用原生 `VECTOR(1536)` 字段，并创建 HNSW 余弦距离索引。API 和 Worker 共享代码仓库与沙箱数据卷。

```powershell
docker compose up --build
```

如果本地已经运行 Redis，可以将 `TASK_DISPATCH_MODE` 设置为 `celery`，并单独启动 Worker：

```powershell
.\.venv\Scripts\celery.exe -A codeteam.worker:celery_app worker --loglevel=INFO --pool=solo
```

没有 Redis 时保持 `TASK_DISPATCH_MODE=local`，FastAPI 将通过进程内后台任务执行相同的任务函数。

## Agent 与 Patch 配置

- `AGENT_MAX_RETRIEVAL_ATTEMPTS`：限制证据检索的最大尝试次数。
- `AGENT_MAX_REVISION_ATTEMPTS`：限制 Reviewer 返回 Developer 返工的最大次数。
- `SANDBOX_ALLOWED_COMMANDS`：使用逗号分隔的可执行命令白名单。
- `SANDBOX_TIMEOUT_SECONDS`：限制批准后测试进程的运行时间。
- Patch 中的路径必须是仓库相对路径，系统会拒绝路径穿越和符号链接 Patch。
- 测试命令使用 `shell=False` 和最小化环境变量运行。

## 安全边界

系统将代码仓库中的文件视为不可信证据。Agent Prompt 明确禁止执行代码、注释、README、Issue 或其他文档中包含的指令。

当前 MVP 面向可信开发环境。Patch 会在复制的工作区中执行，不会修改源代码仓库，但这不属于操作系统级安全沙箱：仓库测试仍可能以 Worker 账户的权限执行任意代码。

在将系统公开部署之前，应当使用临时容器或 microVM 执行每个 Patch，并补充身份认证、URL 和文件系统白名单、仓库克隆大小限制、网络隔离、资源配额及 API 限流。