# CLAUDE.md - Yume Development Guide

## What is Yume?

Yume is a WhatsApp-native AI scheduling assistant for beauty businesses in Mexico. Business owners connect their WhatsApp number, and Yume handles booking conversations automatically via AI.

**One-liner:** "Connect Yume to your WhatsApp in 2 minutes. Watch your appointments start booking themselves."

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
│   YUME CENTRAL NUMBER          │      BUSINESS NUMBERS (per business)    │
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
1. **WhatsApp** - Two channels: Yume Central (B2B) + Business Numbers (B2C/Staff)
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
yume/
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
| YumeUser (Staff) | Employees identified by phone (alias: Staff) |
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

Yume operates two WhatsApp channels:
- **Yume Central Number** - B2B: business onboarding + management
- **Business Numbers** - B2C: end customers + staff of that specific business

```python
# Simplified routing logic (see full spec for all cases)
if recipient_number == YUME_CENTRAL_NUMBER:
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
| 1 | Yume Central | Unknown | Business Onboarding |
| 2a | Yume Central | Staff of 1 business | Business Management |
| 2b | Yume Central | Staff of 2+ businesses | Redirect |
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
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/yume
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
NEXT_PUBLIC_YUME_WHATSAPP_NUMBER=17759674528
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
- Custom domain configuration (api.yume.mx, app.yume.mx)
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
   - Navigate to https://yume-frontend.onrender.com/admin (or relevant page)
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
1. Navigate to https://yume-frontend.onrender.com/admin
2. Take a screenshot
3. Click the "Organizations" tab and screenshot
4. Verify the table loads with data
```

### Production URLs for Testing
- Admin Dashboard: `https://yume-frontend.onrender.com/admin`
- Business Login: `https://yume-frontend.onrender.com/login`
- Business Dashboard: `https://yume-frontend.onrender.com/schedule`

### What NOT to do
- Never say "done" without visual verification on production
- Never assume code changes work just because there are no type errors
- Never skip testing interactive flows (buttons, forms, navigation)
- Never test UI only on localhost — always verify on production

## Debugging

### Investigation Approach
When investigating bugs, always check the full call chain from entry point to database layer before reporting findings. Don't stop at the first suspicious code - trace the complete flow.

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
- **Backend**: Web Service (Docker) - `yume-backend`
- **Frontend**: Web Service (Node) - `yume-frontend`
- **Database**: Render PostgreSQL - `yume-db`
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
FRONTEND_URL=https://yume-frontend.onrender.com
APP_ENV=production
```

### Environment Variables (Frontend)
```
NEXT_PUBLIC_API_URL=https://yume-backend.onrender.com/api/v1
```

### Render URLs
- Backend: `https://yume-backend-8b6h.onrender.com`
- Frontend: `https://yume-frontend.onrender.com`
- Admin Dashboard: `https://yume-frontend.onrender.com/admin`

### Render CLI
- Load RENDER_API_KEY from .env before running render commands: `export $(grep RENDER_API_KEY .env | xargs)`
- Use `--output json --confirm` for non-interactive mode
- Service IDs:
  - Backend: srv-d6006uh4tr6s73a4ctsg
  - Frontend: srv-d6006gh4tr6s73a4cl9g
  - Postgres: dpg-d6006gh4tr6s73a4clk0-a
  - Redis: red-d6006g94tr6s73a4cl90
- Key commands: `render services`, `render deploys list`, `render logs`, `render deploys create`

## References

- **Full Specification:** `docs/PROJECT_SPEC.md` (business requirements, user journeys, message routing, state machines, permissions)
- **Progress:** `workplan.md`
- [Twilio WhatsApp](https://www.twilio.com/docs/whatsapp)
- [OpenAI API](https://platform.openai.com/docs/api-reference)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
