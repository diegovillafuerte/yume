# Yume Implementation Workplan

This document tracks progress toward production readiness. Requirements are from `docs/PROJECT_SPEC.md`.

**Last Updated:** 2026-02-03 (Implemented Phases 1-6 of Message Routing Architecture refactor - COMPLETE)

---

## Current Status

**Phase:** Production
**Estimated Completion:** ~85% of core functionality implemented
**Blockers:** None currently
**Deployment:** Render (backend, frontend, PostgreSQL) - migrated from Railway
**LLM:** OpenAI GPT-5.2
**WhatsApp:** Twilio WhatsApp API
**Note:** Celery workers (reminders) deferred to reduce hosting costs

### What's Working
- Backend API (63 endpoints) - deployed on Render
- Database models (15 entities) - Render PostgreSQL
- AI conversation with GPT-5.2 tool calling (customer + staff flows)
- Message routing (staff vs customer identification)
- Availability slot calculation
- Appointment conflict validation (double-booking prevention)
- Admin dashboard (complete)
- Admin Playground (conversation debugger with execution tracing)
- Frontend: login, location/staff/service/spot management, company settings
- Frontend: Schedule page with appointment viewing, filtering, and actions
- Magic link authentication
- Twilio WhatsApp integration (send/receive messages)
- Meta Embedded Signup (connect existing WhatsApp Business numbers)
- Twilio number provisioning (provision new numbers for businesses)

### What's Not Working / Deferred
- **Celery workers** (appointment reminders, trace cleanup) - deferred to reduce hosting costs
- Daily schedule summary task (Phase 3.3)
- New booking notifications (Phase 3.4)
- WhatsApp template messages
- Create/Edit appointment modals in dashboard (deferred)

---

## Phase 1: Foundation Verification ✅ COMPLETE

Phase 1 established the core architecture. All items below are implemented.

| Task | Status |
|------|--------|
| Database models (14 entities) | ✅ |
| SQLAlchemy async setup | ✅ |
| Alembic migrations | ✅ |
| FastAPI application structure | ✅ |
| Pydantic schemas | ✅ |
| Basic CRUD endpoints | ✅ |
| OpenAI integration | ✅ |
| Twilio WhatsApp webhook | ✅ |
| Message routing logic | ✅ |
| AI tool definitions | ✅ |
| Frontend Next.js setup | ✅ |
| Magic link auth | ✅ |
| Admin dashboard | ✅ |

---

## Phase 2: Core Booking Flow

**Goal:** Complete the customer booking journey end-to-end via WhatsApp.

### 2.1 Appointment Conflict Validation ✅ COMPLETE
**Priority:** HIGH
**Files:** `app/api/v1/appointments.py`, `app/services/scheduling.py`, `app/ai/tools.py`

- [x] Add validation in `create_appointment` to check for overlapping appointments
- [x] Check staff availability (not double-booked)
- [x] Check spot availability (not double-booked)
- [x] Return clear error messages when conflicts exist (Spanish)
- [x] Add unit tests for conflict scenarios
- [x] Update AI tools (book_appointment, book_walk_in, reschedule_appointment)

**Implementation:**
- Added `check_appointment_conflicts()` function to `app/services/scheduling.py`
- REST API returns 409 Conflict with Spanish error message
- AI tools return error dict with suggestion for alternatives
- Created `tests/test_scheduling.py` with 13 test cases

**Acceptance:** Cannot create overlapping appointments for same staff or spot.

### 2.2 Complete Schedule Page ✅ COMPLETE
**Priority:** HIGH
**Files:** `frontend/src/app/schedule/page.tsx`, `frontend/src/lib/api/appointments.ts`

- [x] Wire up appointment fetching API
- [x] Display appointments in calendar view
- [x] Display appointments in list view
- [x] Add date navigation (day/week)
- [x] Filter by staff member
- [ ] Add "Create Appointment" modal (deferred - rarely used via dashboard)
- [ ] Add "Edit Appointment" modal (deferred - rarely used via dashboard)
- [x] Add "Cancel Appointment" action with confirmation
- [x] Add "Mark Complete" action
- [x] Add "Mark No-Show" action

**Implementation:**
- Created `frontend/src/lib/api/appointments.ts` with API client functions
- Updated schedule page with data fetching via useEffect/useCallback
- Added staff filter dropdown with real staff data
- Calendar view shows appointments in time slots (8 AM - 8 PM)
- List view shows sortable table with all appointment details
- Added action buttons: Complete, No-Show, Cancel
- Status badges with Spanish labels and color coding
- Loading and empty states with appropriate messaging

**Acceptance:** Business owner can view, cancel, complete appointments from dashboard.

### 2.3 AI Tool Fixes ✅ COMPLETE
**Priority:** MEDIUM
**Files:** `app/ai/tools.py`

- [x] Verify `check_availability` returns correct slots (fixed slot.date bug)
- [x] Verify `book_appointment` creates appointment with all required fields (added staff_name support)
- [x] Verify `cancel_appointment` works for customer's own appointments (added ownership validation)
- [x] Verify `reschedule_appointment` checks availability before moving (added ownership validation)
- [x] Add `update_customer_info` tool to capture name during booking (new tool added)
- [ ] Test complete booking flow via WhatsApp (requires live testing)

