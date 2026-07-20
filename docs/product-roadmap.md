# Business Plan Writer Product Roadmap

Version: roadmap-v0.1
Last reviewed: 2026-07-03
Current product rating: 4/10
Target launch-readiness rating: 8/10

This document is the product roadmap source of truth. Treat it like version control for product maturity: every meaningful feature, launch decision, scope change, and completed milestone should be reflected here.

## Product Thesis

Business Plan Writer should become a funding-ready business plan creation service for founders who do not want to learn planning software or pay $1,500+ for a traditional consultant.

The strongest positioning is not "AI business plan generator." The stronger wedge is:

> Lender-ready business plans with guided intake, financial credibility checks, professional DOCX/PDF export, and included revision passes.

The product should compete upward against expensive human writing services, not downward against cheap planning templates.

## Target Customer

Primary buyer:
- Early-stage founder or small business owner who needs a business plan for a lender, grant, investor, partner, franchise application, or internal planning.
- Has enough business context to answer guided questions, but does not know how to turn that context into a professional document.
- Values speed, confidence, and formatting more than learning a full planning platform.

Initial beachhead candidates:
- SBA loan applicants
- Grant applicants
- Daycare and childcare businesses
- Med spas and wellness clinics
- Food trucks and restaurants
- Home care and healthcare services
- Trucking, cleaning, landscaping, and construction businesses
- Nonprofits seeking grants

## Scorecard

| Area | Current | 8/10 Target | Notes |
|---|---:|---:|---|
| Core generation reliability | 4 | 8 | Backend/model config and job reliability must be dependable. |
| Output quality | 5 | 8 | Strong skeleton exists; needs quality baselines and industry modes. |
| User experience | 3 | 8 | Current UI feels internal; paid product needs guided onboarding. |
| Trust and positioning | 3 | 8 | Needs sample plans, guarantees, disclaimers, privacy language. |
| Monetization readiness | 1 | 8 | Needs Stripe, packages, account/project lifecycle. |
| Operational readiness | 4 | 8 | Needs run monitoring, support flow, cost controls, QA checklist. |
| Market validation | 3 | 8 | Needs beta users, conversion data, willingness-to-pay proof. |

## Status Legend

| Status | Meaning |
|---|---|
| Planned | Accepted into roadmap but not started. |
| In Progress | Actively being designed, implemented, tested, or validated. |
| Blocked | Cannot proceed until a dependency is resolved. |
| Shipped | Completed, verified, and available in the product or docs. |
| Cut | Intentionally removed from scope. |
| Watch | Useful idea, but not committed yet. |

## Roadmap Rules

1. Update this file when a feature meaningfully changes product maturity.
2. Do not mark an item Shipped until it is implemented and verified.
3. Add acceptance criteria before starting larger features.
4. If scope changes, record the decision in the Decision Log.
5. If a feature ships, add the date and link to the implementation commit or doc when available.
6. Keep the 8/10 launch target focused. Do not let 10/10 polish block paid validation.

## Now: 4/10 to 5/10 - Make The Core Product Work Reliably

Goal: a user can generate a plan without developer intervention, and failures are understandable.

| ID | Initiative | Status | Priority | Acceptance Criteria |
|---|---|---|---|---|
| R-001 | Connect frontend Generate Plan flow to working backend in dev/prod | Planned | Must | Button starts a run, receives a run ID, polls status, and renders the result. |
| R-002 | Configure production-ready model environment variables | Planned | Must | Anthropic/OpenAI/Groq provider and writer model settings are documented and validated at startup. |
| R-003 | Add user-facing API/model error states | Planned | Must | Missing key, backend offline, timeout, failed run, and malformed response show clear UI messages. |
| R-004 | Show five-agent progress states in the UI | Planned | Must | User sees validation, market, financials, draft, and review progress. |
| R-005 | Persist runs and allow refresh recovery | Planned | Must | Refreshing during or after generation does not lose the run. |
| R-006 | Add run history for drafts, exports, critic report, and timestamps | Planned | Should | User can revisit prior generated plans. |
| R-007 | Add job-level retry controls and cost caps | Planned | Must | Failed transient jobs can retry within a bounded cost/retry limit. |
| R-008 | Add backend health check and frontend unavailable state | Planned | Should | Frontend can distinguish service outage from user/input errors. |
| R-009 | Verify DOCX/PDF export reliability | Planned | Must | Every successful run produces valid export links or a clear export failure. |
| R-010 | Add happy-path pipeline test | Planned | Must | Automated test covers intake -> generation job -> result payload shape. |
| R-011 | Add failure-mode tests | Planned | Should | Missing API key, failed model call, invalid JSON, and export failure are covered. |

