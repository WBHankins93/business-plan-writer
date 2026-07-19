# Reusable Product Build Prompts

Copy-and-paste templates for planning, building, reviewing, and launching product features.

Replace bracketed placeholders before using a prompt:

- `[PROJECT_PATH]` — repository path
- `[FEATURE_NAME]` — feature or initiative name
- `[USER]` — target user
- `[PROBLEM]` — problem being solved
- `[SUCCESS_METRIC]` — measurable outcome
- `[LAUNCH_STAGE]` — prototype, private beta, public beta, or production
- `[CONSTRAINTS]` — technical, legal, budget, or timeline constraints

These prompts are intentionally designed for separate chats. Each chat should have one clear owner, one bounded scope, and one auditable outcome.

---

## Shared engineering rules

Append this section to any engineering prompt.

```text
Repository: [PROJECT_PATH]

Before changing code:
1. Inspect the repository, current architecture, relevant files, tests, and working-tree status.
2. Identify existing behavior that must be preserved.
3. State assumptions and list the files likely to change.
4. Define acceptance criteria before implementation.

Implementation rules:
- Make the smallest coherent change that solves the stated problem.
- Every changed line must have a direct purpose tied to a requirement, test, defect, or operational need.
- Remove dead code, unused imports, duplicate helpers, stale comments, obsolete feature flags, and misleading documentation when they are directly related to the work.
- Do not add speculative abstractions, frameworks, features, or configuration.
- Do not rewrite unrelated files or silently change unrelated behavior.
- Prefer explicit names, typed contracts, small modules, and predictable data flow.
- Keep business logic separate from transport, persistence, presentation, and provider integrations.
- Make failures visible, structured, and actionable.
- Add tests for the happy path, failure paths, and important boundary conditions.
- Update documentation only when the implemented behavior or operating procedure changes.

Service-boundary rules:
- Break complex work into small services or modules with one clear responsibility.
- Give each service an explicit input contract, output contract, failure contract, and audit trail.
- Prefer independently testable modules in one repository and one deployable process while scale is low.
- Create separate network/deployment microservices only when isolation, scaling, security, or ownership requires them.
- Do not create microservice ceremony merely to make the architecture look distributed.

Verification rules:
1. Run the narrowest relevant tests while iterating.
2. Run the full relevant test suite, type checks, linting, and production build before handoff.
3. Report files changed, code removed, tests run, behavior changed, and unresolved risks.
4. If verification cannot run, explain exactly why and provide the next command needed.
```

---

## 1. Repository and feature discovery

Use this before implementing any substantial feature.

```text
You are reviewing [FEATURE_NAME] in [PROJECT_PATH].

User and problem:
- Target user: [USER]
- Problem: [PROBLEM]
- Launch stage: [LAUNCH_STAGE]
- Success metric: [SUCCESS_METRIC]
- Constraints: [CONSTRAINTS]

Do not implement yet.

First:
1. Inventory the repository and identify the current entry points.
2. Trace the existing user flow from input to output.
3. Identify the current UI, API, service, persistence, and external-provider boundaries.
4. Inspect tests, fixtures, configuration, deployment files, and documentation.
5. Check the working tree for unrelated user changes.
6. Identify defects, duplicated responsibilities, missing contracts, and stale documentation.
7. Describe the smallest viable implementation path.

Deliver:
- Current-state summary
- User-flow diagram or sequence
- Relevant files and responsibilities
- Current behavior that must remain unchanged
- Major risks and blockers
- Proposed scope
- Explicit non-goals
- Acceptance criteria
- Recommended implementation order

Stop after the review unless implementation is explicitly requested.
```

---

## 2. UI feature implementation

Use for a new screen, workflow, form, dashboard, or interaction.

