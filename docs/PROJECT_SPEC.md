# Parlo: Project Initialization Prompt for Claude Code
<!-- last-verified: 2026-02-15 -->

## Instructions for Claude Code

You are initializing the codebase for **Parlo**, a WhatsApp-native AI scheduling assistant for beauty businesses in Mexico (hair and nail saloons, etc.). This document provides complete business and technical context. Your first task is to create the project structure, including a comprehensive README.md that will serve as the source of truth for any engineer or AI agent working on this codebase.

Read this entire document before writing any code. Ask clarifying questions if anything is ambiguous.

---

## Part 1: Business Context

### What is Parlo?

Parlo is a conversational AI that handles appointment scheduling for beauty businesses (barbershops, nail salons, hair salons, spas) in Mexico via WhatsApp. Business owners connect their existing WhatsApp number, and Parlo automatically handles booking conversations with their customers.

**The one-liner:** "Connect Parlo to your WhatsApp in 2 minutes. Watch your appointments start booking themselves."

### The Problem We Solve

Small beauty businesses in Mexico currently manage appointments through:
- Manual WhatsApp conversations (owner texts back and forth all day)
- Instagram DMs
- Phone calls
- Paper notebooks

This is painful because:
- Owners are constantly interrupted during haircuts/services to respond
- Messages get lost or forgotten, leading to missed bookings
- No systematic reminders, leading to no-shows
- No visibility into schedule until they check the notebook
- Can't easily see availability to quote to walk-ins

### Our Solution

Parlo integrates with the business owner's existing WhatsApp number using Meta's Coexistence feature. When a customer messages to book:

1. Parlo's AI handles the conversation naturally in Spanish
2. Checks real-time availability
3. Books the appointment
4. Sends confirmation to customer
5. Sends notification to business owner
6. Sends reminder before appointment

The business owner can watch all conversations happen in their WhatsApp Business App on their phone. They can take over any conversation manually if needed.

### Target Market (Wedge)

- **Geography:** Mexico (WhatsApp-dominant market, Coexistence supported)
- **Vertical:** Beauty services (barbershops, nail salons, hair salons, spas)
- **Size:** 1-10 employees (solo operators to small teams)
- **Initial cities:** Start with one metro area (likely CDMX, Guadalajara, or Monterrey)

### Business Model

**Freemium:**
- Free: First 50 bookings per month
- Paid: Unlimited bookings for $X MXN/month per location (price TBD, likely 299-499 MXN range)

**Future monetization** (not for v1, but architecture should accommodate):
- Marketing services (Google Business Profile setup, review requests, ads)
- Payments integration (deposits, prepayment)
- Multi-location management
- Staff/payroll features

### Key User Journeys

**Journey 1: Business Owner Onboarding (target: 10 minutes)**

```
Owner discovers Parlo (ad, referral, social)
  → Clicks link to WhatsApp
  → Chats with Parlo onboarding bot
  → Connects their WhatsApp via Embedded Signup (scans QR code)
  → Provides business name, services, prices, durations, hours, etc.
  → Done—ready to receive bookings
  → Optionally: access web dashboard for richer management
```

**Journey 2: Customer Booking (target: under 2 minutes)**

```
Customer messages business WhatsApp: "Hola, quiero una cita"
  → Parlo responds, asks what service
  → Customer: "Un corte"
  → Parlo shows available slots for requested timeframe
  → Customer picks slot
  → Parlo confirms booking
  → Parlo notifies business owner
  → Day before: Parlo sends reminder to customer
  → After appointment: Parlo optionally requests Google review
```

**Journey 3: Staff Daily Operations (via their personal WhatsApp)**

```
Staff member messages Parlo from their registered phone number
  → Parlo recognizes them as staff (not a customer)
  → Staff: "¿Qué tengo hoy?"
  → Parlo shows their schedule for the day
  → Staff: "Bloquea de 2 a 3 para mi comida"
  → Parlo blocks that time slot
  → Staff: "El cliente de las 11 no llegó"
  → Parlo marks appointment as no-show
  → Staff can also book walk-ins, view customer history, etc.
```

**Journey 4: Business Owner Daily Operations**

```
Morning: Owner receives daily schedule summary via WhatsApp
During day: Gets notified of new bookings, can see in app
Anytime: Can message Parlo "mi agenda" to see upcoming appointments
For complex tasks: Uses web dashboard (view week, manage staff, block time, etc.)
```

### Staff as WhatsApp Users

A key architectural decision: **staff members interact with Parlo via their personal WhatsApp accounts.** This means:

1. During onboarding, the owner registers staff with their phone numbers
2. When a staff member messages the business's WhatsApp number, they're identified by their phone number and treated as staff (not customers)
3. Staff get a different set of capabilities than customers
4. No separate app needed—everyone uses WhatsApp

**How it works technically:**
- The business has ONE WhatsApp number (connected via Coexistence)
- Both customers AND staff message this same number
- When a message arrives, we look up the sender's phone number
- If it matches a registered staff member → staff conversation flow
- If not → customer conversation flow
- The owner also messages this number and gets owner-level capabilities

**Staff capabilities via WhatsApp:**
- View their own schedule ("¿Qué tengo hoy?", "¿Qué sigue?")
- View full business schedule (if permitted)
- Block off personal time ("Bloquea mañana de 2 a 4")
- Mark appointments as completed or no-show
- Book walk-in customers ("Acaba de llegar alguien para corte")
- View customer history ("¿Este cliente ha venido antes?")
- Cancel/reschedule on behalf of customers

**Owner-only capabilities:**
- Add/remove staff
- Change business hours
- Modify services and prices
- View business analytics
- Billing and account management

### Competitive Positioning

Competitors in scheduling:
- **Fresha, Booksy, Treatwell:** Marketplace-first, complex onboarding, designed for consumers not businesses
- **Calendly, Cal.com:** Not WhatsApp-native, not localized for Mexico, not vertical-specific
- **Square Appointments:** Payment-first, more complex than needed

Parlo differentiators:
- WhatsApp-native (meets businesses where they are)
- AI-first (no app to learn, no buttons to click)
- Mexico-first (Spanish-native, local payment methods later, peso pricing)
- Radically simple onboarding (10 min via chat)
- Coexistence means owner watches it work in their own app

---

## Part 2: Technical Architecture

### Core Principles

1. **Data primitives over features:** The system is built around stable entities (Actors, Services, Appointments, etc.) that model service businesses generically. Features are orchestration on top of primitives.

2. **AI-native by construction:** Every API is typed and documented so AI agents can discover and use capabilities. The conversational AI is not a bolt-on; it's the primary interface.

3. **Extensibility for future verticals:** While we start with beauty/scheduling, the data model should support other service businesses (dental, auto repair, cleaning) and other features (payments, inventory) without rewriting core.

4. **Database as truth:** The database enforces invariants (referential integrity, time ordering, uniqueness). Business rules live in the application layer.

5. **Incremental identity:** Entities can be created with minimal data and enriched over time. A customer can exist with just a phone number; name comes later.

### Tech Stack

**Backend:**
- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Validation:** Pydantic v2
- **Database:** PostgreSQL 15+
- **ORM:** SQLAlchemy 2.0 (async)
- **Migrations:** Alembic
- **Task Queue:** Redis + Celery (for reminders, async jobs)
- **AI/LLM:** OpenAI gpt-4.1 (for conversational AI, via function calling)

**WhatsApp Integration:**
- **API:** Twilio WhatsApp API
- **Onboarding:** Meta Embedded Signup for connecting existing WhatsApp Business numbers
- **Webhooks:** Receive messages via Twilio webhook

**Infrastructure (deployed on Render):**
- **Hosting:** Render (backend + frontend deployed)
- **Database:** Render PostgreSQL
- **Redis:** Not deployed (Celery workers deferred to save costs)
- **Secrets:** Environment variables (12-factor style)

**Frontend (later, not v1 priority):**
- **Framework:** Next.js 14+ (App Router)
- **Styling:** Tailwind CSS
- **Language:** TypeScript

### Data Model (Core Primitives)

```
┌─────────────────────────────────────────────────────────────────┐
│                         CORE ENTITIES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Organization ─────────────── Location ─────────────► Spot      │
│       │                          │                     │        │
│       │                          │                     │        │
│       ▼                          ▼                     ▼        │
│    Staff ◄──────────────── Appointment ────────► ServiceType    │
│       │                          │                              │
│       │                          │                              │
│       ▼                          ▼                              │
│  Availability                Customer                           │
│                                                                 │
│                                                                 │
│  Conversation ─────────────► Message                            │
│       │                                                         │
│       └──────────────────► Customer                             │
│                                                                 │
│  AuthToken ──────────────► Organization (magic link auth)       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Entity Definitions:**

```python
# Organization: The business entity (e.g., "Barbería Don Carlos")
# NOTE: Onboarding state is stored directly on Organization (no separate OnboardingSession model)
Organization:
    id: UUID
    name: str
    phone_country_code: str  # +52 for Mexico
    phone_number: str        # The WhatsApp-connected number
    whatsapp_phone_number_id: str  # Meta's phone number ID
    whatsapp_waba_id: str    # WhatsApp Business Account ID
    timezone: str            # e.g., "America/Mexico_City"
    status: enum (onboarding, active, suspended, churned)
    settings: JSONB          # Flexible config
    onboarding_state: str    # Current onboarding step (initiated, collecting_business_info, etc.)
    onboarding_data: JSONB   # Data collected during onboarding
    onboarding_conversation_context: JSONB  # AI conversation state during onboarding
    last_message_at: datetime  # For abandoned session detection
    created_at: datetime
    updated_at: datetime

# Location: Physical location (supports multi-location later)
Location:
    id: UUID
    organization_id: FK → Organization
    name: str
    address: str (optional)
    is_primary: bool
    business_hours: JSONB    # {mon: {open: "10:00", close: "20:00"}, ...}
    created_at: datetime
    updated_at: datetime

# ParloUser (Staff): People who provide services (also users who can interact via WhatsApp)
# NOTE: Model class is ParloUser, with backward-compat alias "Staff"
ParloUser:
    id: UUID
    organization_id: FK → Organization
    location_id: FK → Location (optional, null = all locations)
    name: str
    phone_number: str             # Their personal WhatsApp - used to identify them as staff
    role: enum (owner, employee)
    permission_level: enum (owner, admin, staff, viewer)  # Finer-grained access control
    permissions: JSONB            # {can_view_schedule: true, can_book: true, can_cancel: true, ...}
    is_active: bool
    first_message_at: datetime    # Tracks first WhatsApp contact (null = never messaged)
    default_spot_id: FK → Spot (optional)
    settings: JSONB
    created_at: datetime
    updated_at: datetime

    # Unique constraint: (organization_id, phone_number)
    # This phone number is how we identify staff when they message Parlo

