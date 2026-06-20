"use client";

import { FormEvent, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

type StepState = { step: number; name: string; status: string };
type FieldIssue = { field?: string } | string;
type ValidationWarnings = {
  missing_required: FieldIssue[];
  thin_fields: FieldIssue[];
  completeness_score?: number;
};
type CriticOutput = {
  scores?: Record<string, number>;
  primary_risks?: string[];
  critical_issues?: Array<{ severity?: string; section?: string; issue?: string }>;
  approval_status?: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const SECTIONS = [
  "business_information",
  "management_details",
  "product_service_summary",
  "sales_strategy",
  "market_analysis",
  "advertising_strategy",
  "competition",
  "strategy_and_implementation",
  "milestones",
  "financial_information",
  "income",
  "expenses",
];
const STEP_NAMES = ["Validation", "Market", "Financials", "Draft", "Review"];
const DEMO_SECTIONS: Record<string, string> = {
  business_information:
    "Northstar Home Care Advisors is a Chicago-based eldercare planning firm founded in 2026. It helps adult children coordinate care options, home safety, benefits navigation, and transition planning for aging parents.",
  management_details:
    "The founder has 12 years in care coordination, discharge planning, and family advocacy, with referral relationships across senior centers, estate attorneys, and home health providers.",
  product_service_summary:
    "Services include $350 care assessments, $1,200 transition plans, and $275 monthly advisory retainers. Delivery is hybrid with in-home visits, virtual family meetings, and partner referrals.",
  sales_strategy:
    "Primary acquisition comes from referral partners, local seminars, SEO pages for eldercare planning terms, and LinkedIn outreach to estate attorneys. Consultations convert into assessments, then retainers.",
  market_analysis:
    "The target customer is a 45-65 year-old adult child managing care decisions for a parent in Cook County. Demand is driven by aging demographics, fragmented care options, and family time constraints.",
  advertising_strategy:
    "Launch budget is $3,500 per month across local search, referral events, printed partner materials, and two monthly educational workshops.",
  competition:
    "Competitors include geriatric care managers, home health agencies, and senior placement services. Northstar differentiates by staying vendor-neutral and combining planning, benefits guidance, and family facilitation.",
  strategy_and_implementation:
    "Months 1-3 focus on partner development and paid pilots. Months 4-6 add workshops and retainer conversion. Months 7-12 hire a part-time care coordinator.",
  milestones:
    "First 90 days: 20 partner meetings, 12 paid assessments, 4 retainers. Month 6: $18,000 monthly revenue. Month 12: $38,000 monthly revenue and one coordinator hired.",
  financial_information:
    "The business seeks $85,000 for launch payroll, insurance, marketing, software, legal setup, and working capital. Break-even target is month 8.",
  income:
    "Year 1 revenue target is $245,000 from assessments, transition plans, and retainers. Year 2 target is $510,000 with one coordinator and expanded partner referrals.",
  expenses:
    "Monthly expenses include $8,000 owner draw, $3,500 marketing, $1,200 software and insurance, $900 professional services, and $2,500 contractor support before hiring.",
};

const emptySections = () => Object.fromEntries(SECTIONS.map((section) => [section, ""]));
const issueLabel = (item: FieldIssue) => (typeof item === "string" ? item : item.field || "Unknown field");
const statusSteps = (status: string) =>
  STEP_NAMES.map((name, idx) => ({ step: idx + 1, name, status }));

export default function HomePage() {
  const [businessName, setBusinessName] = useState("");
  const [sections, setSections] = useState<Record<string, string>>(emptySections);
  const [route, setRoute] = useState("recommended");
  const [steps, setSteps] = useState<StepState[]>([]);
  const [draft, setDraft] = useState("");
  const [warnings, setWarnings] = useState<ValidationWarnings>({
    missing_required: [],
    thin_fields: [],
  });
  const [critic, setCritic] = useState<CriticOutput>({});
  const [exports, setExports] = useState<{ docx: string | null; pdf: string | null }>({
    docx: null,
    pdf: null,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const completed = useMemo(
    () => SECTIONS.filter((section) => sections[section]?.trim()).length,
    [sections]
  );

  const loadDemo = () => {
    setBusinessName("Northstar Home Care Advisors");
    setSections(DEMO_SECTIONS);
    setDraft("");
    setError("");
    setSteps([]);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSteps(statusSteps("queued"));

    const intake = Object.fromEntries(
      SECTIONS.map((section) => [section, { notes: sections[section] || "" }])
    ) as Record<string, Record<string, string>>;
    intake.business_information.business_name = businessName || "Demo Client";
    intake._meta = { workflow_route: route };

    try {
      setSteps(statusSteps("running"));
      const res = await fetch(`${API_BASE}/generate-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intake }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail?.message || "Failed to generate plan.");

      setSteps(data.progress || statusSteps("complete"));
      setDraft(data.draft_markdown || "");
      setWarnings(data.validation_warnings || { missing_required: [], thin_fields: [] });
      setCritic(data.critic || {});
      setExports({
        docx: data.exports?.docx ? `${API_BASE}${data.exports.docx}` : null,
        pdf: data.exports?.pdf ? `${API_BASE}${data.exports.pdf}` : null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setSteps(statusSteps("failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="workspace">
      <section className="hero">
        <p className="eyebrow">Bring your own AI API key for best results</p>
        <h1>Business Plan Writer</h1>
        <p>
          A five-agent workflow that turns structured intake into a lender-ready draft,
          then checks the plan for completeness, financial credibility, and submission risk.
        </p>
      </section>

      <aside className="panel sidebar">
        <h2>Default Route</h2>
        <ol>
          {STEP_NAMES.map((name) => (
            <li key={name}>{name}</li>
          ))}
        </ol>
        <button className="secondary" type="button" onClick={loadDemo}>
          Load demo workflow
        </button>
        <p className="finePrint">
          Non-default paths are user-directed experiments. Generated output requires human
          review, and we are not liable for decisions made from customized routes.
        </p>
      </aside>

      <section className="panel main">
        <div className="sectionHeader">
          <div>
            <h2>Client Intake</h2>
            <p>{completed}/{SECTIONS.length} sections filled</p>
          </div>
          <span className="badge">Recommended: efficient 5-agent pass</span>
        </div>

        <form onSubmit={onSubmit} className="form">
          <label>
            Business Name
            <input
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              placeholder="Northstar Home Care Advisors"
            />
          </label>

          <fieldset>
            <legend>Workflow Route</legend>
            <label className="radio">
              <input
                checked={route === "recommended"}
                name="route"
                onChange={() => setRoute("recommended")}
                type="radio"
              />
              Recommended 5-agent path
            </label>
            <label className="radio">
              <input
                checked={route === "custom"}
                name="route"
                onChange={() => setRoute("custom")}
                type="radio"
              />
              Custom route
            </label>
          </fieldset>

          {SECTIONS.map((section) => (
            <label key={section}>
              {section.replaceAll("_", " ")}
              <textarea
                value={sections[section]}
                onChange={(e) => setSections((prev) => ({ ...prev, [section]: e.target.value }))}
                rows={3}
              />
            </label>
          ))}

          <button type="submit" disabled={loading}>
            {loading ? "Generating..." : "Generate Plan"}
          </button>
        </form>
        {error && <p className="error">{error}</p>}
      </section>

      <aside className="panel flags">
        <h2>Pipeline</h2>
        <ul className="statusList">
          {(steps.length ? steps : statusSteps("waiting")).map((step) => (
            <li key={step.step}>
              <span>{step.name}</span>
              <strong>{step.status}</strong>
            </li>
          ))}
        </ul>

        <h2>Review</h2>
        <p>Completeness: {warnings.completeness_score ?? "n/a"}</p>
        <p>Approval: {critic.approval_status || "n/a"}</p>
        <p>
          Overall score: {critic.scores?.overall ?? "n/a"} · Credibility:{" "}
          {critic.scores?.credibility ?? "n/a"}
        </p>
        <ul>
          {warnings.missing_required.slice(0, 3).map((item, idx) => (
            <li key={`missing-${idx}`}>Missing: {issueLabel(item)}</li>
          ))}
          {warnings.thin_fields.slice(0, 3).map((item, idx) => (
            <li key={`thin-${idx}`}>Thin: {issueLabel(item)}</li>
          ))}
          {(critic.primary_risks || []).slice(0, 3).map((risk, idx) => (
            <li key={`risk-${idx}`}>Risk: {risk}</li>
          ))}
        </ul>

        <div className="exportRow">
          <a className={exports.docx ? "btn" : "btn disabled"} href={exports.docx || "#"}>
            Export DOCX
          </a>
          <a className={exports.pdf ? "btn" : "btn disabled"} href={exports.pdf || "#"}>
            Export PDF
          </a>
        </div>
      </aside>

      <section className="panel previewPanel">
        <h2>Draft Preview</h2>
        <article className="preview">
          <ReactMarkdown>{draft || "_Load the demo workflow or enter client intake to generate a draft._"}</ReactMarkdown>
        </article>
      </section>
    </main>
  );
}
