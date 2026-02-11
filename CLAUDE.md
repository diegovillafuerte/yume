# CLAUDE.md - Parlo Development Guide

## Core Principle: You Can Test Everything Yourself

**This is the most important principle in this codebase. Protect it.**

You (Claude) have full ability to test AI conversation flows, message routing, and UI changes without human intervention. The simulation layer exists so that every change you make can be verified before reporting "done." Never rely on the user to test via WhatsApp — simulate it yourself, read the logs, and confirm correctness.

**What this means in practice:**
- After changing AI behavior (prompts, tools, flows) → simulate conversations via `/admin/simulate` or the API and verify the response
- After changing routing logic → simulate messages to different recipients and check the `case` field
- After changing UI → use Playwright to screenshot staging and verify
- After any change → run `pytest` to check for regressions
- If you add a new feature that can't be tested by you, you MUST also add the testability infrastructure (endpoint, eval, etc.) so that it can be

**What to protect:**
- The simulation endpoints (`app/api/v1/simulate.py`) must stay functional. If you refactor `MessageRouter.route_message()`, ensure simulation still works.
- The eval tests (`tests/evals/`) must stay passing. If you change AI tools or flows, update the evals.
- The staging environment must stay deployable. If you add new env vars, update `render-staging.yaml`.
- The admin logs integration must stay functional. Tracing via `@traced` decorator is how you debug AI behavior — don't remove or break it.
- Never introduce a code path that can only be tested via real WhatsApp. Every flow must be simulatable.

## What is Parlo?

Parlo is a WhatsApp-native AI scheduling assistant for beauty businesses in Mexico. Business owners connect their WhatsApp number, and Parlo handles booking conversations automatically via AI.

**One-liner:** "Connect Parlo to your WhatsApp in 2 minutes. Watch your appointments start booking themselves."

**Full specification:** See `docs/PROJECT_SPEC.md` for detailed requirements, user journeys, and example conversations.

## Quick Reference

```bash
# Start infrastructure
docker-compose up -d              # Postgres + Redis + Celery

# Backend
source .venv/bin/activate
alembic upgrade head              # Run migrations
uvicorn app.main:app --reload     # Start API (port 8000)

# Frontend
cd frontend && npm run dev        # Start Next.js (port 3000)
cd frontend && npm run build      # Build for production

# Celery (for background tasks like reminders)
celery -A app.tasks.celery_app worker --loglevel=info  # Worker
celery -A app.tasks.celery_app beat --loglevel=info    # Scheduler

# Testing
pytest                            # Run all tests
pytest -x                         # Stop on first failure
pytest tests/evals/ --run-evals -v  # Run AI evals (needs real OPENAI_API_KEY)

# Simulation (local dev — requires server running)
# POST /api/v1/simulate/message with admin auth
# GET  /api/v1/simulate/recipients with admin auth

# Database
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1

# Local webhook testing
ngrok http 8000                   # For Twilio webhooks
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         WHATSAPP CHANNELS (Twilio)                        │
├────────────────────────────────┬─────────────────────────────────────────┤
│   PARLO CENTRAL NUMBER          │      BUSINESS NUMBERS (per business)    │
│   - Business onboarding        │      - End customer bookings            │
│   - Business management        │      - Staff management                 │
└────────────────────────────────┴─────────────────────────────────────────┘
                                    │
                                    ▼
              ┌─────────────────────────────────────────┐
              │           FastAPI Backend               │
              │   (Message Router → State Machines)     │
              └──────────────────┬──────────────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
   │  PostgreSQL │      │   OpenAI    │      │   Next.js   │
   │             │      │   gpt-4.1   │      │   Frontend  │
   └─────────────┘      └─────────────┘      └─────────────┘
```

**Three interfaces:**
1. **WhatsApp** - Two channels: Parlo Central (B2B) + Business Numbers (B2C/Staff)
2. **Web Dashboard** - Business owners manage everything (magic link auth)
3. **Admin Dashboard** - Platform management (password auth)

**See `docs/PROJECT_SPEC.md` for complete routing logic, state machines, and permissions.**

