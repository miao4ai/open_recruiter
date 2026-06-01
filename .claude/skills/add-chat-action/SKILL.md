---
name: add-chat-action
description: Add a new chat action (intent → handler → UI card) to Open Recruiter. Use when the user wants to introduce a new chat-triggered behavior like "evaluate candidate", "check inbox", "generate report", etc.
---

# Add a New Chat Action

Touches 6 files in this order. Follow the order — later steps depend on earlier ones being wired correctly.

## 1. Whitelist the action (backend/app/routes/agent.py)

If it's a job-seeker action, add to:
```python
_SEEKER_ALLOWED_ACTIONS = {"search_jobs", ..., "<new_action>"}
```
Recruiter actions don't need whitelisting (default).

## 2. Handler in agent.py

Add an `elif action_type == "<new_action>":` block inside `_process_actions()`. Pattern:
```python
elif action_type == "<new_action>":
    try:
        from app.agents.<your_module> import <your_func>
        param = action_data.get("param", "")
        result = <your_func>(cfg, param)
        response["reply"] = "..."
        response["blocks"].append({"type": "<block_type>", ...})
        response["suggestions"] = [...]
    except Exception as e:
        log.error("Failed to run <new_action>: %s", e)
        response["reply"] = f"Sorry, I encountered an error: {e}"
```

## 3. Trigger phrases in backend/app/prompts.py

Edit `CHAT_SYSTEM_WITH_ACTIONS` (recruiter) or `CHAT_SYSTEM_JOB_SEEKER` (seeker). Add a section:
```
When the user asks to <X> (e.g. "<trigger 1>", "<trigger 2>", "<中文 trigger>"), return:
{{
  "message": "...",
  "action": {{"type": "<new_action>", "param": "..."}}
}}
```

## 4. (Optional) Keyword fallback in agent.py

For Ollama / weak local models, add to `_detect_action_from_keywords()`:
```python
if re.search(r"<pattern>", msg):
    return {"type": "<new_action>", "param": ""}
```

## 5. Block type in frontend/src/types/index.ts

```typescript
export interface <YourBlock>Block {
  type: "<block_type>";
  // ...fields
}
```
Add to the `MessageBlock` union at the bottom:
```typescript
export type MessageBlock = ... | <YourBlock>Block;
```

## 6. Render card in frontend/src/components/MessageBlocks.tsx

- Import the new block type
- Add dispatch case:
  ```tsx
  if (block.type === "<block_type>") {
    return <YourCard key={i} block={block} onSendPrompt={onSendPrompt} />;
  }
  ```
- Add the `YourCard` component at the bottom of the file

## 7. Tests

Add intent test cases to `tests/harness/test_intent_detection.py`. For each new keyword phrase, assert it maps to the expected action.

Run: `cd backend && uv run python -m pytest ../tests/harness/ -q`

## Verification checklist

- [ ] Frontend type-checks: `cd frontend && npx tsc --noEmit`
- [ ] Backend tests pass: `cd backend && uv run python -m pytest ../tests/harness/ -q`
- [ ] Manual: trigger the phrase in chat, verify the card renders, verify any side effects (DB write, email, etc.)
