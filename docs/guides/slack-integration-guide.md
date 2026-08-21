# Open Recruiter — Slack Integration Guide

This guide walks you through connecting Open Recruiter to your Slack workspace, enabling resume submission directly in a Slack channel with automatic parsing and job matching.

---

## Table of Contents

1. [Feature Overview](#feature-overview)
2. [Prerequisites](#prerequisites)
3. [Step 1: Create a Slack App](#step-1-create-a-slack-app)
4. [Step 2: Configure Bot Permissions](#step-2-configure-bot-permissions)
5. [Step 3: Obtain Tokens and Signing Secret](#step-3-obtain-tokens-and-signing-secret)
6. [Step 4: Configure Open Recruiter](#step-4-configure-open-recruiter)
7. [Step 5: Set Up Event Subscriptions](#step-5-set-up-event-subscriptions)
8. [Step 6: Enable Interactivity](#step-6-enable-interactivity)
9. [Step 7: Install the App to Your Workspace](#step-7-install-the-app-to-your-workspace)
10. [Step 8: Create the Intake Channel](#step-8-create-the-intake-channel)
11. [Verify the Connection](#verify-the-connection)
12. [Usage](#usage)
13. [FAQ](#faq)

---

## Feature Overview

Once integrated with Slack, Open Recruiter provides the following capabilities:

- **File Upload Parsing** — Upload resume files (PDF / DOCX / DOC / TXT) in a designated channel; the bot automatically downloads and parses them
- **Text Paste Parsing** — Paste resume text directly into the channel (>50 characters); the bot automatically detects and ingests it
- **Candidate Summary Reply** — After parsing, the bot replies in a message thread with a candidate summary (name, title, skills, matching jobs, etc.)
- **Automatic Deduplication** — Deduplicates by email address; repeated submissions update the existing record
- **Job Matching** — Automatically matches candidates to the best-fit jobs via vector similarity, displaying the Top 3 matches in the summary
- **Privacy Filtering** — Automatically strips sensitive PII such as SSN, passport numbers, and driver's license numbers

---

## Prerequisites

- Open Recruiter backend is deployed and accessible via a public URL (or use a tunneling tool like ngrok)
- You have admin privileges for the target Slack workspace (required to install the app)
- The backend listens on `http://localhost:8000` by default

---

## Step 1: Create a Slack App

1. Go to [Slack API - Your Apps](https://api.slack.com/apps)
2. Click **Create New App**
3. Select **From scratch**
4. Fill in the details:
   - **App Name**: `Open Recruiter` (or any name you prefer)
   - **Pick a workspace**: Select your target workspace
5. Click **Create App**

---

## Step 2: Configure Bot Permissions

In the App management page, navigate to **OAuth & Permissions** in the left sidebar. Under **Bot Token Scopes**, add the following permissions:

| Scope | Purpose |
|-------|---------|
| `chat:write` | Send messages (candidate summary replies) |
| `files:read` | Read uploaded resume files |
| `channels:history` | Read messages in public channels |
| `groups:history` | Read messages in private channels (if using private channels) |
| `channels:read` | Access channel information |
| `im:history` | Read direct messages (optional) |

---

## Step 3: Obtain Tokens and Signing Secret

You need to collect 3 key credentials:

### 3.1 Signing Secret

1. In the App management page, navigate to **Basic Information**
2. Find the **App Credentials** section
3. Copy the **Signing Secret**

### 3.2 Bot User OAuth Token

1. Navigate to **OAuth & Permissions**
2. Click **Install to Workspace** (if not already installed)
3. After authorization, copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 3.3 App-Level Token (Optional)

If you need Socket Mode:
1. Navigate to **Basic Information**
2. Scroll to **App-Level Tokens**
3. Click **Generate Token and Scopes**, add the `connections:write` scope
4. Copy the generated token (starts with `xapp-`)

---

## Step 4: Configure Open Recruiter

### Option A: Environment Variables

Add the following to your `.env` file:

```bash
# Slack Integration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_APP_TOKEN=xapp-your-app-token          # Optional, used for Socket Mode
SLACK_INTAKE_CHANNEL=C0123456789              # Optional, restrict to a specific channel ID
```

### Option B: Settings Page

1. Open the Open Recruiter frontend
2. Go to the **Settings** page
3. Enter the credentials in the Slack configuration section
4. Click Save

> **Note**: `SLACK_INTAKE_CHANNEL` requires the channel **ID**, not the channel name. To find the ID: right-click the channel name in Slack → Copy link — the string at the end of the URL is the channel ID. If left empty, the bot will listen on all channels it has been invited to.

---

## Step 5: Set Up Event Subscriptions

1. In the App management page, navigate to **Event Subscriptions**
2. Toggle **Enable Events** on
3. Enter the **Request URL**:

```
https://your-domain.com/slack/events
```

> For local development, use ngrok: `ngrok http 8000`, then enter `https://xxxx.ngrok.io/slack/events`

4. Slack will send a verification challenge; Open Recruiter handles this automatically (URL Verification)
5. Under **Subscribe to bot events**, add the following:

| Event | Purpose |
|-------|---------|
| `message.channels` | Listen for messages in public channels |
| `message.groups` | Listen for messages in private channels |
| `file_shared` | Listen for file upload events |

6. Click **Save Changes**

---

## Step 6: Enable Interactivity

1. Navigate to **Interactivity & Shortcuts**
2. Toggle **Interactivity** on
3. Enter the **Request URL**:

```
https://your-domain.com/slack/interactions
```

4. Click **Save Changes**

---

## Step 7: Install the App to Your Workspace

1. Navigate to **Install App**
2. Click **Install to Workspace** (or **Reinstall to Workspace** if previously installed)
3. Click **Allow** on the authorization page

---

## Step 8: Create the Intake Channel

1. Create a dedicated channel in your Slack workspace, e.g. `#open-recruiter-intake`
2. Invite the bot to the channel: type `/invite @Open Recruiter` in the channel
3. Copy the channel ID and set it as `SLACK_INTAKE_CHANNEL`
4. Restart the Open Recruiter backend for the configuration to take effect

---

## Verify the Connection

### Via API

```bash
curl -X POST http://localhost:8000/api/settings/test-slack
```

Successful response example:

```json
{
  "status": "ok",
  "bot_user": "open_recruiter",
  "team": "Your Workspace"
}
```

### Via Slack

Upload a resume PDF in the intake channel. The bot should reply in the message thread with a candidate summary.

---

## Usage

### Uploading Resume Files

Upload files directly in the intake channel. Supported formats:
- `.pdf`
- `.docx` / `.doc`
- `.txt`

The bot will automatically process the file and reply with the parsed result in a thread.

### Pasting Resume Text

Paste the full resume text directly in the intake channel (minimum 50 characters). The bot will automatically detect and process it.

### Bot Reply Content

After successful parsing, the bot replies in the message thread with a summary card containing:

- Candidate name
- Current title and company
- Years of experience
- Skills
- Resume summary
- Top 3 matching jobs (with match percentage)
- Candidate ID

---

## FAQ

### Q: The bot is not responding to messages?

1. Confirm the bot has been invited to the target channel
2. Verify that `SLACK_INTAKE_CHANNEL` is set to the correct channel ID
3. Check that the Event Subscriptions Request URL is reachable
4. Review backend logs to confirm whether Slack webhook requests are being received

### Q: Getting "Slack bot not configured"?

`SLACK_BOT_TOKEN` or `SLACK_SIGNING_SECRET` is missing or empty. Check your `.env` file or the Settings page.

### Q: Getting "Unsupported file type" after uploading a file?

Only `.pdf`, `.docx`, `.doc`, and `.txt` formats are supported. Other formats (e.g. images, Excel) are not currently supported.

### Q: How do I test in a local development environment?

Use ngrok to expose your local server to the internet:

```bash
ngrok http 8000
```

Enter the generated HTTPS URL as the Request URL in both Event Subscriptions and Interactivity settings of your Slack App.

### Q: Do I need to update the URL after every redeployment?

If you deploy with a fixed domain (e.g. `recruiter.example.com`), no. If you use ngrok's free tier, a new URL is generated each time ngrok restarts, and you'll need to update the Slack App configuration accordingly.

---

## Architecture Reference

```
Slack Workspace
  └── #open-recruiter-intake channel
        │
        ▼  (User uploads resume / pastes text)
Slack Events API
        │
        ▼  POST /slack/events
Open Recruiter Backend
  ├── slack/routes.py          ← Receives webhooks
  ├── slack/bot.py             ← Slack Bolt App initialization
  ├── slack/handlers.py        ← Event handlers (messages, files)
  ├── slack/pipeline.py        ← Three-stage ingestion pipeline
  │     ├── Stage 1: Resume Parsing (PDF/text extraction + LLM structured parsing)
  │     ├── Stage 2: Profile Normalization (name casing, skill canonicalization, phone formatting)
  │     └── Stage 3: Privacy Filter (strip PII)
  └── slack/notifier.py        ← Slack reply (candidate summary card)
```
