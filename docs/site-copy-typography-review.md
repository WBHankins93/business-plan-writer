# Website copy, typography, and buyer-confidence review

Date: July 20, 2026

Scope: public marketing page, account entry points, saved-plan experience, and intake workspace. The assessment is a heuristic conversion and usability review, not measured buyer research. Confidence scores should be validated with qualified-buyer interviews and funnel data.

## Executive assessment

The original site had a credible offer underneath a demanding presentation. Its strongest assets were specificity, a fixed price, a downloadable sample, a named human reviewer, and honest limitations. Its biggest weaknesses were an oversized slab-serif hierarchy, small supporting text, repetitive left-anchored sections, product-mechanism language, and policy copy that asked buyers to process risk before they had absorbed the value.

### Buyer-confidence score

| Dimension | Before | After this revision | Rationale |
| --- | ---: | ---: | --- |
| Offer clarity | 6.5/10 | 8.5/10 | Audience, outcome, price, delivery timing, revisions, and CTA now appear together above the fold. |
| Readability | 6/10 | 8.5/10 | Smaller display type, larger body copy, calmer line lengths, more spacing, and a screen-first font system reduce effort. |
| Trust | 6.5/10 | 7.8/10 | Human review, assumptions, file ownership, and scope are visible earlier. Trust is still limited by missing independent proof and formal policies. |
| Purchase confidence | 6/10 | 8/10 | “Check fit” lowers commitment anxiety, the sample is framed as evidence, and key terms remain visible while detailed policy is progressively disclosed. |
| Overall | **6.3/10** | **8.2/10** | The page now feels like a focused professional service instead of an AI workflow looking for a buyer. |

The revised score is intentionally below 9/10. No typography or copy change can replace customer proof, a published privacy/retention policy, clear legal seller details, a direct support address, and demonstrated outcomes.

## What attracts qualified buyers

- A narrow audience: operating US local service businesses seeking expansion financing.
- A concrete outcome: a lender-reviewable business-plan draft, not generic “strategy.”
- A fixed $750 fee, seven-day delivery window, and two revision rounds.
- A named person who reviews and edits the work before delivery.
- A downloadable sample that lets buyers inspect the deliverable.
- Clear exclusions and no financing guarantee. Boundaries build trust when they follow a clear value proposition.
- Editable files and visible assumptions, which give the buyer control over high-stakes content.

## Wording that reduced confidence

| Original pattern | Why it hurt | Revision principle |
| --- | --- | --- |
| “Private beta” as the first hero message | Made a $750 buyer feel like a tester before they understood the value. | Lead with who the service is for; keep beta context in account areas where it is operationally relevant. |
| “Five-agent process” and “Five-agent desk” | Centered implementation machinery and amplified AI risk. | Describe checks, progress, and human accountability in buyer language. |
| “Fixed validation price” | “Validation” was ambiguous: validation of the service, business, or plan? | Say “$750 fixed fee for one expansion plan.” |
| “Start fit and intake” | Grammatically awkward and vague about the action. | Use the consistent, lower-risk CTA “Check fit and start intake.” |
| “A fictional plan, shown without borrowed proof” | Clever but required interpretation and led with a disclaimer. | Invite inspection: “See what complete looks like before you begin.” |
| “Clear boundaries make the plan more useful” | Reasonable, but defensive as the main trust headline. | Frame the section as a plain-language commitment and state capability limits directly. |
| Dense delivery/refund paragraphs | Visually overwhelmed the pricing decision and made edge cases feel primary. | Keep delivery, revisions, and fit visible; place full terms in an explicit disclosure. |
| “Queueing,” “Agents working,” and “workflow” in the intake | Exposed system state instead of reassuring the customer about progress. | Use “Starting,” “Creating your draft,” and named quality checks. |

## Typography research

The useful pattern among leading B2C brands is not one universal “selling font.” It is a flexible, legible core type system with enough proprietary or display character to be recognizable:

- Airbnb introduced Cereal across product and brand around “character, function, and scale,” creating consistency across platforms ([Airbnb design case study](https://medium.com/airbnb-design/working-type-81294544608b)).
- Netflix Sans was designed to work from billboards down to subtitle-scale text, unifying expressive marketing and practical UI needs ([Dalton Maag case study](https://www.daltonmaag.com/portfolio/custom-fonts/netflix-sans.html)).
- Apple uses SF Pro as its system font and provides optical/variable behavior across device contexts, prioritizing legibility and consistency ([Apple typography guidance](https://developer.apple.com/design/human-interface-guidelines/typography)).
- Google found that its geometric display face needed taller, more open, more widely spaced text forms at small sizes; its newer variable system uses optical sizing to preserve both personality and legibility ([Google Sans case study](https://design.google/library/google-sans-flex-font)).
- Spotify replaced its prior system with the bespoke Spotify Mix to unify marketing and product expression, reinforcing the value of an ownable but scalable family ([Spotify Mix launch coverage](https://www.itsnicethat.com/articles/spotify-dinamo-new-typeface-spotify-mix-project-230524)).

The implication for this service is to borrow the strategy, not proprietary letterforms. A business-plan service needs calm UI reading plus a restrained editorial signal that connects the site to the document being purchased.

### Selected type system

- **DM Sans** for body copy, navigation, controls, and labels. It is friendly and contemporary without making paragraphs feel decorative. Using a variable family creates consistent weight and scale across marketing and product screens.
- **Newsreader** for major headings and document-preview titles. Production Type designed it for continuous on-screen reading in content-rich environments, making it a more relevant editorial signal than the previous locally dependent Rockwell stack ([Newsreader project](https://github.com/productiontype/Newsreader)).
- Both families are loaded through Next.js font tooling, which self-hosts the generated font assets and avoids layout dependence on whatever fonts happen to be installed on a visitor’s computer.

Font choice alone does not create conversion. The high-impact improvements are the combined system: moderate headline scale, open line height, clear weight contrast, short line lengths, progressive disclosure, and limited use of the display face.

## Readability and layout decisions

W3C guidance explains why long lines and tight leading can be barriers for people with low vision or cognitive disabilities; its visual-presentation guidance references lines no wider than 80 characters and line spacing of at least 1.5 as useful adaptable presentation targets ([W3C visual presentation guidance](https://www.w3.org/WAI/WCAG22/Understanding/visual-presentation.html)). WCAG AA also requires 4.5:1 contrast for ordinary text ([W3C contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)).

Implemented changes:

- Reduced the maximum hero scale and balanced headline wrapping.
- Increased body and support-copy sizes and preserved 1.5–1.7 line heights.
- Kept paragraph measures constrained rather than stretching text across containers.
- Removed decorative numbers from the three deliverables because they are not sequential.
- Retained numbers only for the five-step process, where order carries meaning.
- Added visible “terms at a glance” and placed full policy text in a keyboard-accessible disclosure.
- Added a three-part commitment strip immediately after the hero.
- Varied desktop section composition: left-led fit and process, centered deliverables, a right-side sample narrative, right-aligned trust framing, and a centered final CTA.
- Returned headings to left alignment on mobile, where a predictable reading edge is easier to scan.
- Preserved large touch targets, keyboard focus, reduced-motion behavior, responsive reflow, and semantic heading order.

## Retention-oriented language

Retention starts before purchase when expectations match delivery. The revised language reduces later disappointment by stating the niche, input requirements, revision format, timing trigger, and service limits before commitment.

Inside the product, the language now:

- calls saved work “plans” consistently;
- explains that answers save automatically;
- describes progress as plan-quality checks rather than agent activity;
- distinguishes an AI-assisted draft from Ben’s reviewed customer delivery;
- uses “Create business plan draft” so the action and result match;
- keeps error and retry language concrete; and
- preserves buyer control through editable exports and visible review notes.

## Remaining trust work

These should be implemented only when the underlying evidence or policy exists:

1. Publish an About/contact block with Ben’s relevant credentials, location or service jurisdiction, and a monitored support address.
2. Publish formal privacy, retention, deletion, terms, and refund pages before taking direct payment.
3. Add verified customer reviews, attributed case studies, or aggregate outcome data after explicit permission. Do not substitute fictional proof.
4. Explain security and data handling in plain language once the actual storage, subprocessors, retention, and deletion behavior are finalized.
5. Add a short post-delivery feedback loop and track qualified-start, intake-completion, sample-download, purchase, revision, refund, and referral rates.
6. Run five qualified-buyer comprehension interviews. Ask each person to state the audience, deliverable, price, timing, next step, and primary risk after a five-second and thirty-second scan.

## Recommended measurement

Treat this revision as a conversion hypothesis. Compare at least:

- hero CTA click-through;
- sample download rate;
- qualified intake starts;
- completion rate by intake step;
- time to complete intake;
- purchase conversion among qualified starts;
- support questions about scope, timing, revisions, and AI;
- revision volume and reasons;
- refund rate; and
- post-delivery usefulness, confidence, and referral intent.

The most important qualitative signal is whether buyers describe the service as “a human-reviewed business-plan service that uses software” rather than “an AI business-plan generator.”
