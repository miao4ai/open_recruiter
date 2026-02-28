# Open Recruiter v2.0.0 — LangGraph Architecture

> v1.x 使用单体 orchestrator.py（~950行）手动管理 5 种工作流。
> v2.0 采用 LangGraph 实现图编排、Planning Mode、Human-in-the-Loop 和 Guardrails。

---

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│  Chat.tsx ─── SSE Stream ──── api.ts                           │
│  PlanPreview.tsx (NEW)    GuardrailWarning.tsx (NEW)            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ SSE / REST
┌──────────────────────────▼──────────────────────────────────────┐
│                     Backend (FastAPI)                            │
│                                                                  │
│  routes/agent.py ──► SSE Adapter ──► LangGraph Event Stream     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                   graphs/ (LangGraph Core)                 │  │
│  │                                                            │  │
│  │   Router Graph ──┬──► Chat Graph                           │  │
│  │                  ├──► Planner Graph ──► Workflow Graphs     │  │
│  │                  └──► Resume Paused Workflow                │  │
│  │                                                            │  │
│  │   ┌─────────────────────────────────────────────────────┐  │  │
│  │   │              Workflow Graphs                         │  │  │
│  │   │  bulk_outreach | candidate_review | job_launch       │  │  │
│  │   │  interview_scheduling | pipeline_cleanup             │  │  │
│  │   └─────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  agents/   ──── 现有 Agent 模块（保持不变，包装为 Node）          │
│  guardrails/ ── 输入/输出/操作验证层                              │
│  llm.py  ────── LiteLLM 统一调用（LangGraph Node 直接调用）      │
│  SqliteSaver ── 检查点存储（复用同一 SQLite 数据库）              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Router Graph（入口）

```
                    ┌──────────────┐
                    │  User Input  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ check_paused │──── 有暂停的 workflow？
                    └──────┬───────┘
                      No   │   Yes
              ┌────────────┤    │
              │            │    └──────────────────────┐
       ┌──────▼───────┐                         ┌──────▼──────────┐
       │classify_intent│                         │ resume_workflow │
       └──────┬───────┘                         └─────────────────┘
              │
     ┌────────┼──────────┐
     │        │          │
┌────▼───┐┌───▼────┐┌────▼──────┐
│  Chat  ││Planner ││  Direct   │
│  Graph ││ Graph  ││ Workflow  │
└────────┘└────────┘└───────────┘
```

- **check_paused**: 检查是否有该用户暂停中的 workflow（通过 SqliteSaver thread_id 查询）
- **classify_intent**: 复用现有 action 检测逻辑，判断用户意图
  - 简单问答 → Chat Graph
  - 复杂任务（需要多步骤） → Planner Graph
  - 明确的单一工作流触发 → Direct Workflow

---

## 3. Chat Graph（单轮对话）

```
┌──────────┐   ┌─────────────┐   ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────┐
│  build   │──▶│ input_guard │──▶│ call_llm │──▶│ parse_response│──▶│ output_guard │──▶│ process  │
│ context  │   │ (guardrail) │   │(streaming)│  │              │   │ (guardrail)  │   │ action   │
└──────────┘   └─────────────┘   └──────────┘   └──────────────┘   └──────────────┘   └────┬─────┘
                                                                                           │
                                                                                    ┌──────▼─────┐
                                                                                    │  finalize  │
                                                                                    └────────────┘
```

- **build_context**: 加载会话历史 + RAG 检索相关数据
- **input_guard**: Prompt 注入检测、PII 扫描、长度限制
- **call_llm**: 通过 `llm.chat_stream()` 流式调用，token 通过 `asyncio.Queue` 桥接到 SSE
- **parse_response**: 解析 LLM 回复中的 action 指令（保留 keyword fallback）
- **output_guard**: 内容安全检查、格式验证
- **process_action**: 如果有 action，执行对应操作（创建职位、查询候选人等）
- **finalize**: 保存消息到数据库，返回最终结果

---

## 4. Planner Graph（规划模式 — 新增）