**Fixes Applied:**
- Fixed `check_availability`: `slot.date` → `slot.start_time` (bug fix)
- Fixed `book_appointment`: Now respects `staff_name` parameter
- Fixed `cancel_appointment`: Added customer ownership validation (security fix)
- Fixed `reschedule_appointment`: Added customer ownership validation (security fix)
- Added `update_customer_info` tool: Allows updating customer name during conversation

**Acceptance:** Customer can book, view, cancel, reschedule appointments via WhatsApp conversation.

### 2.4 Staff WhatsApp Flow ✅ COMPLETE
**Priority:** MEDIUM
**Files:** `app/ai/tools.py`, `app/ai/prompts.py`

- [x] Enhanced `get_my_schedule` returns staff's appointments + blocked times
- [x] Improved staff system prompt with relative date handling (today/tomorrow)
- [x] Verify `block_time` creates availability exception
- [x] Verify `mark_appointment_complete` updates status
- [x] Verify `mark_no_show` updates status
- [x] Verify `book_walk_in` creates appointment with source=walk_in
- [ ] Test complete staff flow via WhatsApp (requires live testing)

**Implementation:**
- Staff prompt now includes today/tomorrow dates for AI to interpret relative dates
- `get_my_schedule` returns formatted display string with emojis for easy response
- Tool descriptions enhanced to help AI understand date/time parsing
- Schedule results grouped by type (appointments vs blocked time)

**Acceptance:** Staff can view schedule, block time, manage appointments via WhatsApp.

---

## Phase 3: Background Tasks & Notifications

**Goal:** Implement Celery workers for reminders and notifications.

### 3.1 Celery Setup ✅ COMPLETE
**Priority:** HIGH
**Files:** `app/tasks/`, `app/config.py`, `docker-compose.yml`

- [x] Create `app/tasks/celery_app.py` with Celery configuration
- [x] Add Celery worker to docker-compose
- [x] Verify Redis connection for task queue
- [x] Create basic health check task
- [x] Create appointment reminder task with Celery Beat schedule

**Implementation:**
- Created `app/tasks/celery_app.py` with Redis broker configuration
- Created `app/tasks/health.py` with ping/echo tasks
- Created `app/tasks/reminders.py` with reminder tasks
- Added `celery-worker` and `celery-beat` services to docker-compose.yml
- Beat schedule checks for reminders every 5 minutes

**Acceptance:** `celery -A app.tasks.celery_app worker` starts without errors.

### 3.2 Appointment Reminders ✅ COMPLETE
**Priority:** HIGH
**Files:** `app/tasks/reminders.py`, `app/services/whatsapp.py`
**Requirement:** 3.5.2

- [x] Create `send_appointment_reminder` task
- [x] Schedule reminder 24 hours before appointment
- [x] Use Twilio to send WhatsApp message
- [x] Create reminder message template (Spanish)
- [x] Add Celery Beat schedule for checking upcoming appointments
- [x] Mark `reminder_sent_at` on appointment after sending
- [ ] Handle failed sends gracefully (retry logic) - basic error handling added

**Implementation:**
- `check_and_send_reminders` runs every 5 minutes via Celery Beat
- Finds appointments in 23-25 hour window without reminders sent
- `send_appointment_reminder` sends individual WhatsApp messages
- Spanish message with date/time in org timezone
- Dev mode logs instead of sending when no Twilio credentials

**Acceptance:** Customers receive WhatsApp reminder 24 hours before appointment.

### 3.3 Daily Schedule Summary
**Priority:** MEDIUM
**Files:** `app/tasks/notifications.py`
**Requirement:** 1.6.22

- [ ] Create `send_daily_schedule` task
- [ ] Run at configured time (e.g., 7 AM local time)
- [ ] Format schedule as WhatsApp message
- [ ] Send to business owner's WhatsApp
- [ ] Include: appointments for the day, any blocked times

**Acceptance:** Business owner receives daily schedule summary each morning.

### 3.4 New Booking Notifications
**Priority:** MEDIUM
**Files:** `app/ai/tools.py`, `app/services/whatsapp.py`
**Requirement:** 1.6.21

- [ ] When `book_appointment` tool succeeds, notify owner
- [ ] Send WhatsApp message with booking details
- [ ] Include: customer name/phone, service, time, staff

**Acceptance:** Business owner receives notification when new appointment is booked.

### 3.5 Cancellation Notifications
**Priority:** MEDIUM
**Requirement:** 3.5.3, 3.5.4

- [ ] Notify customer when appointment cancelled by business
- [ ] Notify customer when appointment rescheduled by business
- [ ] Use template messages for outside 24-hour window

**Acceptance:** Customers notified of changes to their appointments.

---

## Phase 4: Web Dashboard Completion

**Goal:** Complete remaining dashboard functionality.

### 4.1 Customer Management
**Priority:** MEDIUM
**Files:** `frontend/src/app/customers/page.tsx` (new)
**Requirements:** 1.7.x

- [ ] Create customers list page
- [ ] Add customer search by name/phone
- [ ] Add customer detail view
- [ ] Show appointment history for customer
- [ ] Allow editing customer details
- [ ] Allow adding notes to customer

**Acceptance:** Business owner can view and manage customers from dashboard.

