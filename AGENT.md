# AGENT.md — Wiki Agent 项目记忆

> 本文件是 AI 协作的入口。`CLAUDE.md` 仅指向本文。未来任何 Claude 会话先读本文件再动手。
>
> 最近更新：2026-07-23

---

## 0. 一句话

**内网 ChatGPT-Deep-Research 同类助手**：把 WIKI / TD 技术文档 / KB / 代码仓库 / Web 当作可路由的信息源，启动研究时开简易沙箱 → 先学非代码知识 → 回代码取证 → 输出一份带证据链的可信报告，并能根据人的反馈自动更新认知，沉淀进 Graphiti 供下次与编码流复用。

---

## 1. 进展速览

| 状态 | 模块 | 说明 |
|---|---|---|
| ✅ | Tauri 桌面外壳 + Python sidecar | macOS `.app`/`.dmg` 已本地打出，CI 流水线同时产 `.exe`/`.msi` |
| ✅ | FalkorDB + Graphiti 内核 | `EMBEDDING_DIM=512`、DeepSeek `json_object`、FalkorDriver `database=GROUP_ID`、属性拍平 shim 已稳定 |
| ✅ | 文档导入（md/txt/pdf/docx） | SHA256 增量跳过，溯源 `sources[]` |
| ✅ | LangGraph 问答工作流 | retrieve → reason → judge → reflect，AsyncSqliteSaver checkpoint |
| ✅ | 决策/规则/风险/经验查询 | 自定义 EntityType，已暴露 `/decisions` |
| ✅ | SearXNG Web 搜索 | URL 可配置，默认公共实例 |
| ✅ | 配置持久化 + Keychain | 密钥不落 `.env`、不返回前端、不写二进制 |
| ✅ | 参考实现挂入 | `repos/weknora` (MIT)、`repos/llm_wiki` (GPLv3 pattern-only) |
| 🚧 | 多源路由 | 当前所有源共用一个 GROUP_ID，差距见 §4 |
| 🚧 | 反馈闭环 | 无 `/feedback` API；`invalid_at` 字段已存在但无人写 |
| 🚧 | 研究沙箱 | 全进程内执行 |
| 🚧 | 双步 ingest | 当前单步 `add_episode` |
| 🚧 | 真实 reranker | PassthroughReranker 占位 |
| 🚧 | 引文 UI | 答案只展示 edge fact 文本，无引用编号 |
| 📋 | 深度研究主循环 | 仅有 README 设想，未实现 |
| 📋 | MCP 服务化 | 编码流集成未启动 |

---

## 2. 终态架构

```
                          ┌────────────────────────┐
            用户提问 ───▶ │  Intent Classifier     │
                          │  (LLM: WIKI/TD/KB/...) │
                          └────────┬───────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
       ┌────────┐             ┌────────┐             ┌────────┐
       │  WIKI  │             │   TD   │             │   KB   │   ← 多源 fanout
       └────┬───┘             └────┬───┘             └────┬───┘     (RRF merge)
            └──────────────────────┼──────────────────────┘
                                   │
                          ┌────────▼───────────┐
                          │   Rerank + Cite    │
                          └────────┬───────────┘
                                   │
                  证据充分? ────▶ 直接出答 ◀──── 反馈闭环
                        │
                        ▼ 否
              ┌─────────────────────┐
              │  Research Sandbox   │   ← tempfile 隔离
              │  1. topic 优化      │
              │  2. web/code 抓取   │
              │  3. 流式综合        │
              │  4. 报告落盘        │
              └────────┬────────────┘
                       ▼
            ┌──────────────────────┐
            │   可信报告 + 引文    │
            └────────┬─────────────┘
                     ▼
            ┌──────────────────────┐
            │  用户反馈            │
            │  → invalid_at 写回   │   ← Graphiti 时序失效
            │  → 关联 episode 重排 │
            └──────────────────────┘
```

辅助编码流：把 sidecar 暴露为 MCP server，Claude Code / IDE 内直接 `search_kb` / `recall_decisions` / `record_decision`。

---

## 3. 已验证底座（不可重做）