**Note:** This is a Python-primary codebase with TypeScript frontend. Always check for import mismatches between services when debugging deployment errors.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Database | PostgreSQL 15+, SQLAlchemy 2.0 (async), Alembic |
| AI | OpenAI gpt-4.1 with function calling |
| WhatsApp | Twilio WhatsApp API |
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| Background | Redis + Celery (appointment reminders) |

## Project Structure

```
parlo/
├── app/                         # Backend
│   ├── main.py                  # FastAPI entry
│   ├── config.py                # Settings
│   ├── api/v1/                  # Endpoints (~72 routes)
│   ├── models/                  # SQLAlchemy (14 models + 2 association tables)
│   ├── schemas/                 # Pydantic schemas
│   ├── services/                # Business logic
│   ├── ai/                      # OpenAI integration
│   └── tasks/                   # Celery tasks (reminders)
├── frontend/                    # Next.js app
│   └── src/
│       ├── app/                 # Pages (13 routes)
│       ├── components/          # UI components
│       ├── lib/api/             # API client
│       └── providers/           # Auth, Location context
├── alembic/                     # Migrations
└── docs/PROJECT_SPEC.md         # Requirements (source of truth)
```

## Core Entities

| Entity | Purpose |
|--------|---------|
| Organization | The business (also stores onboarding state directly) |
| Location | Physical location (1+ per org) |
| Spot | Service station (chair, table) - linked to services |
| ParloUser (Staff) | Employees identified by phone (alias: Staff) |
| ServiceType | What they offer |
| EndCustomer (Customer) | End consumer (incremental identity, alias: Customer) |
| Appointment | Scheduled event |
| Conversation/Message | WhatsApp threads |
| Availability | Staff schedules |
| AuthToken | Magic link tokens (stored as SHA256 hash) |
| StaffOnboardingSession | Tracks staff WhatsApp onboarding progress |
| CustomerFlowSession | Tracks customer conversation flows (booking, cancel, etc.) |
| FunctionTrace | Function execution traces for debugging |

**Key relationships:**
- Staff ↔ ServiceType: many-to-many (what staff can do)
- Spot ↔ ServiceType: many-to-many (what spot supports)
- Appointment requires: customer, service, spot, (optional) staff

## Critical Patterns

### 1. Message Routing (THE CORE)

**⚠️ IMPORTANT: See `docs/PROJECT_SPEC.md` for the complete routing specification (including state machines and permissions).**

Parlo operates two WhatsApp channels:
- **Parlo Central Number** - B2B: business onboarding + management
- **Business Numbers** - B2C: end customers + staff of that specific business

```python
# Simplified routing logic (see full spec for all cases)
if recipient_number == PARLO_CENTRAL_NUMBER:
    registrations = await get_staff_registrations(sender_phone)
    if len(registrations) == 0:
        return handle_business_onboarding(sender_phone, message)
    elif len(registrations) == 1:
        return handle_business_management(registrations[0].business, message)
    else:
        return send_redirect_message("Text your business directly")
else:
    business = await get_business_by_whatsapp_number(recipient_number)
    staff = await get_staff_by_phone(business.id, sender_phone)
    if staff:
        return handle_staff_flow(business, staff, message)
    else:
        customer = await get_or_create_customer(business.id, sender_phone)
        return handle_customer_flow(business, customer, message)
```

**Key routing cases:**
| Case | Recipient | Sender | Route |
|------|-----------|--------|-------|
| 1 | Parlo Central | Unknown | Business Onboarding |
| 2a | Parlo Central | Staff of 1 business | Business Management |
| 2b | Parlo Central | Staff of 2+ businesses | Redirect |
| 3 | Business Number | New staff | Staff Onboarding |
| 4 | Business Number | Known staff | Business Management |
| 5 | Business Number | Anyone else | End Customer |

### 2. Dual Authentication
- **Business owners:** Magic link via WhatsApp → JWT (7 days)
- **Admin:** Password → JWT (shorter expiry)
- Frontend uses different tokens: `auth_token` vs `admin_token`

### 3. Tool-Based AI
AI uses typed tools, never accesses DB directly:
- Customer tools: check_availability, book_appointment, cancel, reschedule
- Staff tools: get_schedule, block_time, mark_complete, book_walk_in

### 4. All Times in UTC
Store UTC, convert to org timezone only for display.

### 5. Webhook Idempotency
Check message_id before processing to handle duplicate deliveries.