### 4.2 Availability Management
**Priority:** MEDIUM
**Files:** `frontend/src/app/availability/page.tsx` (new), `app/api/v1/availability.py`
**Requirements:** 1.8.x

- [ ] Fix org validation in availability endpoints
- [ ] Create availability management UI
- [ ] Allow blocking time for all employees (holiday)
- [ ] Allow blocking time for specific employee
- [ ] Show blocked times in schedule view
- [ ] Allow removing blocks

**Acceptance:** Business owner can manage availability and block times.

### 4.3 Business Hours Management
**Priority:** MEDIUM
**Files:** `frontend/src/app/company/page.tsx`
**Requirement:** 1.2.3, 1.2.4

- [ ] Add business hours editor to location settings
- [ ] Allow setting open/close time per day
- [ ] Allow marking days as closed
- [ ] Validate hours (open < close)
- [ ] Update AI prompts to use actual location hours

**Acceptance:** Business owner can set business hours per location.

---

## Phase 5: WhatsApp Onboarding Flow ✅ COMPLETE

**Goal:** Allow business owners to complete initial setup via WhatsApp conversation.

### 5.1 Onboarding Conversation Handler ✅ COMPLETE
**Priority:** MEDIUM
**Files:** `app/services/onboarding.py`, `app/ai/prompts.py`
**Requirements:** 1.1.x

- [x] Create onboarding conversation state machine
- [x] Collect: business name, owner name, business type
- [x] Collect: services (name, duration, price)
- [x] Collect: business hours
- [x] Collect: staff members (name, phone, services)
- [x] Collect: address and city (optional)
- [x] Create organization, location, staff (owner + employees), services
- [x] Send confirmation when setup complete
- [x] Provide link to web dashboard

**Implementation:**
- Conversational AI flow collects business info progressively
- 8 AI tools: save_business_info, add_service, get_current_menu, add_staff_member, save_business_hours, complete_onboarding, send_whatsapp_connect_link, send_dashboard_link
- Supports optional staff member collection with service specialties
- Creates full organization structure on completion
- Uses frontend_url from config (not hardcoded)

**Acceptance:** New business can set up Yume by messaging Yume's WhatsApp number.

### 5.2 WhatsApp Number Connection ✅ COMPLETE
**Priority:** HIGH (for production)
**Requirements:** 1.1.5, 6.1.5

- [x] Twilio number provisioning service created
- [x] Meta Embedded Signup integration (for connecting existing numbers)
- [x] Store phone_number_id and access tokens per organization
- [x] Multi-business webhook routing based on phone_number_id
- [x] Meta Cloud API webhook endpoint (receive messages from connected business numbers)
- [x] Webhook signature verification (HMAC-SHA256)
- [x] Webhook registration with Meta after business connects

**Implementation:**
- `app/services/twilio_provisioning.py` - Service to list, purchase, and configure Twilio numbers
- Organizations store `whatsapp_phone_number_id` and `whatsapp_access_token`
- Message router identifies org by incoming phone_number_id
- Supports hybrid approach: Yume provisioned numbers + business's own numbers
- `GET /api/v1/webhooks/whatsapp/meta` - Webhook verification endpoint for Meta
- `POST /api/v1/webhooks/whatsapp/meta` - Receive messages from Meta Cloud API
- `register_webhook_with_meta()` in connect.py - Subscribe to WABA webhooks after connection
- Token expiry stored in org settings (60 days from connection)

**Manual Setup Required:**
1. Configure Meta App Dashboard with webhook URL: `https://yume-backend.onrender.com/api/v1/webhooks/whatsapp/meta`
2. Set verify token to match `META_WEBHOOK_VERIFY_TOKEN` env var (default: `yume-webhook-token`)
3. Subscribe to `messages` field

**Acceptance:** Each business can connect their own WhatsApp number or get a Yume-provisioned number.

### 5.3 Conversation Debug Playground ✅ COMPLETE
**Priority:** MEDIUM
**Files:** Multiple new files

**Backend:**
- [x] Create ExecutionTrace model with JSONB columns for flexible trace storage
- [x] Create ExecutionTracer service with context manager pattern
- [x] Modify conversation.py to add optional tracer parameter
- [x] Modify message_router.py for tracing and skip_whatsapp_send
- [x] Add 6 new playground API endpoints
- [x] Add Celery cleanup task for traces older than 30 days

**Frontend:**
- [x] Create playground page with two-column layout
- [x] UserSelector component (dropdown with search)
- [x] UserInfoPanel component (selected user details)
- [x] ChatEmulator component (WhatsApp-style chat)
- [x] ExecutionLogger component (expandable trace view L1/L2)
- [x] TraceDetailModal component (full trace detail L3)
- [x] Add Playground tab to admin navigation

**New Files Created:**
- `app/models/execution_trace.py`
- `app/services/execution_tracer.py`
- `app/services/playground.py`
- `app/schemas/playground.py`
- `app/tasks/cleanup.py`
- `alembic/versions/20260127_*_add_execution_traces_table.py`
- `frontend/src/app/admin/playground/page.tsx`
- `frontend/src/components/admin/playground/*.tsx` (5 files)
- `frontend/src/lib/api/playground.ts`