```
┌──────────────┐   ┌───────────────┐   ┌───────────────┐   ┌─────────────────┐
│ generate_plan│──▶│ validate_plan │──▶│ present_plan  │──▶│   INTERRUPT     │
│  (LLM)       │   │ (guardrails)  │   │ (SSE → 前端)  │   │ (等待用户审批)   │
└──────────────┘   └───────────────┘   └───────────────┘   └────────┬────────┘
       ▲                                                            │
       │                                              ┌─────────────┼──────────────┐
       │                                              │             │              │
       │                                       ┌──────▼───┐  ┌─────▼────┐  ┌──────▼─────┐
       └───────────── modify ─────────────────│  Modify  │  │ Approve  │  │  Cancel    │
                                               └──────────┘  └─────┬────┘  └────────────┘
                                                                    │
                                                             ┌──────▼──────────┐
                                                             │dispatch_workflow│
                                                             │(启动对应 Graph) │
                                                             └─────────────────┘
```

**Plan JSON 结构:**
```json
{
  "goal": "为 Senior Engineer 职位找到候选人并发送外联邮件",
  "workflow_type": "job_launch",
  "steps": [
    {"step": 1, "action": "搜索匹配候选人", "description": "基于 JD 向量匹配"},
    {"step": 2, "action": "排名与筛选", "description": "取 Top 10 候选人"},
    {"step": 3, "action": "生成邮件", "description": "为每人生成个性化外联邮件"},
    {"step": 4, "action": "审批发送", "description": "等待用户确认后批量发送"}
  ],
  "estimated_actions": {"emails": 10, "api_calls": 15},
  "requires_approval": true
}
```

---

## 5. Workflow Graphs

### 5.1 Bulk Outreach（批量外联）

```
┌────────────────┐   ┌──────────────┐   ┌────────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────┐
│find_candidates │──▶│ draft_emails │──▶│check_guardrails│──▶│  INTERRUPT   │──▶│ send_emails  │──▶│ finalize │
│(matching.py)   │   │(communic.py) │   │(action_limits) │   │(用户审批邮件) │   │(communic.py) │   │          │
└────────────────┘   └──────────────┘   └────────────────┘   └──────────────┘   └──────────────┘   └──────────┘
```

### 5.2 Candidate Review（候选人审查）

```
┌──────────────┐   ┌────────────┐   ┌──────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────┐
│load_candidate│──▶│  analyze   │──▶│    rank      │──▶│  INTERRUPT   │──▶│ update_status │──▶│ finalize │
│              │   │(matching.py)│  │              │   │(确认操作建议) │   │               │   │          │
└──────────────┘   └────────────┘   └──────────────┘   └──────────────┘   └───────────────┘   └──────────┘
```

### 5.3 Interview Scheduling（面试安排）

```
┌──────────────────┐   ┌───────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────┐
│load_candidate_job│──▶│ propose_slots │──▶│  INTERRUPT   │──▶│ create_event │──▶│ finalize │
│                  │   │(scheduling.py)│   │(确认时间段)   │   │+ draft_invite│   │          │
└──────────────────┘   └───────────────┘   └──────────────┘   └──────────────┘   └──────────┘
```

### 5.4 Pipeline Cleanup（管道清理）

```
┌──────────┐   ┌────────────┐   ┌──────────────┐   ┌─────────┐   ┌──────────┐
│   scan   │──▶│ categorize │──▶│  INTERRUPT   │──▶│ execute │──▶│ finalize │
│          │   │            │   │(确认清理操作) │   │         │   │          │
└──────────┘   └────────────┘   └──────────────┘   └─────────┘   └──────────┘
```

### 5.5 Job Launch（职位启动）

```
┌──────────┐   ┌────────┐   ┌───────┐   ┌──────────────┐   ┌────────────────┐   ┌──────────────┐   ┌──────────┐
│ load_job │──▶│ search │──▶│ match │──▶│ draft_emails │──▶│check_guardrails│──▶│  INTERRUPT   │──▶│  send +  │
│          │   │        │   │       │   │              │   │                │   │(审批邮件)     │   │ finalize │
└──────────┘   └────────┘   └───────┘   └──────────────┘   └────────────────┘   └──────────────┘   └──────────┘
```

---

## 6. Guardrails 架构