5/10 exit criteria:
- A full sample run succeeds end to end.
- The user sees progress and a usable result.
- Known failure modes produce clear messages.
- Exports work or fail visibly.

## Next: 5/10 to 6/10 - Make The Output Good Enough To Show

Goal: the generated plan is specific, credible, and reviewable.

| ID | Initiative | Status | Priority | Acceptance Criteria |
|---|---|---|---|---|
| Q-001 | Build 5-10 gold-standard sample plans | Planned | Must | Sample plans exist for key niches and set expected quality. |
| Q-002 | Create output quality rubric | Planned | Must | Plans are scored for specificity, completeness, financial credibility, formatting, and readiness. |
| Q-003 | Tighten Agent 4 writing prompts | Planned | Must | Output consistently avoids generic filler and follows lender-ready structure. |
| Q-004 | Add industry-specific writer modes | Planned | Should | At least 3 high-value niches have tailored prompt behavior. |
| Q-005 | Strengthen financial projection output | Planned | Must | Plan includes startup costs, monthly revenue, expenses, break-even, and cash-flow narrative. |
| Q-006 | Enforce intake readiness gate | Planned | Must | Critical missing fields trigger guided follow-up before generation. |
| Q-007 | Add funding-readiness score | Planned | Should | User sees completeness, financial credibility, and review-risk indicators. |
| Q-008 | Add revision modes | Planned | Must | User can request common revisions: more formal, shorter, lender-ready, more financial detail, grant-oriented. |
| Q-009 | Store before/after revisions | Planned | Should | User can compare or recover prior drafts. |
| Q-010 | Polish DOCX/PDF formatting | Planned | Must | Export includes cover page, clean headings, page breaks, and readable tables. |
| Q-011 | Publish example downloadable plan | Shipped | Should | Marketing/product can point to a realistic sample output. |

6/10 exit criteria:
- Generated sample plans score 7/10 or higher on the quality rubric.
- Human reviewer would feel comfortable showing at least one sample publicly.
- Revisions materially improve output.

## Next: 6/10 to 7/10 - Make It Feel Like A Paid Product

Goal: a customer can buy, complete intake, generate, revise, and download without hand-holding.

| ID | Initiative | Status | Priority | Acceptance Criteria |
|---|---|---|---|---|
| P-001 | Replace raw form with guided onboarding | Planned | Must | Intake is split into clear steps with progress and save behavior. |
| P-002 | Add examples and helper text for hard questions | Planned | Must | Users understand what good answers look like. |
| P-003 | Add "I do not know" answer paths | Planned | Should | Unknown answers can be inferred, skipped, or flagged without blocking unnecessarily. |
| P-004 | Add account creation and login | Planned | Must | Users can own projects and return later. |
| P-005 | Add Stripe checkout | Implemented | Must | User can purchase the single public-beta offer before generation. |
| P-006 | Add package definition | Implemented | Must | The Funding-Focused one-time offer is the only in-product package. |
| P-007 | Add post-payment project dashboard | Planned | Must | User sees purchased plan, status, exports, and revisions. |
| P-008 | Add revision counter | Implemented | Should | Two included revision passes are tracked and enforced. |
| P-009 | Add terms, disclaimers, and privacy language | In Progress | Must | Public beta page states AI-assisted nature, no legal/financial advice, privacy limits, and user review responsibility; formal terms and retention policy remain. |
| P-010 | Add support contact path | Implemented | Must | Customer support/refund requests are idempotent and linked to payments or runs. |
| P-011 | Add email notifications | Planned | Should | User receives draft-ready and export-ready notifications. |
| P-012 | Polish responsive UI states | Planned | Must | Empty, loading, failed, mobile, and success states look intentional. |