## Environment Variables

Backend `.env`:
```bash
APP_ENV=development  # development, staging, production
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/parlo
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
JWT_SECRET_KEY=change-in-production
FRONTEND_URL=http://localhost:3000
ADMIN_MASTER_PASSWORD=change-in-production
```

Frontend `.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_PARLO_WHATSAPP_NUMBER=17759674528
```

## Current Implementation Status

### Fully Implemented
- 14 database models + 2 association tables with proper relationships
- ~72 API endpoints for all resources
- Admin dashboard (stats, org management, impersonation, conversations, activity, function trace logs)
- AI conversation handler with tool calling (customer + staff + onboarding flows)
- Message routing (all 5 routing cases from spec)
- Availability slot calculation with conflict validation
- Magic link authentication (tokens stored as SHA256 hashes)
- Frontend: login, location management, company settings, schedule page
- Schedule page with filtering, appointment actions (complete, no-show, cancel)
- Celery background tasks with 24-hour appointment reminders + trace cleanup
- WhatsApp onboarding flow (business setup via chat with state machine)
- Staff onboarding flow via WhatsApp (state machine tracked in StaffOnboardingSession)
- Customer flow sessions (booking, cancel, modify tracked in CustomerFlowSession)
- Twilio WhatsApp integration (send/receive messages)
- Twilio number provisioning for businesses
- Function-level tracing with @traced decorator and admin log viewer

