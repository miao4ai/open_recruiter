# Open Recruiter V3.0 Roadmap

> V1.x 把核心招聘工作流跑通；V2.x 把单体 orchestrator 重构成 LangGraph 多 Agent 架构，并加入 guardrails、HIL、本地 LLM、语音输入。
> **V3.0 的主旨**：从「响应式工具」进化为「自主招聘合伙人」（Autonomous Recruiting Partner）。
>
> - 不再只在用户开口时工作 → 主动监控、主动推送行动建议
> - 不再只是单次问答 → 跨 session、跨日的长程目标驱动
> - 不再只是录入工具 → 端到端候选人生命周期闭环

---

## V2 回顾 — 已交付 vs 未交付

| V2 路线图方向 | 状态 | 备注 |
|--------------|------|------|
| LangGraph 重构 AI 层 | ✅ 已交付 (V2.0) | 全量替换 orchestrator；加入 guardrails / HIL / SqliteSaver |
| 4-Agent 候选人评估 swarm | ✅ 已交付 (V2.1) | resume / culture / risk / market 并行打分 + synthesizer |
| Voice 语音输入 | ✅ 已交付 (V2.1.x) | 本地 faster-whisper，离线转写 |
| Recruiter Chrome Extension | ⏳ 推迟到 V3 | LinkedIn DOM 选择器维护成本评估中 |
| Job Seeker Chrome Extension | ⏳ 推迟到 V3 | 与 Recruiter 插件合并为单一插件 |
| Voice 语音回复 (TTS) | ⏳ 推迟到 V3 | 与方向二合并 |

---

## 五大方向

### 方向一：Autonomous Agents — 主动招聘助手

**目标**：从「等用户提问」转向「主动发现需要行动的时刻」。

**核心能力**

| 能力 | 说明 |
|------|------|
| Goal-driven Agents | 用户给出目标（"两周内招一个 Senior Backend"），Agent 自主拆解任务、推进、阶段性汇报 |
| Pipeline Watcher | 持续监控 pipeline 滞留、邮件未回复、面试无反馈，主动生成行动卡片 |
| Idle-time 任务调度 | 用户离开时后台跑评估、整理 inbox、生成日报，回来时一并呈现 |
| 跨 session 长程工作流 | LangGraph 工作流跨进程持久化（已有 SqliteSaver 基础），支持中断后续跑 |
| Proactive Briefing | 每天早晨自动生成"今日招聘简报"：紧急动作 / 候选人状态变化 / 待回复邮件 |

**技术方案**
- 复用 `app/scheduler.py`（APScheduler）作为触发器，但执行体替换为 LangGraph workflow
- 新增 `app/agents/autonomous/` 模块：`pipeline_watcher.py`、`goal_driver.py`、`briefing_agent.py`
- 持久化目标：新表 `agent_goals`（id, user_id, description, status, progress_jsonl, created_at）
- 主动通知：复用现有 `notifications` 表 + 前端 toast

**关键约束**
- 所有破坏性操作（发邮件、改 pipeline、删数据）**必须**走 HIL 审批，不允许 Agent 静默执行
- 用户可一键暂停/接管任意 Agent
- Agent 行为日志可审计（新表 `agent_actions`：thread_id, agent, action, params_json, status, created_at）

**成功指标**
- 用户主动操作次数下降 ≥ 30%
- Pipeline 阶段滞留 > 3 天的候选人比例下降 ≥ 50%
- 每日 briefing 打开率 ≥ 60%

---

### 方向二：Voice Suite — 全双工语音 + 面试转写

**目标**：把 V2.1 的语音输入扩展为一整套语音交互系统。

**核心能力**

| 能力 | 状态 | 说明 |
|------|------|------|
| 语音输入 (STT) | ✅ V2.1 已交付 | faster-whisper, 本地 |
| 语音回复 (TTS) | 🆕 V3 | Piper（本地，~50MB）作为默认；ElevenLabs 作为可选云端高质量 |
| 连续对话模式 | 🆕 V3 | VAD（voice activity detection）自动断句，无需每次点麦克风 |
| 面试转写 | 🆕 V3 | 浏览器/会议麦克风录制 → 实时转写 → 按胜任力维度结构化笔记 |
| 多语言自动识别 | 🆕 V3 | Whisper 自带语言检测；UI 显示检测到的语言 |
| 语音指令 | 🆕 V3 | "保存这个候选人"、"发邮件给 HR" 等高频指令直接走 intent → action |