```text
Build [FEATURE_NAME] in [PROJECT_PATH].

Target user: [USER]
Problem: [PROBLEM]
Launch stage: [LAUNCH_STAGE]
Success metric: [SUCCESS_METRIC]
Constraints: [CONSTRAINTS]

Design the experience before coding:
1. Define the primary user task.
2. Define the primary CTA and the expected next state.
3. Map empty, loading, success, partial-success, validation, offline, timeout, and failure states.
4. Identify what information should be shown immediately and what belongs behind progressive disclosure.
5. Define the data needed by the UI and where it comes from.
6. Define keyboard, screen-reader, focus, color-contrast, and touch-target behavior.

Implementation requirements:
- Use existing design tokens and components where they exist.
- Keep presentation separate from data-fetching and business logic.
- Use human-readable labels and actionable errors.
- Avoid duplicate headings, duplicate state, duplicate previews, and placeholder copy that suggests unsupported behavior.
- Do not expose internal field names or implementation details unless the user needs them.
- Do not add visual decoration that does not support comprehension, trust, or conversion.

Acceptance criteria:
- [ ] Primary user task is clear without explanation.
- [ ] Happy path works end to end.
- [ ] Empty state explains what to do next.
- [ ] Loading state communicates progress without misleading certainty.
- [ ] Validation errors identify the affected field and recovery action.
- [ ] Failure state distinguishes user error, service error, and timeout.
- [ ] Success state confirms the outcome and provides the next action.
- [ ] Keyboard and responsive behavior are verified.
- [ ] Production build passes.

Use the shared engineering rules above. Do not modify backend contracts unless the change is explicitly required and documented.
```

---

## 3. API or backend feature

Use for a new endpoint, workflow, integration, or backend capability.

```text
Build [FEATURE_NAME] in [PROJECT_PATH].

User problem: [PROBLEM]
Consumer: [UI, CLI, worker, external integration, or admin tool]
Launch stage: [LAUNCH_STAGE]
Constraints: [CONSTRAINTS]

Define before implementation:
1. Request contract.
2. Response contract.
3. Authentication and authorization rules.
4. Validation rules.
5. State transitions.
6. Idempotency behavior.
7. Timeout, retry, cancellation, and rate-limit behavior.
8. User-safe error messages and operator diagnostics.
9. Audit events and fields that must be retained.
10. Observability: logs, metrics, traces, and correlation IDs.

Architecture requirements:
- Keep transport, business logic, persistence, and provider calls in separate modules.
- Do not put business logic directly in route handlers.
- Use explicit typed request and response models.
- Make side effects idempotent where retries are possible.
- Never trust client-provided ownership, payment, role, or status fields.
- Do not expose secrets or sensitive payloads in logs.

Acceptance criteria:
- [ ] Valid request succeeds.
- [ ] Invalid request returns a structured, actionable error.
- [ ] Unauthorized request is rejected.
- [ ] Duplicate request behaves safely.
- [ ] Provider timeout/failure is persisted and reported.
- [ ] Database failure is handled without data corruption.
- [ ] Audit record is created for important state changes.
- [ ] Tests cover success, validation, auth, retries, idempotency, and failure.
- [ ] API documentation includes examples.

Use the shared engineering rules above. Remove dead code and do not add endpoints without a current consumer.
```

---

## 4. Agent, pipeline, or workflow refactor

Use for multi-step AI or automation systems.

```text
Refactor [WORKFLOW_NAME] in [PROJECT_PATH].

Current stages:
[LIST_STAGES]

User outcome: [PROBLEM]
Launch stage: [LAUNCH_STAGE]
Constraints: [CONSTRAINTS]

Goals:
1. Give every stage one clearly defined responsibility.
2. Define typed input, output, failure, and retry contracts for every stage.
3. Identify which stages can run in parallel and which require ordered dependencies.
4. Preserve raw input, normalized input, stage output, revision output, and final output separately.
5. Emit real progress events rather than simulated statuses.
6. Record model/provider/version, duration, token usage if available, cost estimate, and failure reason.
7. Make partial failure recoverable without rerunning unnecessary successful stages.
8. Make human review and revision states explicit.
9. Add fixtures and quality baselines for representative inputs.

Efficiency rules:
- Parallelize independent work.
- Avoid passing oversized or duplicated context between stages.
- Use structured summaries instead of repeatedly sending full raw payloads.
- Bound retries at one layer and make retry reasons explicit.
- Add timeouts and cancellation behavior.
- Do not optimize for theoretical scale before measuring real latency and cost.

Audit-trail rules:
- Every stage must have a run ID, stage ID, input reference, output reference, timestamp, status, and error record.
- Never overwrite a previous stage output.
- Revisions must point to the prior version.
- Preserve enough metadata to reproduce or explain a result.

Acceptance criteria:
- [ ] Each stage can be tested independently.
- [ ] Pipeline state is recoverable after interruption.
- [ ] Progress reflects the actual executing stage.
- [ ] Failed stages have actionable errors.
- [ ] Independent stages run concurrently where safe.
- [ ] Cost and latency can be measured per run.
- [ ] Quality is evaluated against fixtures or a rubric.

Use the shared engineering rules above. Prefer small service boundaries in one repository before creating deployed microservices.
```