### Partially Implemented
- WhatsApp template messages (fall back to regular text — need Twilio Content setup)
- Daily schedule summaries (task not yet created)
- New booking notifications to owner (not sent after AI booking)
- handoff_to_human tool (acknowledges but doesn't actually notify owner)
- Staff conversation persistence (each message starts fresh, no history)
- Business hours in AI prompts (returns placeholder, not actual location hours)

### Not Implemented
- Create/Edit appointment modals in dashboard (deferred — most bookings via WhatsApp)
- Custom domain configuration (api.parlo.mx, app.parlo.mx)
- Customer management page in frontend (API exists, no UI)
- Availability management UI in frontend (API exists, no UI)
- AI error recovery (no retry logic for OpenAI API failures)
- Row-level locking for booking (race condition risk on concurrent bookings)
- Sentry/error tracking integration
- send_message_to_customer AI tool

## Key Files

| File | What it does |
|------|--------------|
| `app/api/v1/webhooks.py` | Twilio webhook handler |
| `app/services/message_router.py` | Staff/customer routing (all 5 cases) |
| `app/services/conversation.py` | AI orchestration |
| `app/services/scheduling.py` | Availability calculation + conflict validation |
| `app/services/onboarding.py` | WhatsApp onboarding flow for new businesses |
| `app/services/customer_flows.py` | Customer booking/cancel/modify state machines |
| `app/services/staff_onboarding.py` | Staff WhatsApp onboarding flow |
| `app/services/ai_handler_base.py` | Shared base for AI conversation handlers |
| `app/ai/tools.py` | AI tool definitions + execution (~1590 lines) |
| `app/ai/prompts.py` | System prompts (Spanish) |
| `app/tasks/celery_app.py` | Celery configuration + beat schedule |
| `app/tasks/reminders.py` | 24-hour appointment reminder tasks |
| `app/services/tracing.py` | Function-level tracing decorator |
| `frontend/src/providers/AuthProvider.tsx` | Auth context |
| `frontend/src/lib/api/client.ts` | Axios with dual token handling |
| `app/api/v1/simulate.py` | Simulation endpoints (admin-only, non-production) |
| `app/schemas/simulate.py` | Simulation request/response models |
| `frontend/src/app/admin/simulate/page.tsx` | Simulation chat UI |
| `tests/evals/conftest.py` | Eval fixtures + `simulate_message()` helper |
| `tests/evals/seed_helpers.py` | Seed functions for eval test data |
| `render-staging.yaml` | Render blueprint for staging environment |

## Development Guidelines

### Spanish Only
- All AI responses in Mexican Spanish
- Use "tú" not "usted"
- Currency: MXN, prices as "$150"
- Dates: "viernes 15 de enero"
- Times: "3:00 PM" (12-hour)

### Organization Scoping
Every query must filter by `organization_id` to prevent data leakage.

### Avoid Over-Engineering
- No abstractions for one-time operations
- Simple solutions over complex patterns
- Don't add features beyond what's requested

### Testing
- Use pytest with async support
- Mock external APIs (Twilio, OpenAI)
- Test availability edge cases thoroughly

## Visual Verification (Production via Playwright)

All UI testing should be done **directly in production** via Playwright MCP, not on localhost.

### Mandatory Steps
1. **After completing any UI change**, deploy and use Playwright MCP to verify on production:
   ```
   - Navigate to https://parlo-frontend.onrender.com/admin (or relevant page)
   - Take a screenshot
   - Analyze: Does it match the intended design? Are there errors?
   ```

2. **If something is broken**:
   - Check browser console for errors
   - Fix the issue, deploy
   - Re-verify with another screenshot on production
   - Repeat until it works

3. **Only report "done" when**:
   - The UI renders correctly on production (screenshot confirms)
   - No console errors
   - Interactive elements work (click through flows if needed)

### Example Verification Commands
```
Use Playwright to:
1. Navigate to https://parlo-frontend.onrender.com/admin
2. Take a screenshot
3. Click the "Organizations" tab and screenshot
4. Verify the table loads with data
```

### URLs for Testing
**Production:**
- Admin Dashboard: `https://parlo-frontend.onrender.com/admin`
- Business Login: `https://parlo-frontend.onrender.com/login`
- Business Dashboard: `https://parlo-frontend.onrender.com/schedule`

**Staging (preferred for testing changes before production):**
- Admin Dashboard: `https://parlo-staging-frontend.onrender.com/admin`
- Simulate: `https://parlo-staging-frontend.onrender.com/admin/simulate`

### What NOT to do
- Never say "done" without verifying the change yourself (simulate, screenshot, or test)
- Never assume code changes work just because there are no type errors
- Never skip testing interactive flows (buttons, forms, navigation)
- Never test UI only on localhost — always verify on staging/production
- Never skip simulation testing after changing AI behavior, prompts, or tools
- Never introduce a feature that only the user can test — always add testability
- Never break the simulation layer, eval tests, or tracing infrastructure

## Message Simulation (IMPORTANT — Use This for Testing)

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
  "case": "5",              // Routing case (1, 1b, 2a, 2b, 3, 4, 5)
  "route": "business_whatsapp",  // Handler that processed it
  "response_text": "¡Hola! ...",  // What the AI would have sent via WhatsApp
  "sender_type": "customer",     // How the sender was classified
  "organization_id": "uuid..."   // Which org context was used
}
```

### Debugging with Admin Logs After Simulation

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

### Eval Tests (Automated Regression Testing)

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

## Debugging

### Investigation Approach
When investigating bugs, always check the full call chain from entry point to database layer before reporting findings. Don't stop at the first suspicious code - trace the complete flow.

### Standard Debugging Workflow
1. **Reproduce via simulation** — Use the simulate endpoint or UI to trigger the bug
2. **Read the logs** — Check `/admin/logs` for the trace waterfall of the failed request
3. **Identify the failing trace** — Look for red (error) traces or unexpected tool calls
4. **Read the code** — Follow the call chain from the trace back to the source
5. **Fix and re-simulate** — Apply the fix, simulate the same message sequence, verify the fix
6. **Check evals** — Run `pytest tests/evals/ --run-evals` to ensure no regressions

### Summarizing Findings
For debugging sessions, summarize findings with:
1. **Root cause identified** - What is actually causing the issue
2. **Files affected** - All files involved in the bug
3. **Proposed fix** - Specific changes to make
4. **How to verify** - Steps to confirm the fix works

### Quick Tips
- Webhook logs show incoming message format
- WhatsApp webhook must respond within 20 seconds
- Check tool call format if AI seems stuck
- Admin dashboard has conversation viewer for debugging
- **Admin Logs** (`/admin/logs`): View function execution traces with latencies
- **Simulate tab** (`/admin/simulate`): Test any message flow without real WhatsApp

## Git Workflow

```
feature-branch → PR to staging → CI passes → merge → staging auto-deploys
                                                       ↓
                                              validate on staging
                                                       ↓
                                    staging → PR to main → CI passes → merge → production auto-deploys