| 资产 | 路径 | 备注 |
|---|---|---|
| Graphiti 四坑 shim | `python-core/wiki_agent/memory.py` | `EMBEDDING_DIM` 顺序、`json_object`、properties 拍平、`database=GROUP_ID`。已踩过，直接复用 |
| FastAPI 应用骨架 | `python-core/wiki_agent/api.py` | 异步 lifespan、CORS、静态挂载都已配 |
| Tauri 桌面外壳 | `src-tauri/`、`src/App.tsx` | 5 个 tab + Web 端同 UI |
| PyInstaller sidecar 构建 | `python-core/build_sidecar.py` | 跨平台 `--triple`，CI 现场构建 |
| CI/CD 流水线 | `.github/workflows/{release,ci}.yml` | tag 触发，matrix 出 dmg/exe/msi |
| LangGraph checkpoint 模式 | `python-core/wiki_agent/agent_graph.py` | AsyncSqliteSaver by `thread_id`；深度研究可复用此模式持久化长任务 |
| Keychain 配置 | `python-core/wiki_agent/config.py` | `keyring` 存 API key，`public_config()` 永不返回密钥 |
| SHA256 增量 ingest | `python-core/wiki_agent/ingest.py` | `data/ingest-index.json` |

---

## 4. 能力差距 → 参考实现映射（核心复用表）

> 许可证提醒：**llm_wiki = GPLv3，仅借 prompt/架构思路，绝不抄代码；WeKnora = MIT，可代码复用并附 attribution**。

| 差距 | 参考位置 | 复用方式 |
|---|---|---|
| 多源 fanout 路由 | `repos/weknora/internal/application/service/knowledgebase_search_fanout.go` + `chat_pipeline/query_understand.go` | 思路移植，LangGraph 节点重写；不同源分配 `group_id` 前缀 |
| 研究沙箱 | `repos/weknora/docker/Dockerfile.sandbox` + `internal/agent/tools/skill_execute.go` | 简化为 `tempfile.TemporaryDirectory()` 每次研究一目录；不引入 Docker 依赖 |
| 双步 ingest（分析→抽取） | `repos/llm_wiki/src/lib/ingest.ts` lines 977-1073（Step 1 analyze）+ 1942-2100（Step 2 generate） | prompt 模板照搬思想，重写为 Python；Step 1 输出作为 Step 2 context |
| 反馈闭环 | 无现成参考（llm_wiki 仅有 review queue 且为单用户） | 自设计：`POST /feedback {answer_id, verdict, correction}` → Graphiti `invalid_at` + 相关 episode 标记待重审 |
| 真实 reranker | `repos/weknora/internal/application/service/chat_pipeline/rerank.go` | 用 fastembed 加 `BAAI/bge-reranker-base` 替换 PassthroughReranker |
| Topic 优化 | `repos/llm_wiki/src/lib/optimize-research-topic.ts` | prompt 思路复用：读 `purpose.md` + 缺口描述 → `TOPIC:` + 3 `QUERY:` |
| 引文与可追溯报告 | `repos/weknora/frontend/src/components/ChatReferencesDrawer.vue`（MIT） | 抄组件结构，rewrite-to-react（机械工作） |
| 评估指标 | `repos/weknora/internal/application/service/evaluation.go` + `metric/{mrr,ndcg,recall}.go` | 借公式，不抄实现；金标准集自己造 |
| 长上下文压缩 | `repos/weknora/internal/agent/memory/consolidator.go` + `token/` | 借鉴 LLM 摘要思路，结合我们已有 LangGraph 的 reflect 节点 |
| 思考/规划 | `repos/weknora/internal/agent/tools/sequentialthinking.go` + `todo_write.go` | 思路：plan → execute → observe，作为研究 agent 主循环骨架 |
| 知识图查询工具 | `repos/weknora/internal/agent/tools/query_knowledge_graph.go` | 思路：在 LangGraph 内加 `kg_query` 节点，调用 graphiti `search` + 邻居展开 |
| 文档解析 | `repos/weknora/docreader/` | **不复制**：gRPC 服务太重；继续用 `markitdown` + `pypdf` + `python-docx` |
| 三语言 i18n | `repos/llm_wiki/src/i18n/` | 跳过，先 zh + en |

---

## 5. 关键设计抉择（提前定，避免后续摇摆）

### 5.1 多源隔离方式
- **不引入多图**：每个源在 Graphiti 同一个 DB 内分配独立 `group_id`：`wiki-{topic}` / `td-{team}` / `kb-{project}`。一个 `ExpertMemory` 实例支持多 group_id 检索。
- 路由器是 LLM + 关键词混合判别，先白名单后 fallback 到全源 fanout。