**Key Features:**
- Emulate conversations from any user (staff/customer)
- Process messages through real AI pipeline
- Skip WhatsApp sending in playground mode
- Three-level execution trace viewer:
  - L1: Exchange tiles with total latency
  - L2: Processing steps with emoji indicators (🧠 LLM, ⚙️ Tool)
  - L3: Full trace detail in modal (prompts, tool params, responses)
- Automatic trace cleanup after 30 days

**Acceptance:** Admins can debug any conversation with full pipeline visibility.

---

## Phase 5.4: Message Routing Architecture ✅ PHASE 1 COMPLETE

**Goal:** Implement the two-channel message routing architecture from `docs/PROJECT_SPEC.md`.

### Phase 1: Core Routing Logic ✅ COMPLETE

- [x] Add `first_message_at` field to YumeUser model (tracks first WhatsApp message)
- [x] Add `permission_level` field to YumeUser model (owner/admin/staff/viewer)
- [x] Create migration for new fields
- [x] Add `get_all_staff_registrations()` to find ALL staff records for a phone
- [x] Implement 5-case routing decision tree:
  - Case 1: Unknown sender to Yume Central → Business Onboarding
  - Case 2a: Staff of 1 business to Yume Central → Business Management
  - Case 2b: Staff of 2+ businesses to Yume Central → Redirect Message
  - Case 3: Pre-registered staff (first msg) to Business Number → Staff Onboarding
  - Case 4: Known staff to Business Number → Business Management
  - Case 5: Anyone else to Business Number → End Customer
- [x] Fix onboarding restart bug (completed sessions now redirect to staff flow)

**Files Modified:**
- `app/models/yume_user.py` - Added `first_message_at`, `permission_level`, `YumeUserPermissionLevel` enum
- `app/models/__init__.py` - Export new enum
- `app/services/staff.py` - Added `get_all_staff_registrations()`, `mark_first_message()`, `is_first_message()`
- `app/services/message_router.py` - Full refactor with 5-case routing
- `app/services/onboarding.py` - Fixed to detect completed sessions
- `alembic/versions/20260203_*.py` - Migration for new fields

### Phase 2: Business Onboarding Flow Alignment ✅ COMPLETE

- [x] Update `OnboardingState` enum to match architecture states (STARTED → INITIATED)
- [x] Strengthen AI prompt to ALWAYS call `complete_onboarding` tool
- [x] Add detailed logging for tool execution
- [x] Set `permission_level` to 'owner' for business owners during creation
- [ ] Test end-to-end onboarding flow (requires live testing)

**Files Modified:**
- `app/models/onboarding_session.py` - Renamed STARTED → INITIATED, added docstrings
- `app/services/onboarding.py` - Strengthened prompt, added detailed logging, set owner permission_level
- `alembic/versions/20260203_0930_*.py` - Migration to update existing 'started' states

### Phase 3: Staff Onboarding Flow ✅ COMPLETE

- [x] Create `StaffOnboardingSession` model with state machine
- [x] Create `StaffOnboardingHandler` service with AI tool calling
- [x] Implement staff onboarding state machine (initiated → collecting_name → collecting_availability → showing_tutorial → completed)
- [x] Update message_router.py to use StaffOnboardingHandler for Case 3
- [x] Handle pending onboarding in Case 4 (check for incomplete sessions)
- [x] Notify owner when staff completes onboarding

**Files Created:**
- `app/models/staff_onboarding_session.py` - Model with `StaffOnboardingState` enum
- `app/services/staff_onboarding.py` - Handler with AI tools (confirm_name, save_availability, complete_tutorial)
- `alembic/versions/20260203_1000-f6a7b8c9d0e1_add_staff_onboarding_sessions_table.py` - Migration

### Phase 4: End Customer Flow State Machines ✅ COMPLETE

- [x] Create `CustomerFlowSession` model with flow types (booking, modify, cancel, rating)
- [x] Create `CustomerFlowState` enum covering all states across flows
- [x] Create migration for `customer_flow_sessions` table
- [x] Create `CustomerFlowHandler` service with:
  - State-aware system prompts that guide AI based on current flow state
  - Automatic flow detection from tool usage
  - State transitions based on tool results
  - Abandoned state handling (30 min timeout)
  - Resume capability for interrupted flows
- [x] Update message_router.py to use CustomerFlowHandler for Case 5
- [x] Implement booking flow state machine: initiated → collecting_service → collecting_datetime → collecting_staff_preference → collecting_personal_info → confirming_summary → confirmed
- [x] Implement modify flow state machine: initiated → identifying_booking → selecting_modification → collecting_new_* → confirming_summary → confirmed
- [x] Implement cancel flow state machine: initiated → identifying_booking → confirming_cancellation → cancelled
- [x] Rating flow states defined (triggered by Celery task after appointment)

**Files Created:**
- `app/models/customer_flow_session.py` - Model with `CustomerFlowType` and `CustomerFlowState` enums
- `app/services/customer_flows.py` - Handler with flow-aware prompts and state tracking
- `alembic/versions/20260203_1100-g7h8i9j0k1l2_add_customer_flow_sessions_table.py` - Migration

**Note:** Rating flow prompting depends on Celery workers (deferred). The state machine is ready.

### Phase 5: Business Management Flows + Permissions ✅ COMPLETE