```

- CI runs on push/PR to both `main` and `staging` branches
- Evals can be triggered manually via GitHub Actions (`evals.yml` workflow_dispatch)

## Session Workflow

**Starting:**
1. Read `workplan.md` for current status
2. Reference this file for conventions
3. See `docs/PROJECT_SPEC.md` for requirements

**Ending:**
1. Verify backend loads, frontend builds
2. Update `workplan.md` with completed tasks

## Render Deployment Notes

**Deployed on Render (migrated from Railway on 2026-02-01)**

### Infrastructure
- **Backend**: Web Service (Docker) - `parlo-backend`
- **Frontend**: Web Service (Node) - `parlo-frontend`
- **Database**: Render PostgreSQL - `parlo-db`
- **Redis**: Not deployed (Celery workers deferred to save costs)

### Configuration File
Use `render.yaml` (Infrastructure as Code) to deploy all services at once via Render Dashboard → New → Blueprint.

### Backend (FastAPI/Python)
1. **DATABASE_URL format**: Render provides `postgresql://...` via `fromDatabase` - the app automatically adds `+asyncpg` driver
2. **Use start.sh script**: Chaining commands with `&&` in Dockerfile CMD can fail silently. Use a bash script with `set -e` and explicit logging
3. **All env vars required**: Missing `OPENAI_API_KEY`, `JWT_SECRET_KEY` will crash silently - no error in logs
4. **pip install**: Use `pip install .` not `pip install -e .` in Docker (editable mode needs source)
5. **Health check**: Configure `/health` endpoint in Render for monitoring

### Frontend (Next.js)
1. **Use Node runtime**: Set `runtime: node` in render.yaml, not Docker
2. **Root directory**: Set `rootDir: frontend` for monorepo structure
3. **Build command**: `npm install && npm run build`
4. **Start command**: `npm run start`

### Monorepo Setup
- Backend and frontend are separate Render services from the same repo
- Backend uses Docker runtime (root Dockerfile)
- Frontend uses Node runtime with `rootDir: frontend`
- **.gitignore `lib/` trap**: Using `lib/` ignores `frontend/src/lib/`. Use `/lib/` (with leading slash) to only match root level

### Environment Variables (Backend)
```
DATABASE_URL=<from render postgres>  # Auto-configured via fromDatabase
REDIS_URL=""                         # Empty - not using Redis
OPENAI_API_KEY=sk-...               # Set manually in dashboard
JWT_SECRET_KEY=<auto-generated>
ADMIN_MASTER_PASSWORD=<set manually>
FRONTEND_URL=https://parlo-frontend.onrender.com
APP_ENV=production
```

### Environment Variables (Frontend)
```
NEXT_PUBLIC_API_URL=https://parlo-backend.onrender.com/api/v1
```

### Render URLs
**Production:**
- Backend: `https://parlo-backend.onrender.com`
- Frontend: `https://parlo-frontend.onrender.com`
- Admin Dashboard: `https://parlo-frontend.onrender.com/admin`

**Staging:**
- Backend: `https://parlo-staging-backend.onrender.com`
- Frontend: `https://parlo-staging-frontend.onrender.com`
- Admin + Simulate: `https://parlo-staging-frontend.onrender.com/admin/simulate`
- Blueprint file: `render-staging.yaml` (auto-deploys from `staging` branch)
- Seed script: `python scripts/seed_staging.py` (run against staging DB)

### Render CLI
- Load RENDER_API_KEY from .env before running render commands: `export $(grep RENDER_API_KEY .env | xargs)`
- Use `--output json --confirm` for non-interactive mode
- Old service IDs (update after decommissioning yume-* services):
  - Backend: srv-d6006uh4tr6s73a4ctsg
  - Frontend: srv-d6006gh4tr6s73a4cl9g
  - Postgres: dpg-d6006gh4tr6s73a4clk0-a
  - Redis: red-d6006g94tr6s73a4cl90
- Key commands: `render services`, `render deploys list`, `render logs`, `render deploys create`

## References

- **Full Specification:** `docs/PROJECT_SPEC.md` (business requirements, user journeys, message routing, state machines, permissions)
- [Twilio WhatsApp](https://www.twilio.com/docs/whatsapp)
- [OpenAI API](https://platform.openai.com/docs/api-reference)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