# ServiceType: What the business offers
ServiceType:
    id: UUID
    organization_id: FK → Organization
    name: str                # "Corte de cabello"
    description: str (optional)
    duration_minutes: int    # 45
    price_cents: int         # 15000 = $150.00 MXN
    currency: str            # "MXN"
    is_active: bool
    settings: JSONB          # e.g., {requires_deposit: false}
    created_at: datetime
    updated_at: datetime

# EndCustomer (Customer): End consumers who book appointments
# NOTE: Model class is EndCustomer, with backward-compat alias "Customer"
EndCustomer:
    id: UUID
    organization_id: FK → Organization
    phone_number: str        # Primary identifier, may be only data initially
    name: str (optional)     # Learned over time
    name_verified_at: datetime (optional)  # When customer confirmed their name
    email: str (optional)
    notes: str (optional)    # Business owner's notes
    profile_data: JSONB      # Preferences, history, communication style
    settings: JSONB
    created_at: datetime
    updated_at: datetime

    # Unique constraint: (organization_id, phone_number)

# Appointment: A scheduled service event
Appointment:
    id: UUID
    organization_id: FK → Organization
    location_id: FK → Location
    customer_id: FK → Customer
    staff_id: FK → Staff (optional, null = any available)
    service_type_id: FK → ServiceType
    
    scheduled_start: datetime (with timezone)
    scheduled_end: datetime (with timezone)
    
    status: enum (pending, confirmed, completed, cancelled, no_show)
    source: enum (whatsapp, web, manual, walk_in)
    
    notes: str (optional)
    cancellation_reason: str (optional)
    
    reminder_sent_at: datetime (optional)
    
    created_at: datetime
    updated_at: datetime
    
    # Constraint: scheduled_start < scheduled_end
    # Constraint: no overlapping appointments for same staff

