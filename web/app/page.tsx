"use client";

import { FormEvent, useState } from "react";
import ReactMarkdown from "react-markdown";

type StepState = { step: number; name: string; status: string };
type ValidationWarnings = {
  missing_required: Array<{ field?: string } | string>;
  thin_fields: Array<{ field?: string } | string>;
  completeness_score?: number;
};
type CriticOutput = {
  scores?: Record<string, number>;
  primary_risks?: string[];
  critical_issues?: Array<{
    severity?: string;
    section?: string;
    issue?: string;
  }>;
  approval_status?: string;
};

const SECTION_KEYS = [
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

export default function HomePage() {
  const [businessName, setBusinessName] = useState("");
  const [sections, setSections] = useState<Record<string, string>>(
    Object.fromEntries(SECTION_KEYS.map((s) => [s, ""]))
  );
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

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSteps(
      [1, 2, 3, 4, 5].map((step) => ({
        step,
        name: ["Validation", "Market", "Financials", "Draft", "Review"][step - 1],
        status: "running",
      }))
    );

    const intake: Record<string, Record<string, string>> = {};
    for (const section of SECTION_KEYS) {
      intake[section] = { notes: sections[section] || "" };
    }
    intake.business_information.business_name = businessName || "Web Client";

    try {
      const res = await fetch("http://localhost:8000/generate-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intake }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail?.message || "Failed to generate plan.");
      }
      setSteps(data.progress || []);
      setDraft(data.draft_markdown || "");
      setWarnings(data.validation_warnings || { missing_required: [], thin_fields: [] });
      setCritic(data.critic || {});
      setExports(data.exports || { docx: null, pdf: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setError(msg);
      setSteps((prev) => prev.map((s) => ({ ...s, status: "failed" })));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="workspace">
      <aside className="panel sidebar">
        <h2>Workflow</h2>
        <ul>
          {["Intake", "Validation", "Market", "Financials", "Draft", "Review"].map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
        <h3>Pipeline Status</h3>
        <ul>
          {steps.map((s) => (
            <li key={s.step}>
              {s.name}: <strong>{s.status}</strong>
            </li>
          ))}
        </ul>
      </aside>

      <section className="panel main">
        <h1>Business Plan Writer</h1>
        <p>Complete intake, generate draft, and review before export.</p>

        <form onSubmit={onSubmit} className="form">
          <label>
            Business Name
            <input
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              placeholder="Acme Ventures"
            />
          </label>
          {SECTION_KEYS.map((section) => (
            <label key={section}>
              {section}
              <textarea
                value={sections[section]}
                onChange={(e) =>
                  setSections((prev) => ({ ...prev, [section]: e.target.value }))
                }
                rows={3}
              />
            </label>
          ))}
          <button type="submit" disabled={loading}>
            {loading ? "Generating..." : "Generate Plan"}
          </button>
        </form>
        {error && <p className="error">{error}</p>}

        <div className="exportRow">
          <a className={exports.docx ? "btn" : "btn disabled"} href={exports.docx || "#"}>
            Export DOCX
          </a>
          <a className={exports.pdf ? "btn" : "btn disabled"} href={exports.pdf || "#"}>
            Export PDF
          </a>
        </div>

        <h2>Draft Preview</h2>
        <article className="preview">
          <ReactMarkdown>{draft || "_No draft generated yet._"}</ReactMarkdown>
        </article>
      </section>

      <aside className="panel flags">
        <h2>Flags & Issues</h2>
        <p>Completeness score: {warnings.completeness_score ?? "n/a"}</p>
        <h3>Validation Warnings</h3>
        <ul>
          {warnings.missing_required.slice(0, 5).map((item, idx) => (
            <li key={`missing-${idx}`}>
              Missing: {typeof item === "string" ? item : item.field || "Unknown field"}
            </li>
          ))}
          {warnings.thin_fields.slice(0, 5).map((item, idx) => (
            <li key={`thin-${idx}`}>
              Thin: {typeof item === "string" ? item : item.field || "Unknown field"}
            </li>
          ))}
        </ul>

        <h3>Critic Output</h3>
        <p>Approval: {critic.approval_status || "n/a"}</p>
        <p>
          Scores: clarity {critic.scores?.clarity ?? "n/a"}, credibility{" "}
          {critic.scores?.credibility ?? "n/a"}, overall {critic.scores?.overall ?? "n/a"}
        </p>
        <ul>
          {(critic.primary_risks || []).slice(0, 3).map((risk, idx) => (
            <li key={`risk-${idx}`}>Risk: {risk}</li>
          ))}
          {(critic.critical_issues || []).slice(0, 3).map((issue, idx) => (
            <li key={`issue-${idx}`}>
              [{issue.severity || "n/a"}] {issue.section || "general"} — {issue.issue || ""}
            </li>
          ))}
        </ul>
      </aside>
    </main>
  );
}
