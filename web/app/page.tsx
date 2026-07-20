import { AnalyticsLink, type AnalyticsEvent } from "./components/AnalyticsLink";

const accountStartUrl = process.env.NEXT_PUBLIC_ACCOUNT_START_URL || "/demo";

const accountEvents = (location: string): AnalyticsEvent[] => [
  {
    name: "cta_click" as const,
    properties: {
      cta_name: "start_demo_intake",
      cta_location: location,
      destination: accountStartUrl,
    },
  },
  {
    name: "account_start" as const,
    properties: { entry_point: location, destination: accountStartUrl },
  },
];

const sampleEvents = (location: string, format: "pdf" | "docx"): AnalyticsEvent[] => [
  {
    name: "sample_download" as const,
    properties: {
      sample_name: "bywater_grounds",
      file_format: format,
      download_location: location,
    },
  },
];

const processSteps = [
  {
    title: "Share your starting point",
    body: "A guided intake captures your operating history, offer, funding request, and forecast assumptions.",
  },
  {
    title: "Close the important gaps",
    body: "A readiness check flags missing answers and thin details before they turn into vague sections.",
  },
  {
    title: "Shape the business case",
    body: "Your customer, competition, positioning, and path to revenue are organized around the evidence you provide.",
  },
  {
    title: "Pressure-test the numbers",
    body: "Revenue, expenses, cash flow, break-even timing, and funding use are checked for internal consistency.",
  },
  {
    title: "Draft, review, and refine",
    body: "The workflow builds the draft and flags weak claims. Ben then reviews every section before delivery.",
  },
];

