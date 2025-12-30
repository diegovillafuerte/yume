# WORKPLAN.md - Project Progress Tracker

> **Purpose:** This file tracks what has been completed, decisions made, and current state. Update this file after completing each task. Read this file at the start of every session.

---

## Current Status

**Phase:** Web App Implementation Complete ✅
**Last Updated:** December 27, 2024
**Last Task Completed:** Web App implementation (backend + frontend)
**Next Steps:** Run migrations when database is available, test full flow

---

## Completed Tasks

<!-- Add completed tasks here with dates. Most recent first. -->

### 2024-12-27 - Web App for Business Owners

**What was built:**
- **Spot Model** (`app/models/spot.py`)
  - Physical service stations (chairs, tables, beds)
  - Linked to locations with cascade delete
  - Unique constraint on (location_id, name)
  - Display order for UI sorting

- **Authentication System**
  - `app/models/auth_token.py` - Magic link tokens with expiry
  - `app/utils/jwt.py` - JWT token creation and validation
  - `app/services/auth.py` - Magic link generation and verification
  - `app/api/v1/auth.py` - Auth endpoints (request-magic-link, verify-magic-link, logout)

- **Location CRUD API** (`app/api/v1/locations.py`)
  - Full CRUD for organization locations
  - Validation: can't delete the only location

- **Spots CRUD API** (`app/api/v1/spots.py`)
  - Full CRUD for spots within locations
  - Soft delete (is_active = false)

- **Next.js Frontend** (`/frontend`)
  - Login page with phone number input
  - Magic link verification page
  - Dashboard layout with 3 tabs and responsive navigation
  - Schedule tab with calendar/list view toggle
  - Employees tab (ready for data integration)
  - Company tab with settings, locations, services, spots sections

**Key Files Created:**
- `app/models/spot.py` - Spot model
- `app/models/auth_token.py` - Auth token model
- `app/schemas/spot.py` - Spot schemas
- `app/schemas/auth.py` - Auth schemas
- `app/services/location.py` - Location service
- `app/services/spot.py` - Spot service
- `app/services/auth.py` - Auth service
- `app/api/v1/locations.py` - Location endpoints
- `app/api/v1/spots.py` - Spot endpoints
- `app/api/v1/auth.py` - Auth endpoints
- `app/utils/jwt.py` - JWT utilities
- `frontend/` - Complete Next.js application

**Files Modified:**
- `app/models/appointment.py` - Added spot_id FK
- `app/models/staff.py` - Added default_spot_id FK
- `app/models/location.py` - Added spots relationship
- `app/schemas/appointment.py` - Added spot_id fields
- `app/schemas/staff.py` - Added default_spot_id fields
- `app/api/deps.py` - Added JWT auth dependency
- `app/config.py` - Added JWT and frontend settings
- `pyproject.toml` - Added PyJWT dependency
- `.env.example` - Added JWT and frontend config

**Verification:**
- ✅ Backend loads with 52 routes
- ✅ Frontend builds successfully
- ✅ All 6 pages render (/, /login, /verify, /schedule, /employees, /company)
- ✅ Auth flow ready (magic link → JWT)

**Architecture:**
```
Magic Link Flow:
1. User enters phone → POST /auth/request-magic-link
2. System sends WhatsApp with link (or prints in dev mode)
3. User clicks link → GET /verify?token=xxx
4. Frontend calls POST /auth/verify-magic-link
5. Backend validates token, returns JWT
6. Frontend stores JWT, redirects to /schedule
```

---

### 2024-12-27 - Conversational AI Integration

**What was built:**
- **Anthropic Client Wrapper** (`app/ai/client.py`)
  - Claude API integration with error handling
  - Tool call extraction and response parsing
  - Fallback handling when API key not configured

- **System Prompts** (`app/ai/prompts.py`)
  - Customer prompt: Natural Mexican Spanish, booking flow guidance
  - Staff prompt: Schedule management, walk-ins, status updates
  - Dynamic context injection (services, business hours, customer history)

- **Customer Tools** - 6 tools for booking flow:
  - `check_availability` - Check available slots (ALWAYS before offering times)
  - `book_appointment` - Book confirmed appointments
  - `get_my_appointments` - View upcoming appointments
  - `cancel_appointment` - Cancel existing appointments
  - `reschedule_appointment` - Change appointment times
  - `handoff_to_human` - Transfer to business owner

- **Staff Tools** - 7 tools for schedule management:
  - `get_my_schedule` - View personal schedule
  - `get_business_schedule` - View all appointments
  - `block_time` - Block personal time (lunch, breaks)
  - `mark_appointment_status` - Complete/no-show/cancel
  - `book_walk_in` - Register walk-in customers
  - `get_customer_history` - Lookup customer history
  - `cancel_customer_appointment` - Cancel with optional notification