- [x] Create `app/services/permissions.py` with permission matrix
- [x] Implement permission checking in tool handler (staff tools check permissions before execution)
- [x] Add new management tools (owner/admin only):
  - `get_business_stats` - View business statistics
  - `add_staff_member` - Add new employees
  - `remove_staff_member` - Deactivate employees
  - `change_staff_permission` - Change permission levels (owner only)
- [x] Update staff system prompt with permission-level information
- [x] Add permission-denied error messages (Spanish)

**Files Created:**
- `app/services/permissions.py` - Permission matrix, checking functions, tool-permission mapping

**Files Modified:**
- `app/ai/tools.py` - Added permission checking in execute_tool(), added 4 new management tools
- `app/ai/prompts.py` - Updated format_staff_permissions() to show level-based capabilities

### Phase 6: Universal Patterns ✅ COMPLETE

- [x] Create `app/services/abandoned_state.py` with centralized abandoned state logic
- [x] Add Celery task `check_abandoned_sessions` for all session types
- [x] Add Celery beat schedule (every 10 minutes)
- [x] Create `app/services/customer_profile.py` for cross-business lookup
- [x] Enhance EndCustomer model with profile fields:
  - `name_verified_at` - When customer confirmed their name
  - `profile_data` - JSONB for preferences and history
- [x] Create migration for EndCustomer profile fields
- [x] Update CustomerFlowHandler to use profile data in prompts
- [x] Implement returning customer experience:
  - Cross-business name lookup
  - Preference detection (times, days, services)
  - Name reconfirmation logic (30-day threshold)
- [x] Update flow-aware prompts with customer context

**Files Created:**
- `app/services/abandoned_state.py` - Centralized abandoned state pattern
- `app/services/customer_profile.py` - Cross-business lookup and profile management
- `alembic/versions/20260203_1200-h8i9j0k1l2m3_add_end_customer_profile_fields.py` - Migration

**Files Modified:**
- `app/models/end_customer.py` - Added name_verified_at, profile_data fields
- `app/services/customer_flows.py` - Integrated profile and abandoned state services
- `app/tasks/cleanup.py` - Added check_abandoned_sessions task
- `app/tasks/celery_app.py` - Added beat schedule for abandoned check

---

## Message Routing Architecture Implementation ✅ COMPLETE

All 6 phases of the Message Routing Architecture refactor are now implemented:

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Core Routing Logic (5-case decision tree) | ✅ |
| 2 | Business Onboarding Flow Alignment | ✅ |
| 3 | Staff Onboarding Flow | ✅ |
| 4 | End Customer Flow State Machines | ✅ |
| 5 | Business Management Flows + Permissions | ✅ |
| 6 | Universal Patterns (Abandoned State, Profiles) | ✅ |

See `docs/PROJECT_SPEC.md` for the full specification.

---

## Phase 6: Testing & Quality

**Goal:** Ensure reliability through comprehensive testing.

### 6.1 API Integration Tests
**Priority:** HIGH
**Files:** `tests/test_api/`

- [ ] Test all organization endpoints
- [ ] Test all location endpoints
- [ ] Test all staff endpoints
- [ ] Test all service endpoints
- [ ] Test all spot endpoints
- [ ] Test all appointment endpoints
- [ ] Test all availability endpoints
- [ ] Test all auth endpoints
- [ ] Test admin endpoints
- [ ] Test webhook endpoint with mock payloads

**Acceptance:** `pytest tests/test_api/` passes with >80% coverage.

### 6.2 AI Conversation Tests
**Priority:** HIGH
**Files:** `tests/test_ai/`

- [ ] Test customer booking flow end-to-end
- [ ] Test customer cancellation flow
- [ ] Test customer reschedule flow
- [ ] Test staff schedule viewing
- [ ] Test staff time blocking
- [ ] Test staff walk-in booking
- [ ] Test handoff to human
- [ ] Test edge cases (no availability, invalid dates)

**Acceptance:** AI conversation flows work correctly with mocked OpenAI.

### 6.3 Frontend Tests
**Priority:** MEDIUM
**Files:** `frontend/`

- [ ] Add component tests for critical forms
- [ ] Add integration tests for auth flow
- [ ] Add integration tests for appointment CRUD
- [ ] Test mobile responsiveness

**Acceptance:** Key user flows work correctly in browser.

### 6.4 Load Testing
**Priority:** LOW
**Requirement:** 5.4.x

- [ ] Test webhook response time under load
- [ ] Verify <20 second response time
- [ ] Test concurrent appointment bookings
- [ ] Test database query performance

**Acceptance:** System handles expected load without degradation.

---

## Phase 7: Production Readiness

**Goal:** Prepare for deployment and real users.

### 7.1 Security Hardening
**Priority:** HIGH
**Requirements:** 5.3.x

- [ ] Change all default passwords/secrets
- [ ] Verify organization scoping on all queries
- [ ] Add rate limiting to API
- [ ] Add rate limiting to webhook
- [ ] Verify no sensitive data in logs
- [ ] Review SQL injection prevention
- [ ] Review XSS prevention in frontend
- [ ] Add HTTPS enforcement
- [ ] Add CORS configuration

**Acceptance:** Security checklist complete.

### 7.2 Error Handling
**Priority:** MEDIUM
**Requirements:** 5.8.x

