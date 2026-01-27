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
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   WhatsApp      │────▶│   FastAPI       │────▶│   PostgreSQL    │
│   (Twilio)      │◀────│   Backend       │◀────│                 │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                        ┌────────┼────────┐
                        ▼        ▼        ▼
               ┌─────────────┐ ┌───────┐ ┌─────────────┐
               │   OpenAI    │ │ Redis │ │   Next.js   │
               │   GPT-5.2   │ │       │ │   Frontend  │
               └─────────────┘ └───────┘ └─────────────┘
```

**Three interfaces:**
1. **WhatsApp** - Customers book, staff manage schedules (via Twilio)
2. **Web Dashboard** - Business owners manage everything (magic link auth)
3. **Admin Dashboard** - Platform management (password auth)

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| Database | PostgreSQL 15+, SQLAlchemy 2.0 (async), Alembic |
| AI | OpenAI GPT-5.2 with function calling |
| WhatsApp | Twilio WhatsApp API |
| Frontend | Next.js 15, TypeScript, Tailwind CSS |
| Background | Redis + Celery (appointment reminders) |

## Project Structure

```
yume/
├── app/                         # Backend
│   ├── main.py                  # FastAPI entry
│   ├── config.py                # Settings
│   ├── api/v1/                  # Endpoints (~63 routes)
│   ├── models/                  # SQLAlchemy (15 models)
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
| Organization | The business |
| Location | Physical location (1+ per org) |
| Spot | Service station (chair, table) - linked to services |
| Staff | Employees identified by phone |
| ServiceType | What they offer |
| Customer | End consumer (incremental identity) |
| Appointment | Scheduled event |
| Conversation/Message | WhatsApp threads |
| Availability | Staff schedules |
| AuthToken | Magic link tokens |
| OnboardingSession | Tracks WhatsApp onboarding state for new businesses |
| ExecutionTrace | AI pipeline execution traces for debugging |

**Key relationships:**
- Staff ↔ ServiceType: many-to-many (what staff can do)
- Spot ↔ ServiceType: many-to-many (what spot supports)
- Appointment requires: customer, service, spot, (optional) staff

## Critical Patterns

### 1. Message Routing (THE CORE)
```python
# Incoming WhatsApp → identify sender → route to correct handler
staff = await get_staff_by_phone(org.id, sender_phone)
if staff:
    return handle_staff_message(org, staff, message)
else:
    customer = await get_or_create_customer(org.id, sender_phone)
    return handle_customer_message(org, customer, message)
```

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
```

## Current Implementation Status

### Fully Implemented
- All 15 database models with proper relationships
- ~63 API endpoints for all resources
- Admin dashboard (stats, org management, impersonation, conversations, activity, playground)
- Admin conversation playground (emulate users, view AI pipeline execution traces)
- AI conversation handler with tool calling (customer + staff flows)
- Message routing (staff vs customer identification)
- Availability slot calculation with conflict validation
- Magic link authentication
- Frontend: login, location management, company settings, schedule page
- Schedule page with filtering, appointment actions (complete, no-show, cancel)
- Celery background tasks with 24-hour appointment reminders + trace cleanup
- WhatsApp onboarding flow (business setup via chat)
- Twilio WhatsApp integration (send/receive messages)
- Meta Embedded Signup (connect existing WhatsApp Business numbers)

### Partially Implemented
- WhatsApp template messages (need Twilio Content setup)
- Daily schedule summaries (task not yet created)
- New booking notifications to owner

### Not Implemented
- Create/Edit appointment modals in dashboard (deferred - most bookings via WhatsApp)
- Custom domain configuration (api.yume.mx, app.yume.mx)

## Key Files

| File | What it does |
|------|--------------|
| `app/api/v1/webhooks.py` | Twilio webhook handler |
| `app/services/message_router.py` | Staff/customer routing |
| `app/services/conversation.py` | AI orchestration |
| `app/services/scheduling.py` | Availability calculation + conflict validation |
| `app/services/onboarding.py` | WhatsApp onboarding flow for new businesses |
| `app/ai/tools.py` | AI tool definitions |
| `app/ai/prompts.py` | System prompts (Spanish) |
| `app/tasks/celery_app.py` | Celery configuration + beat schedule |
| `app/tasks/reminders.py` | 24-hour appointment reminder tasks |
| `app/services/execution_tracer.py` | Captures AI pipeline execution traces |
| `app/services/playground.py` | Admin playground business logic |
| `frontend/src/providers/AuthProvider.tsx` | Auth context |
| `frontend/src/lib/api/client.ts` | Axios with dual token handling |
| `frontend/src/app/admin/playground/page.tsx` | Admin conversation playground UI |

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

## Debugging

- Webhook logs show incoming message format
- WhatsApp webhook must respond within 20 seconds
- Check tool call format if AI seems stuck
- Admin dashboard has conversation viewer for debugging
- **Admin Playground** (`/admin/playground`): Emulate any user, see full AI execution traces with latencies

## Session Workflow

**Starting:**
1. Read `workplan.md` for current status
2. Reference this file for conventions
3. See `docs/PROJECT_SPEC.md` for requirements

**Ending:**
1. Verify backend loads, frontend builds
2. Update `workplan.md` with completed tasks

## Railway Deployment Notes

**Key learnings from deployment (avoid these mistakes):**

### Backend (FastAPI/Python)
1. **DATABASE_URL format**: Railway provides `postgresql://...` but SQLAlchemy async needs `postgresql+asyncpg://...` - must add `+asyncpg` manually
2. **Use start.sh script**: Chaining commands with `&&` in Dockerfile CMD can fail silently. Use a bash script with `set -e` and explicit logging
3. **All env vars required**: Missing `REDIS_URL`, `OPENAI_API_KEY`, `JWT_SECRET_KEY` will crash silently - no error in logs
4. **pip install**: Use `pip install .` not `pip install -e .` in Docker (editable mode needs source)

### Frontend (Next.js)
1. **Use Nixpacks, not Dockerfile**: Railway's auto-detection works better for Next.js. Remove `Dockerfile`, `railway.json` from frontend and let Railpack handle it
2. **Root directory setting**: Must set to `frontend` in Railway UI for monorepo
3. **Next.js 16**: Doesn't support `eslint` key in next.config.ts - remove it
4. **Builder caching**: Railway caches aggressively. If wrong Dockerfile is used, delete service and recreate

### Monorepo Issues
1. **Root railway.json conflicts**: Can interfere with subdirectory services - rename to `railway.backend.json` or delete
2. **.gitignore `lib/` trap**: Using `lib/` ignores `frontend/src/lib/`. Use `/lib/` (with leading slash) to only match root level
3. **Separate services**: Deploy backend and frontend as separate Railway services from same repo

### Environment Variables (Backend)
```
DATABASE_URL=postgresql+asyncpg://...  # Note: +asyncpg required!
REDIS_URL=redis://...
OPENAI_API_KEY=sk-...
JWT_SECRET_KEY=<generate>
ADMIN_MASTER_PASSWORD=<generate>
FRONTEND_URL=https://frontend-url.railway.app
APP_ENV=production
```

### Environment Variables (Frontend)
```
NEXT_PUBLIC_API_URL=https://backend-url.railway.app/api/v1
```

## References

- **Requirements:** `docs/PROJECT_SPEC.md` (source of truth)
- **Progress:** `workplan.md`
- [Twilio WhatsApp](https://www.twilio.com/docs/whatsapp)
- [OpenAI API](https://platform.openai.com/docs/api-reference)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
