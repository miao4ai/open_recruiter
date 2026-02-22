# Open Recruiter V2.0 Roadmap

> V1.x 聚焦于核心招聘工作流（职位管理、候选人管理、AI 匹配、邮件外联）。
> V2.0 将从「工具」进化为「平台」，围绕四大方向展开。

---

## 方向一：Recruiter Chrome Extension — LinkedIn 候选人采集

### 目标
Recruiter 在浏览 LinkedIn 时，一键将候选人档案保存到 Open Recruiter 系统中。

### 核心功能
| 功能 | 说明 |
|------|------|
| 一键保存 Profile | 在 LinkedIn 个人主页点击插件按钮，自动提取并保存候选人信息 |
| 批量保存 | 在 LinkedIn 搜索结果页，勾选多个候选人批量导入 |
| 去重标记 | 已保存的候选人显示标记，避免重复采集 |
| 自动匹配 | 保存后自动与系统中的职位进行向量匹配 |

### 技术方案
```
┌─────────────────────────┐       ┌───────────────────────┐
│  Chrome Extension        │       │  Open Recruiter API   │
│                          │       │                       │
│  Content Script          │──────▶│  POST /api/candidates │
│  (解析 LinkedIn DOM)     │  REST │  GET  /api/candidates/│
│                          │       │       check?url=xxx   │
│  Popup UI (状态/设置)    │       │                       │
│  Background Service Worker│       └───────────────────────┘
└─────────────────────────┘
```

- **Manifest V3** — Chrome 强制要求
- **最小权限** — 仅申请 `linkedin.com` host permission
- **Token 认证** — 插件登录 Open Recruiter 账号后获取 token
- **DOM 选择器维护** — LinkedIn 频繁改版，需做多套 fallback 选择器 + 错误上报

### 需提取的字段
姓名、当前职位、公司、地点、工作经历、教育背景、技能、LinkedIn URL、头像

### 后端新增 API
- `POST /api/candidates/from-extension` — 接收插件提交的候选人数据
- `GET /api/candidates/check?linkedin_url=xxx` — 去重检查

### 文件结构
```
chrome-extension/
├── manifest.json
├── content.js          # 注入 LinkedIn 页面，解析 DOM
├── background.js       # Service Worker，API 通信
├── popup.html/js       # 插件弹窗 UI
├── styles.css
└── icons/
```

---

## 方向二：Job Seeker Chrome Extension — 职位采集

### 目标
Job Seeker 在浏览招聘网站时，一键将职位信息保存到 Open Recruiter 的 My Jobs 中。

### 核心功能
| 功能 | 说明 |
|------|------|
| 一键保存职位 | 在 LinkedIn Jobs / Indeed / Glassdoor 等页面一键保存 |
| 多平台支持 | 适配主流招聘网站的 DOM 结构 |
| 去重检测 | URL 或 title+company 去重，已保存职位显示标记 |
| 自动匹配 | 保存后自动与用户简历进行 AI 匹配打分 |
| 申请状态追踪 | 保存时标记申请状态（收藏 / 已投 / 面试中） |

### 支持的平台（优先级排序）
1. LinkedIn Jobs
2. Indeed
3. Glassdoor
4. 其他（通过通用解析 + LLM 提取）

### 需提取的字段
职位标题、公司名、地点、薪资范围、职位描述、发布日期、来源 URL

### 后端新增 API
- `POST /seeker/jobs/from-extension` — 接收插件提交的职位数据
- 复用现有 `GET /seeker/jobs/saved-urls` 做去重状态

### 与方向一共享
Recruiter Extension 和 Job Seeker Extension 可以合并为**同一个插件**，根据用户角色（Recruiter / Job Seeker）切换功能面板。

---

## 方向三：AI Native — 基于 LangChain 重构 AI 层

### 目标
将现有散落的 LLM 调用统一迁移到 LangChain 框架，实现更强的 AI Agent 能力。

### 重构范围

| 现有模块 | 当前实现 | LangChain 迁移方案 |
|----------|---------|-------------------|
| 简历解析 | 直接调用 LLM API | LangChain Structured Output + Parser |
| AI 匹配分析 | Prompt + LLM API | LangChain Chain (Retrieval + Analysis) |
| Bot Chat | SSE Streaming + 手动 context | LangChain Agent + Memory + Tools |
| 邮件生成 | Prompt template | LangChain PromptTemplate + Chain |
| 职位解析 | 直接调用 LLM API | LangChain Document Loader + Parser |

### 新增 AI 能力
| 能力 | 说明 |
|------|------|
| Agent with Tools | Bot 可以直接执行操作（创建职位、发邮件、更新 pipeline） |
| RAG 增强 | 基于 ChromaDB 的检索增强生成，回答基于实际数据 |
| Multi-step Reasoning | 复杂任务拆解（如「帮我找适合这个职位的前 3 名候选人并发邮件」） |
| Conversation Memory | LangChain Memory 管理多轮对话上下文 |
| Provider 无关 | 通过 LangChain 统一接口，轻松切换 Anthropic / OpenAI / 本地模型 |

### 技术选型
- **LangChain Core** — Chain / Agent / Memory / Tools 基础框架
- **LangSmith**（可选）— 调试和监控 AI 调用链路
- **LangGraph**（可选）— 复杂多步骤 Agent 工作流

---

## 方向四：Voice 语音功能

### 目标
支持语音交互，让用户可以通过语音与 AI 助手对话，以及语音录入信息。

### 核心功能
| 功能 | 说明 |
|------|------|
| 语音输入 | 对着 Bot Chat 说话，自动转文字发送 |
| 语音回复 | AI 回复可朗读（TTS） |
| 语音面试笔记 | 面试时实时语音转文字，自动生成面试记录 |
| 语音指令 | 语音控制常用操作（「保存这个候选人」「发邮件给 HR」） |

### 技术方案
| 组件 | 方案 |
|------|------|
| STT (语音转文字) | Web Speech API（免费）/ Whisper API（更准确） |
| TTS (文字转语音) | Web Speech Synthesis API / ElevenLabs API |
| 前端集成 | React 录音组件 + 实时 waveform 动画 |
| 后端集成 | 语音流 → 转文字 → 送入 LangChain Agent → 回复 → TTS |

### 与 LangChain 的联动
语音指令通过 STT 转文字后，直接进入 LangChain Agent 处理，实现语音驱动的 AI 工作流。

---

## 版本规划

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| V2.0-alpha | LangChain 重构 AI 层（方向三） | P0 |
| V2.0-beta | Chrome Extension — Recruiter + Job Seeker（方向一 & 二） | P0 |
| V2.0-rc | Voice 语音输入/输出（方向四） | P1 |
| V2.0 | 全部功能集成、测试、发布 | — |

> LangChain 重构放在最前面，因为方向四的语音功能依赖 LangChain Agent 作为处理管道。