- [ ] Add Sentry or equivalent error tracking
- [ ] Ensure all errors return appropriate HTTP status
- [ ] Add user-friendly error messages in Spanish
- [ ] Ensure webhook always returns 200 (prevent Meta retries)
- [ ] Add graceful degradation when OpenAI unavailable
- [ ] Add graceful degradation when Twilio unavailable

**Acceptance:** Errors are tracked and handled gracefully.

### 7.3 Deployment Setup ✅ COMPLETE
**Priority:** HIGH
**Requirements:** 7.3.x

- [x] Choose hosting provider → Render (migrated from Railway 2026-02-01)
- [x] Set up managed PostgreSQL → Render PostgreSQL
- [ ] ~~Set up managed Redis~~ → Deferred (only needed for Celery)
- [x] Configure environment variables
- [ ] Set up CI/CD pipeline
- [ ] Configure domain (api.yume.mx, app.yume.mx)
- [x] Set up SSL certificates → Render provides HTTPS
- [x] Deploy backend
- [x] Deploy frontend
- [ ] ~~Deploy Celery worker~~ → Deferred (see Future Features)

**Acceptance:** System deployed and accessible on Render URLs.

### 7.4 Monitoring
**Priority:** MEDIUM
**Requirements:** 7.4.x

- [ ] Add health check endpoints
- [ ] Set up uptime monitoring
- [ ] Set up log aggregation
- [ ] Create alerting for critical errors
- [ ] Monitor API response times
- [ ] Monitor webhook processing times

**Acceptance:** System health is monitored with alerts.

---

## Requirements Coverage Matrix

This maps PROJECT_SPEC.md requirements to implementation tasks.

### 1. Business Owner Requirements

| Req | Description | Status | Phase |
|-----|-------------|--------|-------|
| 1.1.x | Create account (onboarding) | ✅ Done | 5.1 |
| 1.2.1-2 | Location name/address | ✅ Done | 1 |
| 1.2.3-4 | Business hours | ❌ UI needed | 4.3 |
| 1.2.5-9 | Services, spots setup | ✅ Done | 1 |
| 1.3.x | Employee management | ✅ Done | 1 |
| 1.4.x | Service management | ✅ Done | 1 |
| 1.5.x | Spot management | ✅ Done | 1 |
| 1.6.1-8 | View appointments | 🔶 Partial | 2.2 |
| 1.6.9-20 | Manage appointments | 🔶 Partial | 2.2 |
| 1.6.21 | New booking notification | ❌ Not started | 3.4 |
| 1.6.22 | Daily schedule summary | ❌ Not started | 3.3 |
| 1.7.x | Customer management | 🔶 API done, UI needed | 4.1 |
| 1.8.x | Availability management | 🔶 API done, UI needed | 4.2 |
| 1.9.x | Web dashboard access | ✅ Done | 1 |
| 1.10.x | Business settings | ✅ Done | 1 |

### 2. Employee Requirements

| Req | Description | Status | Phase |
|-----|-------------|--------|-------|
| 2.1.x | Employee onboarding | ✅ Done (via owner onboarding) | 5.1 |
| 2.2.x | View my schedule | ✅ AI tools enhanced | 2.4 |
| 2.3.x | View business schedule | ✅ AI tools done | 2.4 |
| 2.4.x | Manage appointments | ✅ AI tools done | 2.4 |
| 2.5.x | Manage availability | ✅ AI tools done | 2.4 |
| 2.6.x | Customer lookup | ✅ AI tools done | 2.4 |
| 2.7.x | Customer messaging | 🔶 Needs testing | 2.4 |

### 3. Customer Requirements

| Req | Description | Status | Phase |
|-----|-------------|--------|-------|
| 3.1.x | Discover & initiate | ✅ Done | 1 |
| 3.2.x | Book appointment | ✅ AI tools done | 2.3 |
| 3.3.x | View appointments | ✅ AI tools done | 2.3 |
| 3.4.x | Modify appointments | ✅ AI tools done | 2.3 |
| 3.5.1 | Booking confirmation | ✅ Done (in conversation) | 1 |
| 3.5.2 | 24h reminder | ⏸️ Deferred (needs Celery) | 3.2 |
| 3.5.3-4 | Cancellation/reschedule notification | ❌ Not started | 3.5 |
| 3.6.x | Get help / handoff | ✅ AI tools done | 1 |

### 4. Admin Requirements

| Req | Description | Status | Phase |
|-----|-------------|--------|-------|
| 4.1.x | Admin access | ✅ Done | 1 |
| 4.2.x | Platform statistics | ✅ Done | 1 |
| 4.3.x | Manage organizations | ✅ Done | 1 |
| 4.4.x | Debug conversations | ✅ Done (Playground with execution tracing) | 5.3 |
| 4.5.x | Monitor activity | ✅ Done | 1 |
| 4.6.x | Perform org actions | ✅ Done (via impersonation) | 1 |

### 5. Non-Functional Requirements

| Req | Description | Status | Phase |
|-----|-------------|--------|-------|
| 5.1.x | Spanish/Localization | ✅ Done | 1 |
| 5.2.x | Timezone handling | ✅ Done | 1 |
| 5.3.x | Security | 🔶 Partial | 7.1 |
| 5.4.x | Performance | ❌ Not tested | 6.4 |
| 5.5.x | Reliability | 🔶 Partial | 3.x |
| 5.6.x | Data integrity | 🔶 Constraints exist, validation needed | 2.1 |
| 5.7.x | Mobile experience | ✅ Responsive | 1 |
| 5.8.x | Error handling | 🔶 Partial | 7.2 |