7/10 exit criteria:
- A user can pay and receive a usable deliverable.
- The product feels credible enough to charge for.
- Support and revision expectations are visible before purchase.

## Next: 7/10 to 8/10 - Prove It Can Launch

Goal: validate one niche and prove the product can sell, deliver, and support real customers.

| ID | Initiative | Status | Priority | Acceptance Criteria |
|---|---|---|---|---|
| L-001 | Choose first beachhead niche | Shipped | Must | One niche is selected and all near-term messaging targets it. |
| L-002 | Create niche landing page | Shipped | Must | Page explains problem, fit, offer, deliverables, price, limitations, process, human review, and next step. |
| L-003 | Define launch offer | Shipped | Must | Price, revision count, turnaround promise, refund policy, and scope limits are documented. |
| L-004 | Add sample screenshots or output preview | Shipped | Must | Public page includes representative previews and downloadable fictional DOCX/PDF files. |
| L-005 | Run 10 beta customers through the flow | Planned | Must | At least 10 real users complete intake or attempt to. |
| L-006 | Measure funnel analytics | In Progress | Must | CTA click, account start, and sample download hooks are implemented; checkout and lifecycle conversion tracking remain. |
| L-007 | Measure support burden | Planned | Must | Average support time per customer is known. |
| L-008 | Measure model cost per completed plan | Planned | Must | Cost per plan includes retries and revisions. |
| L-009 | Collect user quality ratings | Planned | Must | Users rate output usefulness and whether they would send it to a lender/investor/grant reviewer. |
| L-010 | Add internal QA checklist | Planned | Must | First paid outputs are reviewed against a consistent checklist before delivery if needed. |
| L-011 | Build admin inspection tools | Planned | Should | Failed runs and customer projects can be inspected without database spelunking. |
| L-012 | Document common failure modes | Planned | Should | Top issues and fixes are tracked for product improvement. |

8/10 exit criteria:
- A stranger can pay without help.
- A stranger can complete intake without help.
- Generation succeeds at least 95% of the time.
- Final DOCX/PDF looks professional.
- Average model cost is known and controlled.
- Average support burden is manageable.
- At least 7 of 10 beta users say the output is useful.
- At least 3 beta users say they would have paid.
- One niche landing page has a clear offer.
- Legal, privacy, and disclaimer basics are in place.

## Later: 8/10 to 10/10 - Scale, Moat, And Expansion

These are intentionally not required for the 8/10 launch threshold.

| ID | Initiative | Status | Priority | Notes |
|---|---|---|---|---|
| S-001 | Pitch deck generation | Watch | Could | Useful expansion after plan quality is proven. |
| S-002 | Financial spreadsheet export | Watch | Should | Strong upsell and lender-facing value. |
| S-003 | Lender-specific formats | Watch | Should | Helps niche positioning and conversion. |
| S-004 | Grant-specific formats | Watch | Should | Important if grant applicants become the beachhead. |
| S-005 | Industry benchmark data | Watch | Could | Adds credibility but requires sourcing discipline. |
| S-006 | Market research citations | Watch | Should | Strong trust layer; may increase cost/complexity. |
| S-007 | Human expert review marketplace | Watch | Could | Converts AI tool into service platform. |
| S-008 | Advisor/accountant collaboration | Watch | Could | Useful for higher-ticket packages. |
| S-009 | Version comparison between revisions | Watch | Could | Product polish for serious users. |
| S-010 | Funding readiness checklist | Watch | Should | Low-friction trust and upsell surface. |
| S-011 | Abandoned intake recovery | Watch | Should | Revenue recovery once traffic exists. |
| S-012 | Affiliate/referral program | Watch | Could | Useful after offer conversion is proven. |
| S-013 | Niche SEO pages | Watch | Should | Main distribution lever after beachhead proof. |
| S-014 | White-label consultant/accountant version | Watch | Could | Potential B2B channel. |
| S-015 | Partner offers for LLC, bookkeeping, payroll, lending | Watch | Could | Monetization expansion after trust exists. |

## Public Beta Launch Offer

The earlier $149–$1,497 multi-tier software/package hypotheses are superseded for the first-customer validation window. The current launch tests one professional service:

| Offer | Price | Included |
|---|---:|---|
| Funding-Focused Business Plan Service | $750 | Structured intake, funding-focused plan, three-year projection summary based on customer inputs, human review, DOCX/PDF, seven-day delivery after complete intake, and two revision rounds. |

Independent market research, a custom spreadsheet, legal/accounting advice, and financing approval are not included. Cancellation and refund terms are documented in `docs/launch-playbook.md` and `FIVERR-GIG.md`.

No subscription, alternate tier, add-on ladder, coupon, or upgrade path is supported in this release.

## Key Product Metrics

| Metric | Target By 8/10 | Why It Matters |
|---|---:|---|
| Generation success rate | 95%+ | Trust and support burden. |
| Intake completion rate | 60%+ | Measures whether onboarding is understandable. |
| Paid conversion rate | TBD after traffic | Measures offer strength. |
| Average model cost per completed plan | <$10 | Confirms margin even with revisions. |
| Average support time per customer | <30 minutes | Confirms operational viability. |
| Output usefulness score | 7/10+ | Measures whether users trust the deliverable. |
| Refund rate | <10% early, lower over time | Measures quality and expectation fit. |
| Export download rate | 80%+ | Confirms users reach the deliverable. |

## Current Known Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Generic AI output reduces trust | High | Quality rubric, critic step, industry modes, human review option. |
| Users provide weak intake | High | Guided examples, readiness gate, follow-up questions, "I do not know" paths. |
| $750 price feels high before public proof exists | Medium | Position as a human-reviewed professional service, show the fictional sample, and validate willingness to pay before changing price. |
| Liability around funding/financial claims | High | Disclaimers, user review, conservative prompts, optional expert review. |
| Backend/model failures hurt confidence | High | Progress states, retries, clear errors, monitoring, admin tooling. |
| Support burden eats margin | Medium | Better onboarding, QA checklist, revision templates, scoped packages. |
| Competitors copy basic AI generation | Medium | Differentiate through workflow, trust, niche expertise, examples, distribution. |

## Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-07-03 | Treat this document as the roadmap source of truth. | Product maturity needs a single updateable artifact. |
| 2026-07-03 | Use 8/10 as the pre-launch readiness target. | 10/10 polish should not block market validation. |
| 2026-07-03 | Position against business plan writing services, not cheap AI generators. | The product has better margin and perceived value as a funding-ready package. |
| 2026-07-19 | Supersede the earlier lower-price hypothesis with one $750 Funding-Focused validation offer. | Keep checkout, landing-page copy, delivery, and support scope operationally consistent. |
| 2026-07-19 | Focus the private-beta landing page on operating local-service-business owners seeking expansion financing. | A narrow funding conversation makes the problem, fit, sample, and offer easier to evaluate without implying unsupported research or approval. |
| 2026-07-19 | Use Business Plan Writer publicly, with Ben Hankins as the named practitioner; keep Sproutflow out of launch messaging except where it is the actual legal payee. | The buyer needs one descriptive service identity and one accountable human, not three competing names. |
| 2026-07-19 | Target owners of operating US local service businesses preparing for SBA-backed or conventional expansion financing. | This buyer has a specific job-to-be-done and is more likely than an idea-stage founder to have usable operating and financial inputs. |
| 2026-07-19 | Validate one $750 Funding-Focused Business Plan Service with seven-day delivery after complete intake and two revision rounds. | One fixed offer makes early conversion, labor, quality, and willingness-to-pay data interpretable. See `docs/launch-playbook.md`. |
| 2026-07-19 | Do not market sourced or independent research in the validation offer. | Market research citations remain a future roadmap item; public claims must match current capability and delivered scope. |

## Update Template

When a feature ships, update the relevant row and add a note here:

| Date | Feature ID | Change | Evidence |
|---|---|---|---|
| YYYY-MM-DD | R-000 | Marked Shipped / changed scope / cut | Commit, test, screenshot, customer result, or doc link. |
| 2026-07-19 | L-001, L-002, L-004, Q-011 | Shipped niche landing page and fictional sample; moved trust, support, offer policy, and analytics items to In Progress where operational work remains. | `web/app/page.tsx`, public sample DOCX/PDF, production build, automated accessibility check, and marketing contract tests. |
