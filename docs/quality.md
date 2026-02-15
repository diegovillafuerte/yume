# Quality Grades
<!-- last-verified: 2026-02-15 -->

Last updated: 2026-02-15

## Grading Scale
- **A** — Automated test coverage, mechanical enforcement, well-documented
- **B** — Some test coverage, documented but not mechanically enforced
- **C** — Minimal/no test coverage, relies on manual verification
- **D** — Known gaps, no coverage

## Domain Grades

| Domain | Grade | Coverage | Notes |
|--------|-------|----------|-------|
| Message Routing | A | 5 routing cases in evals | All cases simulated & tested |
| Customer Booking | A | Eval: book/cancel/reschedule | DB state assertions |
| Staff Management | B | Eval: schedule check | Missing: staff onboarding eval |
| Business Onboarding | B | 2 eval tests | Number provisioning not eval-tested |
| Handoff-to-Human | C | No eval | Only manual testing via simulation |
| Admin Dashboard | C | No tests | Visual verification only |
| Frontend Components | C | Vitest configured, no meaningful tests | |
| Auth System | B | Some unit tests | No E2E auth flow test |
| Scheduling/Availability | A | 14 conflict detection tests | Edge cases well covered |
| Error Handling | C | No global middleware | Traced but no error tracking |

## Architectural Layer Grades

| Layer | Grade | Notes |
|-------|-------|-------|
| API Routes | B | Typed schemas, no explicit route tests |
| Services | B | Traced, some tested via evals |
| AI (prompts/tools) | B | Eval coverage for main flows |
| Database/Models | A | Migrations, relationships, scoping |
| Frontend API Client | B | Some unit tests for client.ts |
| Frontend UI | C | No component tests in CI |

## Deferred Work (from Harness Engineering assessment)

These items were identified during the harness engineering gap analysis
and should be picked up in future iterations:

### Phase 5: Strengthen Feedback Loops
- Run evals in CI on PRs (non-blocking, requires OPENAI_API_KEY secret)
- Add pre-commit hooks (.pre-commit-config.yaml with ruff + golden rules)
- Add frontend vitest to CI pipeline
- Promote human review feedback into linter rules systematically

### Phase 6: Improve Agent Legibility
- Local app boot script (scripts/boot_local.sh) for isolated testing
- Simulation response enrichment (inline trace waterfall, tool calls, state changes)
- Per-branch isolated app instances (longer-term)

### Other Deferred Items
- Sentry/error tracking integration
- Rate limiting on auth endpoints
- Row-level locking for concurrent bookings
- Admin password hashing (currently plaintext comparison)
- OpenAPI/Swagger documentation exposure