### 6. Integration Requirements

| Req | Description | Status | Phase |
|-----|-------------|--------|-------|
| 6.1.x | WhatsApp API | ✅ Twilio implemented | 1 |
| 6.2.x | Message templates | ❌ Need Twilio Content setup | 3.x |
| 6.3.x | AI/LLM | ✅ GPT-5.2 implemented | 1 |
| 6.4.x | Background tasks | ⏸️ Celery code ready, workers deferred | 3.1 |

### 7. Infrastructure Requirements

| Req | Description | Status | Phase |
|-----|-------------|--------|-------|
| 7.1.x | Database | ✅ Render PostgreSQL | 7.3 |
| 7.2.x | Redis | ⏸️ Deferred (not needed without Celery) | 7.3 |
| 7.3.x | Deployment | ✅ Render (backend + frontend) | 7.3 |
| 7.4.x | Monitoring | ❌ Not set up | 7.4 |

---

## Implementation Priority Order

Based on dependencies and business value:

1. **Phase 2.1** - Appointment conflict validation (blocks booking reliability)
2. **Phase 2.3** - AI tool fixes (blocks WhatsApp booking flow)
3. **Phase 2.2** - Schedule page completion (blocks dashboard usability)
4. **Phase 3.1** - Celery setup (blocks all notifications)
5. **Phase 3.2** - Appointment reminders (high customer value)
6. **Phase 6.1** - API tests (ensures stability)
7. **Phase 4.3** - Business hours (needed for accurate availability)
8. **Phase 3.4** - Booking notifications (owner visibility)
9. **Phase 4.1** - Customer management UI
10. **Phase 4.2** - Availability management UI
11. **Phase 7.1** - Security hardening (before production)
12. **Phase 7.3** - Deployment
13. **Phase 5.x** - Onboarding flow (can use manual setup initially)

---

## Notes for Next Session

- **Deployed on Render:** Backend, frontend, PostgreSQL (migrated from Railway 2026-02-01)
- **LLM:** Using GPT-5.2 for all AI conversations
- **WhatsApp:** Using Twilio API (not Meta direct)
- Phase 2 Core (2.1-2.4) and Phase 5 now COMPLETE
- **Celery workers deferred:** No Redis, no background workers to save on hosting costs
- **Playground:** Conversation debugger in admin dashboard (Phase 5.3)
  - Traces stored for ALL messages for retroactive debugging
  - Note: Trace cleanup task won't run without Celery worker
- Onboarding flow: Business owners can set up via WhatsApp conversation in <15 min
- Customer booking flow enhanced: Faster booking with flexible date interpretation
- Staff tools enhanced: Better schedule display with blocked times
- Twilio provisioning service ready but not integrated into onboarding flow yet
- Create/Edit appointment modals were deferred - most appointments come via WhatsApp
- Custom domain (api.yume.mx, app.yume.mx) still needs to be configured

---

## Future Features (To Add Later)

Features deferred to reduce initial hosting costs or complexity. Add these when needed.

### High Priority (Add when scaling)

| Feature | Description | Why Deferred | To Implement |
|---------|-------------|--------------|--------------|
| **Celery Workers** | Background task processing for reminders and cleanup | Requires paid tier ($14/mo for Redis + workers) | Add Redis + 2 background workers on Render |
| **24-Hour Reminders** | WhatsApp reminder 24 hours before appointment | Requires Celery workers | `app/tasks/reminders.py` already written |
| **Trace Cleanup** | Auto-delete execution traces older than 30 days | Requires Celery workers | `app/tasks/cleanup.py` already written |
| **Daily Schedule Summary** | Morning WhatsApp with day's appointments | Requires Celery workers | Phase 3.3 in workplan |

### Medium Priority (Nice to have)

| Feature | Description | Why Deferred | To Implement |
|---------|-------------|--------------|--------------|
| **New Booking Notifications** | Notify owner when appointment booked | Not critical for MVP | Phase 3.4 |
| **Cancellation Notifications** | Notify customer when business cancels | Not critical for MVP | Phase 3.5 |
| **Customer Management UI** | View/edit customers in dashboard | Can use admin impersonation | Phase 4.1 |
| **Availability Management UI** | Block times via dashboard | Staff can do via WhatsApp | Phase 4.2 |
| **Business Hours UI** | Edit hours per location | Currently set in onboarding | Phase 4.3 |

### Low Priority (Future roadmap)

| Feature | Description | Why Deferred | To Implement |
|---------|-------------|--------------|--------------|
| **Custom Domains** | api.yume.mx, app.yume.mx | Not needed for beta | Render custom domains |
| **Create/Edit Appointment Modal** | Dashboard appointment creation | Most bookings via WhatsApp | Frontend modal |
| **WhatsApp Template Messages** | Pre-approved message templates | Only needed for >24h window | Twilio Content API |
| **CI/CD Pipeline** | Automated testing/deployment | Manual deploy works for now | GitHub Actions |
| **Load Testing** | Performance verification | Not enough traffic yet | Phase 6.4 |
| **Sentry Integration** | Error tracking | Console logs sufficient for now | Phase 7.2 |