- **Conversation Handler** (`app/services/conversation.py`)
  - Tool execution loop (Claude → tool → Claude → response)
  - Conversation history management
  - Context updates for continuity
  - Graceful fallbacks when AI not configured

- **Message Router Updates**
  - Integrated AI handlers for both staff and customers
  - Replaced placeholder responses with full AI flow

**Key Files Created:**
- `app/ai/client.py` - Anthropic client wrapper
- `app/ai/prompts.py` - System prompts (Mexican Spanish)
- `app/ai/tools.py` - Tool definitions and handlers
- `app/services/conversation.py` - AI conversation orchestration

**Architecture:**
```
Message → Router → ConversationHandler
                         ↓
                   Build System Prompt
                         ↓
                   Get Conversation History
                         ↓
                   Claude API Call (with tools)
                         ↓
                   Tool Execution Loop ←──┐
                         ↓                │
                   Execute Tool ──────────┘
                         ↓
                   Final Response → WhatsApp
```

**Tool Flow Example (Booking):**
```
Customer: "Quiero una cita para corte mañana"
Claude: [uses check_availability tool]
System: Returns available slots
Claude: "Tengo estos horarios disponibles para mañana: 10:00 AM, 2:00 PM, 4:00 PM"
Customer: "A las 2"
Claude: [uses book_appointment tool]
System: Returns confirmation
Claude: "Listo, tu cita quedó agendada para mañana a las 2:00 PM ✓"
```

**Verification:**
- ✅ App loads successfully with 39 routes
- ✅ All imports resolve correctly
- ✅ AI client has fallback for missing API key
- ✅ Tools defined for all customer and staff operations
- ✅ Prompts in natural Mexican Spanish

**Next Steps:**
- Install Docker and set up database
- Create Alembic migration
- Test with real Claude API key
- Fine-tune prompts based on real conversations

---

### 2024-12-27 - Testing Infrastructure

**What was built:**
- **Comprehensive Testing Guide** (`TESTING.md`) with step-by-step instructions
- **Seed Data Script** (`scripts/seed_test_data.py`) for creating test organization and data
- Complete testing workflow documented: database setup → seed data → test webhooks
- Test data includes:
  - Test organization with WhatsApp connection (phone_number_id: `test_phone_123`)
  - Staff member for routing tests (Pedro González: `525512345678`)
  - Service type (Corte de cabello - 30 min)
  - Primary location with business hours

**Key files created:**
- `TESTING.md` - Comprehensive testing guide with 10 steps
- `scripts/seed_test_data.py` - Test data seeding and cleanup script

**Status:**
- ✅ Testing documentation complete
- ✅ Seed script ready
- ⏳ **Blocked by**: Docker not installed on development machine

---

### 2024-12-26 - WhatsApp Integration (Mock Mode)

**What was built:**
- Complete WhatsApp webhook endpoint (GET verification + POST message handling)
- WhatsApp API client with mock mode (send messages, templates)
- Pydantic schemas for Meta's webhook payload format
- **MESSAGE ROUTER** - The core product differentiator:
  - Phone number-based staff vs customer identification
  - Organization lookup by WhatsApp phone_number_id
  - Message deduplication (idempotency)
  - Conversation continuity management
  - Extensive logging for debugging routing decisions
- Simple conversation handlers (staff and customer)
- Test utilities for local testing without Meta credentials
- Full message flow working in mock mode

**Key files created:**
- `app/schemas/whatsapp.py` - Meta webhook payload schemas
- `app/services/whatsapp.py` - WhatsApp API client (with mock mode)
- `app/services/message_router.py` - THE CORE routing logic
- `app/api/v1/webhooks.py` - Webhook endpoints
- `scripts/test_webhook.py` - Local testing utility

**Message Router Architecture:**
```
Message Arrives
     ↓
Lookup Organization (by phone_number_id)
     ↓
Lookup Sender (by phone number)
     ↓
Is Sender Staff? (get_staff_by_phone)
   ├─ YES → StaffConversationHandler
   └─ NO  → CustomerConversationHandler (get_or_create)
     ↓
Process & Respond
```

**Key Implementations:**
1. **Deduplication** - Checks message_id to prevent processing duplicates
2. **Staff Recognition** - `get_staff_by_phone(org_id, phone)` for routing
3. **Incremental Identity** - `get_or_create_customer()` pattern
4. **Conversation Context** - Links messages to conversations
5. **Mock Mode** - Full testing without Meta credentials

**Mock Mode Features:**
- WhatsApp client logs instead of calling Meta API
- Test script simulates webhook payloads
- Can test full flow locally: webhook → router → response
- Easy to switch to production (just update settings)