---

## 5. Authentication and save/resume

Use for accounts, sessions, protected routes, and draft recovery.

```text
Add authentication and save/resume for [FEATURE_NAME] in [PROJECT_PATH].

User problem: [PROBLEM]
Launch stage: [LAUNCH_STAGE]
Identity provider: [IDENTITY_PROVIDER]

Goals:
1. Users can create an account and sign in.
2. Users can save progress automatically.
3. Users can resume the correct project after refresh or returning later.
4. Users cannot access another user’s projects.
5. Expired sessions and failed saves have clear recovery paths.
6. Demo/test access is explicit and cannot bypass production ownership rules.

Security requirements:
- Enforce ownership server-side.
- Do not trust client-provided user IDs or roles.
- Keep secret credentials server-side.
- Define session expiry, logout, password reset, and account deletion behavior.
- Minimize sensitive data in logs.

Acceptance criteria:
- [ ] Unauthenticated users are redirected or rejected appropriately.
- [ ] Authenticated users can create and reopen a project.
- [ ] Draft data survives refresh.
- [ ] Draft save failures are visible.
- [ ] Cross-user access tests fail safely.
- [ ] Session expiry is handled.
- [ ] Account deletion behavior is documented.

Do not implement payment or marketing features in this task. Use the shared engineering rules above.
```

---

## 6. Database and persistence

Use for schema design, migrations, ownership, retention, and auditability.

```text
Design and implement persistence for [FEATURE_NAME] in [PROJECT_PATH].

Entities currently needed:
[LIST_ENTITIES]

Goals:
1. Each record has one clear responsibility.
2. Ownership and authorization are enforceable.
3. Important state changes are auditable.
4. Large files are stored as artifact references rather than database blobs.
5. Records can be deleted or retained according to a documented policy.
6. Migrations are reproducible, reversible where practical, and tested.

Define:
- Entity relationship model
- Primary keys and uniqueness rules
- Foreign keys and deletion behavior
- Status/state fields
- Indexes justified by current queries
- Ownership rules
- Retention and deletion rules
- Migration strategy
- Backup and recovery assumptions

Acceptance criteria:
- [ ] New environment can migrate successfully.
- [ ] Existing data remains compatible.
- [ ] Ownership boundaries are tested.
- [ ] Duplicate records are prevented where required.
- [ ] Important state transitions are auditable.
- [ ] Sensitive data handling is documented.
- [ ] No unused speculative tables or fields are added.

Use the shared engineering rules above. Do not introduce a data warehouse or complex event system without a current need.
```

---

## 7. Payments and paywall

Use for checkout, entitlements, credits, subscriptions, or paid access.

```text
Implement the paid-access flow for [FEATURE_NAME] in [PROJECT_PATH].

Offer:
- Product/package: [PACKAGE]
- Price: [PRICE]
- Included deliverable: [DELIVERABLE]
- Revision/usage limit: [LIMIT]
- Refund policy: [POLICY]

Goals:
1. Users understand what they are buying before payment.
2. Checkout uses a hosted or appropriately secured payment flow.
3. Payment state is confirmed server-side.
4. Duplicate webhook delivery is safe.
5. Entitlements are separate from payment records and generation records.
6. Failed work does not silently consume paid value.
7. Refunds, disputes, and support requests are traceable.

Define the state machines for:
- checkout
- payment
- entitlement/credit
- fulfillment/generation
- refund

Security requirements:
- Never trust browser redirects as payment confirmation.
- Verify webhook signatures.
- Make webhook handling idempotent.
- Keep secret payment credentials server-side.
- Do not expose internal payment identifiers unnecessarily.

Acceptance criteria:
- [ ] Successful payment creates exactly one entitlement.
- [ ] Duplicate webhook does not duplicate entitlement.
- [ ] Abandoned checkout does not grant access.
- [ ] Failed fulfillment is visible and recoverable.
- [ ] Refund behavior is documented and tested.
- [ ] Test-mode purchase completes end to end.

Do not add subscriptions, coupons, affiliate systems, or multiple packages unless they are required for the current launch.
```

---

## 8. Landing page and trust layer

Use for a public-facing website or conversion page.

