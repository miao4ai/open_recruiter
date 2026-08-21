# Open Recruiter — Product Features

## 1. Job Management

| Feature | Description |
|---------|-------------|
| Create Job | Input title, company, posted date, and full job description |
| Edit / Delete | Inline editing with live save; one-click delete |
| Matched Candidates | Each job card shows how many candidates match (vector similarity >= 30%) |
| Email to Company | Send candidate recommendation emails directly from the job card, with resume attachment |

## 2. Candidate Management

| Feature | Description |
|---------|-------------|
| Resume Upload | Supports PDF, DOCX, TXT; auto-extracts name, email, skills, experience via LLM |
| Duplicate Detection | Rejects upload if name + email already exists in database |
| Candidate Profile | Detailed view with contact info, skills, linked job, notes |
| Inline Editing | Edit all candidate fields including linked job and skills |
| Delete Candidate | Remove candidate from database and vector store |
| Job Linking | Link candidates to jobs during upload or via profile editing |

## 3. AI Match Analysis

| Feature | Description |
|---------|-------------|
| Vector Matching | Semantic similarity using ChromaDB + BAAI/bge-small-en-v1.5 embeddings |
| Auto-Match | Automatically scores candidates against linked jobs on upload/edit |
| Deep Analysis | One-click LLM-powered analysis returning score, strengths, gaps, and reasoning |
| Typewriter Effect | Analysis results stream in with character-by-character animation |
| Job Selector | If no job is linked, pick any job to match against on-demand |
| Ranked Candidates | Email modal shows all candidates sorted by match score for a given job |

## 4. Email Outreach

| Feature | Description |
|---------|-------------|
| Compose to Company | Pre-filled email template referencing job title and company |
| Candidate Selection | Dropdown with all candidates ranked by match score |
| Resume Attachment | Attach candidate's uploaded resume or upload a new PDF |
| Draft / Send | Save as draft for review or send immediately via SMTP |
| Email History | Per-candidate communication timeline on profile page |
| Pending Queue | Outreach page shows all drafts awaiting approval/send |

## 5. Dashboard

| Feature | Description |
|---------|-------------|
| Stat Cards | Active jobs, total candidates, pending emails, scheduled interviews |
| Pipeline Kanban | Visual board with columns: New, Contacted, Screening, Interview, Offer, Hired, etc. |
| Recent Activity | Real-time feed combining job creation, candidate uploads, and email events |

## 6. Bot Chat

| Feature | Description |
|---------|-------------|
| Context-Aware | AI assistant has access to your jobs, candidates, and email data |
| Conversation History | Persistent chat history per user with clear option |
| Use Cases | Analyze candidate fit, draft outreach strategies, discuss interview planning |

## 7. Settings

| Feature | Description |
|---------|-------------|
| LLM Provider | Switch between Anthropic Claude and OpenAI; configure model and API key |
| SMTP Config | Email host, port, username, password for outreach sending |
| Connection Test | One-click test buttons for LLM and email connectivity |

## Architecture Overview

```
Browser (React + TailwindCSS)
    │
    ▼ REST API
FastAPI Backend
    ├── SQLite ──── Structured data (jobs, candidates, emails, users)
    ├── ChromaDB ── Vector embeddings (semantic search)
    └── LLM API ── Resume parsing, match analysis, chat (Anthropic / OpenAI)
```

## Key Technical Decisions

- **Local embeddings** (bge-small-en-v1.5) — No API cost for vector matching; runs on CPU
- **Vector + LLM two-stage matching** — Fast vector pre-filter, then optional deep LLM analysis
- **SQLite + ChromaDB** — Zero infrastructure; both persist to local files
- **Upsert pattern** — Editing jobs/candidates automatically re-indexes vectors
- **Match threshold 0.30** — Cosine similarity cutoff for counting matched candidates
