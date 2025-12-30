# CLAUDE.md - Yume Project Guide

## What is Yume?

Yume is a WhatsApp-native AI scheduling assistant for beauty businesses in Mexico. Business owners connect their existing WhatsApp number, and Yume handles booking conversations with customers automatically. Staff members can also interact with Yume via WhatsApp to manage their schedules.

**One-liner:** "Connect Yume to your WhatsApp in 2 minutes. Watch your appointments start booking themselves."

## Quick Reference

```bash
# Backend development
docker-compose up -d              # Start Postgres + Redis
source .venv/bin/activate         # Activate virtualenv
alembic upgrade head              # Run migrations
uvicorn app.main:app --reload     # Start API server (64 routes)

# Frontend development
cd frontend && npm run dev        # Start Next.js dev server (port 3000)
cd frontend && npm run build      # Build for production
cd frontend && npm run lint       # Run ESLint

# Testing
pytest                            # Run all tests
pytest tests/test_api/            # Run API tests only
pytest -x                         # Stop on first failure

# Database
alembic revision --autogenerate -m "description"  # Create migration
alembic upgrade head              # Apply migrations
alembic downgrade -1              # Rollback one migration

# Background tasks
celery -A app.tasks worker --loglevel=info

# Local webhook testing
ngrok http 8000                   # Expose local server for Meta webhooks
```

## Architecture Overview

```
                        ┌─────────────────┐
                        │   Next.js       │
                        │   Frontend      │ ◀── Business Owner Dashboard
                        └────────┬────────┘
                                 │
┌─────────────────┐     ┌────────▼────────┐     ┌─────────────────┐
│   WhatsApp      │────▶│   FastAPI       │────▶│   PostgreSQL    │
│   Cloud API     │◀────│   Backend       │◀────│                 │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                        ┌────────┴────────┐
                        ▼                 ▼
               ┌─────────────┐   ┌─────────────────┐
               │   OpenAI    │   │   Redis/Celery  │
               │   (AI)      │   │   (Tasks)       │
               └─────────────┘   └─────────────────┘
```

**Two interfaces:**
1. **WhatsApp (Customers & Staff):** webhook → Identify sender → Route to AI handler → AI uses tools → Send response
2. **Web App (Business Owners):** Next.js dashboard → JWT auth via magic link → Manage schedule, employees, settings

## Tech Stack

**Backend:**
- **Python 3.11+** with **FastAPI** and **Pydantic v2**
- **PostgreSQL 15+** with **SQLAlchemy 2.0** (async)
- **Redis + Celery** for background tasks
- **OpenAI GPT** for conversational AI
- **Meta WhatsApp Cloud API** (direct, no BSP)
- **PyJWT** for authentication tokens

**Frontend:**
- **Next.js 15** with App Router
- **TypeScript** for type safety
- **Tailwind CSS** for styling
- **TanStack Query** for data fetching
- **React Hook Form + Zod** for forms

## Dashboard Structure

The web dashboard has three main tabs:

1. **Agenda** (`/schedule`) - Calendar and appointment management
   - View all appointments in calendar or list format
   - Filter by location (via location switcher)
   - Create, edit, cancel appointments

2. **Sucursal** (`/location`) - Location-specific operations
   - **Empleados section**: Staff management with service assignments
   - **Servicios section**: Service types (name, duration, price)
   - **Estaciones section**: Spots/stations with service capabilities
   - All data scoped to currently selected location

3. **Negocio** (`/company`) - Organization-wide settings
   - Organization info (name, timezone)
   - Locations CRUD (add/edit/delete locations)
   - WhatsApp connection status

**Location Switcher**: Dropdown in header to switch between locations. Selected location persists in localStorage.

## Admin Dashboard

The admin dashboard provides platform-wide management at `/admin/*` routes. It uses password authentication (separate from business owner magic link auth).

**Access**: Navigate to `/admin/login` and enter password from `ADMIN_MASTER_PASSWORD` environment variable (default: `yume-admin-2024`)

**Features**:

1. **Dashboard** (`/admin/dashboard`) - Platform statistics
   - Organization count
   - Total appointments, customers, messages
   - Overview of platform health

2. **Organizations** (`/admin/organizations`) - Manage all businesses
   - Search organizations by name
   - Filter by status (active, suspended, onboarding)
   - **Login As** button - Impersonate any organization (generates org JWT, opens in new tab)
   - **Suspend/Activate** button - Disable/enable organization access
   - View detailed org stats (locations, staff, customers, appointments)