```text
Create the public landing page for [FEATURE_NAME].

Target user: [USER]
Problem: [PROBLEM]
Offer: [OFFER]
Primary CTA: [CTA]
Success metric: [SUCCESS_METRIC]

Page requirements:
1. Explain the user problem immediately.
2. State who the product is for and who it is not for.
3. Show the outcome and deliverables.
4. Explain the process in plain language.
5. Show proof: sample, testimonial, benchmark, or transparent limitation.
6. Show price, scope, turnaround, revisions, and support expectations.
7. Address trust, privacy, AI assistance, and review responsibility.
8. Provide one primary CTA and a clear next step.
9. Add analytics events for CTA, signup, sample download, checkout start, and conversion.

Copy rules:
- Do not claim capabilities that are not implemented.
- Do not use private customer data without permission.
- Avoid vague superlatives such as “best” or “guaranteed” without proof.
- Match the landing page promise to the paid deliverable.

Acceptance criteria:
- [ ] First-screen purpose is clear.
- [ ] Offer and audience are specific.
- [ ] Proof or limitation is visible.
- [ ] CTA works.
- [ ] Mobile layout works.
- [ ] Accessibility checks pass.
- [ ] Analytics events are testable.

Use the shared engineering rules above. Remove decorative sections that do not improve clarity, trust, or conversion.
```

---

## 9. QA and launch readiness

Use before a beta, public release, or paid launch.

```text
Audit [FEATURE_NAME] in [PROJECT_PATH] for [LAUNCH_STAGE] readiness.

Primary user: [USER]
Intended outcome: [SUCCESS_METRIC]
Known constraints: [CONSTRAINTS]

Review:
1. Core user flow.
2. UI usability and accessibility.
3. API and data contracts.
4. Authentication and authorization.
5. Persistence and recovery.
6. External provider failures.
7. Security and privacy.
8. Observability and supportability.
9. Output quality.
10. Deployment and rollback.
11. Analytics and success measurement.

Classify every finding:
- P0: blocks testing or causes data/security/payment failure.
- P1: materially harms usability, trust, or support burden.
- P2: improvement that can wait until after validation.

For every finding provide:
- evidence with file and line reference where possible
- why it matters
- smallest safe fix
- acceptance test
- dependency

Do not implement fixes unless explicitly requested.

End with:
- launch decision: ready, ready for private beta, or not ready
- exact blockers
- recommended launch sequence
- tests that must pass before release
```

---

## 10. Go-to-market and marketplace launch

Use for service launches, freelancer marketplaces, and early acquisition.

```text
Create a minimum go-to-market plan for [FEATURE_NAME].

Target customer: [USER]
Offer: [OFFER]
Price: [PRICE]
Available proof: [PROOF]
Current channels: [CHANNELS]
Budget: [BUDGET]
Launch stage: [LAUNCH_STAGE]

Goals:
1. Choose one beachhead audience.
2. Choose one offer and one primary CTA.
3. Select the smallest number of channels needed to validate demand.
4. Define a 30-day outreach/content schedule.
5. Define marketplace positioning and profile identity.
6. Define metrics for lead quality, conversion, delivery, and satisfaction.
7. Define when paid advertising becomes justified.

Channel rules:
- Start with the channel where high-intent buyers already search.
- Prefer direct outreach, partnerships, and marketplaces before broad paid ads.
- Do not automate social content before the offer and proof are validated.
- Do not open multiple brand accounts without a clear audience and content plan.
- Keep seller identity, website identity, invoices, contracts, and checkout consistent.

Deliver:
- audience recommendation
- offer and positioning
- marketplace sequence
- profile/gig copy
- 30-day schedule
- outreach scripts
- funnel metrics
- ad-readiness checklist
- assumptions and risks
```

---

## Recommended multi-chat sequence

Use the templates in this order for most product launches:

1. Repository and feature discovery
2. Agent/workflow or core architecture
3. API/backend reliability
4. UI feature and intake flow
5. Authentication and save/resume
6. Database and persistence
7. Landing page and trust layer
8. Payments and paywall
9. QA and launch readiness
10. Go-to-market and marketplace launch

For a private usability beta, steps 1–4 may be sufficient if the product is invite-only and manually operated. For a public paid launch, steps 5–10 should be completed or explicitly accepted as launch risks.

The goal is not to maximize architecture, automation, or channel count. The goal is to create a small, observable system that can reliably deliver the promised user outcome and produce evidence for the next decision.