### 5.2 沙箱边界
- 仅隔离**数据**，不隔离**进程**：`tempfile.TemporaryDirectory()` 给每次研究一个工作目录。
- 抓回的 web/code 内容先写沙箱，提取后再决定是否 `promote` 进主图（promote = 触发正式 ingest 流程）。
- 沙箱不引入 Docker；研究脚本仍跑在 sidecar 进程内。

### 5.3 反馈闭环语义
- 反馈粒度：`answer`（整段）/ `fact`（单条 edge）两级。
- 反馈动作：`up` / `down` / `correct`（带修正文本）。
- 落点：Graphiti edge 的 `invalid_at`（纠错时设）；episode 加 `feedback:*` tag 触发下次 recall 重排。
- **不立即重 ingest**：先标记，下次同问题召回时把带 `feedback:down` 的降权 / 带 `feedback:correct` 的提升。

### 5.4 双步 ingest 触发条件
- 单步 `add_episode` 保留作为快速路径（小型 md/聊天片段）。
- 长文档（>4KB）或检测到现有知识有 5+ 相关 edge 时，走双步：Step 1 = LLM 分析（找连接/矛盾，**输出仅作为 Step 2 context**，不回写）、Step 2 = 抽取实体 + 边 + 来源。
- Step 1 prompt 直接参考 `repos/llm_wiki/src/lib/ingest.ts:1942`。

### 5.5 编码流集成方式
- 不重做客户端：把现有 sidecar HTTP API 暴露为 MCP server（stdio bridge）。
- Claude Code 配置 `mcpServers.wiki-agent` 指向 sidecar，开发时直接 `mcp__wiki-agent__search_kb` / `mcp__wiki-agent__record_decision`。
- 实现细节：参考 llm_wiki `mcp-server/` 的目录布局（**仅看布局，不抄代码**）。

---

## 6. 里程碑

- **M1（多源 + 反馈）**：每个源独立 group_id；`/ask` 自动路由；新增 `POST /feedback` API；端到端验证一条「错误反馈 → 下次召回避开」
- **M2（双步 ingest + reranker）**：长文档走两步；`bge-reranker-base` 接入；recall 准确率肉眼可见提升
- **M3（深度研究主循环）**：topic 优化 → 用户确认 → 沙箱抓取 → 流式综合 → 报告落 `data/reports/{id}.md`
- **M4（引文 UI + 评估）**：答案带 `[1][2]` 编号，可点开溯源；构建 golden-set 跑 mrr/ndcg
- **M5（MCP 服务化）**：sidecar 暴露 MCP，Claude Code 内直接调；编码遇到术语自动追加 KB
- **M6（多端 + 协作）**：当前单用户仅保留本地；如未来需多人加 OIDC（参考 WeKnora `internal/service/user_oidc*`，但默认不做）

---

## 7. 仓库布局

```
wiki-agent/
├── AGENT.md             ← 本文件
├── CLAUDE.md            ← 仅指向 AGENT.md
├── README.md
├── repos/
│   ├── weknora/         ← MIT，复用组件
│   └── llm_wiki/        ← GPLv3，仅参考模式，不抄代码
├── python-core/
│   └── wiki_agent/      ← 当前 sidecar 内核
├── src/                 ← React UI
├── src-tauri/           ← Tauri 外壳
├── raw/                 ← 原始文档（不可变）
└── data/                ← 索引、checkpoint、报告
```

### submodule 同步
```bash
git submodule update --init --recursive   # 首次克隆
git submodule update --remote             # 升级参考实现
```

---

## 8. 反模式（历史教训，不要重犯）

- **不要碰 GPLv3 代码**：llm_wiki 仅做模式参考；任何 PR 里出现 llm_wiki 代码片段都拒收
- **不要重写 Graphiti shim**：已踩坑，搬过来用
- **不要引入 Docker**：本机 brew 已坏，sidecar 自身设计就避免 Docker 依赖
- **不要写死 LLM 端点**：配置层都在 `config.py`，任何 UI 改动都得走 `/config` 持久化
- **不要把密钥写进二进制 / Git**：Keychain 唯一出口
- **不要做大而全**：先 M1 闭环验证「错→自动修正」再扩 M2