**Verification:**
- ✅ App loads with webhook endpoints
- ✅ GET /webhooks/whatsapp - Verification endpoint
- ✅ POST /webhooks/whatsapp - Message receiver
- ✅ Message router with extensive logging
- ✅ Test utilities ready for local testing

---

### 2024-12-26 - Core Backend Implementation

**What was built:**
- Comprehensive Pydantic schemas for all entities (Create, Update, Response patterns)
- Service layer with business logic for all core operations
- Complete CRUD API endpoints for:
  - Organizations (with WhatsApp connection)
  - Service Types
  - Staff (with phone lookup for message routing)
  - Customers (with incremental identity pattern)
  - Appointments (with cancel/complete actions)
  - Availability (with slot calculation algorithm)
- API dependencies (organization lookup, pagination, error handling)
- Fully functional availability slot calculation engine

**Key files created:**
- `app/schemas/*.py` - 7 schema files with Create/Update/Response patterns
- `app/services/*.py` - 5 service files with business logic
- `app/api/v1/*.py` - 6 API endpoint files
- `app/api/deps.py` - Common dependencies and utilities

**Key implementations:**
- **Staff phone lookup** (`/staff/lookup`) - Core function for message routing
- **Customer get_or_create** - Incremental identity pattern implementation
- **Availability slot calculation** - Complex scheduling algorithm that:
  - Considers recurring staff availability
  - Applies exception dates
  - Removes conflicting appointments
  - Returns available time slots by staff
- **Organization-scoped endpoints** - All resources properly scoped to organizations

**API Endpoints:**
- 31 total API endpoints across 6 resource types
- All endpoints following REST conventions
- Proper error handling (404, 409 conflicts, validation)
- Pagination support for list endpoints

**Verification:**
- ✅ FastAPI app loads successfully with all 37 routes
- ✅ All imports resolve correctly
- ✅ No circular dependencies
- ✅ Pydantic validation working

**Tests passing:** N/A (no tests written yet)

---

### 2024-12-26 - Project Foundation Setup

**What was built:**
- Complete project structure following PROJECT_SPEC.md architecture
- All 9 core SQLAlchemy models (Organization, Location, Staff, ServiceType, Customer, Appointment, Conversation, Message, Availability)
- FastAPI application skeleton with health endpoints
- Alembic migration configuration
- Docker Compose setup for Postgres + Redis
- Comprehensive README.md with business and technical context
- Development environment with all dependencies

**Key files created:**
- `pyproject.toml` - Python dependencies and project configuration
- `app/models/*.py` - All database models with relationships
- `app/main.py` - FastAPI application entry point
- `app/config.py` - Settings management with pydantic-settings
- `app/database.py` - Async database connection
- `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako` - Migration setup
- `docker-compose.yml` - Local development services
- `.env`, `.env.example` - Environment configuration
- `.gitignore` - Project exclusions
- `README.md` - Comprehensive documentation

**Key decisions made:**
- Used String columns with Enum classes for enum fields (not native Postgres enums) for flexibility
- Staff identified by phone number via unique constraint on (organization_id, phone_number)
- All timestamps in UTC (converted to org timezone only for display)
- Async database operations throughout
- Hatchling as build backend with explicit package configuration

**Tests passing:** N/A (no tests written yet)

**Verification:**
- ✅ FastAPI app loads successfully
- ✅ All models import without errors
- ✅ Virtual environment created with all dependencies installed

---

## In Progress

<!-- Current work that's not yet complete -->

_No tasks currently in progress._

---

## Project Setup Checklist

- [x] Project structure initialized
- [x] pyproject.toml with dependencies
- [x] Docker Compose (Postgres + Redis) - **Config created, needs Docker installed**
- [x] SQLAlchemy models for all entities
- [ ] Initial Alembic migration - **Pending database connection**
- [x] FastAPI app starts successfully
- [x] README.md written

## Core Backend Checklist

- [x] Organization CRUD API
- [x] ServiceType CRUD API
- [x] Staff CRUD API (with phone number lookup)
- [x] Customer CRUD API
- [x] Appointment CRUD API
- [x] Availability engine (slot calculation)
- [ ] Tests for availability edge cases

## WhatsApp Integration Checklist

- [x] Webhook endpoint (POST + GET verification)
- [x] Message parsing from Meta format
- [x] WhatsApp API client (send messages) - **Mock mode**
- [x] Message router (staff vs customer identification)
- [ ] Embedded Signup flow page
- [ ] Message templates submitted to Meta
- [ ] Test with real Meta credentials

## Conversational AI Checklist

- [x] Anthropic client wrapper
- [x] Message routing (staff vs customer)
- [x] Customer conversation handler
- [x] Staff conversation handler
- [x] Customer tools implemented
- [x] Staff tools implemented
- [x] System prompts (Spanish)
- [x] Conversation state management

