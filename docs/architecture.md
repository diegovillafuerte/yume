# Architecture
<!-- last-verified: 2026-02-15 -->

## System Overview

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

## Three Interfaces

1. **WhatsApp** — Two channels: Parlo Central (B2B) + Business Numbers (B2C/Staff)
2. **Web Dashboard** — Business owners manage everything (magic link auth)
3. **Admin Dashboard** — Platform management (password auth)

This is a Python-primary codebase with TypeScript frontend. Always check for import mismatches between services when debugging deployment errors.

## Message Routing (THE CORE)

**See `docs/PROJECT_SPEC.md` for the complete routing specification including state machines and permissions.**

Parlo operates two WhatsApp channels:
- **Parlo Central Number** — B2B: business onboarding + management
- **Business Numbers** — B2C: end customers + staff of that specific business

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

### Routing Cases

| Case | Recipient | Sender | Route |
|------|-----------|--------|-------|
| 1 | Parlo Central | Unknown | Business Onboarding |
| 2a | Parlo Central | Staff of 1 business | Business Management |
| 2b | Parlo Central | Staff of 2+ businesses | Redirect |
| 3 | Business Number | New staff | Staff Onboarding |
| 4 | Business Number | Known staff | Business Management |
| 5 | Business Number | Anyone else | End Customer |

## Key Patterns

### Dual Authentication
- **Business owners:** Magic link via WhatsApp → JWT (7 days)
- **Admin:** Password → JWT (shorter expiry)
- Frontend uses different tokens: `auth_token` vs `admin_token`

### Tool-Based AI
AI uses typed tools, never accesses DB directly:
- Customer tools: check_availability, book_appointment, cancel, reschedule
- Staff tools: get_schedule, block_time, mark_complete, book_walk_in

### All Times in UTC
Store UTC, convert to org timezone only for display.

### Webhook Idempotency
Check message_id before processing to handle duplicate deliveries.

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

### Key Relationships
- Staff ↔ ServiceType: many-to-many (what staff can do)
- Spot ↔ ServiceType: many-to-many (what spot supports)
- Appointment requires: customer, service, spot, (optional) staff

## Layering

```
app/api/v1/     → HTTP layer (routes, auth, serialization)
app/services/   → Business logic (must NOT import from app/api/)
app/models/     → Database models (SQLAlchemy)
app/ai/         → OpenAI integration (prompts, tools, client)
app/tasks/      → Background tasks (Celery)
```

Services must not depend on the API layer. The API layer depends on services, not the other way around.
