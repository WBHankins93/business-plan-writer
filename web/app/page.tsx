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
    title: "Tell us what you know",
    body: "A guided intake turns your experience, offer, funding request, and estimates into usable source material.",
  },
  {
    title: "Find the missing pieces",
    body: "The first check flags required answers and thin details before they become vague sections in the plan.",
  },
  {
    title: "Build the business case",
    body: "A market-focused stage organizes your customer, competition, positioning, and path to revenue from your answers.",
  },
  {
    title: "Challenge the numbers",
    body: "A financial stage checks whether revenue, expenses, cash flow, break-even, and funding use tell a consistent story.",
  },
  {
    title: "Draft, then stress-test",
    body: "The plan is written in a funding-focused structure, then a final automated review stage flags weak claims and unresolved risks for Ben to address.",
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
          Start intake
        </AnalyticsLink>
      </header>

      <main id="main-content">
        <section className="marketingHero" id="top" aria-labelledby="hero-title">
          <div className="heroMessage">
            <p className="marketingEyebrow">Private beta · Expansion financing plans</p>
            <h1 id="hero-title">Turn your business details into a plan a lender can review.</h1>
            <p className="heroLead">
              For owners of operating US local service businesses preparing for SBA-backed
              or conventional expansion financing—not idea-stage founders starting from scratch.
            </p>
            <div className="heroActions">
              <AnalyticsLink
                className="primaryAction"
                href={accountStartUrl}
                events={accountEvents("hero")}
              >
                Start fit and intake
                <span aria-hidden="true">→</span>
              </AnalyticsLink>
              <AnalyticsLink
                className="textAction"
                href="/samples/bywater-grounds-sample-plan.pdf"
                events={sampleEvents("hero", "pdf")}
                download
              >
                Download the fictional sample
                <span aria-hidden="true">↓</span>
              </AnalyticsLink>
            </div>
            <ul className="offerFacts" aria-label="Offer summary">
              <li><strong>$750</strong><span>fixed validation price</span></li>
              <li><strong>DOCX + PDF</strong><span>editable and shareable</span></li>
              <li><strong>2 revisions</strong><span>two consolidated rounds</span></li>
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

        <section className="fitSection" aria-labelledby="fit-title">
          <div>
            <p className="sectionLabel">A focused starting point</p>
            <h2 id="fit-title">Built for a specific funding conversation.</h2>
          </div>
          <div className="fitColumns">
            <div>
              <h3>Good fit</h3>
              <p>You operate a US local service business, are preparing to finance an expansion, and can provide operating history or explicit forecast assumptions.</p>
            </div>
            <div>
              <h3>Not the right fit</h3>
              <p>You are pre-revenue, or need audited projections, legal or tax advice, independent research, verified citations, or a guarantee that a lender will approve the plan.</p>
            </div>
          </div>
        </section>

        <section className="deliverablesSection" aria-labelledby="deliverables-title">
          <div className="sectionHeading">
            <p className="sectionLabel">What you receive</p>
            <h2 id="deliverables-title">A complete draft, plus a clearer view of its weak spots.</h2>
            <p>The workflow uses the facts and estimates you provide. It organizes them, checks their internal consistency, and turns them into documents you can edit and review.</p>
          </div>
          <div className="deliverablesGrid">
            <article>
              <span>01</span>
              <h3>Funding-focused plan structure</h3>
              <p>Executive summary, company and market context, offer, operations, management, funding use, risks, milestones, and financial narrative.</p>
            </article>
            <article>
              <span>02</span>
              <h3>Financial credibility notes</h3>
              <p>Automated checks flag gaps or conflicts across revenue, expenses, cash flow, break-even timing, and the amount requested.</p>
            </article>
            <article>
              <span>03</span>
              <h3>Professional delivery files</h3>
              <p>An editable DOCX and a shareable PDF, so you can correct facts, add lender-specific requirements, and control the final version.</p>
            </article>
          </div>
        </section>

        <section className="sampleSection" id="sample" aria-labelledby="sample-title">
          <div className="sampleCopy">
            <p className="sectionLabel">See the deliverable</p>
            <h2 id="sample-title">A fictional plan, shown without borrowed proof.</h2>
            <p>Bywater Grounds Coffee House is a made-up New Orleans business created to demonstrate structure, depth, financial tables, and review notes. It is not a customer and its numbers are not research-backed.</p>
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
            <p className="sectionLabel">The five-agent process</p>
            <h2 id="process-title">Five focused jobs, followed by direct human review.</h2>
            <p>Each automated stage has a narrow responsibility. Ben then reviews and edits the deliverable before delivery; this does not replace your lender, accountant, attorney, or advisor.</p>
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
            <p className="sectionLabel">One validation offer</p>
            <h2 id="pricing-title">Funding-Focused Business Plan Service</h2>
            <p>For one operating local service business and one expansion-financing use case.</p>
            <div className="price"><strong>$750</strong><span>fixed fee</span></div>
          </div>
          <div className="packageDetails">
            <h3>Included</h3>
            <ul>
              <li>Guided intake and readiness check</li>
              <li>Five-stage AI-assisted workflow</li>
              <li>Three-year projection summary based on your inputs</li>
              <li>Human editorial and consistency review by Ben</li>
              <li>DOCX and PDF delivery</li>
              <li>Two consolidated revision rounds</li>
            </ul>
            <div className="expectationNote">
              <strong>Delivery and revision policy</strong>
              <p>No payment is collected on this page. Delivery is seven calendar days after Ben accepts the intake as complete. Each revision round is one consolidated list submitted within seven days of delivery. Revisions refine the agreed plan; a new concept, audience, material data set, or custom analysis is new scope.</p>
              <p>Fit is confirmed before work is accepted. A pre-acceptance scope mismatch or inability to deliver the agreed scope is canceled and refunded. After the first complete draft, a change of mind, business direction, or financing denial is not refundable; the included revisions cover in-scope corrections.</p>
            </div>
            <AnalyticsLink
              className="primaryAction packageAction"
              href={accountStartUrl}
              events={accountEvents("pricing")}
            >
              Start fit and intake
              <span aria-hidden="true">→</span>
            </AnalyticsLink>
          </div>
        </section>

        <section className="trustSection" id="trust" aria-labelledby="trust-title">
          <div className="sectionHeading">
            <p className="sectionLabel">Before you begin</p>
            <h2 id="trust-title">Clear boundaries make the plan more useful.</h2>
          </div>
          <div className="trustGrid">
            <article id="disclaimer">
              <h3>AI assistance and responsibility</h3>
              <p>Your plan is supported by an automated five-stage drafting and quality workflow, then personally reviewed and edited by Ben Hankins before delivery. Review every fact, assumption, and projection before sharing it.</p>
              <p>The output is planning support—not legal, tax, accounting, investment, or lending advice. It does not guarantee financing or lender acceptance.</p>
            </article>
            <article id="privacy">
              <h3>Privacy during beta</h3>
              <p>Submit only information needed to prepare the plan. Do not include Social Security numbers, bank or card numbers, passwords, medical records, or other sensitive personal data.</p>
              <p>Intake content is used to generate and deliver your plan and to support the beta. A formal retention schedule is not yet published; reply to your beta invitation to request deletion.</p>
            </article>
            <article id="support">
              <h3>Support and revisions</h3>
              <p>Reply to your private-beta invitation for access help, intake questions, file-delivery issues, or either included consolidated revision round.</p>
              <p>Beta support can help operate the product, but it cannot validate financial assumptions or advise you on a loan application.</p>
            </article>
          </div>
        </section>

        <section className="finalCta" aria-labelledby="final-cta-title">
          <p className="sectionLabel">Start with the facts you already have</p>
          <h2 id="final-cta-title">Build a plan you can question before a lender does.</h2>
          <p>The intake is organized into business, market, growth, and financial sections. You can mark some follow-up answers as unknown.</p>
          <AnalyticsLink
            className="primaryAction lightAction"
            href={accountStartUrl}
            events={accountEvents("final_cta")}
          >
            Start fit and intake
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