## Web App Checklist

- [x] Spot model created
- [ ] Spot migrations created (pending database)
- [x] spot_id added to Appointment model
- [x] Location CRUD API endpoints
- [x] Spots CRUD API endpoints
- [ ] Spot conflict detection in scheduling
- [x] AuthToken model created
- [x] JWT utilities
- [x] Auth API endpoints (magic link)
- [x] Next.js project setup
- [x] Auth pages (login, verify)
- [x] Dashboard layout with tabs
- [x] Schedule tab (calendar + list views)
- [x] Employees tab
- [x] Company tab

## Notifications Checklist

- [ ] Celery worker setup
- [ ] Appointment reminder task
- [ ] Daily schedule summary task
- [ ] New booking notification to owner

## Production Readiness Checklist

- [ ] Error handling throughout
- [ ] Logging configured
- [ ] Environment variables documented
- [ ] Deployment configuration
- [ ] Webhook idempotency

---

## Key Decisions Log

<!-- Document important decisions made during development -->

| Date | Decision | Rationale |
|------|----------|-----------|
| 2024-12-27 | Add Web App for business owners | Essential for setup and testing - owners need to manage schedule, employees, and settings |
| 2024-12-27 | Magic link auth via WhatsApp | Aligns with WhatsApp-native experience, no passwords to remember |
| 2024-12-27 | Add Spots model with booking constraints | Chairs/tables need to be tracked, can't double-book same spot |
| 2024-12-27 | Next.js for frontend | App Router, TypeScript, good DX, easy deployment |
| 2024-12-27 | Frontend in `/frontend` folder | Monorepo approach, shared codebase |
| 2024-12-26 | Use String columns with Enum value defaults instead of SQLAlchemy native enums | Provides more flexibility, avoids database-level enum types, easier migrations |
| 2024-12-26 | Staff identification via unique constraint on (organization_id, phone_number) | Enables staff to message the business WhatsApp and be identified automatically |
| 2024-12-26 | All models use UUID primary keys | Better for distributed systems, no collision risk, harder to enumerate |
| 2024-12-26 | Async SQLAlchemy with asyncpg driver | Modern async/await pattern, better performance for I/O operations |
| 2024-12-26 | Hatchling as build backend | Simpler than setuptools, good defaults, widely supported |

---

## Known Issues / Tech Debt

<!-- Track things that need fixing or improving later -->

**Current Issues:**
- Docker not installed on development machine - need to install Docker Desktop to run Postgres/Redis
- Initial Alembic migration not created yet - pending database availability
- Spot conflict detection in scheduling service not yet implemented (model ready, logic pending)

**Technical Debt:**
- Consider adding database indexes for common queries (e.g., appointments by date range, staff by phone)
- May want to add check constraints for business logic (e.g., appointment end > start)
- Consider adding audit fields (created_by, updated_by) for tracking
- Frontend data fetching hooks (`lib/hooks/`) not yet connected to real APIs
- Frontend forms not yet wired to backend mutations

---

## Environment & Accounts

<!-- Track setup status of external services -->

- [ ] Meta Developer App created
- [ ] WhatsApp Business Account set up
- [ ] Anthropic API key obtained
- [ ] Hosting provider selected
- [ ] Database provisioned
- [ ] Domain configured

---

## Notes for Next Session

<!-- Leave notes for yourself or Claude about what to do next -->

**Immediate Next Steps:**

1. **Install Docker Desktop** and start services:
   ```bash
   docker compose up -d
   ```

2. **Create and run migrations** (includes Spot, AuthToken, and spot_id on Appointment):
   ```bash
   source .venv/bin/activate
   alembic revision --autogenerate -m "Initial schema with all entities"
   alembic upgrade head
   ```

3. **Seed test data:**
   ```bash
   python scripts/seed_test_data.py
   ```

4. **Test the full flow:**
   - Backend: `uvicorn app.main:app --reload` (52 routes)
   - Frontend: `cd frontend && npm run dev` (http://localhost:3000)
   - Test magic link auth flow
   - Test webhook routing with `scripts/test_webhook.py`

5. **Wire up frontend to backend:**
   - Connect TanStack Query hooks to real API endpoints
   - Test Schedule, Employees, Company tabs with real data

6. **Add spot conflict detection:**
   - Update `app/services/scheduling.py` to check spot availability
   - Prevent double-booking same spot at same time

**Reference Files:**
- Business context: `docs/PROJECT_SPEC.md`
- Development patterns: `CLAUDE.md`
- Testing guide: `TESTING.md`
- Project overview: `README.md`

**Remember:**
- Mexican Spanish for all user-facing text
- All times stored in UTC
- Staff identified by phone number
- Incremental identity (customers can exist with just phone number)
- JWT auth for web app, WhatsApp for magic link delivery