3. **Conversations** (`/admin/conversations`) - Debug AI interactions
   - View all WhatsApp conversations across organizations
   - Filter by organization
   - See customer-AI message exchanges
   - Grouped by date with sender labels (Customer, AI, Staff)
   - Useful for debugging conversation flow issues

4. **Activity Feed** (`/admin/activity`) - Monitor platform activity
   - Recent organization signups
   - Appointment status changes (created, confirmed, completed, cancelled, no-show)
   - Click any activity to view related organization
   - Real-time feed of platform events

**Authentication**:
- Admin uses password-based JWT auth (type: `admin_access`)
- Business owners use magic link JWT auth (type: `access`)
- Frontend automatically uses correct token based on route (`/admin/*` vs others)
- Admin token stored in `localStorage` as `admin_token`

**Key Patterns**:

```python
# Backend - Admin JWT creation
def create_admin_access_token() -> str:
    payload = {
        "sub": "admin",
        "type": "admin_access",
        "exp": expires,
    }
    return jwt.encode(payload, secret_key, algorithm)

# Backend - Protecting admin routes
@router.get("/admin/stats")
async def get_stats(_: Annotated[bool, Depends(require_admin)]):
    # Only admins can access
    pass

# Backend - Organization impersonation
def generate_impersonation_token(org_id: str) -> str:
    # Creates regular org JWT for admin to "Login As" organization
    return create_access_token(data={"sub": org_id})
```

```typescript
// Frontend - Token routing
api.interceptors.request.use((config) => {
  const isAdminCall = config.url?.startsWith('/admin');
  const tokenKey = isAdminCall ? 'admin_token' : 'auth_token';
  const token = localStorage.getItem(tokenKey);
  config.headers.Authorization = `Bearer ${token}`;
});
```

**Security Notes**:
- Admin password should be strong in production (change from default)
- Suspended organizations cannot login via magic link (blocked in auth service)
- Admin impersonation creates time-limited org tokens (respects JWT expiration)
- All admin endpoints require `require_admin` dependency

## Project Structure

```
yume/
├── app/                         # Backend (FastAPI)
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Settings (pydantic-settings)
│   ├── api/v1/                  # API endpoints (64 routes)
│   │   ├── auth.py              # Magic link + JWT auth
│   │   ├── admin.py             # Admin dashboard endpoints (9 routes)
│   │   ├── locations.py         # Location CRUD
│   │   ├── spots.py             # Spot/station CRUD
│   │   └── ...                  # Other resource endpoints
│   ├── api/admin_deps.py        # Admin authentication dependency
│   ├── models/                  # SQLAlchemy models
│   │   ├── associations.py      # Many-to-many tables (spot↔service, staff↔service)
│   │   ├── spot.py              # Physical service stations
│   │   ├── auth_token.py        # Magic link tokens
│   │   └── ...                  # Other entity models
│   ├── schemas/                 # Pydantic schemas
│   │   ├── admin.py             # Admin-specific schemas
│   │   └── ...                  # Other schemas
│   ├── services/                # Business logic
│   │   ├── admin.py             # Admin service layer
│   │   └── ...                  # Other services
│   ├── ai/                      # LLM integration (OpenAI)
│   ├── utils/jwt.py             # JWT token utilities (org + admin)
│   └── tasks/                   # Celery tasks
├── frontend/                    # Frontend (Next.js)
│   ├── src/
│   │   ├── app/                 # App Router pages
│   │   │   ├── login/           # Phone input, magic link
│   │   │   ├── verify/          # Token verification
│   │   │   ├── schedule/        # Calendar + list view
│   │   │   ├── location/        # Location-specific: staff, services, spots
│   │   │   ├── company/         # Business settings, locations CRUD
│   │   │   └── admin/           # Admin dashboard
│   │   │       ├── login/       # Admin password login
│   │   │       ├── dashboard/   # Stats overview
│   │   │       ├── organizations/ # Org management + [id] detail
│   │   │       ├── conversations/ # Conversation viewer + [id] detail
│   │   │       └── activity/    # Activity feed
│   │   ├── components/          # Reusable components
│   │   │   ├── layout/          # DashboardLayout, LocationSwitcher
│   │   │   ├── admin/           # AdminLayout
│   │   │   └── location/        # EmployeeModal, ServiceModal, SpotModal
│   │   ├── lib/
│   │   │   ├── api/             # API client + endpoints
│   │   │   │   ├── admin.ts     # Admin API functions
│   │   │   │   └── ...          # Other API modules
│   │   │   └── types.ts         # TypeScript types (includes admin types)
│   │   └── providers/           # Auth, Query, Location, AdminAuth providers
│   └── package.json
├── alembic/                     # Database migrations
├── tests/
└── scripts/
```