**面试转写流程**
```
浏览器 MediaRecorder ──► 分片上传 (10s/片) ──► /api/transcribe/stream
                                                       │
                                                       ▼
                                              faster-whisper
                                                       │
                                                       ▼
                                              片段拼接 + 说话人分离
                                                       │
                                                       ▼
                                              LangGraph 笔记 Agent
                                                  （按维度提取）
                                                       │
                                                       ▼
                                              CandidateInterviewNote 表
```

**新增依赖**
- TTS：`piper-tts`（本地，CPU 友好）
- 说话人分离（可选，复杂度高）：`pyannote-audio` —— 评估后再决定是否纳入 V3

**成功指标**
- 语音转写准确率 ≥ 92%（英文）/ ≥ 88%（中文）
- 面试笔记自动化率 ≥ 80%（recruiter 接受/微调即可）
- 端到端延迟 ≤ 3 秒（说话结束 → 文字出现）

---

### 方向三：Sourcing & Outbound — 主动候选人发现

**目标**：从「等候选人来」变成「主动找人 + 自动跟进」。

**Chrome Extension（V2 推迟项落地）**
- 单一插件，根据登录账号角色（Recruiter / Job Seeker）切换面板
- 一键保存 LinkedIn / Indeed / Glassdoor 页面到本地
- 已保存候选人/职位显示标记
- DOM 选择器多套 fallback + 错误上报到本地 SQLite 表 `extension_errors`

**主动 Sourcing**

| 渠道 | 方案 |
|------|------|
| GitHub | 按 language / location / repo stars 搜开发者，公开 API |
| LinkedIn 公开搜索 | 通过插件用户主动浏览触发，不做后端爬虫（合规） |
| 公开数据集 | HuggingFace / Kaggle 上的公开简历语料，离线索引 |
| 候选人活跃度 | GitHub commit 频率 / LinkedIn updated_at 信号 |

**Outbound 序列引擎**
- 3-touch 模板：初始接触 → 软跟进 (3 天) → 最后一次 (7 天)
- 每封邮件由 LLM 基于候选人 profile 个性化生成
- A/B 测试主题行（success metric: open rate）
- 状态分支：已 reply / 已 open 未回 / 未 open
- 整套序列受 HIL 审批控制，可批量预览/编辑/取消

**新增 API**
- `POST /api/candidates/from-extension`
- `GET /api/candidates/check?linkedin_url=...`
- `POST /api/sourcing/github/search`
- `POST /api/outreach/sequence` — 创建 3-touch 序列
- `GET /api/outreach/sequence/{id}/status` — 查看每个 touch 的状态

**成功指标**
- 平均回复率较单封邮件提升 ≥ 2x
- 候选人来源中"主动 sourcing"占比 ≥ 30%
- Chrome 插件月活 ≥ 系统总用户的 50%

---

### 方向四：Deep Integrations — ATS / Calendar / Mail

**目标**：让 Open Recruiter 成为现有招聘工具栈的"智能层"，而不是孤立工具。

**ATS 集成**（按优先级）
1. **Greenhouse** — 最广泛使用，REST API 完整
2. **Lever** — 第二大，API 稳定
3. **Ashby** — 增长快，新一代 ATS

**集成深度**：双向同步候选人 / 职位 / pipeline 状态。冲突解决策略：以最近修改方为准，冲突时弹审批卡片。

**Calendar 升级**
- Google Calendar OAuth + 双向同步（不只是单向写入）
- Outlook / Microsoft 365
- 冲突检测：调度面试时自动避开候选人和面试官的日程冲突
- 时区智能：跨时区候选人自动建议双方均合理的时段

**Email 升级**
- Gmail API / Microsoft Graph 原生集成（取代 IMAP 轮询）
- 实时 webhook：候选人回复立即入 inbox，不再 5 分钟一轮询
- 已读/未读状态、Thread 完整结构、附件原生处理

**Slack 升级**
- 完整工作流卡片（不只是简历接收）
- HIL 审批可在 Slack 完成（不必回到桌面端）
- `/recruiter` slash command 支持常用操作

**成功指标**
- 至少 1 个 ATS 集成达到生产可用（端到端 sync 错误率 < 1%）
- Calendar 双向同步冲突率 < 5%
- 邮件回复延迟从 5 分钟降到 < 30 秒

---

### 方向五：Analytics & Forecasting

**目标**：把已有数据变成可决策的洞察。