# Conversation: A WhatsApp conversation thread
Conversation:
    id: UUID
    organization_id: FK → Organization
    customer_id: FK → Customer
    whatsapp_conversation_id: str (optional, Meta's ID)
    
    status: enum (active, resolved, handed_off)
    context: JSONB           # AI conversation state
    
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime

# Message: Individual messages in a conversation
Message:
    id: UUID
    conversation_id: FK → Conversation
    
    direction: enum (inbound, outbound)
    sender_type: enum (customer, ai, staff)
    
    content_type: enum (text, image, audio, template)
    content: text            # Message body
    media_url: str (optional)
    
    whatsapp_message_id: str (optional)
    
    created_at: datetime
    
    # Appointments can be linked to the message that created them
    # via a separate AppointmentMessage join table if needed

# Availability: Staff availability patterns and exceptions
Availability:
    id: UUID
    staff_id: FK → Staff
    
    type: enum (recurring, exception)
    
    # For recurring: day of week pattern
    day_of_week: int (optional, 0=Monday)
    start_time: time
    end_time: time
    
    # For exceptions: specific date range
    exception_date: date (optional)
    is_available: bool       # false = blocked off

    created_at: datetime
    updated_at: datetime

# Spot: Physical service stations (chairs, tables, beds)
Spot:
    id: UUID
    location_id: FK → Location
    name: str                # "Silla 1", "Mesa de manicure 2"
    display_order: int       # Order to show in UI
    is_active: bool
    service_types: M2M → ServiceType  # Services this spot can handle
    created_at: datetime
    updated_at: datetime

    # Appointments reference spots to prevent double-booking

# AuthToken: Magic link tokens for web app authentication
# NOTE: Implementation stores token_hash (SHA256) not plain token for security
AuthToken:
    id: UUID
    organization_id: FK → Organization
    token_hash: str          # SHA256 hash of the token (not stored in plain text)
    token_type: enum (magic_link)
    expires_at: datetime
    used_at: datetime (optional)  # Timestamp instead of boolean
    created_at: datetime

# StaffOnboardingSession: Tracks staff WhatsApp onboarding progress
StaffOnboardingSession:
    id: UUID
    staff_id: FK → ParloUser (unique)
    organization_id: FK → Organization
    state: enum (initiated, collecting_name, collecting_availability, showing_tutorial, completed, abandoned)
    collected_data: JSONB    # Data gathered during onboarding
    conversation_context: JSONB  # AI conversation state
    last_message_at: datetime
    created_at: datetime
    updated_at: datetime

# CustomerFlowSession: Tracks end-customer conversation flows (booking, cancel, etc.)
CustomerFlowSession:
    id: UUID
    organization_id: FK → Organization
    conversation_id: FK → Conversation
    customer_id: FK → EndCustomer
    flow_type: enum (booking, modify, cancel, rating, inquiry)
    state: str               # Flow-specific state (e.g., collecting_service, confirming_summary)
    collected_data: JSONB    # Data gathered during flow
    created_at: datetime
    updated_at: datetime

# FunctionTrace: Function execution traces for debugging and observability
FunctionTrace:
    id: UUID
    correlation_id: str      # Groups traces from same request
    sequence_number: int     # Order within correlation
    function_name: str
    trace_type: enum (service, ai_tool, external_api)
    phone_number: str (optional)
    organization_id: FK → Organization (optional)
    input_summary: JSONB     # Captured function args
    output_summary: JSONB    # Captured return value
    duration_ms: float (optional)
    is_error: bool
    error_message: str (optional)
    created_at: datetime
```

### API Design

RESTful API with OpenAPI documentation auto-generated by FastAPI.

**Endpoint Structure:**

```
# Organization management (used during onboarding and by dashboard)
POST   /api/v1/organizations              # Create org (onboarding start)
GET    /api/v1/organizations/{id}         # Get org details
PATCH  /api/v1/organizations/{id}         # Update org
POST   /api/v1/organizations/{id}/connect-whatsapp  # Complete Embedded Signup

# Services
GET    /api/v1/organizations/{org_id}/services
POST   /api/v1/organizations/{org_id}/services
PATCH  /api/v1/organizations/{org_id}/services/{id}
DELETE /api/v1/organizations/{org_id}/services/{id}

# Staff
GET    /api/v1/organizations/{org_id}/staff
POST   /api/v1/organizations/{org_id}/staff
PATCH  /api/v1/organizations/{org_id}/staff/{id}

# Customers
GET    /api/v1/organizations/{org_id}/customers
GET    /api/v1/organizations/{org_id}/customers/{id}
POST   /api/v1/organizations/{org_id}/customers
PATCH  /api/v1/organizations/{org_id}/customers/{id}

# Appointments
GET    /api/v1/organizations/{org_id}/appointments
POST   /api/v1/organizations/{org_id}/appointments
GET    /api/v1/organizations/{org_id}/appointments/{id}
PATCH  /api/v1/organizations/{org_id}/appointments/{id}
POST   /api/v1/organizations/{org_id}/appointments/{id}/cancel
POST   /api/v1/organizations/{org_id}/appointments/{id}/complete

# Availability
GET    /api/v1/organizations/{org_id}/availability
GET    /api/v1/organizations/{org_id}/availability/slots  # Available slots for booking
POST   /api/v1/organizations/{org_id}/availability
DELETE /api/v1/organizations/{org_id}/availability/{id}

# Spots (physical service stations)
GET    /api/v1/organizations/{org_id}/locations/{location_id}/spots
POST   /api/v1/organizations/{org_id}/locations/{location_id}/spots
GET    /api/v1/organizations/{org_id}/spots/{spot_id}
PATCH  /api/v1/organizations/{org_id}/spots/{spot_id}
DELETE /api/v1/organizations/{org_id}/spots/{spot_id}
PUT    /api/v1/organizations/{org_id}/spots/{spot_id}/services  # Assign services

# Authentication (magic link flow)
POST   /api/v1/auth/request-magic-link   # Send magic link to WhatsApp
POST   /api/v1/auth/verify-magic-link    # Verify token, return JWT

# WhatsApp Webhook (Meta calls this)
POST   /api/v1/webhooks/whatsapp
GET    /api/v1/webhooks/whatsapp  # Webhook verification

# Conversations (mostly internal, used by AI and dashboard)
GET    /api/v1/organizations/{org_id}/conversations
GET    /api/v1/organizations/{org_id}/conversations/{id}
GET    /api/v1/organizations/{org_id}/conversations/{id}/messages

# Admin Dashboard (platform management)
POST   /api/v1/admin/auth/login           # Password-based admin login
GET    /api/v1/admin/stats                # Platform-wide statistics
GET    /api/v1/admin/organizations        # List orgs with search/filter
GET    /api/v1/admin/organizations/{org_id}  # Org details with counts
POST   /api/v1/admin/organizations/{org_id}/impersonate  # Login as org
PATCH  /api/v1/admin/organizations/{org_id}/status       # Suspend/activate
GET    /api/v1/admin/conversations        # All conversations across orgs
GET    /api/v1/admin/conversations/{id}   # Full conversation with messages
GET    /api/v1/admin/activity             # Activity feed
```

### WhatsApp Integration Details

**Twilio WhatsApp API Integration:**

1. **Number Provisioning (Hybrid Approach):**
   - Parlo provisions dedicated Twilio WhatsApp numbers for each business
   - Business is live immediately with their Parlo-provisioned number
   - Optional: Connect existing WhatsApp Business number via Meta Embedded Signup
   - Multi-business routing based on phone_number_id in webhook

2. **Webhook Setup:**
   - Register webhook URL with Twilio: `https://api.parlo.mx/api/v1/webhooks/whatsapp`
   - Twilio sends webhook for incoming messages and status updates
   - Each business's provisioned number points to same webhook endpoint

3. **Receiving Messages:**
   ```python
   # Twilio webhook payload (form data)
   {
       "MessageSid": "SM...",
       "From": "whatsapp:+521234567890",
       "To": "whatsapp:+14155238886",  # Business's Twilio number
       "Body": "Hola, quiero una cita",
       "NumMedia": "0"
   }
   ```

4. **Sending Messages:**
   ```python
   # Send text message via Twilio
   from twilio.rest import Client

   client = Client(account_sid, auth_token)
   message = client.messages.create(
       from_='whatsapp:+14155238886',  # Twilio number
       body='¡Hola! Claro, ¿qué servicio te gustaría?',
       to='whatsapp:+521234567890'
   )

   # Send template message (for notifications outside 24h window)
   # Requires pre-approved template in Twilio console
   message = client.messages.create(
       from_='whatsapp:+14155238886',
       content_sid='HXXXXXXXXX',  # Template content SID
       content_variables='{"1":"mañana a las 3:00 PM","2":"Corte de cabello"}',
       to='whatsapp:+521234567890'
   )
   ```

5. **Template Messages Needed (submit to Twilio/Meta for approval):**
   - `appointment_confirmation` - Sent when appointment is booked
   - `appointment_reminder` - Sent 24h before appointment
   - `appointment_cancelled` - Sent when appointment is cancelled
   - `review_request` - Sent after appointment (optional, for growth)

### Conversational AI Architecture

**LLM Integration:**

```python
# Core conversation handler
class ConversationHandler:
    def __init__(self, openai_client, organization, customer, conversation):
        self.client = openai_client
        self.org = organization
        self.customer = customer
        self.conversation = conversation

    async def process_message(self, message_text: str) -> str:
        # Build context for GPT
        system_prompt = self.build_system_prompt()
        conversation_history = await self.get_conversation_history()

        # Call GPT with function calling
        response = await self.client.chat.completions.create(
            model="gpt-4.1",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                *conversation_history,
                {"role": "user", "content": message_text}
            ],
            tools=self.get_available_tools()
        )

        # Handle tool calls (check availability, book appointment, etc.)
        # Return final response text
```

**Available Tools for AI:**

```python
tools = [
    {
        "name": "check_availability",
        "description": "Check available appointment slots for a given date range and service",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string"},
                "date_from": {"type": "string", "format": "date"},
                "date_to": {"type": "string", "format": "date"},
                "preferred_staff_id": {"type": "string", "optional": True}
            },
            "required": ["service_id", "date_from"]
        }
    },
    {
        "name": "book_appointment",
        "description": "Book an appointment for the customer",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string"},
                "staff_id": {"type": "string"},
                "start_time": {"type": "string", "format": "datetime"},
                "customer_name": {"type": "string", "optional": True}
            },
            "required": ["service_id", "start_time"]
        }
    },
    {
        "name": "get_customer_appointments",
        "description": "Get upcoming appointments for the current customer",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an existing appointment",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string"},
                "reason": {"type": "string", "optional": True}
            },
            "required": ["appointment_id"]
        }
    },
    {
        "name": "reschedule_appointment",
        "description": "Reschedule an existing appointment to a new time",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string"},
                "new_start_time": {"type": "string", "format": "datetime"}
            },
            "required": ["appointment_id", "new_start_time"]
        }
    },
    {
        "name": "handoff_to_human",
        "description": "Transfer the conversation to the business owner when AI cannot help or customer requests it",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"}
            },
            "required": ["reason"]
        }
    }
]

# Additional tools available ONLY for staff/owner conversations
staff_tools = [
    {
        "name": "get_my_schedule",
        "description": "Get the staff member's own schedule for a given date range",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "format": "date"},
                "date_to": {"type": "string", "format": "date"}
            }
        }
    },
    {
        "name": "get_business_schedule",
        "description": "Get the full business schedule (all staff) for a given date range",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "format": "date"},
                "date_to": {"type": "string", "format": "date"}
            }
        }
    },
    {
        "name": "block_time",
        "description": "Block off time in the staff member's schedule (for lunch, personal time, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_time": {"type": "string", "format": "datetime"},
                "end_time": {"type": "string", "format": "datetime"},
                "reason": {"type": "string", "optional": True}
            },
            "required": ["start_time", "end_time"]
        }
    },
    {
        "name": "mark_appointment_status",
        "description": "Mark an appointment as completed, no-show, or cancelled",
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string"},
                "status": {"type": "string", "enum": ["completed", "no_show", "cancelled"]},
                "notes": {"type": "string", "optional": True}
            },
            "required": ["appointment_id", "status"]
        }
    },
    {
        "name": "book_walk_in",
        "description": "Book a walk-in customer who just arrived",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string"},
                "customer_phone": {"type": "string", "optional": True},
                "customer_name": {"type": "string", "optional": True},
                "staff_id": {"type": "string", "optional": True}
            },
            "required": ["service_id"]
        }
    },
    {
        "name": "get_customer_history",
        "description": "Look up a customer's appointment history",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_phone": {"type": "string"}
            },
            "required": ["customer_phone"]
        }
    },
    {
        "name": "send_message_to_customer",
        "description": "Send a WhatsApp message to a customer on behalf of the business",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_phone": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["customer_phone", "message"]
        }
    }
]
```

**System Prompt Structure:**

```python
def build_system_prompt(self) -> str:
    # Different prompts for staff vs customers
    if self.is_staff_conversation:
        return self.build_staff_system_prompt()
    else:
        return self.build_customer_system_prompt()
```

### Message Routing Architecture

Parlo operates two distinct WhatsApp channels:

1. **Parlo's Central Number** - For B2B interactions (business onboarding and management)
2. **Business Numbers** - For B2C interactions (end customers) and staff of that specific business

Every incoming WhatsApp message is routed based on:
- **Which number received the message** (recipient)
- **Who sent the message** (sender identification)

#### Two-Channel Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PARLO MESSAGE ROUTING                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────────────┐         ┌───────────────────────────────────┐  │
│   │  PARLO CENTRAL NUMBER  │         │     BUSINESS NUMBERS (per biz)    │  │
│   │                       │         │                                   │  │
│   │  Purpose: B2B         │         │  Purpose: B2C + Staff             │  │
│   │  - Business onboarding│         │  - End customer bookings          │  │
│   │  - Business management│         │  - Staff management               │  │
│   │                       │         │                                   │  │
│   │  Recipients:          │         │  Recipients:                      │  │
│   │  - New businesses     │         │  - Customers of that business     │  │
│   │  - Existing owners    │         │  - Staff of that business         │  │
│   │  - Existing staff     │         │                                   │  │
│   └───────────────────────┘         └───────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Routing Principles:**

1. **Staff registration is business-specific.** Maria can be staff at "Salon A" but is just a customer at "Barber Shop B".

2. **Management access is flexible.** Business owners/staff can manage their business via:
   - Parlo's central WhatsApp number
   - Their own business WhatsApp number
   - The web portal

3. **Multi-business staff use direct messaging.** If someone is staff at multiple businesses, they must message each business number directly (not the central number).

#### Routing Flowchart

```mermaid
flowchart TD
    START([Incoming WhatsApp Message]) --> CHECK_RECIPIENT{Which number<br/>received this?}

    CHECK_RECIPIENT -->|Parlo Central Number| CENTRAL_FLOW
    CHECK_RECIPIENT -->|Business Number X| BUSINESS_FLOW

    subgraph CENTRAL_FLOW [Parlo Central Number Flow]
        C1{Sender in DB?}
        C1 -->|No / Incomplete Onboarding| CASE1[Case 1: Business Onboarding]
        C1 -->|Yes - Registered| C2{Registered to<br/>how many businesses?}
        C2 -->|Exactly 1| CASE2A[Case 2a: Business Management]
        C2 -->|Multiple| CASE2B[Case 2b: Redirect Message]
    end

    subgraph BUSINESS_FLOW [Business Number X Flow]
        B1{Sender is pre-registered<br/>staff for Business X?}
        B1 -->|Yes| B2{First message<br/>from this staff?}
        B2 -->|Yes| CASE3[Case 3: Staff Onboarding]
        B2 -->|No| CASE4[Case 4: Business Management]
        B1 -->|No| CASE5[Case 5: End Customer]
    end

    CASE1 --> FLOW1([Business Onboarding Flow])
    CASE2A --> FLOW2([Business Management Flows])
    CASE2B --> MSG2B([Send: Text your business directly])
    CASE3 --> FLOW3([Staff Onboarding Flow])
    CASE4 --> FLOW2
    CASE5 --> FLOW5([End Customer Flows])
```

#### Routing Table

| Case | Recipient | Sender Identification | Route To | Actions Available |
|------|-----------|----------------------|----------|-------------------|
| **1** | Parlo Central | Unknown OR incomplete onboarding | Business Onboarding Flow | Gather info, provision number, complete setup |
| **2a** | Parlo Central | Staff/owner of exactly 1 business | Business Management Flows | All management actions per permissions |
| **2b** | Parlo Central | Staff/owner of multiple businesses | Redirect Message | Send: "You're registered to multiple businesses, please text them directly" |
| **3** | Business Number X | Pre-registered staff (first message) | Staff Onboarding Flow | Collect name, availability, show tutorial |
| **4** | Business Number X | Known staff for Business X | Business Management Flows | All management actions per permissions |
| **5** | Business Number X | Anyone not staff of Business X | End Customer Flows | Booking, inquiry, modify, cancel |

#### Routing Pseudocode

```python
async def route_message(recipient_number: str, sender_phone: str, message: str):
    """Main message routing logic."""

    if recipient_number == PARLO_CENTRAL_NUMBER:
        # Central number flow
        registrations = await get_staff_registrations(sender_phone)

        if len(registrations) == 0:
            # Check for incomplete onboarding
            onboarding = await get_onboarding_session(sender_phone)
            return handle_business_onboarding(sender_phone, message, onboarding)

        elif len(registrations) == 1:
            # Single business - allow management
            business = registrations[0].business
            staff = registrations[0]
            return handle_business_management(business, staff, message)

        else:
            # Multiple businesses - redirect
            return send_redirect_message(sender_phone, registrations)

    else:
        # Business number flow
        business = await get_business_by_whatsapp_number(recipient_number)
        staff = await get_staff_by_phone(business.id, sender_phone)

        if staff:
            if staff.is_first_message:
                return handle_staff_onboarding(business, staff, message)
            else:
                return handle_business_management(business, staff, message)
        else:
            customer = await get_or_create_customer(business.id, sender_phone)
            return handle_end_customer(business, customer, message)
```

#### Quick Reference: Routing Decision Tree

```
Incoming Message
│
├── Recipient = Parlo Central Number?
│   ├── Sender = Unknown/Incomplete? → BUSINESS ONBOARDING
│   ├── Sender = Staff of 1 business? → BUSINESS MANAGEMENT
│   └── Sender = Staff of 2+ businesses? → REDIRECT MESSAGE
│
└── Recipient = Business Number X?
    ├── Sender = Pre-registered staff (new)? → STAFF ONBOARDING
    ├── Sender = Known staff? → BUSINESS MANAGEMENT
    └── Sender = Anyone else? → END CUSTOMER FLOWS
```

---

### State Machine Flows

All flows use state machines to track progress. Each state represents a step in the conversation.

**Universal State Patterns:**

1. **Abandoned State:** Triggered after X time of inactivity. The system remembers the last active state for resumption.

2. **State Naming Convention:**
   - Active states use present progressive: `collecting_service`, `confirming_summary`
   - Completed states use past tense: `gave_order`, `confirmed`

#### 1. Business Onboarding Flow

**Trigger:** Message to Parlo Central from unknown number or incomplete onboarding.

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> collecting_business_info: Start conversation
    collecting_business_info --> collecting_owner_info: Got name, type, services
    collecting_owner_info --> provisioning_number: Got owner name, contact
    provisioning_number --> completed: Number provisioned successfully
    completed --> [*]

    collecting_business_info --> abandoned: Timeout
    collecting_owner_info --> abandoned: Timeout
    abandoned --> collecting_business_info: Resume (remembered state)
    abandoned --> collecting_owner_info: Resume (remembered state)
```

**States:**

| State | Description | Data Collected |
|-------|-------------|----------------|
| `initiated` | Conversation started | - |
| `collecting_business_info` | Gathering business details | name, type, services offered |
| `collecting_owner_info` | Gathering owner details | owner name, contact info |
| `provisioning_number` | Automatic: creating WhatsApp number | (system action) |
| `completed` | Onboarding complete, business is live | - |
| `abandoned` | Timeout, remembers last state | last_active_state, timestamp |

#### 2. Staff Onboarding Flow

**Trigger:** First message from pre-registered staff to their business number.

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> collecting_name: Welcome message sent
    collecting_name --> collecting_availability: Got name
    collecting_availability --> showing_tutorial: Got availability
    showing_tutorial --> completed: Viewed tutorial
    completed --> [*]

    collecting_name --> abandoned: Timeout
    collecting_availability --> abandoned: Timeout
    showing_tutorial --> abandoned: Timeout
    abandoned --> collecting_name: Resume
    abandoned --> collecting_availability: Resume
    abandoned --> showing_tutorial: Resume
```

**States:**

| State | Description | Data Collected |
|-------|-------------|----------------|
| `initiated` | First message received | - |
| `collecting_name` | Asking for display name | name |
| `collecting_availability` | Asking for working hours | day/time preferences |
| `showing_tutorial` | Showing capabilities | (tutorial acknowledgment) |
| `completed` | Staff fully onboarded | - |
| `abandoned` | Timeout with memory | last_active_state |

**On Completion:** Notify admin/owner who invited them.

#### 3. New Booking Flow (End Customer)

**Trigger:** End customer expresses intent to book.

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> collecting_service: Intent detected
    collecting_service --> collecting_datetime: Service selected
    collecting_datetime --> collecting_staff_preference: Date/time selected
    collecting_staff_preference --> collecting_personal_info: Staff selected (if multiple)
    collecting_datetime --> collecting_personal_info: Skip (single staff)
    collecting_personal_info --> confirming_summary: Info collected/prefilled
    confirming_summary --> confirmed: Customer confirms
    confirmed --> [*]

    collecting_service --> abandoned: Timeout
    collecting_datetime --> abandoned: Timeout
    collecting_staff_preference --> abandoned: Timeout
    collecting_personal_info --> abandoned: Timeout
    confirming_summary --> abandoned: Timeout
```

**States:**

| State | Description | Data Collected |
|-------|-------------|----------------|
| `initiated` | Booking intent detected | - |
| `collecting_service` | Asking which service | service_id |
| `collecting_datetime` | Asking when | date, time slot |
| `collecting_staff_preference` | Asking who (if multiple staff) | staff_id (optional) |
| `collecting_personal_info` | Asking name, etc. (prefilled for returning) | name, phone |
| `confirming_summary` | Showing summary, asking confirmation | - |
| `confirmed` | Booking created | booking_id |
| `abandoned` | Timeout with memory | last_active_state |

**Note:** `collecting_staff_preference` is skipped if business has single staff.

**Post-Booking Lifecycle:**

```mermaid
stateDiagram-v2
    confirmed --> reminded: 24h before
    reminded --> pending_attendance: Appointment time
    pending_attendance --> attended: Business confirms
    pending_attendance --> no_show: Time passes, no confirmation
    attended --> prompted_rating: After service
    prompted_rating --> rated: Rating submitted
    rated --> closed: Complete
    no_show --> prompted_reschedule: Ask about reschedule
    prompted_reschedule --> rescheduled: New booking created
    prompted_reschedule --> closed: Customer declines
    no_show --> disputed: Customer claims attended
    disputed --> attended: Verified
```

#### 4. Modify Booking Flow (End Customer)

**Trigger:** End customer expresses intent to modify existing booking.

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> identifying_booking: Intent detected
    identifying_booking --> selecting_modification: Booking identified
    selecting_modification --> collecting_new_service: Change service
    selecting_modification --> collecting_new_datetime: Change time
    selecting_modification --> collecting_new_staff: Change staff
    collecting_new_service --> confirming_summary
    collecting_new_datetime --> confirming_summary
    collecting_new_staff --> confirming_summary
    confirming_summary --> confirmed: Customer confirms
    confirmed --> [*]
```

**States:**

| State | Description | Data Collected |
|-------|-------------|----------------|
| `initiated` | Modify intent detected | - |
| `identifying_booking` | Which booking? (skip if only one active) | booking_id |
| `selecting_modification` | What to change? | modification_type |
| `collecting_new_service` | New service selection | new_service_id |
| `collecting_new_datetime` | New date/time selection | new_datetime |
| `collecting_new_staff` | New staff selection | new_staff_id |
| `confirming_summary` | Showing changes, asking confirmation | - |
| `confirmed` | Modification saved | - |

#### 5. Cancel Booking Flow (End Customer)

**Trigger:** End customer expresses intent to cancel.

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> identifying_booking: Intent detected
    identifying_booking --> confirming_cancellation: Booking identified
    confirming_cancellation --> cancelled: Customer confirms
    cancelled --> [*]
```

**States:**

| State | Description |
|-------|-------------|
| `initiated` | Cancel intent detected |
| `identifying_booking` | Which booking? (skip if only one) |
| `confirming_cancellation` | Are you sure? |
| `cancelled` | Booking cancelled, confirmation sent |

#### 6. Inquiry Flow (End Customer)

**Trigger:** End customer asks about services, hours, prices, etc.

**Type:** Stateless - AI answers from business profile.

No state machine needed. AI responds directly using business data.

#### 7. Give Rating Flow (End Customer)

**Trigger:** System prompts customer after confirmed attendance.

```mermaid
stateDiagram-v2
    [*] --> prompted
    prompted --> collecting_rating: Customer responds
    collecting_rating --> collecting_feedback: Rating given
    collecting_feedback --> submitted: Feedback given (optional)
    collecting_rating --> submitted: Skip feedback
    submitted --> [*]
```

**States:**

| State | Description | Data Collected |
|-------|-------------|----------------|
| `prompted` | Rating request sent | - |
| `collecting_rating` | Waiting for 1-5 rating | rating (1-5) |
| `collecting_feedback` | Optional text feedback | feedback_text (optional) |
| `submitted` | Rating saved | - |

#### 8. Block Time Slots Flow (Business Management)

**Trigger:** Staff/owner wants to block time off.

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> collecting_date_range: Intent detected
    collecting_date_range --> collecting_time_range: Dates selected
    collecting_time_range --> collecting_reason: Times selected
    collecting_reason --> confirming: Reason given (optional)
    collecting_time_range --> confirming: Skip reason
    confirming --> confirmed: User confirms
    confirmed --> [*]
```

**States:**

| State | Description | Data Collected |
|-------|-------------|----------------|
| `initiated` | Block intent detected | - |
| `collecting_date_range` | Which date(s)? | start_date, end_date |
| `collecting_time_range` | Which time(s)? | start_time, end_time |
| `collecting_reason` | Why? (optional) | reason |
| `confirming` | Summary and confirmation | - |
| `confirmed` | Time blocked | - |

#### 9. Change Business Hours Flow (Business Management)

**Trigger:** Owner wants to change operating hours.

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> selecting_days: Intent detected
    selecting_days --> collecting_new_hours: Days selected
    collecting_new_hours --> confirming: Hours provided
    confirming --> confirmed: User confirms
    confirmed --> [*]
```

**States:**

| State | Description | Data Collected |
|-------|-------------|----------------|
| `initiated` | Change hours intent detected | - |
| `selecting_days` | All days or specific? | days (list or "all") |
| `collecting_new_hours` | New open/close times | open_time, close_time |
| `confirming` | Summary and confirmation | - |
| `confirmed` | Hours updated | - |

#### 10. Change Service Duration Flow (Business Management)

**Trigger:** Owner wants to change service duration.

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> selecting_service: Intent detected
    selecting_service --> collecting_new_duration: Service selected
    collecting_new_duration --> confirming: Duration provided
    confirming --> confirmed: User confirms
    confirmed --> [*]
```

#### 11. Add Staff Flow (Business Management)

**Trigger:** Owner/admin wants to add new staff member.

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> collecting_phone: Intent detected
    collecting_phone --> collecting_name: Phone provided
    collecting_name --> collecting_permissions: Name provided
    collecting_permissions --> confirming: Permissions selected
    confirming --> confirmed: User confirms
    confirmed --> [*]
```

**States:**

| State | Description | Data Collected |
|-------|-------------|----------------|
| `initiated` | Add staff intent detected | - |
| `collecting_phone` | Staff's WhatsApp number | phone_number |
| `collecting_name` | Staff's display name | name |
| `collecting_permissions` | Permission level | permission_level |
| `confirming` | Summary and confirmation | - |
| `confirmed` | Staff invited, awaiting their onboarding | - |

**On Completion:** Staff is pre-registered. When they message the business number, they enter Staff Onboarding (Case 3).

#### 12. Remove Staff Flow (Business Management)

**Trigger:** Owner/admin wants to remove staff member.

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> selecting_staff: Intent detected
    selecting_staff --> confirming_removal: Staff selected
    confirming_removal --> confirmed: User confirms
    confirmed --> [*]
```

**States:**

| State | Description | Data Collected |
|-------|-------------|----------------|
| `initiated` | Remove staff intent detected | - |
| `selecting_staff` | Which staff member? | staff_id |
| `confirming_removal` | Are you sure? | - |
| `confirmed` | Staff removed | - |

#### 13. Change Staff Permissions Flow (Business Management)

**Trigger:** Owner/admin wants to change staff permissions.

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> selecting_staff: Intent detected
    selecting_staff --> selecting_new_permissions: Staff selected
    selecting_new_permissions --> confirming: Permissions selected
    confirming --> confirmed: User confirms
    confirmed --> [*]
```

#### 14. Create Booking (Walk-in/On-Behalf) Flow (Business Management)

**Trigger:** Staff creates booking for a customer (walk-in or phone booking).

```mermaid
stateDiagram-v2
    [*] --> initiated
    initiated --> collecting_customer_phone: Intent detected
    collecting_customer_phone --> collecting_service: Phone provided
    collecting_service --> collecting_datetime: Service selected
    collecting_datetime --> selecting_staff: Date/time selected
    selecting_staff --> confirming: Staff selected
    confirming --> confirmed: User confirms
    confirmed --> [*]
```

**States:**

| State | Description | Data Collected |
|-------|-------------|----------------|
| `initiated` | Create booking intent detected | - |
| `collecting_customer_phone` | Customer's phone (optional for walk-ins) | phone_number |
| `collecting_service` | Which service? | service_id |
| `collecting_datetime` | When? (now for walk-ins) | datetime |
| `selecting_staff` | Who will serve them? | staff_id |
| `confirming` | Summary and confirmation | - |
| `confirmed` | Booking created, customer notified | - |

**On Confirmation:** Customer receives WhatsApp notification about their booking.

#### Stateless Flows (Business Management)

These flows don't require state machines - they're single request/response:

| Flow | Description |
|------|-------------|
| **View Schedule** | Returns schedule for specified date/range |
| **View Stats** | Returns business statistics |

---

### Permission System

#### Permission Levels

| Level | Description | Typical Use |
|-------|-------------|-------------|
| `owner` | Full access to everything | Business owner |
| `admin` | Can manage staff, see all data | Manager, senior staff |
| `staff` | Can view schedule, create bookings | Regular employees |
| `viewer` | Read-only access | Assistants, trainees |

#### Permission Matrix

| Action | Owner | Admin | Staff | Viewer |
|--------|-------|-------|-------|--------|
| View own schedule | ✅ | ✅ | ✅ | ✅ |
| View full business schedule | ✅ | ✅ | ✅ | ✅ |
| Create booking (walk-in) | ✅ | ✅ | ✅ | ❌ |
| Mark attendance | ✅ | ✅ | ✅ | ❌ |
| Block own time | ✅ | ✅ | ✅ | ❌ |
| Cancel appointment | ✅ | ✅ | ✅ | ❌ |
| View stats | ✅ | ✅ | ❌ | ❌ |
| Add staff | ✅ | ✅ | ❌ | ❌ |
| Remove staff | ✅ | ✅ | ❌ | ❌ |
| Change permissions | ✅ | ❌ | ❌ | ❌ |
| Change business hours | ✅ | ❌ | ❌ | ❌ |
| Change service durations | ✅ | ❌ | ❌ | ❌ |
| Modify services/prices | ✅ | ❌ | ❌ | ❌ |

---

### Number Provisioning

When a new business completes onboarding, Parlo automatically provisions a WhatsApp number.

#### Technical Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PARLO WHATSAPP INFRASTRUCTURE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐  │
│   │    Parlo     │     │   Twilio    │     │   Meta Business Suite   │  │
│   │   Backend   │────▶│    API      │────▶│   (WABA via Twilio)    │  │
│   └─────────────┘     └─────────────┘     └─────────────────────────┘  │
│                                                                         │
│   Single WABA (WhatsApp Business Account) owned by Parlo                │
│   All business numbers registered under this WABA                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Provisioning Flow

1. **Business Completes Onboarding** via WhatsApp conversation with Parlo

2. **Backend Provisions Number:**
   ```python
   async def provision_business_number(business_id: str):
       # 1. Buy Mexican phone number via Twilio Number API
       phone_number = await twilio.available_phone_numbers("MX").fetch()
       purchased = await twilio.incoming_phone_numbers.create(phone_number=phone_number)

       # 2. Register as WhatsApp sender under Parlo's WABA
       sender = await twilio.messaging.senders.create(
           phone_number=purchased.phone_number,
           waba_id=PARLO_WABA_ID
       )

       # 3. Configure webhook to point to Parlo's central endpoint
       await twilio.webhooks.create(
           url=f"{PARLO_API_URL}/api/v1/webhooks/whatsapp",
           phone_number=purchased.phone_number
       )

       # 4. Map number to business in database
       await db.businesses.update(
           business_id,
           whatsapp_number=purchased.phone_number,
           whatsapp_number_id=sender.id
       )

       return purchased.phone_number
   ```

3. **Business is Live** within minutes

#### Number Provisioning Details

| Aspect | Details |
|--------|---------|
| **WABA** | Single verified Meta Business Portfolio owned by Parlo |
| **Number Source** | Mexican numbers via Twilio Number API |
| **Webhook** | All numbers point to same central webhook endpoint |
| **Display Name** | Async approval (250 unique customers/day limit is fine) |
| **Templates** | Pre-approved at WABA level, available instantly |
| **Rejection Handling** | Auto-retry with variant if display name rejected |

---

### Universal Patterns

#### Abandoned State Pattern

All stateful flows implement the abandoned state pattern:

```python
class AbandonedStateHandler:
    TIMEOUT_MINUTES = 30  # Configurable per flow

    async def check_abandoned(self, conversation_id: str):
        session = await get_session(conversation_id)

        if session.last_message_at < now() - timedelta(minutes=self.TIMEOUT_MINUTES):
            if session.state not in ['completed', 'abandoned', 'cancelled']:
                await mark_abandoned(session)
                return True
        return False

    async def resume_session(self, conversation_id: str):
        session = await get_session(conversation_id)

        if session.state == 'abandoned':
            # Restore to last active state
            await set_state(session, session.metadata['last_active_state'])
            return f"Welcome back! Let's continue where we left off..."
```

#### State Transition Rules

1. **Forward Only (mostly):** States generally progress forward
2. **Abandon Anywhere:** Any state can transition to `abandoned`
3. **Resume Preserves Context:** Resuming restores the exact previous state
4. **Completion is Final:** `completed`, `cancelled`, `closed` are terminal states

---

### Customer Profiles

#### Cross-Business Profiles

Customer profiles are maintained globally (not per-business):

```python
class CustomerProfile:
    phone_number: str      # Primary identifier
    name: str | None       # Learned from any business
    email: str | None      # If provided

    # Preferences learned across interactions
    preferred_times: list[str]

    # Business-specific data stored separately
    business_data: dict[business_id, BusinessCustomerData]
```

#### Returning Customer Behavior

When a returning customer books:

1. **Prefill Known Info:** Name, preferences auto-populated
2. **Ask to Confirm:** "Is this still your info, or would you like to change it?"
3. **Skip If Confident:** If info is recent and verified, skip confirmation

```python
async def collect_personal_info(customer: Customer, booking_flow: BookingFlow):
    if customer.name and customer.name_verified_at > days_ago(90):
        # Recent verified name - just confirm
        return f"Confirming your booking as {customer.name}. Is that correct?"
    elif customer.name:
        # Have name but not recent - offer to change
        return f"I have you as {customer.name}. Is that still correct, or would you like to update it?"
    else:
        # No name - ask for it
        return "What name should I put for the booking?"
```

---

### Future Routing Features

The following features are noted for future implementation but **not included in MVP**:

| Feature | Description |
|---------|-------------|
| **Automated Reminders** | System-initiated reminder messages (24h before, etc.) |
| **Waitlist Management** | When slots are full, offer to join waitlist |
| **Business-Initiated Reschedule** | Business requests to move appointment |
| **Escalation to Human** | Transfer conversation to human staff |
| **Multi-Location Management** | Manage multiple locations from one account |
| **Advanced Analytics** | Detailed business insights and reporting |
| **Payment Integration** | Deposits, prepayment, in-app payments |

---

### Implementation Checklist

When implementing message routing:

- [ ] Central webhook receives all messages
- [ ] Lookup recipient number to determine channel type
- [ ] Lookup sender phone in staff registrations
- [ ] Count business registrations for multi-business handling
- [ ] Route to appropriate flow handler
- [ ] Initialize or resume state machine
- [ ] Track state transitions in database
- [ ] Handle abandoned state detection
- [ ] Send appropriate responses based on state

**Customer System Prompt:**

```python
def build_system_prompt(self) -> str:
    return f"""Eres Parlo, la asistente virtual de {self.org.name}. Tu trabajo es ayudar a los clientes a agendar citas de manera amable y eficiente.

## Información del Negocio
- Nombre: {self.org.name}
- Servicios disponibles:
{self.format_services()}
- Horario de atención:
{self.format_business_hours()}

## Información del Cliente
- Teléfono: {self.customer.phone_number}
- Nombre: {self.customer.name or "No proporcionado aún"}
- Citas anteriores: {self.format_previous_appointments()}

## Instrucciones
1. Sé amable, profesional y concisa. Usa español mexicano natural.
2. Si el cliente quiere agendar, pregunta qué servicio desea y para cuándo.
3. Usa la herramienta check_availability para ver horarios disponibles antes de ofrecer opciones.
4. Confirma siempre los detalles antes de agendar: servicio, fecha, hora.
5. Si el cliente pregunta algo que no puedes resolver (precios especiales, quejas, preguntas complejas), usa handoff_to_human.
6. Si no conoces el nombre del cliente y es natural preguntar, hazlo.
7. Después de agendar, confirma todos los detalles y despídete amablemente.

## Restricciones
- Nunca inventes horarios disponibles. Siempre usa check_availability.
- No hagas más de una pregunta a la vez.
- Si hay ambigüedad (ej: "mañana" sin hora), pregunta para clarificar.
- Responde solo en español.
"""

def build_staff_system_prompt(self) -> str:
    return f"""Eres Parlo, la asistente virtual de {self.org.name}. Estás hablando con {self.staff.name}, que es {self.staff.role} del negocio.

## Información del Negocio
- Nombre: {self.org.name}
- Servicios disponibles:
{self.format_services()}
- Horario de atención:
{self.format_business_hours()}

## Información del Empleado
- Nombre: {self.staff.name}
- Rol: {self.staff.role}
- Permisos: {self.format_permissions()}

## Capacidades
Como empleado, {self.staff.name} puede pedirte:
1. Ver su agenda del día o de fechas específicas
2. Ver la agenda completa del negocio (si tiene permiso)
3. Bloquear tiempo personal (comida, descanso, citas personales)
4. Marcar citas como completadas o no-show
5. Registrar clientes que llegan sin cita (walk-ins)
6. Consultar historial de clientes
7. Enviar mensajes a clientes en nombre del negocio

## Instrucciones
1. Sé concisa y eficiente. Los empleados quieren respuestas rápidas.
2. Si preguntan por "mi agenda", muestra SU agenda personal, no la del negocio.
3. Confirma acciones importantes antes de ejecutarlas (cancelaciones, cambios).
4. Si piden algo fuera de sus permisos, explícalo amablemente.
5. Para acciones que afectan clientes (cancelar citas), ofrece notificar al cliente.

## Formato de respuestas
- Para agendas, usa formato de lista clara con hora, servicio y cliente
- Para confirmaciones, sé breve: "Listo, bloqueado de 2 a 3 PM ✓"
- Usa emojis con moderación para claridad (✓, ⏰, 👤)
"""
```

### Project Structure

```
parlo/
├── README.md                    # Comprehensive project documentation
├── pyproject.toml               # Python dependencies (using Poetry or uv)
├── alembic.ini                  # Database migrations config
├── .env.example                 # Environment variables template
├── docker-compose.yml           # Local development setup
│
├── alembic/
│   └── versions/                # Migration files
│
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entry point
│   ├── config.py                # Settings management (pydantic-settings)
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py              # Dependency injection (db sessions, auth, etc.)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py        # Main API router
│   │       ├── organizations.py
│   │       ├── services.py
│   │       ├── appointments.py
│   │       ├── customers.py
│   │       ├── availability.py
│   │       ├── staff.py
│   │       └── webhooks.py      # WhatsApp webhook handlers
│   │
│   ├── models/                  # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py              # Base model class
│   │   ├── organization.py
│   │   ├── location.py
│   │   ├── staff.py
│   │   ├── service_type.py
│   │   ├── customer.py
│   │   ├── appointment.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   └── availability.py
│   │
│   ├── schemas/                 # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── organization.py
│   │   ├── appointment.py
│   │   ├── customer.py
│   │   └── ... (matching models)
│   │
│   ├── services/                # Business logic layer
│   │   ├── __init__.py
│   │   ├── scheduling.py        # Availability and booking logic
│   │   ├── whatsapp.py          # WhatsApp API client
│   │   ├── conversation.py      # AI conversation handler
│   │   └── notifications.py     # Reminders and alerts
│   │
│   ├── ai/                      # AI/LLM related code
│   │   ├── __init__.py
│   │   ├── client.py            # Anthropic client wrapper
│   │   ├── prompts.py           # System prompts and templates
│   │   └── tools.py             # Tool definitions for Claude
│   │
│   ├── tasks/                   # Celery background tasks
│   │   ├── __init__.py
│   │   ├── reminders.py         # Send appointment reminders
│   │   └── analytics.py         # Usage tracking, etc.
│   │
│   └── utils/
│       ├── __init__.py
│       ├── datetime.py          # Timezone handling
│       └── phone.py             # Phone number parsing/formatting
│
├── tests/
│   ├── conftest.py
│   ├── test_api/
│   ├── test_services/
│   └── test_ai/
│
└── scripts/
    ├── seed_dev_data.py         # Development data seeding
    └── create_whatsapp_templates.py  # Submit templates to Meta
```

### Environment Variables

```bash
# .env.example

# Application
APP_ENV=development  # development, staging, production
APP_SECRET_KEY=your-secret-key-here
APP_BASE_URL=https://api.parlo.mx

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/parlo

# Redis
REDIS_URL=redis://localhost:6379/0

# Meta WhatsApp
META_APP_ID=your-meta-app-id
META_APP_SECRET=your-meta-app-secret
META_WEBHOOK_VERIFY_TOKEN=your-webhook-verify-token
META_API_VERSION=v18.0

# Anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key

# Observability (optional for v1)
SENTRY_DSN=
```

### Development Setup Instructions

```bash
# 1. Clone and enter project
git clone <repo>
cd parlo

# 2. Install dependencies (using uv for speed)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 3. Start infrastructure
docker-compose up -d  # Postgres + Redis

# 4. Run migrations
alembic upgrade head

# 5. Seed development data (optional)
python scripts/seed_dev_data.py

# 6. Start the server
uvicorn app.main:app --reload

# 7. In another terminal, start Celery worker
celery -A app.tasks worker --loglevel=info

# 8. For WhatsApp webhook testing locally, use ngrok
ngrok http 8000
# Update Meta webhook URL to ngrok URL
```

---

### Parlo - Functional Requirements Checklist

This is the comprehensive list of all functional requirements that the system must satisfy to be production-ready. Each user type has journeys from which specific required functionalities are defined.

**How to use this section:**
- Each requirement has a checkbox `[ ]` - mark `[x]` when implemented and tested
- Requirements are numbered hierarchically: User.Journey.Functionality
- UI column indicates where the action must be available: `WA` = WhatsApp, `Web` = Web Dashboard, `Both` = Both

---

## 1. Owner of a business that uses the Parlo platform

The business owner is the primary paying customer. They set up the business, manage employees, and oversee operations.

### 1.1 Create an account for my business
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 1.1.1 | Send a WhatsApp message to Parlo's onboarding number to get started | WA | [ ] |
| 1.1.2 | Conversationally provide business name during onboarding | WA | [ ] |
| 1.1.3 | Conversationally provide business type/category (barbershop, salon, spa, etc.) | WA | [ ] |
| 1.1.4 | Conversationally provide owner's name | WA | [ ] |
| 1.1.5 | Connect existing WhatsApp Business number via Embedded Signup (scan QR) | Web | [ ] |
| 1.1.6 | Receive confirmation that WhatsApp is connected and ready | WA | [ ] |
| 1.1.7 | Set timezone for the business (default: America/Mexico_City) | Both | [ ] |
| 1.1.8 | Complete initial setup in under 10 minutes | WA | [ ] |

### 1.2 Set up my business location
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 1.2.1 | Add location name | Both | [ ] |
| 1.2.2 | Add location address (optional) | Both | [ ] |
| 1.2.3 | Set business hours for each day of the week | Both | [ ] |
| 1.2.4 | Mark certain days as closed | Both | [ ] |
| 1.2.5 | Set up services offered (name, duration, price) | Both | [ ] |
| 1.2.6 | Add service descriptions (optional) | Both | [ ] |
| 1.2.7 | Set up spots/stations (chairs, tables, beds) | Web | [ ] |
| 1.2.8 | Associate spots with services they can provide | Web | [ ] |
| 1.2.9 | View summary of business setup | Both | [ ] |

### 1.3 Manage employees
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 1.3.1 | Add a new employee with name | Both | [ ] |
| 1.3.2 | Add employee's WhatsApp phone number | Both | [ ] |
| 1.3.3 | Assign services the employee can perform | Both | [ ] |
| 1.3.4 | Assign default spot/station for the employee | Web | [ ] |
| 1.3.5 | Set employee's working hours/schedule | Both | [ ] |
| 1.3.6 | Send onboarding WhatsApp to new employee | WA | [ ] |
| 1.3.7 | View list of all employees | Both | [ ] |
| 1.3.8 | Edit employee details | Both | [ ] |
| 1.3.9 | Deactivate/remove an employee | Both | [ ] |
| 1.3.10 | Reactivate a previously deactivated employee | Web | [ ] |

### 1.4 Manage services
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 1.4.1 | Add a new service type | Both | [ ] |
| 1.4.2 | Set service name | Both | [ ] |
| 1.4.3 | Set service duration (minutes) | Both | [ ] |
| 1.4.4 | Set service price (MXN) | Both | [ ] |
| 1.4.5 | Set service description (optional) | Both | [ ] |
| 1.4.6 | Edit existing service | Both | [ ] |
| 1.4.7 | Deactivate a service (hide from booking) | Both | [ ] |
| 1.4.8 | Delete a service that has no appointments | Web | [ ] |
| 1.4.9 | View all services with their details | Both | [ ] |

### 1.5 Manage spots/stations
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 1.5.1 | Add a new spot (chair, table, bed, etc.) | Web | [ ] |
| 1.5.2 | Set spot name | Web | [ ] |
| 1.5.3 | Associate spot with services it can provide | Web | [ ] |
| 1.5.4 | Set spot display order | Web | [ ] |
| 1.5.5 | Edit spot details | Web | [ ] |
| 1.5.6 | Deactivate a spot | Web | [ ] |
| 1.5.7 | Delete a spot with no appointments | Web | [ ] |
| 1.5.8 | View all spots in a location | Web | [ ] |

### 1.6 View and manage appointments
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 1.6.1 | View today's appointments | Both | [ ] |
| 1.6.2 | View appointments for a specific date | Both | [ ] |
| 1.6.3 | View appointments for a date range | Web | [ ] |
| 1.6.4 | View appointments in calendar format | Web | [ ] |
| 1.6.5 | View appointments in list format | Both | [ ] |
| 1.6.6 | Filter appointments by employee | Web | [ ] |
| 1.6.7 | Filter appointments by service | Web | [ ] |
| 1.6.8 | Filter appointments by status (pending, confirmed, completed, cancelled, no-show) | Web | [ ] |
| 1.6.9 | Create a new appointment manually | Both | [ ] |
| 1.6.10 | Select customer for appointment (existing or new) | Both | [ ] |
| 1.6.11 | Select service for appointment | Both | [ ] |
| 1.6.12 | Select employee for appointment | Both | [ ] |
| 1.6.13 | Select spot for appointment | Web | [ ] |
| 1.6.14 | Select date and time for appointment | Both | [ ] |
| 1.6.15 | Add notes to appointment | Both | [ ] |
| 1.6.16 | Edit appointment details | Both | [ ] |
| 1.6.17 | Cancel an appointment | Both | [ ] |
| 1.6.18 | Mark appointment as completed | Both | [ ] |
| 1.6.19 | Mark appointment as no-show | Both | [ ] |
| 1.6.20 | Register a walk-in customer | Both | [ ] |
| 1.6.21 | Receive notification when new appointment is booked | WA | [ ] |
| 1.6.22 | Receive daily schedule summary | WA | [ ] |

### 1.7 Manage customers
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 1.7.1 | View list of all customers | Both | [ ] |
| 1.7.2 | Search customers by name or phone | Both | [ ] |
| 1.7.3 | View customer details (name, phone, notes) | Both | [ ] |
| 1.7.4 | View customer appointment history | Both | [ ] |
| 1.7.5 | Edit customer details | Both | [ ] |
| 1.7.6 | Add notes to customer profile | Both | [ ] |
| 1.7.7 | Send message to customer | WA | [ ] |

### 1.8 Manage availability and exceptions
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 1.8.1 | Block time for all employees (holiday closure) | Both | [ ] |
| 1.8.2 | Block time for specific employee | Both | [ ] |
| 1.8.3 | Set recurring availability for employees | Web | [ ] |
| 1.8.4 | Add one-time availability exception | Both | [ ] |
| 1.8.5 | Remove availability block | Both | [ ] |
| 1.8.6 | View all blocked times | Web | [ ] |

### 1.9 Access web dashboard
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 1.9.1 | Request magic link via WhatsApp | WA | [ ] |
| 1.9.2 | Receive magic link in WhatsApp | WA | [ ] |
| 1.9.3 | Click magic link to access dashboard | Web | [ ] |
| 1.9.4 | Stay logged in for 7 days | Web | [ ] |
| 1.9.5 | Log out of dashboard | Web | [ ] |
| 1.9.6 | Switch between locations (multi-location) | Web | [ ] |

### 1.10 Manage business settings
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 1.10.1 | View business/organization details | Both | [ ] |
| 1.10.2 | Edit business name | Both | [ ] |
| 1.10.3 | Edit timezone | Web | [ ] |
| 1.10.4 | View WhatsApp connection status | Web | [ ] |
| 1.10.5 | Reconnect WhatsApp if disconnected | Web | [ ] |
| 1.10.6 | View account/billing status | Web | [ ] |

---

## 2. Employee of a business that uses the Parlo platform

Employees interact exclusively via WhatsApp to manage their schedule and handle walk-ins.

### 2.1 Get onboarded as an employee
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 2.1.1 | Receive WhatsApp message from Parlo with welcome and instructions | WA | [ ] |
| 2.1.2 | Confirm identity/acceptance via WhatsApp response | WA | [ ] |
| 2.1.3 | Understand what Parlo can do (brief tutorial) | WA | [ ] |

### 2.2 View my schedule
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 2.2.1 | Ask "what do I have today" and see today's appointments | WA | [ ] |
| 2.2.2 | Ask for schedule on a specific date | WA | [ ] |
| 2.2.3 | Ask "what's next" to see next upcoming appointment | WA | [ ] |
| 2.2.4 | See appointment details: time, service, customer name | WA | [ ] |
| 2.2.5 | See blocked times in schedule | WA | [ ] |

### 2.3 View business schedule
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 2.3.1 | Ask for full business schedule if permitted | WA | [ ] |
| 2.3.2 | See all employees' appointments for a date | WA | [ ] |

### 2.4 Manage my appointments
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 2.4.1 | Mark appointment as completed | WA | [ ] |
| 2.4.2 | Mark appointment as no-show | WA | [ ] |
| 2.4.3 | Cancel an appointment | WA | [ ] |
| 2.4.4 | Optionally notify customer when cancelling | WA | [ ] |
| 2.4.5 | Book a walk-in customer | WA | [ ] |
| 2.4.6 | Specify service for walk-in | WA | [ ] |
| 2.4.7 | Optionally capture walk-in customer phone | WA | [ ] |
| 2.4.8 | Optionally capture walk-in customer name | WA | [ ] |

### 2.5 Manage my availability
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 2.5.1 | Block personal time (lunch, break, etc.) | WA | [ ] |
| 2.5.2 | Specify start and end time for block | WA | [ ] |
| 2.5.3 | Optionally specify reason for block | WA | [ ] |
| 2.5.4 | Remove a previously created block | WA | [ ] |
| 2.5.5 | Block time for future dates | WA | [ ] |

### 2.6 Look up customer information
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 2.6.1 | Ask about customer history by phone number | WA | [ ] |
| 2.6.2 | See customer's previous appointments | WA | [ ] |
| 2.6.3 | See customer's name if known | WA | [ ] |

### 2.7 Communicate with customers
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 2.7.1 | Ask Parlo to send message to customer | WA | [ ] |
| 2.7.2 | Specify customer by phone or by recent appointment | WA | [ ] |
| 2.7.3 | Compose custom message to send | WA | [ ] |

---

## 3. Client (customer) of a business that uses the Parlo platform

Clients interact exclusively via WhatsApp. They have no web interface.

### 3.1 Discover and initiate contact
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 3.1.1 | Send any WhatsApp message to business number to start | WA | [ ] |
| 3.1.2 | Receive friendly greeting in Mexican Spanish | WA | [ ] |
| 3.1.3 | Understand what services are available | WA | [ ] |

### 3.2 Book an appointment
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 3.2.1 | Express intent to book (in natural language) | WA | [ ] |
| 3.2.2 | Be asked which service they want | WA | [ ] |
| 3.2.3 | Select from available services | WA | [ ] |
| 3.2.4 | Be asked when they want the appointment | WA | [ ] |
| 3.2.5 | Specify preferred date/time (natural language: "mañana en la tarde") | WA | [ ] |
| 3.2.6 | See available time slots for requested period | WA | [ ] |
| 3.2.7 | Select a time slot | WA | [ ] |
| 3.2.8 | Optionally request specific employee | WA | [ ] |
| 3.2.9 | Provide name if not already known | WA | [ ] |
| 3.2.10 | Receive confirmation with all appointment details | WA | [ ] |
| 3.2.11 | Booking confirmed in under 2 minutes | WA | [ ] |

### 3.3 View my appointments
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 3.3.1 | Ask about upcoming appointments | WA | [ ] |
| 3.3.2 | See list of upcoming appointments with details | WA | [ ] |
| 3.3.3 | See appointment date, time, service, and price | WA | [ ] |

### 3.4 Modify my appointments
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 3.4.1 | Express intent to cancel | WA | [ ] |
| 3.4.2 | See which appointment(s) can be cancelled | WA | [ ] |
| 3.4.3 | Confirm cancellation | WA | [ ] |
| 3.4.4 | Receive cancellation confirmation | WA | [ ] |
| 3.4.5 | Express intent to reschedule | WA | [ ] |
| 3.4.6 | See available alternative times | WA | [ ] |
| 3.4.7 | Select new time | WA | [ ] |
| 3.4.8 | Receive reschedule confirmation | WA | [ ] |

### 3.5 Receive notifications
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 3.5.1 | Receive booking confirmation message | WA | [ ] |
| 3.5.2 | Receive reminder 24 hours before appointment | WA | [ ] |
| 3.5.3 | Receive notification if appointment is cancelled by business | WA | [ ] |
| 3.5.4 | Receive notification if appointment is rescheduled by business | WA | [ ] |

### 3.6 Get help
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 3.6.1 | Ask questions about services or prices | WA | [ ] |
| 3.6.2 | Request to speak with human (handoff) | WA | [ ] |
| 3.6.3 | Be transferred to business owner when AI cannot help | WA | [ ] |
| 3.6.4 | Business owner receives notification of handoff | WA | [ ] |

---

## 4. Parlo admin user

Platform administrators manage all organizations and debug issues.

### 4.1 Access admin dashboard
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 4.1.1 | Login with admin password | Web | [x] |
| 4.1.2 | Password-based authentication (separate from org auth) | Web | [x] |
| 4.1.3 | Stay logged in with admin session | Web | [x] |
| 4.1.4 | Log out of admin dashboard | Web | [x] |

### 4.2 View platform statistics
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 4.2.1 | See total number of organizations | Web | [x] |
| 4.2.2 | See total number of appointments | Web | [x] |
| 4.2.3 | See total number of customers | Web | [x] |
| 4.2.4 | See total number of messages | Web | [x] |
| 4.2.5 | See organizations by status (active, onboarding, suspended) | Web | [x] |

### 4.3 Manage organizations
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 4.3.1 | View list of all organizations | Web | [x] |
| 4.3.2 | Search organizations by name | Web | [x] |
| 4.3.3 | Filter organizations by status | Web | [x] |
| 4.3.4 | View organization details | Web | [x] |
| 4.3.5 | View organization's locations | Web | [x] |
| 4.3.6 | View organization's staff count | Web | [x] |
| 4.3.7 | View organization's customer count | Web | [x] |
| 4.3.8 | View organization's appointment count | Web | [x] |
| 4.3.9 | Suspend an organization (block login) | Web | [x] |
| 4.3.10 | Reactivate a suspended organization | Web | [x] |
| 4.3.11 | "Login As" - impersonate any organization | Web | [x] |
| 4.3.12 | Impersonation opens new tab with org dashboard | Web | [x] |

### 4.4 Debug AI conversations
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 4.4.1 | View all WhatsApp conversations across platform | Web | [x] |
| 4.4.2 | Filter conversations by organization | Web | [x] |
| 4.4.3 | View conversation message history | Web | [x] |
| 4.4.4 | See message sender type (Customer, AI, Staff) | Web | [x] |
| 4.4.5 | See message timestamps | Web | [x] |
| 4.4.6 | Conversations grouped by date | Web | [x] |

### 4.5 Monitor platform activity
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 4.5.1 | View activity feed of recent events | Web | [x] |
| 4.5.2 | See recent organization signups | Web | [x] |
| 4.5.3 | See appointment status changes | Web | [x] |
| 4.5.4 | Click activity to view related organization | Web | [x] |

### 4.6 Perform any organization action
| # | Requirement | UI | Status |
|---|-------------|----|----|
| 4.6.1 | Edit any organization's settings | Web | [ ] |
| 4.6.2 | Edit any organization's services | Web | [ ] |
| 4.6.3 | Edit any organization's employees | Web | [ ] |
| 4.6.4 | Edit any organization's appointments | Web | [ ] |
| 4.6.5 | Edit any organization's customers | Web | [ ] |

---

## 5. Non-Functional Requirements

These requirements apply to the entire system.

### 5.1 Language and Localization
| # | Requirement | Status |
|---|-------------|--------|
| 5.1.1 | All AI responses in natural Mexican Spanish | [x] |
| 5.1.2 | Use informal "tú" form (not "usted") | [x] |
| 5.1.3 | Currency displayed in MXN (Mexican pesos) | [x] |
| 5.1.4 | Prices formatted as "$150" (not "150 MXN") | [x] |
| 5.1.5 | Dates in Spanish format: "viernes 15 de enero" | [x] |
| 5.1.6 | Times in 12-hour format with AM/PM: "3:00 PM" | [x] |
| 5.1.7 | No English words in user-facing text | [x] |

### 5.2 Time and Timezone Handling
| # | Requirement | Status |
|---|-------------|--------|
| 5.2.1 | All times stored in UTC in database | [x] |
| 5.2.2 | Times displayed in organization's timezone | [x] |
| 5.2.3 | Default timezone: America/Mexico_City | [x] |
| 5.2.4 | Natural language date parsing ("mañana", "el lunes", "la próxima semana") | [x] |
| 5.2.5 | Correct handling of DST transitions | [ ] |

### 5.3 Security
| # | Requirement | Status |
|---|-------------|--------|
| 5.3.1 | Organization data is isolated (no cross-org access) | [x] |
| 5.3.2 | JWT tokens expire appropriately (7 days for web, shorter for admin) | [x] |
| 5.3.3 | Magic link tokens single-use and expire in 15 minutes | [x] |
| 5.3.4 | Admin password is configurable via environment variable | [x] |
| 5.3.5 | No sensitive data (API keys, passwords) in logs | [x] |
| 5.3.6 | SQL injection prevention (use ORM, no raw queries) | [x] |
| 5.3.7 | XSS prevention in web dashboard | [x] |
| 5.3.8 | Suspended organizations cannot login | [x] |
| 5.3.9 | WhatsApp webhook validates sender identity | [x] |

### 5.4 Performance
| # | Requirement | Status |
|---|-------------|--------|
| 5.4.1 | WhatsApp webhook responds within 20 seconds | [x] |
| 5.4.2 | AI response generated within 15 seconds | [x] |
| 5.4.3 | Availability slot calculation handles 30-day range | [x] |
| 5.4.4 | Dashboard pages load within 3 seconds | [x] |
| 5.4.5 | API endpoints respond within 500ms (non-AI) | [x] |

### 5.5 Reliability
| # | Requirement | Status |
|---|-------------|--------|
| 5.5.1 | Webhook idempotency (handle duplicate deliveries) | [x] |
| 5.5.2 | Message deduplication by WhatsApp message_id | [x] |
| 5.5.3 | Graceful degradation when AI API is unavailable | [ ] |
| 5.5.4 | Graceful degradation when WhatsApp API is unavailable | [ ] |
| 5.5.5 | Database connection pooling and retry logic | [x] |
| 5.5.6 | Background task retry on failure (reminders, notifications) | [ ] |

### 5.6 Data Integrity
| # | Requirement | Status |
|---|-------------|--------|
| 5.6.1 | Appointments cannot overlap for same staff | [x] |
| 5.6.2 | Appointments cannot overlap for same spot | [x] |
| 5.6.3 | Cannot delete location if it's the only one | [x] |
| 5.6.4 | Cannot delete service with existing appointments | [x] |
| 5.6.5 | Cascade deletes handled properly (org → locations → spots) | [x] |
| 5.6.6 | Unique constraint on (organization_id, staff phone_number) | [x] |
| 5.6.7 | Unique constraint on (organization_id, customer phone_number) | [x] |

### 5.7 Mobile Experience
| # | Requirement | Status |
|---|-------------|--------|
| 5.7.1 | Web dashboard is mobile-responsive | [x] |
| 5.7.2 | Login page works on mobile browsers | [x] |
| 5.7.3 | Calendar view adapts to mobile screens | [x] |
| 5.7.4 | Forms are usable on touch devices | [x] |

### 5.8 Error Handling
| # | Requirement | Status |
|---|-------------|--------|
| 5.8.1 | API returns appropriate HTTP status codes | [x] |
| 5.8.2 | Error messages are user-friendly in Spanish | [x] |
| 5.8.3 | AI handles unknown intents gracefully | [x] |
| 5.8.4 | AI offers handoff when stuck in conversation | [x] |
| 5.8.5 | Failed webhook returns 200 to prevent Meta retries for permanent errors | [x] |

---

## 6. Integration Requirements

### 6.1 WhatsApp API (Twilio)
| # | Requirement | Status |
|---|-------------|--------|
| 6.1.1 | Webhook endpoint for receiving messages (POST) | [x] |
| 6.1.2 | Webhook verification endpoint (GET) | [x] |
| 6.1.3 | Send text messages via Twilio API | [x] |
| 6.1.4 | Send template messages via Twilio API | [ ] |
| 6.1.5 | Meta Embedded Signup for connecting existing business numbers | [x] |
| 6.1.6 | Twilio number provisioning for new businesses | [x] |
| 6.1.7 | Handle message status updates (sent, delivered, read) | [ ] |
| 6.1.8 | Mock mode for local development without Twilio credentials | [x] |

### 6.2 Message Templates (Meta Approved)
| # | Requirement | Status |
|---|-------------|--------|
| 6.2.1 | appointment_confirmation template created | [ ] |
| 6.2.2 | appointment_reminder template created | [ ] |
| 6.2.3 | appointment_cancelled template created | [ ] |
| 6.2.4 | employee_welcome template created | [ ] |
| 6.2.5 | magic_link template created | [ ] |
| 6.2.6 | All templates approved by Meta | [ ] |

### 6.3 AI/LLM Integration (gpt-4.1)
| # | Requirement | Status |
|---|-------------|--------|
| 6.3.1 | OpenAI gpt-4.1 API client implemented | [x] |
| 6.3.2 | Tool calling for booking operations | [x] |
| 6.3.3 | Separate tool sets for customer vs staff | [x] |
| 6.3.4 | System prompts in Mexican Spanish | [x] |
| 6.3.5 | Conversation history management | [x] |
| 6.3.6 | Context injection (services, hours, customer history) | [x] |
| 6.3.7 | Fallback when API key not configured | [ ] |
| 6.3.8 | Tool execution loop (AI → tool → AI → response) | [x] |

### 6.4 Background Tasks (Celery)
| # | Requirement | Status |
|---|-------------|--------|
| 6.4.1 | Celery worker configuration | [x] |
| 6.4.2 | Redis as message broker | [x] |
| 6.4.3 | Appointment reminder task (24h before) | [x] |
| 6.4.4 | Daily schedule summary task | [ ] |
| 6.4.5 | Task retry on failure | [ ] |
| 6.4.6 | Task monitoring/visibility | [ ] |

---

## 7. Infrastructure Requirements

### 7.1 Database (Render PostgreSQL)
| # | Requirement | Status |
|---|-------------|--------|
| 7.1.1 | PostgreSQL 15+ deployed on Render | [x] |
| 7.1.2 | Alembic migrations working | [x] |
| 7.1.3 | All entity migrations created | [x] |
| 7.1.4 | Indexes on frequently queried fields | [x] |
| 7.1.5 | Database backups configured | [ ] |

### 7.2 Redis (Deferred)
| # | Requirement | Status |
|---|-------------|--------|
| 7.2.1 | Redis deployed | [ ] Deferred |
| 7.2.2 | Redis connection handling | [x] Code ready |

### 7.3 Deployment (Render)
| # | Requirement | Status |
|---|-------------|--------|
| 7.3.1 | Backend deployed and accessible on Render | [x] |
| 7.3.2 | Frontend deployed and accessible on Render | [x] |
| 7.3.3 | HTTPS configured | [x] |
| 7.3.4 | Domain configured (api.parlo.mx, app.parlo.mx) | [ ] |
| 7.3.5 | Environment variables configured | [x] |
| 7.3.6 | Celery worker running | [ ] Deferred |

### 7.4 Monitoring
| # | Requirement | Status |
|---|-------------|--------|
| 7.4.1 | Application logs accessible | [ ] |
| 7.4.2 | Error tracking (Sentry or equivalent) | [ ] |
| 7.4.3 | Health check endpoint | [x] |
| 7.4.4 | Uptime monitoring | [ ] |

---

## How to Mark Progress

When implementing a requirement:
1. Test the feature thoroughly
2. Mark the checkbox as `[x]`
3. Add date and notes if needed in commit message
4. Update workplan.md with completed tasks

**Production Readiness Criteria:**
- All requirements marked `[x]`
- All tests passing
- No critical bugs in known issues
- Successfully tested with real WhatsApp messages
- At least one business owner has completed full journey

## Appendix: Example Conversations

### Example 1: Simple Booking

```
Cliente: Hola buenas tardes
Parlo: ¡Hola! Bienvenido a Barbería Don Carlos. ¿En qué puedo ayudarte?

Cliente: Quiero una cita para un corte
Parlo: ¡Claro! ¿Para qué día te gustaría agendar tu corte?

Cliente: Mañana en la tarde
Parlo: Perfecto. Mañana viernes tengo disponibles estos horarios para corte de cabello ($150):
• 3:00 PM
• 4:00 PM  
• 5:30 PM
¿Cuál te funciona mejor?

Cliente: A las 4
Parlo: Listo, te agendé tu corte de cabello para mañana viernes a las 4:00 PM. 
¿Me confirmas tu nombre para la cita?

Cliente: Juan Pérez
Parlo: ¡Perfecto, Juan! Tu cita está confirmada:
📅 Viernes 15 de enero
⏰ 4:00 PM
💇 Corte de cabello - $150

Te enviaré un recordatorio mañana. ¡Nos vemos!

Cliente: Gracias
Parlo: ¡Con gusto! Que tengas buena tarde. 👋
```

### Example 2: Rescheduling

```
Cliente: Hola, necesito cambiar mi cita de mañana
Parlo: Hola Juan, claro que sí. Veo que tienes una cita para corte mañana viernes a las 4:00 PM. ¿Para cuándo te gustaría cambiarla?

Cliente: Para el sábado si hay espacio
Parlo: El sábado tengo estos horarios disponibles:
• 10:00 AM
• 11:30 AM
• 2:00 PM
¿Cuál prefieres?

Cliente: 11:30
Parlo: Listo, cambié tu cita para el sábado a las 11:30 AM. ¿Todo bien?

Cliente: Sí perfecto gracias
Parlo: ¡Excelente! Nos vemos el sábado, Juan. 👍
```

### Example 3: Handoff

```
Cliente: Oye quiero saber si hacen tintes para hombre
Parlo: Actualmente los servicios que tenemos son corte de cabello y arreglo de barba. Para preguntas sobre servicios adicionales, deja que le pase tu mensaje a Carlos, el dueño.

[Notificación a Carlos: "Un cliente pregunta por tintes para hombre. Teléfono: +52 55 1234 5678"]

Parlo: Ya le avisé a Carlos, te contactará pronto para darte más información. ¿Hay algo más en lo que pueda ayudarte?
```

### Example 4: Staff Checking Schedule

```
[Message from registered staff phone number]

Pedro (empleado): Qué tengo hoy?
Parlo: Hola Pedro, aquí está tu agenda para hoy viernes:

⏰ 10:00 AM - Corte - Juan Pérez
⏰ 11:00 AM - Corte y barba - Miguel Sánchez  
⏰ 12:30 PM - Corte - Luis Ramírez
🍽️ 2:00 PM - 3:00 PM - Bloqueado (comida)
⏰ 3:00 PM - Barba - Carlos Mendoza
⏰ 4:00 PM - Disponible
⏰ 5:00 PM - Corte - Roberto García

Tienes 5 citas y un espacio libre a las 4.

Pedro: Bloquea las 4, tengo que salir temprano
Parlo: Listo, bloqueé las 4:00 PM ✓ ¿Quieres que también bloquee de 5 en adelante?

Pedro: No solo las 4
Parlo: Perfecto, solo las 4:00 PM bloqueadas. ¿Algo más?
```

### Example 5: Staff Handling Walk-in

```
María (empleada): Acaba de llegar alguien para uñas
Parlo: ¿Qué servicio quiere? Tenemos:
• Manicure - $200 (45 min)
• Pedicure - $250 (1 hr)
• Mani + Pedi - $400 (1.5 hr)

María: Mani pedi
Parlo: Perfecto. ¿Tienes el teléfono de la clienta para registrarla?

María: 55 9876 5432
Parlo: Registrado. ¿Nombre?

María: Ana
Parlo: Listo ✓ Registré a Ana (55 9876 5432) para Mani + Pedi ahora a las 11:30 AM contigo.

María: 👍
```

### Example 6: Staff Marking No-Show

```
Carlos (dueño): El de las 3 no llegó
Parlo: ¿Te refieres a la cita de Roberto García a las 3:00 PM (Corte)?

Carlos: Si
Parlo: Marqué la cita como no-show ✓ ¿Quieres que le envíe un mensaje a Roberto?

Carlos: Si, dile que esperamos que esté bien y que nos avise para reagendar
Parlo: Enviado ✓ Le mandé: "Hola Roberto, notamos que no pudiste llegar a tu cita de hoy. Esperamos que todo esté bien. Cuando gustes, escríbenos para reagendar. - Barbería Don Carlos"
```

### Example 7: Owner Adding Staff

```
Carlos (dueño): Quiero agregar un nuevo empleado
Parlo: ¡Claro! Necesito algunos datos:
1. ¿Cómo se llama?

Carlos: Pedro Hernández
Parlo: 2. ¿Cuál es su número de WhatsApp?

Carlos: 55 1111 2222
Parlo: 3. ¿Qué servicios va a ofrecer Pedro?
• Corte de cabello
• Arreglo de barba
• Corte y barba

Carlos: Todos
Parlo: Perfecto. Agregué a Pedro Hernández (55 1111 2222) como empleado ✓

Ahora Pedro puede escribirme desde su WhatsApp para:
- Ver su agenda
- Bloquear tiempo
- Marcar citas completadas
- Registrar walk-ins

¿Quieres que le mande un mensaje de bienvenida explicándole cómo usar Parlo?

Carlos: Si
Parlo: Enviado ✓
```

---

## Final Note

This is a real product that will serve real small business owners. Quality matters. The AI needs to feel natural and helpful, not robotic. The booking flow needs to be rock solid—a missed appointment damages trust.

Build with care. Ship incrementally. Test with real messages in Spanish.

¡Éxito! 🚀