export default function MarketingPage() {
  return (
    <div className="marketingShell">
      <a className="skipLink" href="#main-content">Skip to content</a>

      <header className="marketingHeader">
        <a className="brand" href="#top" aria-label="Business Plan Writer home">
          <span className="brandMark" aria-hidden="true">BP</span>
          <span>Business Plan Writer <small>Delivered by Ben Hankins</small></span>
        </a>
        <nav aria-label="Primary navigation">
          <a href="#sample">Sample</a>
          <a href="#process">Process</a>
          <a href="#pricing">Pricing</a>
          <a href="#trust">Trust</a>
        </nav>
        <AnalyticsLink
          className="headerCta"
          href={accountStartUrl}
          events={accountEvents("header")}
        >
          Check fit
        </AnalyticsLink>
      </header>

      <main id="main-content">
        <section className="marketingHero" id="top" aria-labelledby="hero-title">
          <div className="heroMessage">
            <p className="marketingEyebrow">For established local service businesses</p>
            <h1 id="hero-title">A business plan built to stand up to lender questions.</h1>
            <p className="heroLead">
              Turn your operating history, funding request, and forecast assumptions into a
              human-reviewed plan for SBA-backed or conventional expansion financing.
            </p>
            <div className="heroActions">
              <AnalyticsLink
                className="primaryAction"
                href={accountStartUrl}
                events={accountEvents("hero")}
              >
                Check fit and start intake
                <span aria-hidden="true">→</span>
              </AnalyticsLink>
              <AnalyticsLink
                className="textAction"
                href="/samples/bywater-grounds-sample-plan.pdf"
                events={sampleEvents("hero", "pdf")}
                download
              >
                Review a fictional sample
                <span aria-hidden="true">↓</span>
              </AnalyticsLink>
            </div>
            <p className="heroNote">Explore the intake before you commit. No payment is collected on this page.</p>
            <ul className="offerFacts" aria-label="Offer summary">
              <li><strong>$750 fixed fee</strong><span>for one expansion plan</span></li>
              <li><strong>7-day delivery</strong><span>after complete intake is accepted</span></li>
              <li><strong>2 revision rounds</strong><span>submitted as consolidated feedback</span></li>
            </ul>
          </div>

          <div className="planArtifact" aria-label="Representative business plan preview">
            <div className="artifactTab">Representative output</div>
            <article className="paperPreview">
              <header>
                <span>BUSINESS PLAN</span>
                <small>Fictional sample · 2026</small>
              </header>
              <h2>Bywater Grounds<br />Coffee House</h2>
              <p className="paperPurpose">SBA 7(a) funding request</p>
              <div className="paperRule" />
              <dl>
                <div><dt>Funding request</dt><dd>$285,000</dd></div>
                <div><dt>Owner contribution</dt><dd>$57,000</dd></div>
                <div><dt>Break-even target</dt><dd>Month 7</dd></div>
              </dl>
              <div className="credibilityNote">
                <span aria-hidden="true">✓</span>
                <p><strong>Consistency check</strong>Funding use, monthly revenue, and break-even assumptions are connected.</p>
              </div>
              <footer>Prepared from owner-supplied fictional information</footer>
            </article>
          </div>
        </section>

        <section className="trustStrip" aria-label="Service commitments">
          <div><strong>Personally reviewed</strong><span>Ben reviews and edits every plan before delivery.</span></div>
          <div><strong>Assumptions made visible</strong><span>Gaps and unsupported claims are flagged for your review.</span></div>
          <div><strong>Files you control</strong><span>Receive an editable DOCX and a shareable PDF.</span></div>
        </section>

        <section className="fitSection" aria-labelledby="fit-title">
          <div>
            <p className="sectionLabel">Who this is for</p>
            <h2 id="fit-title">Designed for businesses with a track record.</h2>
          </div>
          <div className="fitColumns">
            <div>
              <h3>A strong fit</h3>
              <ul className="fitList">
                <li>You operate a US local service business.</li>
                <li>You are seeking financing for a defined expansion.</li>
                <li>You can share operating history and forecast assumptions.</li>
              </ul>
            </div>
            <div>
              <h3>Better served elsewhere</h3>
              <ul className="fitList fitListMuted">
                <li>You are still validating an idea or have no operating history.</li>
                <li>You need audited projections or independent market research.</li>
                <li>You need legal, tax, lending, or approval advice.</li>
              </ul>
            </div>
          </div>
        </section>

        <section className="deliverablesSection" aria-labelledby="deliverables-title">
          <div className="sectionHeading sectionHeadingCentered">
            <p className="sectionLabel">What you receive</p>
            <h2 id="deliverables-title">One plan. Three layers of confidence.</h2>
            <p>Your information is organized, checked for consistency, and reviewed by a person before it becomes a document you control.</p>
          </div>
          <div className="deliverablesGrid">
            <article>
              <span>Structure</span>
              <h3>A clear case for expansion</h3>
              <p>Executive summary, company and market context, offer, operations, management, funding use, risks, milestones, and financial narrative.</p>
            </article>
            <article>
              <span>Checks</span>
              <h3>Numbers that tell one story</h3>
              <p>Consistency checks flag gaps across revenue, expenses, cash flow, break-even timing, and the amount requested.</p>
            </article>
            <article>
              <span>Review</span>
              <h3>A person on the final pass</h3>
              <p>Ben reviews and edits the draft before you receive an editable DOCX and shareable PDF.</p>
            </article>
          </div>
        </section>

        <section className="sampleSection" id="sample" aria-labelledby="sample-title">
          <div className="sampleCopy">
            <p className="sectionLabel">Inspect the work first</p>
            <h2 id="sample-title">See what “complete” looks like before you begin.</h2>
            <p>Bywater Grounds Coffee House is fictional. The sample shows the structure, depth, financial tables, and review notes you can expect—without presenting made-up results as customer proof.</p>
            <div className="sampleActions">
              <AnalyticsLink
                className="primaryAction"
                href="/samples/bywater-grounds-sample-plan.pdf"
                events={sampleEvents("sample_section", "pdf")}
                download
              >
                Download sample PDF
                <span aria-hidden="true">↓</span>
              </AnalyticsLink>
              <AnalyticsLink
                className="textAction"
                href="/samples/bywater-grounds-sample-plan.docx"
                events={sampleEvents("sample_section", "docx")}
                download
              >
                Download editable DOCX
              </AnalyticsLink>
            </div>
          </div>
          <div className="samplePages" aria-hidden="true">
            <div className="samplePage samplePageBack">
              <span>06</span>
              <h3>Funding use</h3>
              <div className="miniTable"><i /><i /><i /><i /></div>
            </div>
            <div className="samplePage samplePageFront">
              <span>04</span>
              <h3>Financial plan</h3>
              <div className="miniChart"><i /><i /><i /><i /><i /></div>
              <p>Revenue grows with daily transactions while fixed costs remain visible in the cash-flow narrative.</p>
            </div>
          </div>
        </section>

        <section className="processSection" id="process" aria-labelledby="process-title">
          <div className="sectionHeading processHeading">
            <p className="sectionLabel">How your plan is built</p>
            <h2 id="process-title">Five quality passes. One accountable reviewer.</h2>
            <p>Software helps organize and check the work. Ben reviews and edits the final deliverable; your lender, accountant, attorney, and advisors remain the experts for their decisions.</p>
          </div>
          <ol className="processList">
            {processSteps.map((step, index) => (
              <li key={step.title}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div><h3>{step.title}</h3><p>{step.body}</p></div>
              </li>
            ))}
          </ol>
        </section>

        <section className="pricingSection" id="pricing" aria-labelledby="pricing-title">
          <div className="pricingIntro">
            <p className="sectionLabel">Transparent pricing</p>
            <h2 id="pricing-title">One complete plan. One fixed fee.</h2>
            <p>For one operating local service business and one expansion-financing goal.</p>
            <div className="price"><strong>$750</strong><span>fixed fee</span></div>
          </div>
          <div className="packageDetails">
            <h3>Funding-focused business plan service</h3>
            <ul>
              <li>Guided intake and readiness check</li>
              <li>Five focused quality checks</li>
              <li>Three-year projection summary based on your inputs</li>
              <li>Human editorial and consistency review by Ben</li>
              <li>DOCX and PDF delivery</li>
              <li>Two consolidated revision rounds</li>
            </ul>
            <div className="termsAtGlance" aria-label="Terms at a glance">
              <span>7-day delivery</span><span>2 revision rounds</span><span>Fit confirmed first</span>
            </div>
            <details className="expectationNote">
              <summary>Delivery, revisions, and refunds</summary>
              <p>No payment is collected on this page. Delivery is seven calendar days after Ben accepts the intake as complete. Two consolidated revision rounds are included; each is one list submitted within seven days of delivery. Revisions refine the agreed plan. A new concept, audience, material data set, or custom analysis is new scope.</p>
              <p>Fit is confirmed before work is accepted. A pre-acceptance scope mismatch or inability to deliver the agreed scope is canceled and refunded. After the first complete draft, a change of mind, business direction, or financing denial is not refundable; the included revisions cover in-scope corrections.</p>
            </details>
            <AnalyticsLink
              className="primaryAction packageAction"
              href={accountStartUrl}
              events={accountEvents("pricing")}
            >
              Check fit and start intake
              <span aria-hidden="true">→</span>
            </AnalyticsLink>
          </div>
        </section>

        <section className="trustSection" id="trust" aria-labelledby="trust-title">
          <div className="sectionHeading trustHeading">
            <p className="sectionLabel">Plain-language commitments</p>
            <h2 id="trust-title">Know what the service can—and cannot—do.</h2>
          </div>
          <div className="trustGrid">
            <article id="disclaimer">
              <h3>A person reviews every plan</h3>
              <p>Software supports drafting and quality checks, then the plan is personally reviewed and edited by Ben Hankins before delivery. You should review every fact, assumption, and projection before sharing it.</p>
              <p>This is planning support—not legal, tax, accounting, investment, or lending advice. It does not guarantee financing or lender acceptance.</p>
            </article>
            <article id="privacy">
              <h3>Only share what the plan needs</h3>
              <p>Do not submit Social Security numbers, bank or card numbers, passwords, medical records, or other sensitive personal data.</p>
              <p>During beta, intake content is used to generate and deliver your plan and support the service. A formal retention schedule is not yet published; you can request deletion through your beta invitation.</p>
            </article>
            <article id="support">
              <h3>Support has a clear path</h3>
              <p>Reply to your private-beta invitation for access help, intake questions, file-delivery issues, or either included consolidated revision round.</p>
              <p>Support can help you use the service. Your financial and lending advisors should validate assumptions and loan decisions.</p>
            </article>
          </div>
        </section>

        <section className="finalCta" aria-labelledby="final-cta-title">
          <p className="sectionLabel">Start with the facts you already have</p>
          <h2 id="final-cta-title">Ready to see if the service fits your funding goal?</h2>
          <p>Walk through the guided intake at your pace. You can mark follow-up items as unknown and return with stronger details later.</p>
          <AnalyticsLink
            className="primaryAction lightAction"
            href={accountStartUrl}
            events={accountEvents("final_cta")}
          >
            Check fit and start intake
            <span aria-hidden="true">→</span>
          </AnalyticsLink>
        </section>
      </main>

      <footer className="marketingFooter">
        <div className="brand footerBrand"><span className="brandMark" aria-hidden="true">BP</span><span>Business Plan Writer <small>Delivered by Ben Hankins</small></span></div>
        <p>Funding-focused business plans with structured intake, human review, financial credibility checks, and professional DOCX/PDF delivery.</p>
        <nav aria-label="Trust and support links">
          <a href="#disclaimer">Disclaimer</a>
          <a href="#privacy">Privacy</a>
          <a href="#support">Support</a>
        </nav>
      </footer>
    </div>
  );
}