**Pipeline Funnel**
- 各阶段转化率可视化（Sankey diagram）
- 按职位 / 按 recruiter / 按时间段分组
- 异常检测：某阶段转化率突然下降时主动告警

**预测模型**（本地 ONNX，避免云端调用）
- Time-to-hire 预测：基于职位类型、地点、薪资 → 预计天数
- 候选人响应概率：基于 profile + 邮件内容 → 回复概率 0-100%
- Pipeline 健康度评分：综合信号给每个 job 打 0-10 分

**报表自动化**
- Hiring manager 周报：每周一早自动生成 PDF + 邮件发送
- 候选人画像分析：当前 pipeline 中候选人的技能 / 地点 / 薪资分布

**技术方案**
- 新增 `backend/app/analytics/` 模块
- 预测模型用 scikit-learn 训练 → 导出 ONNX → 用现有 `onnxruntime` 推理
- 报表生成：`weasyprint` 或 `reportlab`

**成功指标**
- 预测的 time-to-hire 与实际值平均误差 ≤ 5 天
- 响应概率模型 ROC-AUC ≥ 0.75
- 周报订阅率 ≥ 70%

---

## 版本规划

| 阶段 | 内容 | 优先级 | 目标时间 |
|------|------|--------|---------|
| V3.0-alpha | Autonomous Agents 核心（方向一） | P0 | 2026 Q2 |
| V3.0-beta | Voice Suite 全套（方向二） | P0 | 2026 Q3 |
| V3.0-rc1 | Chrome Extension + Sourcing（方向三） | P0 | 2026 Q3 |
| V3.0-rc2 | ATS 集成（方向四，先做 Greenhouse） | P1 | 2026 Q4 |
| V3.0 | Analytics & Forecasting（方向五）+ 整合发布 | P1 | 2026 Q4 |

---

## 关键架构变化

| 变化 | 原因 |
|------|------|
| Long-running agent runtime | Agent 工作流跨 session 持久化，需稳定的恢复机制（已有 SqliteSaver 基础） |
| 用户偏好微调 | 用户接受/拒绝 Agent 建议的信号 → 本地维护偏好向量，Agent 推荐时加权 |
| Vector DB 升级评估 | ChromaDB 在 100k+ 候选人规模下查询变慢，评估 LanceDB / Qdrant |
| Background worker 进程独立 | 当前 APScheduler 与 FastAPI 同进程，长程 Agent 会阻塞；评估抽出独立 worker |
| Webhook ingress | ATS / Calendar / Mail 需要接收 webhook，需考虑桌面端反向隧道（ngrok-like） |

---

## 风险与权衡

| 风险 | 缓解措施 |
|------|---------|
| 自主代理 vs 用户控制感 | 所有 destructive 操作强制 HIL；提供"全局暂停"开关 |
| Chrome 插件维护成本 | LinkedIn DOM 频繁改版 → 多套选择器 + 自动错误上报 + 版本灰度 |
| ATS 集成爆炸 | V3 只做 1 个 reference 实现（Greenhouse），其余社区贡献 |
| Webhook 桌面端可达性 | 桌面 App 默认无公网 IP；评估用 Cloudflare Tunnel / 本地 polling 替代 |
| 隐私合规 (sourcing) | 不爬取登录后内容；候选人首次接触必须包含数据来源声明 |
| 模型成本 | 本地优先策略下，sourcing / 序列生成可能耗费大量 LLM 调用 → 引入结果缓存 |

---

## 不在 V3 范围内（明确划线）

- **移动 App (iOS / Android)** — 推迟到 V4
- **Marketplace / Plugin 商店** — 评估社区需求后再定
- **新增语言** — 现有 6 语言够用（en / zh / zh-TW / ja / ko / es）
- **多租户 SaaS 部署** — 保持 local-first，self-hosted 模式作为可选
- **视频面试录制** — 只做转写，不做录制
- **薪酬数据爬取** — 法律风险高，仅使用公开数据集

---

## 设计原则（沿袭 V1/V2 并强化）

1. **Local-first**：默认本地推理；云端 API 只作为可选增强
2. **Privacy by default**：候选人 PII 永不离开用户设备，除非用户明确同意
3. **Human-in-the-loop**：自主性提升不等于失控，所有破坏性操作必须可审批
4. **Graceful degradation**：任何外部集成（ATS / Calendar / 云 LLM）失败都不能 break 核心流程
5. **观测优先**：每个 Agent 行为可追溯、可回放、可调试（LangGraph 自带的 thread 支持是基础）
