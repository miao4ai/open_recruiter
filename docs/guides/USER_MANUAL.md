# Open Recruiter — User Manual

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Recruiter Guide](#recruiter-guide)
3. [Job Seeker Guide](#job-seeker-guide)
4. [Settings & Configuration](#settings--configuration)
5. [Background Automations](#background-automations)
6. [Desktop App](#desktop-app)
7. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Creating an Account

1. Open the application in your browser (http://localhost:5173) or launch the desktop app
2. Click **Register** and choose your role:
   - **Recruiter** — Full access to job management, candidate tracking, email outreach, and AI assistant
   - **Job Seeker** — Upload your resume, search for matching jobs, and chat with an AI career assistant
3. Enter your name, email, and password
4. Complete the onboarding wizard to configure your AI provider

### Onboarding (First-Time Setup)

After registration, you'll be guided through:

1. **Choose LLM Provider** — Select Anthropic (Claude), OpenAI (GPT), or Google (Gemini)
2. **Enter API Key** — Paste your API key. Use the "Test Connection" button to verify
3. **Email Setup** (Recruiter only, optional) — Configure Gmail, SMTP, or SendGrid for outreach
4. Click **Get Started** to enter the application

---

## Recruiter Guide

### Managing Jobs

- Navigate to **Jobs** from the sidebar
- Click **New Job** to create a job posting manually
- Upload a PDF/DOCX job description — the AI will auto-extract title, company, skills, and requirements
- Each job card shows the number of matched candidates (vector similarity >= 30%)

### Managing Candidates

- Navigate to **Candidates** from the sidebar
- Click **Import Resume** to upload a candidate's resume (PDF, DOCX, or TXT)
- The AI automatically extracts: name, email, phone, title, company, skills, and experience
- Duplicate detection prevents re-uploading the same candidate
- Click a candidate row to view their full profile, edit fields, and see match analysis

### AI Match Analysis

- On a candidate's profile, click **Generate Analysis** to run an AI-powered match against their linked job
- The analysis returns: match score (0-100%), strengths, gaps, and detailed reasoning
- Results stream in with a typewriter effect
- All candidates are ranked by match score on the job page

### Email Outreach

- From a candidate's profile, click **Send Email** to compose a personalized outreach email
- The AI drafts the email using the candidate's resume and job context
- Workflow: Draft → Approve → Send
- Configure reply detection via IMAP in Settings to automatically track responses

### Pipeline Kanban

- Available in the Chat page sidebar
- Columns: New → Contacted → Replied → Screening → Interview → Offer → Hired
- Drag and drop candidate cards between stages
- Match scores are displayed on each card

### Bot Chat (Erika Chan)

- Your AI recruiting assistant on the main Chat page
- Understands your jobs, candidates, and email data
- Can draft emails, upload resumes, start multi-step workflows, and match candidates
- Supports multi-session conversations with memory
- Workflow types: Bulk Outreach, Candidate Review, Interview Scheduling, Pipeline Cleanup, Job Launch

### Calendar

- Schedule interviews, follow-ups, offers, and screening events
- Weekly calendar view with color-coded event types
- Link events to specific candidates and jobs

### Slack Integration

- Receive resumes directly from Slack channels
- Automatic parsing, candidate creation, and duplicate detection
- PII privacy filtering (SSN, passport, driver's license)
- Top 3 job match suggestions posted as threaded replies

---

## Job Seeker Guide

### Your Profile

- Navigate to **My Profile** from the sidebar
- Upload your resume (PDF, DOCX, TXT) to auto-generate your profile
- Edit any field: name, email, phone, title, company, skills, experience, and summary
- Your profile is used by the AI to find matching jobs

### Job Search (Ai Chan)

- Chat with **Ai Chan**, your AI career assistant, on the Home page
- Ask things like "Find me jobs matching my profile" or "Search for React developer positions"
- Ai Chan searches the web for matching positions and presents results with:
  - Match score, strengths, and gaps analysis
  - Direct links to the original job postings
- Save interesting jobs to your **My Jobs** list

### Saved Jobs

- Navigate to **My Jobs** from the sidebar
- Upload job descriptions (PDF/DOCX) to track positions
- View full job details, required skills, and salary information

---

## Settings & Configuration

Access Settings from the sidebar (Recruiter only).

### LLM Provider

| Setting | Description |
|---------|-------------|
| Provider | Anthropic (Claude), OpenAI (GPT), or Google (Gemini) |
| Model | Select the specific model version |
| API Key | Your provider API key (stored locally, never shared) |

Use **Test LLM** to verify your configuration.

### Email Backend

| Backend | Setup |
|---------|-------|
| Console | Development only — prints emails to terminal |
| Gmail | Enter your Gmail App Password (requires 2-Step Verification) |
| Custom SMTP | Enter host, port, username, and password |
| SendGrid | Enter your SendGrid API key |

Use **Test Email** to verify delivery.

### IMAP (Reply Detection)

Configure IMAP to automatically detect when candidates reply:
- Host (e.g., `imap.gmail.com`), Port (993), Username, Password
- The Inbox Scanner automation uses this to check for replies

### Recruiter Profile

- Name, email, and company used in outreach email personalization

### Language

- Switch between English, Japanese, and Korean

---

## Background Automations

Navigate to **Automations** from the sidebar.

### Available Rules

| Rule | Description | Default Schedule |
|------|-------------|------------------|
| **Auto-Match** | Finds unscored candidates, runs AI matching against all jobs | Every 30 minutes |
| **Inbox Scanner** | Checks IMAP inbox for candidate replies | Every 15 minutes |
| **Auto Follow-Up** | Drafts follow-up emails for non-responsive candidates | Daily at 9:00 AM |
| **Pipeline Cleanup** | Flags stale candidates based on age thresholds | Mondays at 8:00 AM |

### Managing Rules

- Toggle rules on/off with the switch
- Click the pencil icon to edit schedule, conditions, and actions
- Click the play button to trigger a rule immediately
- View execution history at the bottom of the page

### Configuration Examples

**Auto-Match Conditions:**
```json
{"min_score_threshold": 0.3, "job_id": ""}
```

**Auto Follow-Up Conditions:**
```json
{"days_since_contact": 3, "max_followups": 2}
```

**Pipeline Cleanup Actions:**
```json
{"dry_run": true, "reject_after_days": 14, "archive_after_days": 21}
```

---

## Desktop App

### Windows

- Download the installer from [GitHub Releases](https://github.com/miao4ai/open_recruiter/releases)
- Run `Open Recruiter Setup 1.0.0.exe` and follow the installation wizard
- The app creates a desktop shortcut and Start Menu entry
- Data is stored in `%AppData%/OpenRecruiter/`

### Uninstalling

- Use Windows Settings → Apps → Open Recruiter → Uninstall

---

## Troubleshooting

### LLM not responding

- Verify your API key in Settings → Test LLM
- Check that your API key has sufficient credits/quota
- Try switching to a different model

### Emails not sending

- Verify email configuration in Settings → Test Email
- For Gmail: ensure you're using an App Password (not your regular password)
- Check that 2-Step Verification is enabled on your Google account

### Candidates not matching

- Ensure the job has a detailed description with required skills
- Run **Generate Analysis** manually from the candidate profile
- Check that the embedding model loaded (look for startup logs)

### Desktop app won't start

- Check Windows Defender / antivirus is not blocking the app
- Try running as Administrator
- Check the logs in `%AppData%/OpenRecruiter/`