## Core Entities

| Entity | Purpose |
|--------|---------|
| Organization | The business (barbershop, salon) |
| Location | Physical location (single for v1) |
| Staff | Employees + owner, identified by phone number |
| ServiceType | What they offer (haircut, manicure) |
| Customer | End consumers, minimal data initially |
| Appointment | Scheduled service events (requires spot_id) |
| Conversation | WhatsApp conversation thread |
| Message | Individual messages |
| Availability | Staff schedules and exceptions |
| **Spot** | Physical service stations (chairs, tables, beds) - linked to services via many-to-many |
| **AuthToken** | Magic link tokens for web app authentication |

**Key Relationships:**
- **Spot ↔ ServiceType**: Many-to-many via `spot_service_types` table. Each spot can offer specific services.
- **Staff ↔ ServiceType**: Many-to-many via `staff_service_types` table. Each staff member can perform specific services.

## Critical Patterns

### 1. Message Routing

Every incoming WhatsApp message must be routed correctly:

```python
async def route_message(sender_phone: str, org: Organization):
    staff = await get_staff_by_phone(org.id, sender_phone)
    if staff:
        return StaffConversationHandler(org, staff)
    else:
        customer = await get_or_create_customer(org.id, sender_phone)
        return CustomerConversationHandler(org, customer)
```

### 2. Incremental Identity

Customers can exist with minimal data. Don't require fields upfront:

```python
# Good - create with just phone
customer = Customer(organization_id=org.id, phone_number=phone)

# Name comes later during conversation
customer.name = name_from_conversation
```

### 3. All Times in UTC

Store everything in UTC. Convert to org timezone only for display:

```python
from datetime import datetime, timezone

# Storage
appointment.scheduled_start = datetime.now(timezone.utc)

# Display
local_time = appointment.scheduled_start.astimezone(org_timezone)
```

### 4. Tool-Based AI

The AI doesn't access the database directly. It uses typed tools:

```python
# AI decides to book → calls tool → we execute
tools = [
    "check_availability",
    "book_appointment", 
    "cancel_appointment",
    # ... etc
]
```

### 5. Webhook Idempotency

WhatsApp may send duplicate webhooks. Handle gracefully:

```python
# Store message IDs, skip if already processed
if await message_exists(whatsapp_message_id):
    return {"status": "already_processed"}
```

### 6. Magic Link Authentication (Web App)

Business owners authenticate via magic link sent to WhatsApp:

```python
# 1. Request magic link (sends WhatsApp message)
POST /api/v1/auth/request-magic-link
Body: {"phone_number": "+525512345678"}

# 2. Click link → verify token → get JWT
POST /api/v1/auth/verify-magic-link
Body: {"token": "abc123..."}
Response: {"access_token": "jwt...", "organization": {...}}

# 3. Include JWT in subsequent requests
Headers: {"Authorization": "Bearer jwt..."}
```

Frontend stores JWT in localStorage and includes it via Axios interceptors.

## API Conventions

- All endpoints under `/api/v1/`
- Organization-scoped: `/api/v1/organizations/{org_id}/resource`
- Use Pydantic schemas for all request/response bodies
- Return 404 for missing resources, 422 for validation errors
- Async all the way down

## Language & Localization

- **All AI responses in Mexican Spanish** - natural, not formal
- Use "tú" not "usted" 
- Currency in MXN (Mexican pesos)
- Timezone default: America/Mexico_City
- Date format: "viernes 15 de enero" not "15/01"
- Time format: "3:00 PM" (12-hour with AM/PM)

## What NOT to Build (v1)