```
                    ┌──────────────────────────────────────┐
                    │           Guardrails Layer            │
                    │                                      │
                    │  ┌────────────────────────────────┐  │
                    │  │  Input Validator                │  │
                    │  │  · Prompt 注入检测              │  │
                    │  │  · PII 扫描                     │  │
                    │  │  · 长度限制                     │  │
                    │  └────────────────────────────────┘  │
                    │                                      │
                    │  ┌────────────────────────────────┐  │
                    │  │  Output Validator               │  │
                    │  │  · 内容安全检查                 │  │
                    │  │  · 幻觉检测                     │  │
                    │  │  · 格式验证                     │  │
                    │  └────────────────────────────────┘  │
                    │                                      │
                    │  ┌────────────────────────────────┐  │
                    │  │  Action Limits                  │  │
                    │  │  · 速率限制（50 封邮件/天）     │  │
                    │  │  · 批量上限（20 条/批）         │  │
                    │  │  · 成本控制                     │  │
                    │  │  · 权限检查                     │  │
                    │  └────────────────────────────────┘  │
                    └──────────────────────────────────────┘
```

Guardrails 以装饰器/包装函数形式集成到 Graph Node 上，关键操作（邮件发送）同时作为显式 Graph Node 保证可见性。

---

## 7. Human-in-the-Loop 机制

```
  Graph 执行 ──▶ interrupt() 暂停 ──▶ SqliteSaver 保存状态
                                           │
                                    SSE: approval_needed
                                           │
                                    ┌──────▼──────┐
                                    │  Frontend    │
                                    │  审批 UI      │
                                    │ (现有组件复用) │
                                    └──────┬──────┘
                                           │
                                    User: approve / reject / modify
                                           │
                                    Command(resume=value)
                                           │
                                    Graph 继续执行 ──▶ ...
```

**中断点:**
- Plan 审批（Planner Graph）
- 邮件批量发送（Bulk Outreach / Job Launch）
- 候选人状态变更（Candidate Review）
- 面试时间确认（Interview Scheduling）
- 管道清理操作（Pipeline Cleanup）

---

## 8. SSE 事件格式

保留现有 SSE 格式，新增 2 个事件类型：

| 事件类型 | 说明 | 变更 |
|----------|------|------|
| `token` | LLM 流式 token | 保持不变 |
| `workflow_step` | 工作流步骤进度 | 保持不变 |
| `approval_needed` | 等待用户审批 | 保持不变 |
| `done` | 完成 | 保持不变 |
| `plan_preview` | **新增** — 展示计划详情供审批 |
| `guardrail_warning` | **新增** — Guardrail 拦截警告 |

---

## 9. 数据库变更

```sql
-- 新增表：计划记录
CREATE TABLE plans (
    id                TEXT PRIMARY KEY,
    workflow_id       TEXT,
    session_id        TEXT NOT NULL,
    user_id           TEXT NOT NULL,
    goal              TEXT NOT NULL,
    workflow_type     TEXT NOT NULL,
    plan_json         TEXT NOT NULL,     -- JSON: steps, estimated_actions
    status            TEXT DEFAULT 'pending',  -- pending / approved / rejected / completed
    modifications_json TEXT DEFAULT '[]',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

-- 新增表：Guardrail 日志
CREATE TABLE guardrail_logs (
    id            TEXT PRIMARY KEY,
    workflow_id   TEXT,
    session_id    TEXT,
    user_id       TEXT,
    check_name    TEXT NOT NULL,       -- input_injection / output_safety / action_rate_limit ...
    severity      TEXT NOT NULL,       -- info / warning / blocked
    message       TEXT NOT NULL,
    context_json  TEXT DEFAULT '{}',
    created_at    TEXT NOT NULL
);

-- 现有表 workflows 新增列
ALTER TABLE workflows ADD COLUMN plan_id              TEXT DEFAULT '';
ALTER TABLE workflows ADD COLUMN graph_name            TEXT DEFAULT '';
ALTER TABLE workflows ADD COLUMN langgraph_thread_id   TEXT DEFAULT '';
```

---

## 10. 目录结构