### Cost Estimate for Full Features

To enable all background workers on Render:
- Redis (Starter): ~$7/month
- Background Worker x2 (Starter): ~$14/month
- **Total additional cost: ~$21/month**

---

## Changelog

| Date | Changes |
|------|---------|
| 2026-02-03 | **MESSAGE ROUTING ARCHITECTURE COMPLETE** - All 6 phases implemented |
| 2026-02-03 | Implemented Phase 6: Universal Patterns (Abandoned State + Customer Profiles) |
| 2026-02-03 | Created abandoned_state.py with centralized timeout/resume logic |
| 2026-02-03 | Created customer_profile.py with cross-business lookup and preferences |
| 2026-02-03 | Added EndCustomer profile fields (name_verified_at, profile_data) |
| 2026-02-03 | Added Celery task check_abandoned_sessions with 10-minute schedule |
| 2026-02-03 | Updated CustomerFlowHandler with profile-aware prompts |
| 2026-02-03 | Implemented Phase 5: Business Management Flows + Permissions |
| 2026-02-03 | Created permissions.py with PERMISSION_MATRIX and helper functions |
| 2026-02-03 | Added permission checking to tool handler for staff tools |
| 2026-02-03 | Added 4 new management tools: get_business_stats, add_staff_member, remove_staff_member, change_staff_permission |
| 2026-02-03 | Updated staff prompts with permission-level information |
| 2026-02-03 | Implemented Phase 4: End Customer Flow State Machines |
| 2026-02-03 | Created CustomerFlowSession model with flow types and states |
| 2026-02-03 | Created CustomerFlowHandler service with state-aware prompts |
| 2026-02-03 | Updated message_router to use CustomerFlowHandler for customer messages |
| 2026-02-03 | Implemented Phase 3: Staff Onboarding Flow (complete) |
| 2026-02-03 | Created StaffOnboardingSession model with state machine |
| 2026-02-03 | Created StaffOnboardingHandler service with AI tools |
| 2026-02-03 | Added owner notification when staff completes onboarding |
| 2026-02-03 | Implemented Phase 2: Business Onboarding Flow Alignment |
| 2026-02-03 | Renamed OnboardingState.STARTED → INITIATED for architecture consistency |
| 2026-02-03 | Strengthened AI prompt to ensure complete_onboarding is called |
| 2026-02-03 | Added detailed logging for onboarding tool execution |
| 2026-02-03 | Implemented Phase 1 of Message Routing Architecture (5-case routing decision tree) |
| 2026-02-03 | Added `first_message_at` and `permission_level` fields to YumeUser model |
| 2026-02-03 | Added `get_all_staff_registrations()` for multi-business staff detection |
| 2026-02-03 | Added Case 2b: Multi-business staff redirect message |
| 2026-02-03 | Added Case 3: Staff onboarding welcome message for first-time staff |
| 2026-02-03 | Fixed onboarding restart bug (completed sessions now redirect to staff flow) |
| 2026-02-02 | Added Meta Cloud API webhook endpoints (GET verify + POST receive messages) |
| 2026-02-02 | Added webhook registration with Meta after business connects via Embedded Signup |
| 2026-02-02 | Added signature verification for Meta webhooks (HMAC-SHA256) |
| 2026-02-02 | Updated test_webhook.py script to support both Meta and Twilio formats |
| 2026-02-02 | Updated all documentation to reflect Render deployment (removed Railway references) |
| 2026-02-01 | Migrated from Railway to Render (backend, frontend, PostgreSQL) |
| 2026-02-01 | Deferred Celery workers (Redis, reminders, cleanup) to reduce hosting costs |
| 2026-02-01 | Added Future Features section to track deferred functionality |
| 2026-01-27 | Completed Phase 5.3: Conversation Debug Playground with execution tracing |
| 2026-01-27 | Added ExecutionTrace model, ExecutionTracer service, 6 playground API endpoints |
| 2026-01-27 | Added Celery cleanup task for execution traces (30-day retention) |
| 2026-01-27 | Updated PROJECT_SPEC.md: Twilio WhatsApp API, GPT-5.2 |
| 2026-01-27 | Completed Phase 7.3: Deployed on Railway (backend, frontend, PostgreSQL, Redis) |
| 2026-01-26 | Completed Phase 5.1: Full onboarding conversation flow with staff collection |
| 2026-01-26 | Completed Phase 5.2: Twilio number provisioning service + Meta Embedded Signup |
| 2026-01-26 | Enhanced Phase 2.4: Staff tools with better date handling and schedule display |
| 2026-01-26 | Enhanced customer booking: Better availability display, grouped by date |
| 2026-01-26 | Improved AI prompts: Faster booking flow, flexible date interpretation |
| 2026-01-06 | Completed Phase 3.1 & 3.2: Celery setup with appointment reminders |
| 2026-01-06 | Completed Phase 2.2: Schedule page with data fetching, filtering, actions |
| 2026-01-06 | Completed Phase 2.3: AI tool fixes (6 bugs/improvements) |
| 2026-01-06 | Completed Phase 2.1: Appointment conflict validation |
| 2026-01-06 | Initial workplan created from codebase analysis |