- ✅ ~~Frontend/dashboard~~ - **Built!** Next.js web app in `/frontend`
- ❌ Multi-location support (model supports it, UI doesn't)
- ❌ Payments/deposits
- ❌ English or other languages
- ❌ Complex analytics
- ❌ Email notifications
- ❌ Native mobile app (web app is mobile-responsive)

## Environment Variables

Required in `.env` (backend):

```bash
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
OPENAI_API_KEY=sk-...
META_APP_ID=...
META_APP_SECRET=...
META_WEBHOOK_VERIFY_TOKEN=...
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080  # 7 days
FRONTEND_URL=http://localhost:3000
ADMIN_MASTER_PASSWORD=yume-admin-2024  # Change in production!
```

Required in `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Testing Guidelines

- Use pytest with async support (`pytest-asyncio`)
- Factory fixtures for creating test data
- Mock external APIs (WhatsApp, Claude) in tests
- Test both staff and customer conversation flows
- Test availability calculation edge cases thoroughly

```python
# Example test structure
async def test_booking_flow(db_session, mock_claude, mock_whatsapp):
    org = await create_test_org(db_session)
    customer_phone = "+525512345678"

    # Simulate incoming message
    response = await handle_message(org, customer_phone, "Quiero una cita")

    assert "qué servicio" in response.lower()
```

## PR Review Guidelines

When reviewing pull requests, check the following:

### Code Quality Checklist

- [ ] **Follows existing patterns** - Code matches the style and patterns already in the codebase
- [ ] **No over-engineering** - Solution is as simple as possible, no unnecessary abstractions
- [ ] **Async consistency** - All database operations use async/await, no blocking calls
- [ ] **Type hints** - Functions have proper type annotations
- [ ] **No hardcoded values** - Configuration belongs in `app/config.py` or environment variables

### Security Checklist

- [ ] **No secrets in code** - API keys, tokens, passwords are in environment variables
- [ ] **Input validation** - User input is validated via Pydantic schemas
- [ ] **SQL injection safe** - Using SQLAlchemy ORM, no raw SQL with string interpolation
- [ ] **No sensitive data in logs** - Phone numbers, names, messages are not logged in production

### Business Logic Checklist

- [ ] **Organization scoping** - All queries filter by `organization_id` where appropriate
- [ ] **Staff identification** - Phone number lookups work correctly for routing
- [ ] **Timezone handling** - Dates stored in UTC, converted for display only
- [ ] **Mexican Spanish** - All user-facing text is in natural Mexican Spanish (tú, not usted)

### Testing Checklist

- [ ] **Tests included** - New functionality has corresponding tests
- [ ] **Tests pass** - All existing tests still pass
- [ ] **Edge cases covered** - Especially for availability/scheduling logic
- [ ] **Mocks used** - External APIs (WhatsApp, Claude) are mocked in tests

### Database Checklist

- [ ] **Migration included** - Schema changes have an Alembic migration
- [ ] **Migration reversible** - Downgrade path works
- [ ] **Indexes considered** - Frequently queried fields have indexes
- [ ] **Cascade deletes** - Foreign key relationships handle deletions properly

### WhatsApp Integration Checklist

- [ ] **Idempotency** - Duplicate webhooks are handled gracefully (check message_id)
- [ ] **Response time** - Webhook responds within 20 seconds
- [ ] **Error handling** - Failures don't crash the webhook, return 200 to Meta
- [ ] **Mock mode works** - Can test locally without Meta credentials

### Documentation Checklist

- [ ] **Docstrings** - Public functions have docstrings explaining purpose
- [ ] **CLAUDE.md updated** - If adding new patterns or conventions
- [ ] **workplan.md updated** - If completing a tracked task
- [ ] **README updated** - If changing setup or deployment process

### Review Response Format

When leaving PR review comments:

1. **Be specific** - Point to exact lines, suggest concrete fixes
2. **Explain why** - Don't just say "wrong", explain the reasoning
3. **Prioritize** - Distinguish blocking issues from nice-to-haves
4. **Approve when ready** - Don't nitpick if the PR achieves its goal safely

Example review comment:
```
Line 45: This query doesn't filter by organization_id, which could leak
data across organizations. Add `.where(Staff.organization_id == org_id)`
to the query.

Blocking: Yes - security issue
```

## Common Tasks

### Adding a new API endpoint

1. Add Pydantic schemas in `app/schemas/`
2. Add route in `app/api/v1/`
3. Add business logic in `app/services/`
4. Add tests in `tests/test_api/`

### Adding a new AI tool

1. Define tool schema in `app/ai/tools.py`
2. Implement handler in `app/services/`
3. Add to appropriate tool list (customer_tools or staff_tools)
4. Test with real conversation flow

### Adding a database migration

1. Modify model in `app/models/`
2. Run `alembic revision --autogenerate -m "description"`
3. Review generated migration
4. Run `alembic upgrade head`

## Debugging Tips

- Check webhook logs for incoming message format
- Use `print(response.model_dump_json(indent=2))` for Claude responses
- WhatsApp webhook must respond within 20 seconds
- If AI seems stuck, check tool call/response format

## Key Files to Understand

**Backend:**

| File | Purpose |
|------|---------|
| `app/api/v1/webhooks.py` | WhatsApp webhook handler |
| `app/api/v1/auth.py` | Magic link + JWT authentication |
| `app/api/v1/admin.py` | Admin dashboard endpoints (9 routes) |
| `app/api/admin_deps.py` | Admin authentication dependency |
| `app/models/associations.py` | Many-to-many association tables (spot↔service, staff↔service) |
| `app/schemas/admin.py` | Admin Pydantic schemas |
| `app/services/admin.py` | Admin business logic (stats, impersonation, etc.) |
| `app/services/conversation.py` | AI conversation orchestration |
| `app/services/scheduling.py` | Availability calculation |
| `app/services/auth.py` | Auth token generation/verification (blocks suspended orgs) |
| `app/ai/tools.py` | Tool definitions for OpenAI |
| `app/ai/prompts.py` | System prompts (customer & staff) |
| `app/utils/jwt.py` | JWT token utilities (org + admin tokens) |

**Frontend:**

| File | Purpose |
|------|---------|
| `frontend/src/providers/AuthProvider.tsx` | Auth context + login/logout |
| `frontend/src/providers/AdminAuthProvider.tsx` | Admin auth context + password login |
| `frontend/src/providers/LocationProvider.tsx` | Location context + selected location state |
| `frontend/src/lib/api/client.ts` | Axios client with JWT interceptors (dual token routing) |
| `frontend/src/lib/api/admin.ts` | Admin API functions (login, stats, impersonation, etc.) |
| `frontend/src/lib/types.ts` | TypeScript types (includes admin types) |
| `frontend/src/components/layout/DashboardLayout.tsx` | Tab navigation shell (Agenda, Sucursal, Negocio) |
| `frontend/src/components/admin/AdminLayout.tsx` | Admin dashboard layout + navigation |
| `frontend/src/components/layout/LocationSwitcher.tsx` | Location dropdown selector |
| `frontend/src/app/schedule/page.tsx` | Calendar + list views |
| `frontend/src/app/location/page.tsx` | Employees, Services, Spots management (location-scoped) |
| `frontend/src/app/company/page.tsx` | Organization settings + Locations CRUD |
| `frontend/src/app/admin/login/page.tsx` | Admin password login |
| `frontend/src/app/admin/dashboard/page.tsx` | Platform stats overview |
| `frontend/src/app/admin/organizations/page.tsx` | Org list with impersonation + suspend |
| `frontend/src/app/admin/conversations/page.tsx` | AI conversation viewer |
| `frontend/src/app/admin/activity/page.tsx` | Activity feed |

## External Documentation

- [Meta WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Embedded Signup](https://developers.facebook.com/docs/whatsapp/embedded-signup)
- [OpenAI API](https://platform.openai.com/docs/api-reference)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)

## Getting Help

For comprehensive business context, user journeys, data models, and example conversations, see:
- `docs/PROJECT_SPEC.md` - Full project specification
- `workplan.md` - Project progress tracker (update after each task)

## Session Workflow

**Starting a session:**
1. Read `workplan.md` to see current status and what's done
2. Read `CLAUDE.md` for conventions
3. Reference `docs/PROJECT_SPEC.md` as needed for deep context

**Ending a task:**
1. Confirm code works (backend loads, frontend builds)
2. Update `workplan.md`:
   - Add completed task with date and details
   - Check off items in checklists
   - Update "Current Status" section
   - Add any notes for next session

## Remember

1. **Three interfaces** - WhatsApp for customers/staff, Web app for business owners, Admin dashboard for platform management
2. **Staff are users too** - Same WhatsApp number, different experience based on phone lookup
3. **Spanish only** - Mexican Spanish, natural tone (tú, not usted)
4. **Simple first** - Don't over-engineer, ship incrementally
5. **Test with real data** - AI quality only shows in real conversations
6. **Spots matter** - Every appointment needs a spot (chair/table), can't double-book
7. **Dual auth systems** - Magic link (no passwords) for business owners, password-based for admin
8. **Admin can impersonate** - Generates org JWT tokens to "Login As" any organization