```
backend/app/
├── main.py                          # (修改) 初始化 LangGraph checkpointer
├── database.py                      # (修改) 新增 plans, guardrail_logs 表
├── llm.py                           # (保留) LiteLLM — Graph Node 直接调用
├── config.py / models.py / prompts.py / vectorstore.py  # (微调)
│
├── graphs/                          # 新增 — LangGraph 核心
│   ├── __init__.py
│   ├── state.py                     # TypedDict 状态 (BaseWorkflowState, ChatState, PlannerState)
│   ├── checkpointer.py              # SqliteSaver 配置（复用同一 SQLite）
│   ├── router.py                    # 顶层路由: classify → chat | planner | resume
│   ├── planner.py                   # 规划图: generate → validate → present → INTERRUPT → dispatch
│   ├── chat_graph.py                # 单轮聊天图
│   └── workflows/
│       ├── __init__.py
│       ├── bulk_outreach.py         # 批量外联
│       ├── candidate_review.py      # 候选人审查
│       ├── interview_scheduling.py  # 面试安排
│       ├── pipeline_cleanup.py      # 管道清理
│       └── job_launch.py            # 职位启动
│
├── guardrails/                      # 新增 — 验证层
│   ├── __init__.py
│   ├── base.py                      # BaseGuardrail ABC
│   ├── input_validator.py           # Prompt 注入检测、PII 扫描、长度限制
│   ├── output_validator.py          # 内容安全、幻觉检测、格式验证
│   ├── action_limits.py             # 速率限制、批量上限、成本控制
│   └── policy.py                    # 可配置规则引擎
│
├── agents/                          # 重构 — 现有文件保留，包装为 Node
│   ├── tools.py                     # 新增: Agent → Graph Node 适配器
│   ├── communication.py             # (保留)
│   ├── matching.py                  # (保留)
│   ├── resume.py / jd.py / market.py / employer.py / job_search.py / scheduling.py  # (保留)
│   └── orchestrator.py              # 废弃: 迁移期间保留，最终删除
│
├── routes/
│   ├── agent.py                     # (重构) SSE 适配器: LangGraph 事件 → 现有 SSE 格式
│   └── (其他不变)
│
└── tools/                           # (不变)
```

---

## 11. 前端变更

| 组件 | 变更类型 | 说明 |
|------|---------|------|
| `PlanPreview.tsx` | **新增** | 渲染计划步骤，Approve/Modify/Cancel 按钮 |
| `GuardrailWarning.tsx` | **新增** | 黄色警告横幅，显示拦截信息 |
| `Chat.tsx` | 修改 | 处理 `plan_preview` 和 `guardrail_warning` SSE 事件 |
| `api.ts` | 修改 | 在 `_streamSSE` 中解析新事件类型 |
| `types/index.ts` | 修改 | 新增 `PlanPreview`, `GuardrailWarning` 接口 |
| `MessageBlocks.tsx` | 修改 | 新增 `PlanPreviewCard`, `GuardrailWarningCard` 渲染器 |
| 其他现有组件 | **不变** | WorkflowTracker, ApprovalBlockCard 保持不变 |

---

## 12. 新增依赖

```
langgraph>=0.2
langgraph-checkpoint-sqlite>=1.0
```

不需要 LangChain LLM 类，LangGraph Node 直接调用 `llm.py`（LiteLLM）。

---

## 13. 迁移阶段（8 周）

| 阶段 | 周 | 内容 | Feature Flag |
|------|-----|------|-------------|
| 1. 基础设施 | 1-2 | 添加依赖、创建 graphs/ 结构、State Schema、Checkpointer、DB 迁移 | — |
| 2. Chat Graph | 3 | 迁移单轮聊天到 LangGraph | `USE_LANGGRAPH_CHAT` |
| 3. Workflows | 4-5 | 逐个迁移工作流: pipeline_cleanup → candidate_review → interview_scheduling → bulk_outreach → job_launch | `USE_LANGGRAPH_WORKFLOW` |
| 4. Planning Mode | 6 | 新增 Planner Graph、Router、PlanPreview UI | `USE_PLANNER` |
| 5. Guardrails | 7 | 完整 Guardrails 层 + 策略配置 UI | `USE_GUARDRAILS` |
| 6. Cleanup | 8 | 移除 Feature Flags、删除 orchestrator.py、版本号 → 2.0.0 | — |

每个阶段都有 Feature Flag 支持回滚，迁移期间现有 SSE 格式完全兼容。
