# Testing Guide
<!-- last-verified: 2026-02-15 -->

## Core Principle: You Can Test Everything Yourself

**This is the most important principle in this codebase. Protect it.**

You (Claude) have full ability to test AI conversation flows, message routing, and UI changes without human intervention. The simulation layer exists so that every change you make can be verified before reporting "done." Never rely on the user to test via WhatsApp — simulate it yourself, read the logs, and confirm correctness.

### What This Means in Practice
- After changing AI behavior (prompts, tools, flows) → simulate conversations via `/admin/simulate` or the API and verify the response
- After changing routing logic → simulate messages to different recipients and check the `case` field
- After changing UI → use Playwright to screenshot staging and verify
- After any change → run `pytest` to check for regressions
- If you add a new feature that can't be tested by you, you MUST also add the testability infrastructure (endpoint, eval, etc.) so that it can be

### What to Protect
- The simulation endpoints (`app/api/v1/simulate.py`) must stay functional. If you refactor `MessageRouter.route_message()`, ensure simulation still works.
- The eval tests (`tests/evals/`) must stay passing. If you change AI tools or flows, update the evals.
- The staging environment must stay deployable. If you add new env vars, update `render-staging.yaml`.
- The admin logs integration must stay functional. Tracing via `@traced` decorator is how you debug AI behavior — don't remove or break it.
- Never introduce a code path that can only be tested via real WhatsApp. Every flow must be simulatable.

## Message Simulation

**You have the ability to test AI conversation flows without real WhatsApp.** Use this proactively whenever you change AI behavior, routing logic, prompts, tools, or onboarding flows. Do not rely on the user to test via WhatsApp — simulate it yourself.

### How It Works
The simulation API calls the **real** `MessageRouter.route_message()` with `WhatsAppClient(mock_mode=True)`. Everything is real (DB writes, OpenAI calls, state machines) except Twilio delivery. Multi-turn conversations work automatically — same sender+recipient accumulates conversation state.

### Simulation Endpoints (non-production only)
- `POST /api/v1/simulate/message` — Send a simulated message
- `GET /api/v1/simulate/recipients` — List available recipient numbers
- Both require admin auth (`Authorization: Bearer <admin_token>`)
- Endpoints **do not exist** when `APP_ENV=production` (returns 404)

### Option A: Simulate via Playwright (preferred for visual debugging)
```
1. Navigate to the admin simulate page (staging or local)
2. Log in with admin credentials
3. Select a recipient (Parlo Central for onboarding, business number for customer/staff)
4. Enter a sender phone number
5. Type messages and observe AI responses + routing metadata badges
6. After testing, check the Logs tab for the full execution trace
```

**Staging URL:** `https://parlo-staging-frontend.onrender.com/admin/simulate`
**Local URL:** `http://localhost:3000/admin/simulate`

### Option B: Simulate via curl (for quick checks)
```bash
# 1. Get admin token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"password":"YOUR_ADMIN_PASSWORD"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Send a simulated message
curl -X POST http://localhost:8000/api/v1/simulate/message \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "sender_phone": "+525512345678",
    "recipient_phone": "+14155238886",
    "message_body": "Hola, quiero registrar mi negocio",
    "sender_name": "Test User"
  }'

# 3. List available recipients
curl http://localhost:8000/api/v1/simulate/recipients \
  -H "Authorization: Bearer $TOKEN"
```

### When to Simulate
- **After changing AI prompts** (`app/ai/prompts.py`) — verify the AI still responds correctly
- **After changing tools** (`app/ai/tools.py`) — verify tools are called and produce correct DB state
- **After changing routing** (`app/services/message_router.py`) — verify messages route to correct handlers
- **After changing onboarding** (`app/services/onboarding.py`) — walk through the onboarding flow
- **After changing customer flows** (`app/services/customer_flows.py`) — test booking/cancel/modify
- **Before reporting a bug fix as done** — reproduce the original issue, apply fix, simulate again

### Reading the Response
The simulate endpoint returns:
```json
{
  "message_id": "sim_abc123",
  "status": "success",
  "case": "5",
  "route": "business_whatsapp",
  "response_text": "¡Hola! ...",
  "sender_type": "customer",
  "organization_id": "uuid..."
}
```

## Debugging with Admin Logs

After simulating a message, **always check the Logs tab** to understand what happened internally:

1. **Navigate to `/admin/logs`** (via Playwright or browser)
2. **Find the phone number** you used in the simulation — it appears as a row
3. **Expand the phone number** → see the correlation timeline (each message = one correlation)
4. **Expand a correlation** → see the trace waterfall:
   - `route_message` → which routing case was selected
   - `_handle_end_customer` / `_handle_business_management` / etc. → which handler ran
   - `_process_with_tools` → the AI tool-calling loop
   - `_execute_tool` entries → each AI tool call with `input_summary.tool_name`
   - `send_text_message` → the outbound WhatsApp (mocked in simulation)
5. **Click any trace** → see full input/output JSON, duration, and errors

**What to look for:**
- Red traces = errors (check `error_type` and `error_message`)
- Orange durations = slow calls (>500ms for traces, >2s for correlations)
- `ai_tool` traces tell you exactly which tools the AI decided to call and what arguments it used
- If the AI didn't call the expected tool, check the prompt and tool definitions

## Eval Tests (Automated Regression Testing)

```bash
# Run all evals (requires real OPENAI_API_KEY + test database)
pytest tests/evals/ --run-evals -v

# Regular pytest skips evals automatically
pytest  # evals show as SKIPPED
```

Evals test end-to-end flows: seed data → simulate messages → assert DB state. They verify tool calls happened and produced correct outcomes (appointments created/cancelled, orgs created, etc.). They do NOT assert on response text wording (non-deterministic).

**Current eval coverage:**
- `test_customer_booking.py` — Customer books appointment (happy path)
- `test_customer_cancel.py` — Customer cancels existing appointment
- `test_customer_reschedule.py` — Customer reschedules appointment
- `test_staff_schedule.py` — Staff checks their schedule
- `test_business_onboarding.py` — New business onboarding (2 tests)

## Visual Verification (via Playwright)

All UI testing should be done **directly in production/staging** via Playwright MCP, not on localhost.

### Mandatory Steps
1. **After completing any UI change**, deploy and use Playwright MCP to verify:
   - Navigate to the relevant page
   - Take a screenshot
   - Analyze: Does it match the intended design? Are there errors?

2. **If something is broken**:
   - Check browser console for errors
   - Fix the issue, deploy
   - Re-verify with another screenshot
   - Repeat until it works

3. **Only report "done" when**:
   - The UI renders correctly (screenshot confirms)
   - No console errors
   - Interactive elements work (click through flows if needed)

4. **Clean up after testing**:
   - Delete any screenshot files saved to the repo directory after verification
   - Screenshots are for transient verification only — never commit them

### URLs for Testing
**Production:**
- Admin Dashboard: `https://parlo-frontend.onrender.com/admin`
- Business Login: `https://parlo-frontend.onrender.com/login`
- Business Dashboard: `https://parlo-frontend.onrender.com/schedule`

**Staging (preferred for testing changes before production):**
- Admin Dashboard: `https://parlo-staging-frontend.onrender.com/admin`
- Simulate: `https://parlo-staging-frontend.onrender.com/admin/simulate`

## Debugging Workflow

### Investigation Approach
When investigating bugs, always check the full call chain from entry point to database layer before reporting findings. Don't stop at the first suspicious code — trace the complete flow.

### Standard Workflow
1. **Reproduce via simulation** — Use the simulate endpoint or UI to trigger the bug
2. **Read the logs** — Check `/admin/logs` for the trace waterfall of the failed request
3. **Identify the failing trace** — Look for red (error) traces or unexpected tool calls
4. **Read the code** — Follow the call chain from the trace back to the source
5. **Fix and re-simulate** — Apply the fix, simulate the same message sequence, verify the fix
6. **Check evals** — Run `pytest tests/evals/ --run-evals` to ensure no regressions

### Summarizing Findings
For debugging sessions, summarize findings with:
1. **Root cause identified** — What is actually causing the issue
2. **Files affected** — All files involved in the bug
3. **Proposed fix** — Specific changes to make
4. **How to verify** — Steps to confirm the fix works

### Quick Tips
- Webhook logs show incoming message format
- WhatsApp webhook must respond within 20 seconds
- Check tool call format if AI seems stuck
- Admin dashboard has conversation viewer for debugging
- **Admin Logs** (`/admin/logs`): View function execution traces with latencies
- **Simulate tab** (`/admin/simulate`): Test any message flow without real WhatsApp

## What NOT to Do
- Never say "done" without verifying the change yourself (simulate, screenshot, or test)
- Never assume code changes work just because there are no type errors
- Never skip testing interactive flows (buttons, forms, navigation)
- Never test UI only on localhost — always verify on staging/production
- Never skip simulation testing after changing AI behavior, prompts, or tools
- Never introduce a feature that only the user can test — always add testability
- Never break the simulation layer, eval tests, or tracing infrastructure
